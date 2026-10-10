"""Local dev and demo setup.

    python -m hermod.demo seed --phone 61400000000      # synthetic patient + antibiotic course
    python -m hermod.demo link --phone 61400000000      # print their Telegram start link
    CHANNEL=console python -m hermod.demo chat --phone 61400000000

In chat, type as the patient. `/checkin` fires a check-in for any due doses, `/flags` lists
flags, `/quit` exits.
"""
import argparse
import asyncio
import itertools
from datetime import datetime, timedelta

from sqlmodel import select

from hermod.adherence.rules import adherence_summary
from hermod.agent.agent import handle_inbound, run_checkin
from hermod.channels.base import IncomingMessage
from hermod.config import get_settings
from hermod.db.models import DoseEvent, DoseStatus, Flag, Medication, Patient, Prescription
from hermod.db.session import init_db, new_session
from hermod.scheduler.jobs import materialise_doses
from hermod.timeutil import local_tz, to_utc, utcnow


def seed(phone: str, name: str) -> None:
    init_db()
    with new_session() as s:
        if s.exec(select(Patient).where(Patient.phone == phone)).first():
            print(f"Patient with {phone} already exists")
            return
        p = Patient(name=name, phone=phone, doctor_name="Dr Lee")
        s.add(p)
        s.commit()
        today = datetime.now(local_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
        rx = Prescription(patient_id=p.id, start_date=to_utc(today),
                          end_date=to_utc(today + timedelta(days=6)),
                          doctor_notes="Synthetic demo data")
        s.add(rx)
        s.commit()
        s.add(Medication(prescription_id=rx.id, name="Amoxicillin 500mg", dose="1 capsule",
                         times_of_day="08:00,14:00,20:00",
                         instructions="Finish the full course", max_daily_doses=3))
        s.commit()
        n = materialise_doses(s)
        print(f"Seeded {name} ({phone}), 7-day amoxicillin course, {n} doses scheduled")
        print_telegram_link(p)


def print_telegram_link(patient: Patient) -> None:
    if not get_settings().telegram_bot_token:
        return
    from hermod.channels.telegram import TelegramChannel

    bot = asyncio.run(TelegramChannel(get_settings()).bot_username())
    print(f"Telegram link for {patient.name}: https://t.me/{bot}?start={patient.link_code}")


def link(phone: str) -> None:
    """Print an existing patient's Telegram onboarding link."""
    init_db()
    with new_session() as s:
        p = s.exec(select(Patient).where(Patient.phone == phone)).first()
        if p is None:
            print(f"No patient with {phone}; run seed first")
            return
        print_telegram_link(p)


async def chat(phone: str) -> None:
    init_db()
    ids = itertools.count(1)
    print("Type as the patient. /checkin, /flags, /quit")
    while True:
        try:
            line = await asyncio.to_thread(input, "you> ")
        except EOFError:
            return
        if line == "/quit":
            return
        with new_session() as s:
            patient = s.exec(select(Patient).where(Patient.phone == phone)).first()
            if line == "/checkin" and patient:
                due = s.exec(select(DoseEvent).where(
                    DoseEvent.patient_id == patient.id, DoseEvent.status == DoseStatus.PENDING,
                    DoseEvent.scheduled_for <= utcnow() + timedelta(hours=1))).all()
                if due:
                    await run_checkin(patient.id, [due[-1].id])
                else:
                    print("  (no due doses)")
                continue
            if line == "/flags" and patient:
                for f in s.exec(select(Flag).where(Flag.patient_id == patient.id)).all():
                    print(f"  [{f.severity}] {f.kind}: {f.summary}")
                print(f"  {adherence_summary(patient.id, s)}")
                continue
        await handle_inbound(IncomingMessage(sender_id=phone, text=line,
                                             message_id=f"cli-{utcnow():%s}-{next(ids)}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["seed", "chat", "link"])
    ap.add_argument("--phone", required=True, help="digits only, e.g. 61400000000 (the patient's id)")
    ap.add_argument("--name", default="Sam Taylor")
    a = ap.parse_args()
    if a.cmd == "seed":
        seed(a.phone, a.name)
    elif a.cmd == "link":
        link(a.phone)
    else:
        asyncio.run(chat(a.phone))


if __name__ == "__main__":
    main()
