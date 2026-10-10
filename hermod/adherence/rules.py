"""Deterministic adherence rules, independent of the LLM.

The LLM records what the patient said; these rules decide what's a problem.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from sqlmodel import Session, col, select

from hermod.db.models import (
    Direction,
    DoseEvent,
    DoseStatus,
    Flag,
    FlagSeverity,
    Medication,
    Message,
)
from hermod.timeutil import to_local, utcnow

MISSED_STREAK = 2
UNRESPONSIVE_AFTER = timedelta(hours=24)
_MISSED = (DoseStatus.MISSED, DoseStatus.UNKNOWN)
_TAKEN = (DoseStatus.TAKEN, DoseStatus.LATE, DoseStatus.EXTRA)


def _has_flag(s: Session, patient_id: int, kind: str, dose_event_id: int | None,
              since=None) -> bool:
    q = select(Flag).where(Flag.patient_id == patient_id, Flag.kind == kind)
    if dose_event_id is not None:
        q = q.where(Flag.dose_event_id == dose_event_id)
    if since is not None:
        q = q.where(Flag.created_at >= since)
    return s.exec(q).first() is not None


def evaluate_patient(patient_id: int, s: Session) -> list[Flag]:
    """Return new flags: >=2 consecutive missed doses, extra doses or more than
    max_daily_doses in a day, check-ins unanswered for 24h. Idempotent: each flag is keyed
    on the dose that triggered it, so re-running doesn't duplicate."""
    now = utcnow()
    events = s.exec(
        select(DoseEvent).where(DoseEvent.patient_id == patient_id,
                                DoseEvent.scheduled_for <= now)
        .order_by(col(DoseEvent.scheduled_for))
    ).all()
    meds = {m.id: m for m in s.exec(select(Medication)).all()}
    new: list[Flag] = []

    def add(kind, severity, summary, ev_id, dedupe=True):
        if not dedupe or not _has_flag(s, patient_id, kind, ev_id):
            f = Flag(patient_id=patient_id, dose_event_id=ev_id, kind=kind,
                     severity=severity, summary=summary)
            s.add(f)
            new.append(f)

    by_med: dict[int, list[DoseEvent]] = defaultdict(list)
    for e in events:
        by_med[e.medication_id].append(e)

    for med_id, evs in by_med.items():
        name = meds[med_id].name if med_id in meds else "medication"
        scheduled = [e for e in evs if e.status != DoseStatus.EXTRA]
        streak = 0
        for e in reversed(scheduled):
            if e.status in _MISSED:
                streak += 1
            elif e.status != DoseStatus.PENDING:
                break
        if streak >= MISSED_STREAK:
            add("missed_doses", FlagSeverity.WARNING,
                f"{streak} doses of {name} missed or unconfirmed in a row",
                [e for e in scheduled if e.status in _MISSED][-1].id)

        for e in evs:
            if e.status == DoseStatus.EXTRA:
                add("extra_dose", FlagSeverity.WARNING,
                    f"Extra dose of {name} reported ({to_local(e.scheduled_for):%a %H:%M})"
                    + (f": {e.patient_note}" if e.patient_note else ""), e.id)

        cap = meds[med_id].max_daily_doses if med_id in meds else None
        if cap:
            per_day = Counter(to_local(e.scheduled_for).date() for e in evs if e.status in _TAKEN)
            for day, n in per_day.items():
                if n > cap:
                    last = [e for e in evs if e.status in _TAKEN
                            and to_local(e.scheduled_for).date() == day][-1]
                    add("over_daily_max", FlagSeverity.URGENT,
                        f"{n} doses of {name} on {day:%a %d %b} (max {cap})", last.id)

    # Check-ins sent but nothing heard back for 24h.
    last_in = s.exec(
        select(Message.created_at).where(Message.patient_id == patient_id,
                                         Message.direction == Direction.INBOUND)
        .order_by(col(Message.created_at).desc())
    ).first()
    unanswered = [e for e in events if e.checkin_sent_at
                  and (last_in is None or e.checkin_sent_at > last_in)]
    if (
        unanswered
        and now - unanswered[0].checkin_sent_at >= UNRESPONSIVE_AFTER
        and not _has_flag(s, patient_id, "unresponsive", None, since=now - UNRESPONSIVE_AFTER)
    ):
        add("unresponsive", FlagSeverity.WARNING,
            f"No reply to {len(unanswered)} check-in(s) in the last "
            f"{int((now - unanswered[0].checkin_sent_at).total_seconds() // 3600)}h",
            None, dedupe=False)

    if new:
        s.commit()
        for f in new:
            s.refresh(f)
    return new


def adherence_summary(patient_id: int, s: Session) -> dict:
    """Taken / late / missed / extra counts and % adherence for the doctor dashboard."""
    events = s.exec(
        select(DoseEvent).where(DoseEvent.patient_id == patient_id,
                                DoseEvent.scheduled_for <= utcnow())
    ).all()
    counts = Counter(str(e.status) for e in events)
    scheduled = sum(counts[k] for k in ("taken", "late", "missed", "unknown"))
    return {
        "taken": counts["taken"],
        "late": counts["late"],
        "missed": counts["missed"],
        "unknown": counts["unknown"],
        "extra": counts["extra"],
        "pending": counts["pending"],
        "adherence_pct": round(100 * (counts["taken"] + counts["late"]) / scheduled)
        if scheduled else None,
    }
