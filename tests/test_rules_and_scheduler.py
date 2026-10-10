from datetime import timedelta

from sqlmodel import select

from hermod.adherence.rules import adherence_summary, evaluate_patient
from hermod.db.models import DoseEvent, DoseStatus, Flag, Medication
from hermod.scheduler.jobs import materialise_doses
from hermod.timeutil import utcnow


def add_dose(session, patient, hours_ago, status):
    med = session.exec(select(Medication)).one()
    ev = DoseEvent(medication_id=med.id, patient_id=patient.id,
                   scheduled_for=utcnow() - timedelta(hours=hours_ago), status=status)
    session.add(ev)
    session.commit()
    return ev


def test_two_missed_in_a_row_flags_once(patient, session):
    add_dose(session, patient, 12, DoseStatus.TAKEN)
    add_dose(session, patient, 8, DoseStatus.MISSED)
    add_dose(session, patient, 4, DoseStatus.UNKNOWN)

    [flag] = evaluate_patient(patient.id, session)
    assert flag.kind == "missed_doses"
    assert evaluate_patient(patient.id, session) == []  # idempotent


def test_single_miss_is_not_flagged(patient, session):
    add_dose(session, patient, 8, DoseStatus.TAKEN)
    add_dose(session, patient, 4, DoseStatus.MISSED)
    assert evaluate_patient(patient.id, session) == []


def test_unresponsive_after_24h(patient, session):
    ev = session.exec(select(DoseEvent)).one()
    ev.checkin_sent_at = utcnow() - timedelta(hours=25)
    session.add(ev)
    session.commit()
    kinds = [f.kind for f in evaluate_patient(patient.id, session)]
    assert "unresponsive" in kinds


def test_summary(patient, session):
    add_dose(session, patient, 8, DoseStatus.TAKEN)
    add_dose(session, patient, 6, DoseStatus.LATE)
    add_dose(session, patient, 4, DoseStatus.MISSED)
    add_dose(session, patient, 2, DoseStatus.MISSED)
    s = adherence_summary(patient.id, session)
    assert s["adherence_pct"] == 50 and s["pending"] == 1


def test_materialise_is_idempotent(patient, session):
    created = materialise_doses(session)
    assert created > 0
    assert materialise_doses(session) == 0
    # Three times a day, nothing before the prescription start.
    assert all(e.scheduled_for >= utcnow() - timedelta(days=2)
               for e in session.exec(select(DoseEvent)).all())
    assert session.exec(select(Flag)).all() == []
