"""A fictional clinic for demos and frontend work: synthetic patients with dose history.

    DATABASE_URL=sqlite:///./hermod-dev.db python -m hermod.demo seed-clinic --reset
    python -m hermod.demo seed-clinic --shared            # add to Supabase (.env DATABASE_URL)
    python -m hermod.demo seed-clinic --remove --shared   # take them out again

Writes to SQLite by default and refuses any other DATABASE_URL unless `--shared` is given.
On a shared database it only adds patients and `--remove` deletes only these demo patients
(matched by phone); `--reset` (drop and recreate every table) is SQLite only. Dose history is built
relative to now, so re-seed to refresh it. Past doses all have a status (taken, late,
missed, unknown); upcoming ones are pending.
"""
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import SQLModel, col, select

from hermod.config import get_settings
from hermod.db.models import DoseEvent, DoseStatus, Medication, Patient, Prescription
from hermod.db.session import engine, init_db, new_session
from hermod.scheduler.jobs import schedule_course
from hermod.timeutil import local_tz, to_utc, utcnow

DOCTOR = "Dr. Sarah Lee"


@dataclass
class Med:
    name: str
    dose: str
    times: list[str]
    started_days_ago: int
    kind: str = "days"  # "days" | "date" | "appointment"
    days: int | None = None
    until: date | None = None
    pct: float = 1.0  # share of past doses taken or late
    counts: dict[str, int] | None = None  # exact past statuses (overrides pct)
    instructions: str = ""


@dataclass
class Person:
    name: str
    # ACMA's reserved fiction numbers (0491 570 xxx etc.), so a texted link reaches no one:
    # https://www.acma.gov.au/use-phone-numbers-fiction
    phone: str
    dob: date
    language: str = "en"
    appointment: datetime | None = None  # clinic-local
    notes: str = ""
    meds: list[Med] = field(default_factory=list)


def _appt(y: int, m: int, d: int, hh: int = 9, mm: int = 30) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=local_tz())


def _eleanor_start() -> int:
    """Days ago to start so Lisinopril 08:00 has exactly 21 past doses."""
    return 20 if datetime.now(local_tz()).time() >= time(8, 0) else 21


def clinic() -> list[Person]:
    return [
        Person("Eleanor Mitchell", "61491570156", date(1968, 4, 18),
               appointment=_appt(2027, 1, 8), notes="Hypertension, reviewing BP at follow-up.",
               meds=[Med("Lisinopril 10 mg", "1 tablet", ["08:00"], _eleanor_start(),
                         kind="appointment", counts={"taken": 18, "missed": 3})]),
        Person("James Okafor", "61491570157", date(1975, 9, 2), appointment=_appt(2026, 11, 20),
               meds=[Med("Metformin 500 mg", "1 tablet", ["08:00", "20:00"], 14, days=90,
                         pct=0.96, instructions="With meals"),
                     Med("Atorvastatin 20 mg", "1 tablet", ["21:00"], 14, days=90, pct=1.0)]),
        Person("Priya Shah", "61491570158", date(1992, 2, 14),
               meds=[Med("Amoxicillin 500 mg", "1 capsule", ["08:00", "14:00", "20:00"], 4,
                         days=7, pct=0.64, instructions="Finish the full course")]),
        Person("Tomás Rivera", "61491570159", date(1959, 11, 30), language="es",
               appointment=_appt(2026, 12, 3, 11, 0),
               meds=[Med("Amlodipine 5 mg", "1 tablet", ["09:00"], 30, days=180, pct=0.9)]),
        Person("Grace Chen", "61491570110", date(1988, 6, 21),
               appointment=_appt(2026, 10, 28, 14, 15), notes="New patient, nothing prescribed yet."),
        Person("Samuel Adeyemi", "61491570313", date(1981, 3, 9),
               meds=[Med("Levothyroxine 50 mcg", "1 tablet", ["06:30"], 35, kind="date",
                         until=date(2027, 3, 31), pct=0.97,
                         instructions="Empty stomach, 30 min before breakfast")]),
        Person("Hannah Kowalski", "61491570737", date(1996, 8, 12),
               appointment=_appt(2026, 10, 24, 10, 0),
               meds=[Med("Sertraline 50 mg", "1 tablet", ["08:00"], 20, days=120, pct=0.6)]),
        Person("Daniel Brooks", "61491571266", date(1970, 12, 5),
               meds=[Med("Prednisone 20 mg", "1 tablet", ["08:00"], 6, days=5, pct=1.0,
                         instructions="With breakfast")]),
        Person("Olivia Nguyen", "61491571491", date(2001, 5, 27),
               appointment=_appt(2026, 11, 12, 15, 45),
               meds=[Med("Montelukast 10 mg", "1 tablet", ["20:00"], 12, days=60, pct=0.83)]),
        Person("Michael O'Brien", "61491571804", date(1963, 1, 15),
               appointment=_appt(2026, 12, 9, 8, 45), notes="Post-MI, on beta blocker.",
               meds=[Med("Metoprolol 50 mg", "1 tablet", ["08:00", "20:00"], 25, days=180,
                         pct=0.88)]),
        Person("Aisha Rahman", "61491572549", date(1994, 10, 3),
               meds=[Med("Doxycycline 100 mg", "1 capsule", ["08:00", "20:00"], 6, days=10,
                         pct=0.75, instructions="With a full glass of water, stay upright")]),
        Person("Ruth Thompson", "61491572665", date(1949, 7, 22), notes="INR checks fortnightly.",
               appointment=_appt(2026, 10, 22, 10, 30),
               meds=[Med("Warfarin 3 mg", "1 tablet", ["18:00"], 40, kind="appointment",
                         pct=0.93)]),
    ]


def _statuses(n: int, med: Med, rng: random.Random) -> list[DoseStatus]:
    if med.counts:
        out = [DoseStatus(k) for k, c in med.counts.items() for _ in range(c)]
        assert len(out) == n, f"{med.name}: {len(out)} statuses for {n} past doses"
    else:
        good = round(n * med.pct)
        late = good // 8
        bad = n - good
        unknown = bad // 3
        out = ([DoseStatus.TAKEN] * (good - late) + [DoseStatus.LATE] * late
               + [DoseStatus.MISSED] * (bad - unknown) + [DoseStatus.UNKNOWN] * unknown)
    rng.shuffle(out)
    return out


def _end_of(d: date) -> datetime:
    return to_utc(datetime.combine(d, time(23, 59, 59)))


def _add_med(s, p: Patient, med: Med, rng: random.Random) -> None:
    today = datetime.now(local_tz()).date()
    first_day = today - timedelta(days=med.started_days_ago)
    start = to_utc(datetime.combine(first_day, time.min))
    if med.kind == "days":
        end = _end_of(first_day + timedelta(days=med.days - 1))
    elif med.kind == "date":
        end = _end_of(med.until)
    else:
        end = p.next_appointment_at
    rx = Prescription(patient_id=p.id, start_date=start, end_date=end, duration_kind=med.kind,
                      duration_days=med.days if med.kind == "days" else None,
                      doctor_notes="Synthetic demo data")
    s.add(rx)
    s.commit()
    m = Medication(prescription_id=rx.id, name=med.name, dose=med.dose,
                   times_of_day=",".join(med.times), instructions=med.instructions,
                   max_daily_doses=len(med.times))
    s.add(m)
    s.commit()

    now = utcnow()
    last_day = min(today, end.astimezone(local_tz()).date())
    past = []
    for d in range((last_day - first_day).days + 1):
        for t in med.times:
            at = to_utc(datetime.combine(first_day + timedelta(days=d), time.fromisoformat(t)))
            if start <= at <= min(now, end):
                past.append(at)
    for at, st in zip(past, _statuses(len(past), med, rng), strict=True):
        reported = {DoseStatus.TAKEN: at + timedelta(minutes=rng.randint(2, 40)),
                    DoseStatus.LATE: at + timedelta(hours=rng.randint(2, 4)),
                    DoseStatus.MISSED: at + timedelta(hours=rng.randint(1, 5))}.get(st)
        s.add(DoseEvent(medication_id=m.id, patient_id=p.id, scheduled_for=at, status=st,
                        checkin_sent_at=at, reported_at=reported,
                        patient_note="Forgot, was out" if st == DoseStatus.MISSED
                        and rng.random() < 0.3 else ""))
    s.commit()
    schedule_course(s, rx, m)  # upcoming doses, pending


def _check_target(url: str, shared: bool, reset: bool) -> None:
    if url.startswith("sqlite"):
        return
    if not shared:
        raise SystemExit("DATABASE_URL isn't SQLite. To write the demo clinic to the shared "
                         "database, add --shared.")
    if reset:
        raise SystemExit("--reset drops every table, so it's SQLite only. Use --remove to take "
                         "the demo patients out of a shared database.")


def remove_clinic(shared: bool = False) -> None:
    """Delete only the demo clinic's patients (matched by their fiction phone numbers)."""
    from hermod.api.routes import delete_patient_rows

    _check_target(get_settings().database_url, shared, reset=False)
    phones = [person.phone for person in clinic()]
    with new_session() as s:
        found = s.exec(select(Patient).where(col(Patient.phone).in_(phones))).all()
        for p in found:
            delete_patient_rows(s, p)
        s.commit()
        print(f"Removed {len(found)} demo patients")


def seed_clinic(reset: bool = False, shared: bool = False) -> None:
    url = get_settings().database_url
    _check_target(url, shared, reset)
    if reset:
        from hermod.db import models  # noqa: F401  (register tables)

        SQLModel.metadata.drop_all(engine)
    init_db()
    rng = random.Random(1203)
    with new_session() as s:
        phones = [person.phone for person in clinic()]
        if s.exec(select(Patient).where(col(Patient.phone).in_(phones))).first():
            raise SystemExit("The demo clinic is already seeded; add --reset to rebuild it")
        for person in clinic():
            p = Patient(name=person.name, phone=person.phone, doctor_name=DOCTOR,
                        date_of_birth=person.dob, language=person.language,
                        next_appointment_at=person.appointment.astimezone(UTC)
                        if person.appointment else None,
                        notes=person.notes, is_synthetic=True)
            s.add(p)
            s.commit()
            s.refresh(p)
            for med in person.meds:
                _add_med(s, p, med, rng)
        where = url.split("///")[-1] if url.startswith("sqlite") else "the shared database"
        print(f"Seeded {len(clinic())} synthetic patients into {where}")
