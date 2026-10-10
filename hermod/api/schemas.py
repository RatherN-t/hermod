"""Request and response shapes for the dashboard API.

JSON is camelCase (to match the React app); Python stays snake_case. Requests accept either.
Datetimes are ISO 8601 with a UTC offset; dates are "YYYY-MM-DD"; times of day are "HH:MM"
in the clinic's timezone.
"""
import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_times(v: list[str]) -> list[str]:
    for t in v:
        if not _HHMM.match(t):
            raise ValueError(f"{t!r} is not HH:MM (24-hour)")
    return sorted(set(v))


class Schema(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True,
                              from_attributes=True)


# --- shared pieces -------------------------------------------------------------------------

class AdherenceSummary(Schema):
    taken: int
    late: int
    missed: int
    unknown: int
    extra: int
    pending: int
    adherence_pct: int | None = Field(description="(taken + late) / doses due; null if none due")


class FlagCounts(Schema):
    urgent: int = 0
    warning: int = 0
    info: int = 0
    total: int = 0


class NextDose(Schema):
    dose_id: int
    reminder_id: int
    medication: str
    scheduled_for: datetime


class TelegramLink(Schema):
    linked: bool = Field(description="True once the patient has opened the link in Telegram")
    link_code: str
    telegram_link: str | None = Field(description="t.me start link; null if no bot token")


# --- patients ------------------------------------------------------------------------------

class PatientCreate(Schema):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=3, max_length=20, description="Digits only; unique id")
    doctor_name: str = ""
    date_of_birth: date | None = None
    language: Literal["en", "es"] = "en"
    next_appointment_at: datetime | None = None
    notes: str = ""
    is_synthetic: bool = True

    @field_validator("phone")
    @classmethod
    def digits_only(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 3:
            raise ValueError("phone must contain digits")
        return digits


class PatientUpdate(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    doctor_name: str | None = None
    date_of_birth: date | None = None
    language: Literal["en", "es"] | None = None
    next_appointment_at: datetime | None = None
    notes: str | None = None


class PatientListItem(Schema):
    id: int
    name: str
    phone: str
    doctor_name: str
    language: str
    is_synthetic: bool
    telegram_linked: bool
    next_appointment_at: datetime | None
    last_message_at: datetime | None
    active_reminders: int
    adherence: AdherenceSummary
    open_flags: FlagCounts
    next_dose: NextDose | None
    created_at: datetime


# --- reminders (one medication on one prescription) ----------------------------------------

DurationKind = Literal["days", "date", "appointment"]
ReminderStatus = Literal["active", "paused", "scheduled", "ended"]


class ReminderCreate(Schema):
    name: str = Field(min_length=1, max_length=120, description='e.g. "Amoxicillin 500mg"')
    dose: str = Field(default="1 dose", max_length=80, description='e.g. "1 capsule"')
    instructions: str = Field(default="", max_length=300)
    times_of_day: list[str] = Field(min_length=1, max_length=8,
                                    description='Local times, e.g. ["08:00", "20:00"]')
    duration_kind: DurationKind = "days"
    duration_days: int | None = Field(default=7, ge=1, le=180)
    until_date: date | None = Field(default=None, description="Last day, for durationKind=date")
    start_date: date | None = Field(default=None, description="Defaults to now")
    max_daily_doses: int | None = Field(default=None, ge=1, le=24)
    custom_message: str | None = Field(
        default=None, max_length=1000,
        description="Check-in text. May use {name}, {medication}, {dose}, {time}.")
    alert_on_missed: bool = True

    @field_validator("times_of_day")
    @classmethod
    def valid_times(cls, v: list[str]) -> list[str]:
        return _check_times(v)


class ReminderUpdate(Schema):
    status: Literal["active", "paused"] | None = None
    dose: str | None = Field(default=None, max_length=80)
    instructions: str | None = Field(default=None, max_length=300)
    times_of_day: list[str] | None = Field(default=None, min_length=1, max_length=8)
    custom_message: str | None = Field(default=None, max_length=1000,
                                       description='Send "" to go back to the standard message')
    alert_on_missed: bool | None = None
    max_daily_doses: int | None = Field(default=None, ge=1, le=24)
    duration_kind: DurationKind | None = Field(
        default=None, description="Change the course length; counted from the course start")
    duration_days: int | None = Field(default=None, ge=1, le=180)
    until_date: date | None = Field(default=None, description="Last day, for durationKind=date")

    @field_validator("times_of_day")
    @classmethod
    def valid_times(cls, v: list[str] | None) -> list[str] | None:
        return v if v is None else _check_times(v)


class Reminder(Schema):
    id: int = Field(description="Medication id")
    prescription_id: int
    patient_id: int
    name: str
    dose: str
    instructions: str
    times_of_day: list[str]
    duration_kind: str
    duration_days: int | None
    start_date: datetime
    end_date: datetime | None
    status: ReminderStatus
    custom_message: str | None
    alert_on_missed: bool
    max_daily_doses: int | None
    doses_sent: int = Field(description="Doses due so far (scheduled time has passed)")
    doses_confirmed: int = Field(description="Of those, reported taken or late")
    total_doses: int | None = Field(description="Whole course; null if open-ended")
    next_dose_at: datetime | None


# --- doses, messages, traces, flags --------------------------------------------------------

class Dose(Schema):
    id: int
    reminder_id: int
    medication: str
    scheduled_for: datetime
    status: str
    checkin_sent_at: datetime | None
    reported_at: datetime | None
    note: str


class ChatMessage(Schema):
    id: int
    direction: Literal["in", "out"]
    text: str
    created_at: datetime
    in_reply_to_id: int | None = Field(description="For replies: the patient message answered")
    trace_ids: list[int] = Field(
        description="LLM calls behind this message (on the patient message being answered)")


class TraceSummary(Schema):
    id: int
    message_id: int | None
    trigger: str
    model: str
    output_text: str
    tool_calls: list[dict]
    latency_ms: int
    error: str
    created_at: datetime


class TraceDetail(TraceSummary):
    patient_id: int | None
    prompt: list[dict] = Field(description="Full message list sent to the model")


class FlagOut(Schema):
    id: int
    patient_id: int
    patient_name: str
    dose_id: int | None
    kind: str
    severity: str
    summary: str
    resolved: bool
    resolved_at: datetime | None
    created_at: datetime


class FlagUpdate(Schema):
    resolved: bool


# --- detail views --------------------------------------------------------------------------

class MedicationAdherence(Schema):
    reminder_id: int
    medication: str
    adherence: AdherenceSummary


class DailyAdherence(Schema):
    date: date
    taken: int = 0
    late: int = 0
    missed: int = 0
    unknown: int = 0
    extra: int = 0
    pending: int = 0


class AdherenceReport(Schema):
    overall: AdherenceSummary
    by_medication: list[MedicationAdherence]
    daily: list[DailyAdherence] = Field(description="One row per local day, oldest first")


class PatientDetail(PatientListItem):
    date_of_birth: date | None
    notes: str
    link: TelegramLink
    reminders: list[Reminder]


class Dashboard(Schema):
    patients: int
    linked_patients: int
    active_reminders: int
    average_adherence_pct: int | None
    open_flags: FlagCounts
    needs_attention: list[PatientListItem] = Field(
        description="Patients with open urgent/warning flags or adherence under 80%, worst first")
    recent_flags: list[FlagOut]
    recent_messages: list["RecentMessage"] = Field(description="Latest messages, newest first")


class RecentMessage(Schema):
    patient_id: int
    patient_name: str
    direction: Literal["in", "out"]
    text: str
    created_at: datetime
