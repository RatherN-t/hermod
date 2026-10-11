"""Schema upkeep: adding new columns to old databases, and copying between databases."""
from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel, select

from hermod.db.copy import copy_all
from hermod.db.models import Medication, Message, Patient, Prescription
from hermod.db.session import add_missing_columns


def test_add_missing_columns_backfills_defaults(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    eng = create_engine(url)
    SQLModel.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(text("INSERT INTO patient (name, phone, link_code, doctor_name, is_synthetic, "
                       "messages_stopped, created_at, language, notes) VALUES ('Old', '1', "
                       "'abc', '', 1, 0, '2026-10-10 00:00:00', 'en', '')"))
        c.execute(text("ALTER TABLE patient DROP COLUMN language"))
        c.execute(text("ALTER TABLE medication DROP COLUMN paused"))

    added = add_missing_columns(eng)

    assert set(added) == {"patient.language", "medication.paused"}
    with Session(eng) as s:
        assert s.exec(select(Patient)).one().language == "en"
    assert add_missing_columns(eng) == []


def test_copy_keeps_ids_and_refuses_non_empty_target(tmp_path, patient, session):
    from hermod.config import get_settings

    session.add(Message(patient_id=patient.id, direction="in", text="hi"))
    session.commit()
    dst = f"sqlite:///{tmp_path / 'copy.db'}"

    copied = copy_all(get_settings().database_url, dst)

    assert copied["patient"] == 1 and copied["message"] == 1 and copied["doseevent"] == 1
    with Session(create_engine(dst)) as s:
        p = s.exec(select(Patient)).one()
        assert (p.id, p.name, p.link_code) == (patient.id, "Sam Taylor", patient.link_code)
        med = s.exec(select(Medication)).one()
        assert s.get(Prescription, med.prescription_id).patient_id == p.id

    try:
        copy_all(get_settings().database_url, dst)
        raise AssertionError("expected refusal")
    except SystemExit as e:
        assert "isn't empty" in str(e)
    assert copy_all(get_settings().database_url, dst, replace=True)["patient"] == 1
