import os
import tempfile

# Must run before any hermod import: settings and the engine are built at import time.
_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["CHANNEL"] = "console"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["N8N_ALERT_WEBHOOK_URL"] = ""
os.environ["TIMEZONE"] = "Australia/Sydney"

from datetime import timedelta

import pytest
from sqlmodel import SQLModel

from hermod.channels import get_channel
from hermod.db import session as db_session
from hermod.db.models import DoseEvent, Medication, Patient, Prescription
from hermod.llm.client import LLMResult
from hermod.timeutil import utcnow


@pytest.fixture(autouse=True)
def fresh_db():
    from hermod.db import models  # noqa: F401

    SQLModel.metadata.drop_all(db_session.engine)
    SQLModel.metadata.create_all(db_session.engine)
    get_channel().sent.clear()
    yield


@pytest.fixture
def channel():
    return get_channel()


@pytest.fixture
def session():
    with db_session.new_session() as s:
        yield s


@pytest.fixture
def patient(session):
    """Synthetic patient on amoxicillin with one dose due 10 minutes ago."""
    p = Patient(name="Sam Taylor", phone="61400000000", doctor_name="Dr Lee")
    session.add(p)
    session.commit()
    rx = Prescription(patient_id=p.id, start_date=utcnow() - timedelta(days=1),
                      end_date=utcnow() + timedelta(days=5))
    session.add(rx)
    session.commit()
    med = Medication(prescription_id=rx.id, name="Amoxicillin 500mg", dose="1 capsule",
                     times_of_day="08:00,14:00,20:00", max_daily_doses=3)
    session.add(med)
    session.commit()
    ev = DoseEvent(medication_id=med.id, patient_id=p.id,
                   scheduled_for=utcnow() - timedelta(minutes=10))
    session.add(ev)
    session.commit()
    return p


class ScriptedLLM:
    """Stands in for llm.client.complete: returns queued results, records prompts."""

    def __init__(self, *results: LLMResult):
        self.results = list(results)
        self.calls: list[list[dict]] = []

    async def __call__(self, messages, tools=None):
        self.calls.append([dict(m) for m in messages])
        return self.results.pop(0)


@pytest.fixture
def llm(monkeypatch):
    def install(*results):
        fake = ScriptedLLM(*results)
        monkeypatch.setattr("hermod.llm.client.complete", fake)
        return fake

    return install
