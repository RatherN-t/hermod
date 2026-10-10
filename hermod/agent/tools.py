"""Tools the LLM can call. Each maps to a DB write, so the log is structured, not prose."""
from datetime import datetime, timedelta

from sqlmodel import Session, select

from hermod.db.models import DoseEvent, DoseStatus, Flag, FlagSeverity, Medication, Prescription
from hermod.timeutil import fmt_local, to_utc, utcnow

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "log_dose",
            "description": (
                "Record what the patient said about a dose. Pass dose_id from the dose list "
                "when you know which dose they mean. Use status 'extra' when they took a dose "
                "that wasn't scheduled or took more than prescribed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dose_id": {"type": "integer", "description": "Id from the dose list."},
                    "medication": {"type": "string"},
                    "status": {"type": "string", "enum": ["taken", "late", "missed", "extra"]},
                    "when": {
                        "type": "string",
                        "description": "Local time the dose was taken, ISO 8601 if known.",
                    },
                    "note": {"type": "string"},
                },
                "required": ["medication", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_issue",
            "description": "Raise something the doctor should review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["missed_doses", "extra_dose", "side_effect", "stopped_early",
                                 "question_for_doctor"],
                    },
                    "severity": {"type": "string", "enum": ["info", "warning", "urgent"]},
                    "summary": {
                        "type": "string",
                        "description": "What the patient said, without added causes or "
                                       "interpretation.",
                    },
                    "dose_id": {"type": "integer"},
                },
                "required": ["kind", "severity", "summary"],
            },
        },
    },
]

# How far ahead of its scheduled time a dose can be reported as taken.
EARLY_WINDOW = timedelta(hours=2)


def active_medications(session: Session, patient_id: int) -> list[Medication]:
    now = utcnow()
    rows = session.exec(
        select(Medication)
        .join(Prescription)
        .where(Prescription.patient_id == patient_id, Prescription.start_date <= now)
    ).all()
    return [
        m
        for m in rows
        if (p := session.get(Prescription, m.prescription_id)).end_date is None
        or p.end_date >= now - timedelta(days=1)
    ]


def _match_medication(meds: list[Medication], name: str) -> Medication | None:
    if len(meds) == 1:
        return meds[0]
    needle = (name or "").lower().strip()
    for m in meds:
        hay = m.name.lower()
        if needle and (needle in hay or hay.split()[0] in needle):
            return m
    return None


def _parse_when(when: str | None) -> datetime | None:
    if not when:
        return None
    try:
        return to_utc(datetime.fromisoformat(when))
    except ValueError:
        return None


def _log_dose(session: Session, patient_id: int, args: dict) -> dict:
    status = DoseStatus(args["status"])
    at = _parse_when(args.get("when")) or utcnow()
    note = args.get("note", "")

    event = None
    if args.get("dose_id"):
        event = session.get(DoseEvent, int(args["dose_id"]))
        if event and event.patient_id != patient_id:
            event = None

    med = session.get(Medication, event.medication_id) if event else None
    if med is None:
        med = _match_medication(active_medications(session, patient_id), args.get("medication"))
    if med is None:
        return {"ok": False, "error": f"No active medication matches {args.get('medication')!r}"}

    if status == DoseStatus.EXTRA and event is None:
        event = DoseEvent(medication_id=med.id, patient_id=patient_id, scheduled_for=at)
        session.add(event)
    elif event is None:
        # Closest open dose that is already due (or nearly).
        candidates = session.exec(
            select(DoseEvent).where(
                DoseEvent.patient_id == patient_id,
                DoseEvent.medication_id == med.id,
                DoseEvent.status.in_([DoseStatus.PENDING, DoseStatus.UNKNOWN]),
                DoseEvent.scheduled_for <= utcnow() + EARLY_WINDOW,
            )
        ).all()
        if not candidates:
            return {"ok": False, "error": f"No open dose of {med.name} to log against"}
        event = min(candidates, key=lambda e: abs(e.scheduled_for - at))

    event.status = status
    event.reported_at = utcnow()
    if note:
        event.patient_note = f"{event.patient_note}\n{note}".strip()
    session.add(event)
    session.commit()
    session.refresh(event)
    return {
        "ok": True,
        "dose_id": event.id,
        "medication": med.name,
        "scheduled_for": fmt_local(event.scheduled_for),
        "status": str(event.status),
    }


def _flag_issue(session: Session, patient_id: int, args: dict) -> dict:
    dose_id = args.get("dose_id")
    if dose_id and (ev := session.get(DoseEvent, int(dose_id))) and ev.patient_id != patient_id:
        dose_id = None
    flag = Flag(
        patient_id=patient_id,
        dose_event_id=int(dose_id) if dose_id else None,
        kind=args["kind"],
        severity=FlagSeverity(args["severity"]),
        summary=args["summary"],
    )
    session.add(flag)
    session.commit()
    session.refresh(flag)
    return {"ok": True, "flag_id": flag.id}


def execute_tool(name: str, args: dict, patient_id: int, session: Session) -> dict:
    try:
        if name == "log_dose":
            return _log_dose(session, patient_id, args)
        if name == "flag_issue":
            return _flag_issue(session, patient_id, args)
    except (KeyError, ValueError) as e:
        session.rollback()
        return {"ok": False, "error": f"Bad arguments: {e}"}
    return {"ok": False, "error": f"Unknown tool {name}"}
