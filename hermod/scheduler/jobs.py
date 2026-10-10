"""APScheduler: materialise DoseEvents from prescriptions and fire check-ins on time."""
import logging
from collections import defaultdict
from datetime import datetime, time, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from hermod.adherence.rules import evaluate_patient
from hermod.db.models import DoseEvent, DoseStatus, Medication, Prescription
from hermod.db.session import new_session
from hermod.harness.alerts import notify_doctor
from hermod.timeutil import local_tz, to_local, to_utc, utcnow

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Don't fire check-ins for doses that went due long ago (e.g. after a restart).
CHECKIN_GRACE = timedelta(hours=2)
# A dose nobody answered about becomes UNKNOWN (counts as missed for the rules).
STALE_AFTER = timedelta(hours=6)


# Whole-course scheduling is capped so an open-ended or mistyped course can't explode.
MAX_COURSE_DAYS = 180


def _times(med: Medication) -> list[time]:
    return [time.fromisoformat(t.strip()) for t in med.times_of_day.split(",") if t.strip()]


def schedule_medication(s: Session, rx: Prescription, med: Medication, days: list) -> int:
    """Create missing DoseEvents for `med` on the given local dates, within the course.
    Returns how many were created. Caller commits."""
    if med.paused:
        return 0
    start = to_local(rx.start_date)
    end_day = to_local(rx.end_date).date() if rx.end_date else None
    existing = set(s.exec(
        select(DoseEvent.scheduled_for).where(DoseEvent.medication_id == med.id)
    ).all())
    created = 0
    for day in days:
        if day < start.date() or (end_day and day > end_day):
            continue
        for t in _times(med):
            local = datetime.combine(day, t, tzinfo=local_tz())
            if local < start:
                continue
            at = to_utc(local)
            if at not in existing:
                s.add(DoseEvent(medication_id=med.id, patient_id=rx.patient_id, scheduled_for=at))
                existing.add(at)
                created += 1
    return created


def schedule_course(s: Session, rx: Prescription, med: Medication) -> int:
    """Create every remaining dose of the course up front (from today), so the dashboard
    can show the whole plan. Open-ended courses get the usual rolling window."""
    today = datetime.now(local_tz()).date()
    first = max(today, to_local(rx.start_date).date())
    last = to_local(rx.end_date).date() if rx.end_date else today + timedelta(days=1)
    last = min(last, first + timedelta(days=MAX_COURSE_DAYS))
    days = [first + timedelta(days=d) for d in range((last - first).days + 1)]
    created = schedule_medication(s, rx, med, days)
    s.commit()
    return created


def planned_dose_count(rx: Prescription, med: Medication) -> int | None:
    """Doses the full course should have, or None for an open-ended course."""
    if rx.end_date is None:
        return None
    start, end = to_local(rx.start_date), to_local(rx.end_date)
    count = 0
    day = start.date()
    while day <= end.date() and (day - start.date()).days <= MAX_COURSE_DAYS:
        for t in _times(med):
            if datetime.combine(day, t, tzinfo=local_tz()) >= start:
                count += 1
        day += timedelta(days=1)
    return count


def materialise_doses(s: Session, days_ahead: int = 1) -> int:
    """Create DoseEvents for every active medication from yesterday to `days_ahead` days out.
    Idempotent. Returns how many were created."""
    today = datetime.now(local_tz()).date()
    window = [today + timedelta(days=d) for d in range(-1, days_ahead + 1)]
    created = 0
    for rx in s.exec(select(Prescription)).all():
        for med in s.exec(select(Medication).where(Medication.prescription_id == rx.id)).all():
            created += schedule_medication(s, rx, med, window)
    s.commit()
    return created


async def tick() -> None:
    from hermod.agent.agent import run_checkin  # avoid import cycle at module load

    now = utcnow()
    with new_session() as s:
        materialise_doses(s)

        due = s.exec(select(DoseEvent).where(
            DoseEvent.status == DoseStatus.PENDING,
            DoseEvent.checkin_sent_at.is_(None),
            DoseEvent.scheduled_for <= now,
            DoseEvent.scheduled_for >= now - CHECKIN_GRACE,
        )).all()
        by_patient: dict[int, list[int]] = defaultdict(list)
        for e in due:
            by_patient[e.patient_id].append(e.id)

        stale = s.exec(select(DoseEvent).where(
            DoseEvent.status == DoseStatus.PENDING,
            DoseEvent.scheduled_for < now - STALE_AFTER,
        )).all()
        for e in stale:
            e.status = DoseStatus.UNKNOWN
            s.add(e)
        s.commit()
        to_evaluate = {e.patient_id for e in stale} | set(by_patient)

    for patient_id, ids in by_patient.items():
        await run_checkin(patient_id, ids)

    with new_session() as s:
        for patient_id in to_evaluate:
            for flag in evaluate_patient(patient_id, s):
                await notify_doctor(flag)


async def _safe_tick() -> None:
    try:
        await tick()
    except Exception:
        log.exception("scheduler tick failed")


def start() -> None:
    scheduler.add_job(_safe_tick, "interval", minutes=1, id="tick", replace_existing=True,
                      next_run_time=datetime.now(local_tz()) + timedelta(seconds=5))
    scheduler.start()


def shutdown() -> None:
    scheduler.shutdown(wait=False)
