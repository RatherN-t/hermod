"""Dashboard API for the doctor-facing frontend. Interactive docs at /docs.

Every route lives under /api. If API_KEY is set, requests need header "X-API-Key".
"""
import hmac
import secrets
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import delete, update
from sqlmodel import Session, col, select

from hermod.api import schemas as S
from hermod.api import views as V
from hermod.channels import patient_address
from hermod.config import get_settings
from hermod.db.models import (
    AgentTrace,
    DoseEvent,
    DoseStatus,
    Flag,
    FlagSeverity,
    Medication,
    Message,
    Patient,
    Prescription,
)
from hermod.db.session import get_session
from hermod.scheduler.jobs import schedule_course
from hermod.timeutil import local_tz, to_local, to_utc, utcnow


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().api_key
    if expected and not hmac.compare_digest(x_api_key or "", expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or wrong X-API-Key")


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_key)])
DB = Annotated[Session, Depends(get_session)]


def _patient(s: Session, patient_id: int) -> Patient:
    p = s.get(Patient, patient_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Patient {patient_id} not found")
    return p


def _med(s: Session, reminder_id: int) -> tuple[Medication, Prescription]:
    m = s.get(Medication, reminder_id)
    if not m:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Reminder {reminder_id} not found")
    return m, s.get(Prescription, m.prescription_id)


def _drop_future_doses(s: Session, m: Medication) -> None:
    """Remove doses that haven't happened or been asked about yet."""
    for e in s.exec(select(DoseEvent).where(
        DoseEvent.medication_id == m.id, DoseEvent.status == DoseStatus.PENDING,
        DoseEvent.scheduled_for > utcnow(), DoseEvent.checkin_sent_at.is_(None),
    )).all():
        s.delete(e)


# --- dashboard -----------------------------------------------------------------------------

@router.get("/dashboard", response_model=S.Dashboard, tags=["dashboard"])
def dashboard(s: DB):
    """Clinic overview: counts, who needs attention, latest flags and messages."""
    patients = s.exec(select(Patient).order_by(col(Patient.name))).all()
    items = [V.patient_item(s, p) for p in patients]
    pcts = [i.adherence.adherence_pct for i in items if i.adherence.adherence_pct is not None]
    attention = [i for i in items if i.open_flags.urgent or i.open_flags.warning
                 or (i.adherence.adherence_pct is not None and i.adherence.adherence_pct < 80)]
    attention.sort(key=lambda i: (-i.open_flags.urgent, -i.open_flags.warning,
                                  i.adherence.adherence_pct if i.adherence.adherence_pct
                                  is not None else 101))
    names = {p.id: p.name for p in patients}
    recent = s.exec(select(Message).order_by(col(Message.created_at).desc()).limit(15)).all()
    return S.Dashboard(
        patients=len(items),
        linked_patients=sum(i.telegram_linked for i in items),
        active_reminders=sum(i.active_reminders for i in items),
        average_adherence_pct=round(sum(pcts) / len(pcts)) if pcts else None,
        open_flags=V.flag_counts(s),
        needs_attention=attention,
        recent_flags=V.flags(s, select(Flag).order_by(col(Flag.created_at).desc()).limit(10)),
        recent_messages=[S.RecentMessage(patient_id=m.patient_id,
                                         patient_name=names.get(m.patient_id, "?"),
                                         direction=str(m.direction), text=m.text,
                                         created_at=m.created_at) for m in recent],
    )


# --- patients ------------------------------------------------------------------------------

@router.get("/patients", response_model=list[S.PatientListItem], tags=["patients"])
def list_patients(s: DB, q: Annotated[str | None, Query(description="Name contains")] = None):
    query = select(Patient).order_by(col(Patient.name))
    if q:
        query = query.where(col(Patient.name).ilike(f"%{q}%"))
    return [V.patient_item(s, p) for p in s.exec(query).all()]


@router.post("/patients", response_model=S.PatientDetail, status_code=201, tags=["patients"])
async def create_patient(body: S.PatientCreate, s: DB):
    """Create a patient. The response includes their Telegram start link to send them."""
    if s.exec(select(Patient).where(Patient.phone == body.phone)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A patient with this phone exists")
    p = Patient(**body.model_dump())
    s.add(p)
    s.commit()
    s.refresh(p)
    return await V.patient_detail(s, p)


@router.get("/patients/{patient_id}", response_model=S.PatientDetail, tags=["patients"])
async def get_patient(patient_id: int, s: DB):
    """Everything about one patient: profile, link, adherence, flags, reminders."""
    return await V.patient_detail(s, _patient(s, patient_id))


@router.patch("/patients/{patient_id}", response_model=S.PatientDetail, tags=["patients"])
async def update_patient(patient_id: int, body: S.PatientUpdate, s: DB):
    p = _patient(s, patient_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    s.add(p)
    s.commit()
    return await V.patient_detail(s, p)


@router.delete("/patients/{patient_id}", status_code=204, tags=["patients"])
def delete_patient(patient_id: int, s: DB) -> None:
    """Permanently delete a patient and everything about them: reminders, doses, messages,
    agent traces and flags. Can't be undone; the dashboard asks for confirmation first."""
    delete_patient_rows(s, _patient(s, patient_id))
    s.commit()


def delete_patient_rows(s: Session, p: Patient) -> None:
    """Delete a patient and all their rows (no commit)."""
    msgs = select(Message.id).where(Message.patient_id == p.id)
    rxs = select(Prescription.id).where(Prescription.patient_id == p.id)
    # Children before parents, so foreign keys hold on Postgres.
    s.execute(delete(AgentTrace).where(
        (AgentTrace.patient_id == p.id) | col(AgentTrace.message_id).in_(msgs)))
    s.execute(delete(Flag).where(Flag.patient_id == p.id))
    s.execute(delete(DoseEvent).where(DoseEvent.patient_id == p.id))
    s.execute(update(Message).where(Message.patient_id == p.id).values(in_reply_to_id=None))
    s.execute(delete(Message).where(Message.patient_id == p.id))
    s.execute(delete(Medication).where(col(Medication.prescription_id).in_(rxs)))
    s.execute(delete(Prescription).where(Prescription.patient_id == p.id))
    s.delete(p)


@router.get("/patients/{patient_id}/link", response_model=S.TelegramLink, tags=["patients"])
async def get_link(patient_id: int, s: DB):
    """The patient's personal Telegram start link (show it as a link or QR code)."""
    return await V.telegram_link(_patient(s, patient_id))


@router.post("/patients/{patient_id}/link/reset", response_model=S.TelegramLink,
             tags=["patients"])
async def reset_link(patient_id: int, s: DB):
    """Issue a new link and unlink the current Telegram chat (e.g. if the link leaked)."""
    p = _patient(s, patient_id)
    p.link_code = secrets.token_urlsafe(9)
    p.telegram_chat_id = None
    s.add(p)
    s.commit()
    return await V.telegram_link(p)


# --- reminders -----------------------------------------------------------------------------

def _end_of(d: date) -> datetime:
    return to_utc(datetime.combine(d, time(23, 59, 59)))


def _course_end(kind: str, days: int | None, until: date | None, first_day: date,
                start: datetime, p: Patient) -> datetime:
    """End of a course that starts at `start` (local day `first_day`). 422 if invalid."""
    if kind == "days":
        if not days:
            raise HTTPException(422, "durationDays is required for durationKind=days")
        return _end_of(first_day + timedelta(days=days - 1))
    if kind == "date":
        if not until or until < first_day:
            raise HTTPException(422, "untilDate is required and must be on/after the start")
        return _end_of(until)
    if not p.next_appointment_at or p.next_appointment_at <= max(start, utcnow()):
        raise HTTPException(422, "durationKind=appointment needs a future nextAppointmentAt "
                                 "on the patient")
    return p.next_appointment_at


def _course_dates(body: S.ReminderCreate, p: Patient) -> tuple[datetime, datetime]:
    now = utcnow()
    today = datetime.now(local_tz()).date()
    if body.start_date and body.start_date < today:
        raise HTTPException(422, "startDate can't be in the past")
    start = now if not body.start_date or body.start_date == today else to_utc(
        datetime.combine(body.start_date, time.min))
    first_day = body.start_date or today
    return start, _course_end(body.duration_kind, body.duration_days, body.until_date,
                              first_day, start, p)


def _change_duration(s: Session, rx: Prescription, changes: dict) -> None:
    """Apply durationKind/durationDays/untilDate from a PATCH to the course. Missing fields
    fall back to the course's current values; days and dates count from the course start."""
    kind = changes.pop("duration_kind", None) or rx.duration_kind
    days = changes.pop("duration_days", None)
    until = changes.pop("until_date", None)
    if kind == "days" and days is None:
        days = rx.duration_days
    if kind == "date" and until is None and rx.duration_kind == "date" and rx.end_date:
        until = to_local(rx.end_date).date()
    end = _course_end(kind, days, until, to_local(rx.start_date).date(), rx.start_date,
                      s.get(Patient, rx.patient_id))
    if end < utcnow():
        raise HTTPException(422, "That would end the course in the past; use "
                                 "POST /api/reminders/{id}/end to stop it now")
    rx.end_date = end
    rx.duration_kind = kind
    rx.duration_days = days if kind == "days" else None
    s.add(rx)


@router.get("/patients/{patient_id}/reminders", response_model=list[S.Reminder],
            tags=["reminders"])
def list_reminders(patient_id: int, s: DB):
    _patient(s, patient_id)
    return [V.reminder(s, m, rx) for m, rx in V.patient_meds(s, patient_id)]


@router.post("/patients/{patient_id}/reminders", response_model=S.Reminder, status_code=201,
             tags=["reminders"])
def create_reminder(patient_id: int, body: S.ReminderCreate, s: DB):
    """Prescribe a medication: creates the course and schedules every dose."""
    p = _patient(s, patient_id)
    start, end = _course_dates(body, p)
    rx = Prescription(patient_id=p.id, start_date=start, end_date=end,
                      duration_kind=body.duration_kind,
                      duration_days=body.duration_days if body.duration_kind == "days" else None)
    s.add(rx)
    s.commit()
    s.refresh(rx)
    m = Medication(prescription_id=rx.id, name=body.name, dose=body.dose,
                   instructions=body.instructions, times_of_day=",".join(body.times_of_day),
                   max_daily_doses=body.max_daily_doses or len(body.times_of_day),
                   checkin_message=body.custom_message or None,
                   alert_on_missed=body.alert_on_missed)
    s.add(m)
    s.commit()
    s.refresh(m)
    schedule_course(s, rx, m)
    return V.reminder(s, m, rx)


@router.get("/reminders/{reminder_id}", response_model=S.Reminder, tags=["reminders"])
def get_reminder(reminder_id: int, s: DB):
    m, rx = _med(s, reminder_id)
    return V.reminder(s, m, rx)


@router.patch("/reminders/{reminder_id}", response_model=S.Reminder, tags=["reminders"])
def update_reminder(reminder_id: int, body: S.ReminderUpdate, s: DB):
    """Pause/resume, change times, course length, dose, message or alerting. Pausing removes
    upcoming doses (so they don't count as missed); resuming, new times or a new course
    length reschedule them. Past doses are never touched."""
    m, rx = _med(s, reminder_id)
    changes = body.model_dump(exclude_unset=True)
    reschedule = False
    if "status" in changes:
        paused = changes.pop("status") == "paused"
        if paused != m.paused:
            m.paused = paused
            reschedule = True
    if "times_of_day" in changes:
        m.times_of_day = ",".join(changes.pop("times_of_day"))
        reschedule = True
    duration_changed = bool({"duration_kind", "duration_days", "until_date"} & changes.keys())
    if duration_changed:
        _change_duration(s, rx, changes)
        reschedule = True
    if "custom_message" in changes:
        m.checkin_message = changes.pop("custom_message") or None
    for k, v in changes.items():
        setattr(m, k, v)
    s.add(m)
    # A new end date applies to every medication on the course (the API makes one per course).
    meds = s.exec(select(Medication).where(Medication.prescription_id == rx.id)).all() \
        if duration_changed else [m]
    if reschedule:
        for med in meds:
            _drop_future_doses(s, med)
    s.commit()
    if reschedule and V.reminder_status(m, rx) != "ended":
        for med in meds:
            if not med.paused:
                schedule_course(s, rx, med)
    return V.reminder(s, m, rx)


@router.post("/reminders/{reminder_id}/end", response_model=S.Reminder, tags=["reminders"])
def end_reminder(reminder_id: int, s: DB):
    """Stop the course now (e.g. the doctor discontinued it). History is kept."""
    m, rx = _med(s, reminder_id)
    rx.end_date = utcnow()
    s.add(rx)
    _drop_future_doses(s, m)
    s.commit()
    return V.reminder(s, m, rx)


@router.post("/reminders/{reminder_id}/checkin", tags=["reminders"])
async def send_checkin_now(reminder_id: int, s: DB) -> dict:
    """Send the check-in for this reminder's current dose right away (demo helper). Uses
    the latest dose that's due, or the next one coming up."""
    from hermod.agent.agent import run_checkin

    m, rx = _med(s, reminder_id)
    p = s.get(Patient, rx.patient_id)
    if not patient_address(p):
        raise HTTPException(status.HTTP_409_CONFLICT, "Patient hasn't linked Telegram yet")
    if m.paused:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reminder is paused")
    open_doses = s.exec(select(DoseEvent).where(
        DoseEvent.medication_id == m.id, DoseEvent.status == DoseStatus.PENDING,
    ).order_by(col(DoseEvent.scheduled_for))).all()
    now = utcnow()
    due = [e for e in open_doses if e.scheduled_for <= now]
    target = due[-1] if due else (open_doses[0] if open_doses else None)
    if not target:
        raise HTTPException(status.HTTP_409_CONFLICT, "No open dose to check in about")
    await run_checkin(p.id, [target.id])
    s.refresh(target)
    if not target.checkin_sent_at:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Sending the check-in failed")
    return {"sent": True, "doseId": target.id, "scheduledFor": target.scheduled_for}


# --- doses, adherence, conversation, traces ------------------------------------------------

@router.get("/patients/{patient_id}/doses", response_model=list[S.Dose], tags=["timeline"])
def list_doses(
    patient_id: int, s: DB,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    dose_status: Annotated[str | None, Query(alias="status",
                                             description="taken, missed, pending, ...")] = None,
    reminder_id: Annotated[int | None, Query(alias="reminderId")] = None,
):
    """The dose timeline, oldest first. Includes future scheduled doses."""
    _patient(s, patient_id)
    q = select(DoseEvent, Medication).join(Medication).where(DoseEvent.patient_id == patient_id)
    if from_:
        q = q.where(DoseEvent.scheduled_for >= from_)
    if to:
        q = q.where(DoseEvent.scheduled_for <= to)
    if dose_status:
        try:
            q = q.where(DoseEvent.status == DoseStatus(dose_status))
        except ValueError:
            raise HTTPException(422, f"Unknown status {dose_status!r}") from None
    if reminder_id:
        q = q.where(DoseEvent.medication_id == reminder_id)
    return [V.dose(e, m) for e, m in s.exec(q.order_by(col(DoseEvent.scheduled_for))).all()]


@router.get("/patients/{patient_id}/adherence", response_model=S.AdherenceReport,
            tags=["timeline"])
def get_adherence(patient_id: int, s: DB,
                  days: Annotated[int, Query(ge=1, le=365, description="Daily chart range")] = 14):
    """Overall and per-medication adherence plus a per-day breakdown for charts."""
    _patient(s, patient_id)
    return V.adherence_report(s, patient_id, days)


@router.get("/patients/{patient_id}/messages", response_model=list[S.ChatMessage],
            tags=["timeline"])
def list_messages(patient_id: int, s: DB,
                  limit: Annotated[int, Query(ge=1, le=500)] = 100):
    """The conversation, oldest first. traceIds point at the LLM calls behind each reply."""
    _patient(s, patient_id)
    return V.messages(s, patient_id, limit)


@router.get("/patients/{patient_id}/traces", response_model=list[S.TraceSummary],
            tags=["traces"])
def list_traces(patient_id: int, s: DB, limit: Annotated[int, Query(ge=1, le=500)] = 50):
    """Every LLM call for this patient, newest first."""
    _patient(s, patient_id)
    rows = s.exec(select(AgentTrace).where(AgentTrace.patient_id == patient_id)
                  .order_by(col(AgentTrace.created_at).desc()).limit(limit)).all()
    return [V.trace_summary(t) for t in rows]


@router.get("/traces/{trace_id}", response_model=S.TraceDetail, tags=["traces"])
def get_trace(trace_id: int, s: DB):
    """One LLM call in full: the prompt sent, the output, tool calls, latency, errors."""
    t = s.get(AgentTrace, trace_id)
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Trace {trace_id} not found")
    return V.trace_detail(t)


# --- flags ---------------------------------------------------------------------------------

FlagState = Literal["open", "resolved", "all"]


def _flag_query(state: FlagState, severity: str | None, patient_id: int | None):
    q = select(Flag).order_by(col(Flag.created_at).desc())
    if state != "all":
        q = q.where(Flag.resolved == (state == "resolved"))
    if severity:
        q = q.where(Flag.severity == FlagSeverity(severity))
    if patient_id:
        q = q.where(Flag.patient_id == patient_id)
    return q


@router.get("/flags", response_model=list[S.FlagOut], tags=["flags"])
def list_flags(s: DB, state: Annotated[FlagState, Query(alias="status")] = "open",
               severity: Literal["urgent", "warning", "info"] | None = None,
               patient_id: Annotated[int | None, Query(alias="patientId")] = None):
    """Flags across all patients, newest first. Defaults to open ones."""
    return V.flags(s, _flag_query(state, severity, patient_id))


@router.get("/patients/{patient_id}/flags", response_model=list[S.FlagOut], tags=["flags"])
def list_patient_flags(patient_id: int, s: DB,
                       state: Annotated[FlagState, Query(alias="status")] = "all"):
    _patient(s, patient_id)
    return V.flags(s, _flag_query(state, None, patient_id))


@router.patch("/flags/{flag_id}", response_model=S.FlagOut, tags=["flags"])
def update_flag(flag_id: int, body: S.FlagUpdate, s: DB):
    """Mark a flag resolved (or reopen it)."""
    f = s.get(Flag, flag_id)
    if not f:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Flag {flag_id} not found")
    f.resolved = body.resolved
    f.resolved_at = utcnow() if body.resolved else None
    s.add(f)
    s.commit()
    return V.flag(f, _patient(s, f.patient_id).name)
