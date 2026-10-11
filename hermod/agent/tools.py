"""Tools the LLM can call. Each maps to a DB write, so the log is structured, not prose."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlmodel import Session, select

from hermod.agent.replies import (
    classify_dose_reply,
    dose_reports,
    is_bare_yes,
    mentions_earlier_day,
    names_medications,
    slot_matches,
    states_a_time,
)
from hermod.db.models import DoseEvent, DoseStatus, Flag, FlagSeverity, Medication, Prescription
from hermod.timeutil import fmt_local, to_local, to_utc, utcnow

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "log_dose",
            "description": (
                "Record a dose the patient just told you about. 'taken' only when they say "
                "they took it (\"yes\", \"took it\", \"done\"); 'missed' only when they say "
                "they missed, forgot or skipped it. \"Not yet\", \"later\" or \"ok\" are not "
                "reports: don't call this. Pass dose_id from the dose list when you know which "
                "dose they mean (a plain \"yes\" is the dose marked DUE NOW). Use 'extra' when "
                "they took a dose that wasn't scheduled or took more than prescribed. Whether "
                "a taken dose counts as late is worked out from the times."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dose_id": {"type": "integer", "description": "Id from the dose list."},
                    "medication": {"type": "string"},
                    "status": {"type": "string", "enum": ["taken", "missed", "extra"]},
                    "when": {
                        "type": "string",
                        "description": "Local time the dose was taken, ISO 8601 if known.",
                    },
                    "note": {"type": "string"},
                },
                "required": ["medication", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_issue",
            "description": "Raise something the doctor should review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["missed_doses", "extra_dose", "side_effect", "stopped_early",
                                 "question_for_doctor"],
                    },
                    "severity": {"type": "string", "enum": ["info", "warning", "urgent"]},
                    "summary": {
                        "type": "string",
                        "description": "What the patient said, without added causes or "
                                       "interpretation.",
                    },
                    "dose_id": {"type": "integer"},
                },
                "required": ["kind", "severity", "summary"],
            },
        },
    },
]

# How far ahead of its scheduled time a dose can be reported as taken.
EARLY_WINDOW = timedelta(hours=2)


def active_medications(session: Session, patient_id: int) -> list[Medication]:
    now = utcnow()
    rows = session.exec(
        select(Medication)
        .join(Prescription)
        .where(Prescription.patient_id == patient_id, Prescription.start_date <= now)
    ).all()
    return [
        m
        for m in rows
        if (p := session.get(Prescription, m.prescription_id)).end_date is None
        or p.end_date >= now - timedelta(days=1)
    ]


def _match_medication(meds: list[Medication], name: str) -> Medication | None:
    """The medication `name` (or a message) refers to: whole-word matches only, longest
    name first, so "vitamin b12" never matches "Vitamin D" and "Iron" never "environment"."""
    if len(meds) == 1:
        return meds[0]
    said = set(_name_words(name))
    if not said:
        return None
    for m in sorted(meds, key=lambda m: len(m.name), reverse=True):
        words = _name_words(m.name)
        # Every word of the name is mentioned ("amoxicillin" for "Amoxicillin 500 mg"), or
        # everything said is part of this name and none of it is a lone letter ("d").
        if words and (set(words) <= said or (said <= set(words) and min(map(len, said)) > 2)):
            return m
    return None


def _name_words(text: str | None) -> list[str]:
    """Words of a medication name or message, without strengths and units ("500", "mg")."""
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if not re.fullmatch(r"\d+(\.\d+)?|mg|mcg|ug|g|ml|iu|units?|tabs?|caps?|x", w)]


def _parse_when(when: str | None) -> datetime | None:
    if not when:
        return None
    try:
        return to_utc(datetime.fromisoformat(when))
    except ValueError:
        return None


# A plain "yes" is only about doses from the last few hours (older ones need an explicit
# dose_id), and a reply can't log a dose from more than a day ago.
CURRENT_WINDOW = timedelta(hours=6)
MAX_LOG_AGE = timedelta(hours=24)


def _open_doses(session: Session, patient_id: int, medication_id: int | None) -> list[DoseEvent]:
    now = utcnow()
    query = select(DoseEvent).where(
        DoseEvent.patient_id == patient_id,
        DoseEvent.status.in_([DoseStatus.PENDING, DoseStatus.UNKNOWN]),
        DoseEvent.scheduled_for <= now + EARLY_WINDOW,
        DoseEvent.scheduled_for >= now - CURRENT_WINDOW,
    )
    if medication_id is not None:
        query = query.where(DoseEvent.medication_id == medication_id)
    return list(session.exec(query).all())


def current_doses(session: Session, patient_id: int,
                  medication_id: int | None = None) -> list[DoseEvent]:
    """The open doses a plain "yes, took it" is about: everything in Hermod's latest
    check-in (one check-in can cover several medications), else the latest dose already
    due, else one coming up within EARLY_WINDOW. Only the last CURRENT_WINDOW hours count, so
    last night's unanswered dose never takes this morning's "yes"."""
    now = utcnow()
    open_doses = _open_doses(session, patient_id, medication_id)
    asked = [e for e in open_doses if e.checkin_sent_at is not None]
    if asked:
        latest = max(e.checkin_sent_at for e in asked)
        return sorted((e for e in asked if latest - e.checkin_sent_at <= timedelta(minutes=1)),
                      key=lambda e: e.id)
    pending = [e for e in open_doses if e.status == DoseStatus.PENDING]
    due = [e for e in pending if e.scheduled_for <= now]
    if due:
        return [max(due, key=lambda e: e.scheduled_for)]
    soon = min(pending, key=lambda e: e.scheduled_for, default=None)
    return [soon] if soon else []


def current_dose(session: Session, patient_id: int,
                 medication_id: int | None = None) -> DoseEvent | None:
    doses = current_doses(session, patient_id, medication_id)
    return doses[0] if doses else None


@dataclass
class Turn:
    """The patient message the agent is answering, for checks that can't trust the LLM."""
    text: str
    # Hermod's last message asked about a dose (a check-in or "have you taken it?"), so a
    # bare "yes" answers that. After "any side effects?", "yes" is not a dose report.
    asked_about_dose: bool = True
    # Names of all the patient's active medications: if the message names some, only those
    # can be logged ("took the amoxicillin, not the paracetamol").
    medication_names: tuple[str, ...] = ()
    # (medication id, "report"|"extra", report index) already logged for this message: each
    # report in the message ("taken the 2 pm one, missed 8 am" is two) logs one dose.
    logged: set[tuple[int, str, int]] = field(default_factory=set)


# Confirmed more than this long after its scheduled time, a dose counts as "late".
LATE_AFTER = timedelta(hours=2)

# What the patient's words have to say before each status can be logged.
_NEEDS = {DoseStatus.TAKEN: "taken", DoseStatus.LATE: "taken", DoseStatus.EXTRA: "taken",
          DoseStatus.MISSED: "missed"}
_REFUSALS = {
    "not_yet": "The patient hasn't taken it yet, so nothing was logged. Don't log it; say "
               "that's fine and ask them to reply once they've taken it.",
    "unclear": "The patient's message doesn't clearly say they {want}, so nothing was "
               "logged. Ask them to confirm (e.g. \"Have you taken your {med} yet?\") and "
               "only log once they say so.",
    "taken": "The patient says they took it, so it can't be logged as missed.",
    "missed": "The patient says they missed it, so it can't be logged as taken.",
}


def _refuse(error: str) -> dict:
    return {"ok": False, "logged": False, "error": error}


def _kind(status: DoseStatus) -> str:
    return "extra" if status == DoseStatus.EXTRA else "report"


def _check_words(turn: Turn, status: DoseStatus, med: Medication) -> str | None:
    """Why the patient's message doesn't support logging `status`, or None if it does."""
    names = (med.name,)
    if not [r for r in dose_reports(turn.text, names) if r.intent == _NEEDS[status]]:
        intent = classify_dose_reply(turn.text, names)
        if intent == _NEEDS[status] or intent in ("taken", "missed"):
            intent = "unclear"
        want = "took it" if _NEEDS[status] == "taken" else "missed it"
        return _REFUSALS[intent].format(want=want, med=med.name)
    if is_bare_yes(turn.text, names) and not turn.asked_about_dose:
        return (f"\"{turn.text[:60]}\" answers your last question, not whether they took "
                f"{med.name}, so nothing was logged. Ask them if they've taken it.")
    named = names_medications(turn.text, turn.medication_names)
    if named and med.name not in named:
        return (f"The patient named {', '.join(sorted(named))}, not {med.name}, so nothing was "
                f"logged for {med.name}. Ask about it separately if needed.")
    return None


def _match_report(turn: Turn, status: DoseStatus, med: Medication,
                  event: DoseEvent) -> tuple[int | None, str | None]:
    """Which report in the message this write is (its index), or why it fits none. With
    several reports ("taken the 2 pm one, missed 8 am"), each can only log the dose at the
    time it names, and each only once."""
    reports = dose_reports(turn.text, (med.name,))
    candidates = [i for i, r in enumerate(reports) if r.intent == _NEEDS[status]
                  and (med.id, _kind(status), i) not in turn.logged]
    if not candidates:
        return None, (f"This message already logged what it says about {med.name}. One "
                      "message reports each dose once; ask about any others.")
    if status == DoseStatus.EXTRA:
        return candidates[0], None  # a new entry; its time is when they took it
    local = to_local(event.scheduled_for)
    fits = [i for i in candidates if slot_matches(reports[i].slot, local)]
    if not fits:
        said = reports[candidates[0]].slot
        return None, (f"The patient's \"{_NEEDS[status]}\" is about the "
                      f"{said[1] if said[0] == 'part' else f'{said[1]:02d}:00'} dose, not the "
                      f"{local:%H:%M} one, so nothing was logged. Pass the dose_id of the dose "
                      "they named from the dose list.")
    return fits[0], None


def _log_dose(session: Session, patient_id: int, args: dict, turn: Turn | None = None) -> dict:
    status = DoseStatus(args["status"])
    now = utcnow()
    note = args.get("note", "")

    event = None
    if args.get("dose_id"):
        event = session.get(DoseEvent, int(args["dose_id"]))
        if event and event.patient_id != patient_id:
            event = None

    med = session.get(Medication, event.medication_id) if event else None
    if med is None:
        med = _match_medication(active_medications(session, patient_id), args.get("medication"))
    if med is None:
        return {"ok": False, "error": f"No active medication matches {args.get('medication')!r}"}

    # Only the patient's own words can mark a dose taken or missed (see hermod.agent.replies).
    if turn is not None and status in _NEEDS and (why := _check_words(turn, status, med)):
        return _refuse(why)

    # When they took it: the model's `when` only if the patient actually said a time.
    stated = turn is None or states_a_time(turn.text)
    at = min((_parse_when(args.get("when")) if stated else None) or now, now)

    if status == DoseStatus.EXTRA:
        # An extra dose is a new entry; it never rewrites a scheduled dose.
        event = DoseEvent(medication_id=med.id, patient_id=patient_id, scheduled_for=at)
        session.add(event)
    elif event is not None and event.status not in (DoseStatus.PENDING, DoseStatus.UNKNOWN):
        # Never overwrite what the patient already reported (the doctor reads this as fact).
        return {"ok": False, "error": f"Dose {event.id} is already logged as "
                f"{event.status} ({fmt_local(event.scheduled_for)}); don't log it again"}
    elif event is not None and event.scheduled_for > now + EARLY_WINDOW:
        return {"ok": False, "error": f"Dose {event.id} ({fmt_local(event.scheduled_for)}) "
                "isn't due yet, so it can't be logged now"}
    elif event is not None and event.scheduled_for < now - MAX_LOG_AGE:
        return {"ok": False, "error": f"Dose {event.id} ({fmt_local(event.scheduled_for)}) is "
                "more than a day old and can't be changed from chat. If it matters, flag it "
                "for the doctor (flag_issue) with what the patient said."}
    elif event is None:
        event = current_dose(session, patient_id, med.id)
        if event is None:
            return {"ok": False, "error": f"No open dose of {med.name} from the last few hours "
                    "to log against. If they mean an older dose, pass its dose_id."}
    if status != DoseStatus.EXTRA:
        # "I took it yesterday" is never about a dose from today.
        if turn is not None and mentions_earlier_day(turn.text) and \
                to_local(event.scheduled_for).date() >= to_local(now).date():
            return _refuse("The patient is talking about an earlier day, so nothing was logged "
                           "for today's dose. Pass the dose_id of that earlier dose from the "
                           "dose list (if it's there), or ask which dose they mean.")
        at = max(at, event.scheduled_for - EARLY_WINDOW)  # a stated time can't predate the dose
    if turn is not None and status in _NEEDS:
        index, why = _match_report(turn, status, med, event)
        if why:
            return _refuse(why)
        turn.logged.add((med.id, _kind(status), index))

    if status in (DoseStatus.TAKEN, DoseStatus.LATE):
        # Taken vs late is a rule on the clock, not the model's call.
        status = DoseStatus.LATE if at - event.scheduled_for > LATE_AFTER else DoseStatus.TAKEN
    event.status = status
    event.reported_at = utcnow()
    if note:
        event.patient_note = f"{event.patient_note}\n{note}".strip()
    session.add(event)
    session.commit()
    session.refresh(event)
    return {
        "ok": True,
        "dose_id": event.id,
        "medication": med.name,
        "scheduled_for": fmt_local(event.scheduled_for),
        "status": str(event.status),
    }


def record_reported_overdose(session: Session, patient_id: int, text: str) -> DoseEvent | None:
    """Log an "extra" dose for an overdose report. Runs on the emergency path, without the
    LLM, so the dose list (and the dashboard) shows it from the next turn on. Returns None
    if it can't tell which medication was meant."""
    med = _match_medication(active_medications(session, patient_id), text)
    if med is None:
        return None
    now = utcnow()
    event = DoseEvent(medication_id=med.id, patient_id=patient_id, scheduled_for=now,
                      status=DoseStatus.EXTRA, reported_at=now,
                      patient_note=f'Reported overdose: "{text[:300]}"')
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


# The LLM may only raise an urgent flag soon after an emergency (e.g. "not good" after an
# overdose report). Otherwise urgent is left to the deterministic checks.
URGENT_CONTEXT = timedelta(hours=24)


def _recent_emergency(session: Session, patient_id: int) -> bool:
    return session.exec(select(Flag).where(
        Flag.patient_id == patient_id, Flag.kind == "emergency",
        Flag.created_at >= utcnow() - URGENT_CONTEXT)).first() is not None


def _flag_issue(session: Session, patient_id: int, args: dict) -> dict:
    dose_id = args.get("dose_id")
    if dose_id and (ev := session.get(DoseEvent, int(dose_id))) and ev.patient_id != patient_id:
        dose_id = None
    severity = FlagSeverity(args["severity"])
    if severity == FlagSeverity.URGENT and not _recent_emergency(session, patient_id):
        severity = FlagSeverity.WARNING
    flag = Flag(
        patient_id=patient_id,
        dose_event_id=int(dose_id) if dose_id else None,
        kind=args["kind"],
        severity=severity,
        summary=args["summary"],
    )
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return {"ok": True, "flag_id": flag.id, "severity": str(severity)}


def execute_tool(name: str, args: dict, patient_id: int, session: Session,
                 turn: Turn | None = None) -> dict:
    """`turn` is the patient message being answered. The agent always passes it, so log_dose
    can check the patient really said they took (or missed) the dose."""
    try:
        if name == "log_dose":
            return _log_dose(session, patient_id, args, turn)
        if name == "flag_issue":
            return _flag_issue(session, patient_id, args)
    except (KeyError, ValueError) as e:
        session.rollback()
        return {"ok": False, "error": f"Bad arguments: {e}"}
    return {"ok": False, "error": f"Unknown tool {name}"}
