"""Build API responses from database rows. Read-only; routes do the writes."""
import json
import logging
from collections import Counter, defaultdict
from datetime import timedelta

from sqlmodel import Session, col, func, select

from hermod.adherence.rules import adherence_summary
from hermod.api import schemas as S
from hermod.config import get_settings
from hermod.db.models import (
    AgentTrace,
    DoseEvent,
    DoseStatus,
    Flag,
    Medication,
    Message,
    Patient,
    Prescription,
)
from hermod.scheduler.jobs import planned_dose_count
from hermod.timeutil import to_local, utcnow

log = logging.getLogger(__name__)

_bot_username: str | None = None


async def bot_username() -> str | None:
    """The bot's @username, fetched once from Telegram. None without a token or on failure."""
    global _bot_username
    if _bot_username or not get_settings().telegram_bot_token:
        return _bot_username
    from hermod.channels.telegram import TelegramChannel

    try:
        _bot_username = await TelegramChannel(get_settings()).bot_username()
    except Exception as e:  # noqa: BLE001  (link is optional; don't fail the request)
        log.warning("Could not fetch bot username (%s)", type(e).__name__)
    return _bot_username


async def telegram_link(p: Patient) -> S.TelegramLink:
    bot = await bot_username()
    return S.TelegramLink(
        linked=p.telegram_chat_id is not None,
        link_code=p.link_code,
        telegram_link=f"https://t.me/{bot}?start={p.link_code}" if bot else None,
    )


def summary(s: Session, patient_id: int) -> S.AdherenceSummary:
    return S.AdherenceSummary(**adherence_summary(patient_id, s))


def _med_summary(events: list[DoseEvent]) -> S.AdherenceSummary:
    now = utcnow()
    c = Counter(str(e.status) for e in events if e.scheduled_for <= now)
    due = sum(c[k] for k in ("taken", "late", "missed", "unknown"))
    return S.AdherenceSummary(
        taken=c["taken"], late=c["late"], missed=c["missed"], unknown=c["unknown"],
        extra=c["extra"], pending=c["pending"],
        adherence_pct=round(100 * (c["taken"] + c["late"]) / due) if due else None)


def flag_counts(s: Session, patient_id: int | None = None) -> S.FlagCounts:
    q = select(Flag.severity, func.count()).where(Flag.resolved == False)
    if patient_id is not None:
        q = q.where(Flag.patient_id == patient_id)
    c = {str(sev): n for sev, n in s.exec(q.group_by(Flag.severity)).all()}
    return S.FlagCounts(urgent=c.get("urgent", 0), warning=c.get("warning", 0),
                        info=c.get("info", 0), total=sum(c.values()))


def next_dose(s: Session, patient_id: int) -> S.NextDose | None:
    row = s.exec(
        select(DoseEvent, Medication).join(Medication)
        .where(DoseEvent.patient_id == patient_id, DoseEvent.status == DoseStatus.PENDING,
               DoseEvent.scheduled_for > utcnow())
        .order_by(col(DoseEvent.scheduled_for)).limit(1)
    ).first()
    if not row:
        return None
    e, m = row
    return S.NextDose(dose_id=e.id, reminder_id=m.id, medication=m.name,
                      scheduled_for=e.scheduled_for)


def patient_meds(s: Session, patient_id: int) -> list[tuple[Medication, Prescription]]:
    return list(s.exec(
        select(Medication, Prescription).join(Prescription)
        .where(Prescription.patient_id == patient_id)
        .order_by(col(Prescription.start_date).desc(), col(Medication.id).desc())
    ).all())


def reminder_status(m: Medication, rx: Prescription) -> str:
    now = utcnow()
    if rx.end_date and rx.end_date < now:
        return "ended"
    if m.paused:
        return "paused"
    if rx.start_date > now:
        return "scheduled"
    return "active"


def reminder(s: Session, m: Medication, rx: Prescription | None = None) -> S.Reminder:
    rx = rx or s.get(Prescription, m.prescription_id)
    events = s.exec(select(DoseEvent).where(DoseEvent.medication_id == m.id)).all()
    now = utcnow()
    due = [e for e in events if e.status != DoseStatus.EXTRA and e.scheduled_for <= now]
    upcoming = [e.scheduled_for for e in events
                if e.status == DoseStatus.PENDING and e.scheduled_for > now]
    return S.Reminder(
        id=m.id, prescription_id=rx.id, patient_id=rx.patient_id, name=m.name, dose=m.dose,
        instructions=m.instructions,
        times_of_day=[t.strip() for t in m.times_of_day.split(",") if t.strip()],
        duration_kind=rx.duration_kind, duration_days=rx.duration_days,
        start_date=rx.start_date, end_date=rx.end_date, status=reminder_status(m, rx),
        custom_message=m.checkin_message, alert_on_missed=m.alert_on_missed,
        max_daily_doses=m.max_daily_doses,
        doses_sent=len(due),
        doses_confirmed=sum(e.status in (DoseStatus.TAKEN, DoseStatus.LATE) for e in due),
        total_doses=planned_dose_count(rx, m),
        next_dose_at=min(upcoming) if upcoming else None,
    )


def patient_item(s: Session, p: Patient) -> S.PatientListItem:
    last_msg = s.exec(select(func.max(Message.created_at))
                      .where(Message.patient_id == p.id)).one()
    active = sum(reminder_status(m, rx) in ("active", "scheduled")
                 for m, rx in patient_meds(s, p.id))
    return S.PatientListItem(
        id=p.id, name=p.name, phone=p.phone, doctor_name=p.doctor_name, language=p.language,
        is_synthetic=p.is_synthetic, telegram_linked=p.telegram_chat_id is not None,
        next_appointment_at=p.next_appointment_at, last_message_at=last_msg,
        active_reminders=active, adherence=summary(s, p.id), open_flags=flag_counts(s, p.id),
        next_dose=next_dose(s, p.id), created_at=p.created_at,
    )


async def patient_detail(s: Session, p: Patient) -> S.PatientDetail:
    item = patient_item(s, p)
    return S.PatientDetail(
        **item.model_dump(), date_of_birth=p.date_of_birth, notes=p.notes,
        link=await telegram_link(p),
        reminders=[reminder(s, m, rx) for m, rx in patient_meds(s, p.id)],
    )


def dose(e: DoseEvent, m: Medication) -> S.Dose:
    return S.Dose(id=e.id, reminder_id=m.id, medication=m.name, scheduled_for=e.scheduled_for,
                  status=str(e.status), checkin_sent_at=e.checkin_sent_at,
                  reported_at=e.reported_at, note=e.patient_note)


def flag(f: Flag, patient_name: str) -> S.FlagOut:
    return S.FlagOut(id=f.id, patient_id=f.patient_id, patient_name=patient_name,
                     dose_id=f.dose_event_id, kind=f.kind, severity=str(f.severity),
                     summary=f.summary, resolved=f.resolved, resolved_at=f.resolved_at,
                     created_at=f.created_at)


def flags(s: Session, q) -> list[S.FlagOut]:
    names = {p.id: p.name for p in s.exec(select(Patient)).all()}
    return [flag(f, names.get(f.patient_id, "?")) for f in s.exec(q).all()]


def _loads(raw: str, default):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def trace_summary(t: AgentTrace) -> S.TraceSummary:
    return S.TraceSummary(id=t.id, message_id=t.message_id, trigger=t.trigger, model=t.model,
                          output_text=t.output_text, tool_calls=_loads(t.tool_calls_json, []),
                          latency_ms=t.latency_ms, error=t.error, created_at=t.created_at)


def trace_detail(t: AgentTrace) -> S.TraceDetail:
    return S.TraceDetail(**trace_summary(t).model_dump(), patient_id=t.patient_id,
                         prompt=_loads(t.prompt_json, []))


def messages(s: Session, patient_id: int, limit: int) -> list[S.ChatMessage]:
    rows = list(reversed(s.exec(
        select(Message).where(Message.patient_id == patient_id)
        .order_by(col(Message.created_at).desc(), col(Message.id).desc()).limit(limit)
    ).all()))
    traces: dict[int, list[int]] = defaultdict(list)
    ids = [m.id for m in rows]
    if ids:
        for t_id, m_id in s.exec(select(AgentTrace.id, AgentTrace.message_id)
                                 .where(col(AgentTrace.message_id).in_(ids))).all():
            traces[m_id].append(t_id)
    return [S.ChatMessage(
        id=m.id, direction=str(m.direction), text=m.text, created_at=m.created_at,
        in_reply_to_id=m.in_reply_to_id,
        trace_ids=traces.get(m.id) or traces.get(m.in_reply_to_id) or [],
    ) for m in rows]


def adherence_report(s: Session, patient_id: int, days: int) -> S.AdherenceReport:
    since = utcnow() - timedelta(days=days)
    rows = s.exec(
        select(DoseEvent, Medication).join(Medication)
        .where(DoseEvent.patient_id == patient_id, DoseEvent.scheduled_for >= since,
               DoseEvent.scheduled_for <= utcnow())
    ).all()
    by_med: dict[int, list[DoseEvent]] = defaultdict(list)
    names: dict[int, str] = {}
    daily: dict = defaultdict(Counter)
    for e, m in rows:
        by_med[m.id].append(e)
        names[m.id] = m.name
        daily[to_local(e.scheduled_for).date()][str(e.status)] += 1
    return S.AdherenceReport(
        overall=summary(s, patient_id),
        by_medication=[S.MedicationAdherence(reminder_id=mid, medication=names[mid],
                                             adherence=_med_summary(evs))
                       for mid, evs in by_med.items()],
        daily=[S.DailyAdherence(date=d, **dict(c)) for d, c in sorted(daily.items())],
    )
