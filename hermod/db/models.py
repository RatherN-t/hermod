"""Data model. One prescription -> many medications -> many scheduled doses.

Every dose has a status the agent fills in from the patient's replies; that
status history *is* the adherence log the doctor reads.
"""
from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Patient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    wa_phone: str = Field(index=True, unique=True)  # E.164 without '+', as WhatsApp sends it
    doctor_name: str = ""
    is_synthetic: bool = True  # demo data must be labelled
    last_inbound_at: datetime | None = None  # drives the 24h free-form window
    created_at: datetime = Field(default_factory=_now)


class Prescription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    start_date: datetime
    end_date: datetime | None = None
    doctor_notes: str = ""
    source: str = "form"  # "form" | "photo"
    created_at: datetime = Field(default_factory=_now)


class Medication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    prescription_id: int = Field(foreign_key="prescription.id", index=True)
    name: str  # e.g. "Amoxicillin 500mg"
    dose: str  # e.g. "1 capsule"
    times_of_day: str  # comma-separated local times, e.g. "08:00,14:00,20:00"
    instructions: str = ""  # e.g. "with food", "finish the full course"
    max_daily_doses: int | None = None  # used by the double-dose rule


class DoseStatus(StrEnum):
    PENDING = "pending"
    TAKEN = "taken"
    LATE = "late"
    MISSED = "missed"
    EXTRA = "extra"  # patient reports taking more than prescribed
    UNKNOWN = "unknown"  # no reply


class DoseEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    medication_id: int = Field(foreign_key="medication.id", index=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    scheduled_for: datetime = Field(index=True)
    status: DoseStatus = DoseStatus.PENDING
    reported_at: datetime | None = None
    patient_note: str = ""  # side effects, reasons for missing, etc.


class Direction(StrEnum):
    INBOUND = "in"
    OUTBOUND = "out"


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    direction: Direction
    text: str
    wa_message_id: str = ""
    created_at: datetime = Field(default_factory=_now, index=True)


class AgentTrace(SQLModel, table=True):
    """Harness log: one row per LLM call, so every agent decision is auditable."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int | None = Field(default=None, foreign_key="patient.id", index=True)
    trigger: str  # "inbound_message" | "scheduled_checkin" | "prescription_photo"
    model: str
    prompt_json: str  # full message list sent to the model
    output_text: str = ""
    tool_calls_json: str = "[]"
    latency_ms: int = 0
    error: str = ""
    created_at: datetime = Field(default_factory=_now, index=True)


class FlagSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"


class Flag(SQLModel, table=True):
    """Something the doctor should look at."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    dose_event_id: int | None = Field(default=None, foreign_key="doseevent.id")
    kind: str  # "missed_doses" | "extra_dose" | "side_effect" | "stopped_early" | ...
    severity: FlagSeverity
    summary: str
    resolved: bool = False
    created_at: datetime = Field(default_factory=_now, index=True)
