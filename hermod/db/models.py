"""Data model. One prescription -> many medications -> many scheduled doses.

Every dose has a status the agent fills in from the patient's replies; that
status history *is* the adherence log the doctor reads.
"""
import secrets
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Patient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    phone: str = Field(index=True, unique=True)  # digits only, e.g. 61400000000
    telegram_chat_id: str | None = Field(default=None, index=True)
    # Secret in the patient's onboarding link (t.me/<bot>?start=<code>) that ties their chat
    # to this record. Telegram doesn't share phone numbers with bots.
    link_code: str = Field(default_factory=lambda: secrets.token_urlsafe(9), index=True)
    doctor_name: str = ""
    date_of_birth: date | None = None
    language: str = "en"  # stored for the dashboard; the agent itself only speaks English
    next_appointment_at: datetime | None = None
    notes: str = ""  # doctor-facing
    is_synthetic: bool = True  # demo data must be labelled
    # The clinic turned Hermod off for this patient: no check-ins and no agent replies (an
    # emergency still gets the fixed escalation message). Upcoming doses are cleared meanwhile.
    messages_stopped: bool = False
    last_inbound_at: datetime | None = None  # None until the patient's first message
    created_at: datetime = Field(default_factory=_now)


class Prescription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    start_date: datetime
    end_date: datetime | None = None
    doctor_notes: str = ""
    source: str = "form"  # "form" | "photo"
    # How the doctor chose the course length, so the form can be re-shown as entered.
    duration_kind: str = "days"  # "days" | "date" | "appointment"
    duration_days: int | None = None
    created_at: datetime = Field(default_factory=_now)


class Medication(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    prescription_id: int = Field(foreign_key="prescription.id", index=True)
    name: str  # e.g. "Amoxicillin 500mg"
    dose: str  # e.g. "1 capsule"
    times_of_day: str  # comma-separated local times, e.g. "08:00,14:00,20:00"
    instructions: str = ""  # e.g. "with food", "finish the full course"
    max_daily_doses: int | None = None  # used by the double-dose rule
    # Check-in text. None = the standard message. May use {name}, {medication}, {dose}, {time}.
    checkin_message: str | None = None
    paused: bool = False  # no check-ins while paused
    alert_on_missed: bool = True  # raise missed-dose flags for this medication


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
    checkin_sent_at: datetime | None = None
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
    external_id: str = ""
    # For agent replies: the inbound message being answered (its AgentTraces explain the reply).
    in_reply_to_id: int | None = Field(default=None, foreign_key="message.id")
    created_at: datetime = Field(default_factory=_now, index=True)


class AgentTrace(SQLModel, table=True):
    """Harness log: one row per LLM call, so every agent decision is auditable."""

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int | None = Field(default=None, foreign_key="patient.id", index=True)
    message_id: int | None = Field(default=None, foreign_key="message.id", index=True)
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
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now, index=True)
