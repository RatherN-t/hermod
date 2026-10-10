"""Agent loop: build context -> traced LLM call -> run tools -> guardrail -> reply."""
import json
import logging
from datetime import timedelta

from sqlmodel import Session, col, select

from hermod.adherence.rules import evaluate_patient
from hermod.agent.prompts import (
    FIRST_CONTACT_NOTE,
    LLM_ERROR_REPLY,
    SYSTEM_PROMPT,
    UNKNOWN_CHAT_REPLY,
)
from hermod.agent.tools import (
    EARLY_WINDOW,
    TOOL_SPECS,
    active_medications,
    execute_tool,
    record_reported_overdose,
)
from hermod.channels import get_channel, patient_address
from hermod.channels.base import Channel, IncomingMessage
from hermod.config import get_settings
from hermod.db.models import (
    Direction,
    DoseEvent,
    DoseStatus,
    Flag,
    FlagSeverity,
    Medication,
    Message,
    Patient,
    Prescription,
)
from hermod.db.session import new_session
from hermod.harness import guardrails
from hermod.harness.alerts import notify_doctor
from hermod.harness.tracer import traced_completion
from hermod.timeutil import fmt_local, to_local, utcnow

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4
# Emergency messages skip the LLM, so without this the next turn would see them unhandled.
ESCALATION_NOTE = ("[Automatic safety reply. The doctor already has an URGENT flag for the "
                   "previous message, and any overdose it reports is already in the dose list "
                   "as 'extra'; don't log or flag it again.] ")
HISTORY_LIMIT = 20


async def handle_inbound(msg: IncomingMessage, channel: Channel | None = None) -> None:
    """`channel` overrides where the reply goes (tests, CLI)."""
    channel = channel or get_channel()
    with new_session() as s:
        if s.exec(select(Message).where(Message.external_id == msg.message_id)).first():
            return  # duplicate delivery
        patient = _find_patient(s, msg)
        if patient is None:
            await channel.send_text(msg.sender_id, UNKNOWN_CHAT_REPLY)
            return
        if msg.text.startswith("/start") or msg.text.strip() == patient.link_code:
            msg.text = "Hi"  # linking is the patient's first hello

        first_contact = patient.last_inbound_at is None
        text = msg.text or ("[sent a photo]" if msg.media_url else "[unsupported message]")
        inbound = Message(patient_id=patient.id, direction=Direction.INBOUND, text=text,
                          external_id=msg.message_id)
        s.add(inbound)
        patient.last_inbound_at = utcnow()
        s.add(patient)
        s.commit()
        s.refresh(inbound)

        new_flags: list[Flag] = []
        if guardrails.detect_emergency(text):
            reply = guardrails.ESCALATION_MESSAGE
            dose = (record_reported_overdose(s, patient.id, text)
                    if guardrails.detect_overdose(text) else None)
            flag = Flag(patient_id=patient.id, kind="emergency", severity=FlagSeverity.URGENT,
                        summary=f'Patient wrote: "{text[:300]}"',
                        dose_event_id=dose.id if dose else None)
            s.add(flag)
            s.commit()
            new_flags.append(flag)
        else:
            reply, tool_flags = await _run_agent(s, patient, first_contact, inbound.id)
            new_flags += tool_flags

        await _send(s, channel, patient, guardrails.check_outbound(reply), inbound.id)
        new_flags += evaluate_patient(patient.id, s)
        for f in new_flags:
            await notify_doctor(f)


def _find_patient(s: Session, msg: IncomingMessage) -> Patient | None:
    if get_settings().channel != "telegram":  # console/CLI: the sender is the patient's phone
        return s.exec(select(Patient).where(Patient.phone == msg.sender_id)).first()
    patient = s.exec(select(Patient).where(Patient.telegram_chat_id == msg.sender_id)).first()
    if patient:
        return patient
    # "/start <code>" arrives when the patient taps their t.me/<bot>?start=<code> link. If the
    # chat was already started, Telegram drops the code, so a bare code message works too.
    parts = msg.text.split()
    code = parts[1] if parts[:1] == ["/start"] and len(parts) == 2 else (
        parts[0] if len(parts) == 1 and not parts[0].startswith("/") else None)
    if code:
        linked = s.exec(select(Patient).where(Patient.link_code == code)).first()
        if linked:
            linked.telegram_chat_id = msg.sender_id
            s.add(linked)
            s.commit()
            log.info("Linked Telegram chat to patient %s", linked.id)
            return linked
    log.info("Message from unlinked Telegram chat (%s)",
             "bare /start, no code" if parts == ["/start"] else "no valid code")
    return None


async def _run_agent(
    s: Session, patient: Patient, first_contact: bool, message_id: int | None = None
) -> tuple[str, list[Flag]]:
    messages = [{"role": "system", "content": build_system_prompt(s, patient, first_contact)}]
    messages += _history(s, patient.id)
    flags: list[Flag] = []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            result = await traced_completion(
                patient_id=patient.id, trigger="inbound_message", messages=messages,
                tools=TOOL_SPECS, message_id=message_id,
            )
        except Exception:
            log.exception("LLM call failed for patient %s", patient.id)
            return LLM_ERROR_REPLY, flags
        if not result.tool_calls:
            return result.text, flags
        messages.append(result.assistant_message())
        for call in result.tool_calls:
            out = execute_tool(call["name"], call["arguments"], patient.id, s)
            if out.get("flag_id"):
                flags.append(s.get(Flag, out["flag_id"]))
            messages.append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                             "content": json.dumps(out)})
    # Ran out of rounds mid-tool-use: the writes happened, so acknowledge plainly.
    return "Thanks, I've noted that.", flags


def build_system_prompt(s: Session, patient: Patient, first_contact: bool = False) -> str:
    meds = active_medications(s, patient.id)
    regimen = []
    for m in meds:
        rx = s.get(Prescription, m.prescription_id)
        course = f"from {to_local(rx.start_date):%d %b}"
        if rx.end_date:
            course += f" to {to_local(rx.end_date):%d %b}"
        line = f"- {m.name}: {m.dose} at {m.times_of_day.replace(',', ', ')} ({course})"
        if m.instructions:
            line += f". {m.instructions}"
        if m.paused:
            line += ". (Paused by the doctor: no check-ins for now.)"
        regimen.append(line)

    now = utcnow()
    events = s.exec(
        select(DoseEvent)
        .where(DoseEvent.patient_id == patient.id,
               DoseEvent.scheduled_for >= now - timedelta(hours=36),
               DoseEvent.scheduled_for <= now + timedelta(hours=12))
        .order_by(col(DoseEvent.scheduled_for).desc())
    ).all()
    med_names = {m.id: m.name for m in s.exec(select(Medication)).all()}
    due_now = next((e for e in events if e.scheduled_for <= now + EARLY_WINDOW), None)

    def label(e: DoseEvent) -> str:
        if e.status == DoseStatus.EXTRA and e.patient_note:
            return f"extra ({e.patient_note[:150]})"
        if e.status != DoseStatus.PENDING:
            return str(e.status)
        if e is due_now:
            return "pending, DUE NOW"
        return "upcoming" if e.scheduled_for > now else "pending"

    doses = [
        f"- {e.id}: {med_names.get(e.medication_id, '?')}, {fmt_local(e.scheduled_for)}, {label(e)}"
        for e in events
    ]
    return SYSTEM_PROMPT.format(
        doctor_name=patient.doctor_name or "your doctor",
        patient_name=patient.name,
        now_local=fmt_local(now),
        now_iso=to_local(now).isoformat(timespec="minutes"),
        timezone=get_settings().timezone,
        regimen="\n".join(regimen) or "(no active prescription)",
        doses="\n".join(doses) or "(none in the last day)",
        first_contact=FIRST_CONTACT_NOTE if first_contact else "",
    )


def _history(s: Session, patient_id: int) -> list[dict]:
    rows = s.exec(
        select(Message).where(Message.patient_id == patient_id)
        .order_by(col(Message.created_at).desc(), col(Message.id).desc()).limit(HISTORY_LIMIT)
    ).all()
    history = [
        {"role": "user" if m.direction == Direction.INBOUND else "assistant",
         "content": ESCALATION_NOTE + m.text if m.text == guardrails.ESCALATION_MESSAGE
         else m.text}
        for m in reversed(rows)
    ]
    if history and history[0]["role"] == "assistant":
        # Gemini wants the conversation to open with a user turn.
        history.insert(0, {"role": "user", "content": "(earlier messages omitted)"})
    return history


async def _send(
    s: Session, channel, patient: Patient, text: str, in_reply_to: int | None = None
) -> None:
    msg_id = await channel.send_text(patient_address(patient), text)
    s.add(Message(patient_id=patient.id, direction=Direction.OUTBOUND, text=text,
                  external_id=msg_id, in_reply_to_id=in_reply_to))
    s.commit()


def checkin_text(patient: Patient, items: list[tuple[DoseEvent, Medication]]) -> str:
    first_name = patient.name.split()[0]
    when = to_local(items[0][0].scheduled_for).strftime("%-I:%M%p").lower()
    custom = [m for _, m in items if m.checkin_message]
    if len(items) == 1 and custom:
        m = custom[0]
        # Plain replacement, not str.format: the template comes from the API, and format()
        # would allow attribute access like {name.__class__}. Unknown braces stay as written.
        text = m.checkin_message
        for key, value in {"name": first_name, "medication": m.name, "dose": m.dose,
                           "time": when}.items():
            text = text.replace("{" + key + "}", value)
        return text
    meds = "; ".join(
        f"{m.name} ({m.dose}{', ' + m.instructions if m.instructions else ''})" for _, m in items
    )
    return f"Hi {first_name}, it's your {when} dose: {meds}. Have you taken it?"


async def run_checkin(patient_id: int, dose_event_ids: list[int]) -> None:
    """Scheduler entrypoint: proactively ask about doses that are due (one message per
    patient per time slot)."""
    channel = get_channel()
    with new_session() as s:
        patient = s.get(Patient, patient_id)
        items = [(e, m) for e in (s.get(DoseEvent, i) for i in dose_event_ids) if e
                 if (m := s.get(Medication, e.medication_id)) and not m.paused]
        if not patient or not items:
            return
        text = checkin_text(patient, items)
        to = patient_address(patient)
        if not to:
            return  # Telegram patient who hasn't linked their chat yet
        try:
            msg_id = await channel.send_text(to, text)
        except Exception:
            log.exception("check-in send failed for patient %s", patient_id)
            return
        now = utcnow()
        for e, _ in items:
            e.checkin_sent_at = now
            s.add(e)
        s.add(Message(patient_id=patient.id, direction=Direction.OUTBOUND, text=text,
                      external_id=msg_id))
        s.commit()
