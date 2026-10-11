"""Dashboard API: every route, against a fresh SQLite DB, with the LLM mocked."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from hermod.adherence.rules import evaluate_patient
from hermod.agent.agent import handle_inbound, run_checkin
from hermod.channels.base import IncomingMessage
from hermod.config import get_settings
from hermod.db.models import (
    AgentTrace,
    DoseEvent,
    DoseStatus,
    Flag,
    FlagSeverity,
    Medication,
    Message,
    Prescription,
)
from hermod.harness.guardrails import ESCALATION_MESSAGE
from hermod.llm.client import LLMResult
from hermod.main import app
from hermod.timeutil import local_tz, utcnow


@pytest.fixture
def api():
    return TestClient(app)  # no `with`: skips lifespan (scheduler), tables come from conftest


def make_patient(api, **kw):
    body = {"name": "Sam Taylor", "phone": "+61 400 000 001", "doctorName": "Dr Lee", **kw}
    r = api.post("/api/patients", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def make_reminder(api, pid, **kw):
    body = {"name": "Amoxicillin 500mg", "dose": "1 capsule",
            "timesOfDay": ["20:00", "08:00"], "durationKind": "days", "durationDays": 7, **kw}
    r = api.post(f"/api/patients/{pid}/reminders", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# --- patients ------------------------------------------------------------------------------

def test_create_patient_returns_camelcase_detail(api):
    p = make_patient(api, dateOfBirth="1968-04-18", language="es")
    assert p["phone"] == "61400000001"  # normalised to digits
    assert p["doctorName"] == "Dr Lee" and p["dateOfBirth"] == "1968-04-18"
    assert p["link"]["linked"] is False and len(p["link"]["linkCode"]) > 8
    assert p["link"]["telegramLink"] is None  # no bot token in tests
    assert p["reminders"] == [] and p["openFlags"]["total"] == 0
    assert p["adherence"]["adherencePct"] is None


def test_duplicate_phone_conflicts(api):
    make_patient(api)
    assert api.post("/api/patients", json={"name": "X", "phone": "61400000001"}).status_code == 409


def test_list_search_get_update_patient(api):
    p = make_patient(api)
    make_patient(api, name="Alex Kim", phone="61400000002")
    assert [x["name"] for x in api.get("/api/patients").json()] == ["Alex Kim", "Sam Taylor"]
    assert [x["name"] for x in api.get("/api/patients?q=sam").json()] == ["Sam Taylor"]
    r = api.patch(f"/api/patients/{p['id']}", json={"notes": "Penicillin ok", "doctorName": "Dr B"})
    assert r.json()["notes"] == "Penicillin ok" and r.json()["doctorName"] == "Dr B"
    assert api.get(f"/api/patients/{p['id']}").json()["notes"] == "Penicillin ok"
    assert api.get("/api/patients/999").status_code == 404


def test_link_reset_unlinks(api, session):
    from hermod.db.models import Patient

    p = make_patient(api)
    row = session.get(Patient, p["id"])
    row.telegram_chat_id = "555"
    session.add(row)
    session.commit()
    assert api.get(f"/api/patients/{p['id']}/link").json()["linked"] is True
    new = api.post(f"/api/patients/{p['id']}/link/reset").json()
    assert new["linked"] is False and new["linkCode"] != p["link"]["linkCode"]


# --- reminders -----------------------------------------------------------------------------

def test_create_reminder_schedules_whole_course(api, session):
    p = make_patient(api)
    r = make_reminder(api, p["id"], customMessage="Hi {name}, {medication} time!")
    assert r["timesOfDay"] == ["08:00", "20:00"] and r["status"] == "active"
    assert r["customMessage"] == "Hi {name}, {medication} time!"
    assert r["maxDailyDoses"] == 2
    scheduled = session.exec(select(DoseEvent).where(DoseEvent.medication_id == r["id"])).all()
    # 7 days x 2, minus any of today's slots that already passed.
    assert len(scheduled) == r["totalDoses"] and 12 <= len(scheduled) <= 14
    detail = api.get(f"/api/patients/{p['id']}").json()
    assert detail["activeReminders"] == 1 and detail["reminders"][0]["id"] == r["id"]
    assert detail["nextDose"]["reminderId"] == r["id"]


def test_reminder_duration_kinds_and_validation(api):
    p = make_patient(api)
    until = (datetime.now(local_tz()).date() + timedelta(days=3)).isoformat()
    r = make_reminder(api, p["id"], durationKind="date", untilDate=until)
    assert r["endDate"].startswith(until) or r["endDate"] > until  # end of that local day
    bad = [
        {"timesOfDay": ["8am"]},
        {"timesOfDay": []},
        {"durationKind": "date"},
        {"durationKind": "appointment"},  # patient has no appointment
        {"startDate": "2020-01-01"},
        {"durationDays": 0},
    ]
    for extra in bad:
        body = {"name": "X", "timesOfDay": ["08:00"], **extra}
        assert api.post(f"/api/patients/{p['id']}/reminders", json=body).status_code == 422, extra
    appt = (utcnow() + timedelta(days=10)).isoformat()
    api.patch(f"/api/patients/{p['id']}", json={"nextAppointmentAt": appt})
    r = make_reminder(api, p["id"], durationKind="appointment")
    assert r["durationKind"] == "appointment" and r["endDate"][:16] == appt[:16]


def test_pause_resume_retime_and_end(api, session):
    p = make_patient(api)
    r = make_reminder(api, p["id"])

    def future():
        return session.exec(select(DoseEvent).where(DoseEvent.medication_id == r["id"],
                                                    DoseEvent.scheduled_for > utcnow())).all()

    n = len(future())
    assert n > 0
    paused = api.patch(f"/api/reminders/{r['id']}", json={"status": "paused"}).json()
    assert paused["status"] == "paused" and future() == []
    resumed = api.patch(f"/api/reminders/{r['id']}", json={"status": "active"}).json()
    assert resumed["status"] == "active" and len(future()) == n

    retimed = api.patch(f"/api/reminders/{r['id']}", json={"timesOfDay": ["09:00"]}).json()
    assert retimed["timesOfDay"] == ["09:00"]
    assert {e.scheduled_for.astimezone(local_tz()).strftime("%H:%M") for e in future()} == {"09:00"}

    cleared = api.patch(f"/api/reminders/{r['id']}", json={"customMessage": ""}).json()
    assert cleared["customMessage"] is None

    ended = api.post(f"/api/reminders/{r['id']}/end").json()
    assert ended["status"] == "ended" and future() == []
    assert api.get(f"/api/patients/{p['id']}").json()["activeReminders"] == 0
    assert api.get("/api/reminders/999").status_code == 404


def test_patch_changes_course_length_keeping_past_doses(api, session):
    p = make_patient(api)
    r = make_reminder(api, p["id"], durationDays=7)
    past = DoseEvent(medication_id=r["id"], patient_id=p["id"], status=DoseStatus.TAKEN,
                     scheduled_for=utcnow() - timedelta(hours=1))
    session.add(past)
    session.commit()

    def doses():
        session.expire_all()
        return session.exec(select(DoseEvent).where(DoseEvent.medication_id == r["id"])).all()

    def last_day(rem):
        return datetime.fromisoformat(rem["endDate"]).astimezone(local_tz()).date()

    start_day = datetime.fromisoformat(r["startDate"]).astimezone(local_tz()).date()
    longer = api.patch(f"/api/reminders/{r['id']}", json={"durationDays": 10}).json()
    assert longer["durationDays"] == 10 and last_day(longer) == start_day + timedelta(days=9)
    assert longer["totalDoses"] > r["totalDoses"]
    future = [e for e in doses() if e.scheduled_for > utcnow()]
    assert max(e.scheduled_for for e in future).astimezone(local_tz()).date() == last_day(longer)

    until = start_day + timedelta(days=2)
    by_date = api.patch(f"/api/reminders/{r['id']}",
                        json={"durationKind": "date", "untilDate": until.isoformat()}).json()
    assert by_date["durationKind"] == "date" and by_date["durationDays"] is None
    assert last_day(by_date) == until
    assert all(e.scheduled_for.astimezone(local_tz()).date() <= until for e in doses()
               if e.scheduled_for > utcnow())
    assert any(e.id == past.id and e.status == DoseStatus.TAKEN for e in doses())

    appt = (utcnow() + timedelta(days=4)).isoformat()
    assert api.patch(f"/api/reminders/{r['id']}",
                     json={"durationKind": "appointment"}).status_code == 422
    api.patch(f"/api/patients/{p['id']}", json={"nextAppointmentAt": appt})
    by_appt = api.patch(f"/api/reminders/{r['id']}", json={"durationKind": "appointment"}).json()
    assert by_appt["durationKind"] == "appointment" and by_appt["endDate"][:16] == appt[:16]

    # Paused reminders keep no upcoming doses after a length change.
    api.patch(f"/api/reminders/{r['id']}", json={"status": "paused"})
    api.patch(f"/api/reminders/{r['id']}", json={"durationKind": "days", "durationDays": 5})
    assert [e for e in doses() if e.scheduled_for > utcnow()] == []
    for bad in ({"durationKind": "date"}, {"durationDays": 0},
                {"durationKind": "date", "untilDate": "2020-01-01"}):
        assert api.patch(f"/api/reminders/{r['id']}", json=bad).status_code == 422, bad


def test_checkin_now_uses_custom_message(api, channel):
    p = make_patient(api, name="Sam Taylor")
    r = make_reminder(api, p["id"], customMessage="Hey {name}, time for {medication} ({dose})")
    out = api.post(f"/api/reminders/{r['id']}/checkin").json()
    assert out["sent"] is True
    assert channel.sent[-1]["text"] == "Hey Sam, time for Amoxicillin 500mg (1 capsule)"
    api.patch(f"/api/reminders/{r['id']}", json={"status": "paused"})
    assert api.post(f"/api/reminders/{r['id']}/checkin").status_code == 409


# --- timeline, conversation, traces --------------------------------------------------------

def test_doses_filters(api, session):
    p = make_patient(api)
    r = make_reminder(api, p["id"])
    first = session.exec(select(DoseEvent).where(DoseEvent.medication_id == r["id"])).first()
    first.status = DoseStatus.TAKEN
    session.add(first)
    session.commit()
    doses = api.get(f"/api/patients/{p['id']}/doses").json()
    assert doses == sorted(doses, key=lambda d: d["scheduledFor"])
    assert doses[0]["medication"] == "Amoxicillin 500mg"
    taken = api.get(f"/api/patients/{p['id']}/doses?status=taken").json()
    assert [d["id"] for d in taken] == [first.id]
    assert api.get(f"/api/patients/{p['id']}/doses?status=nope").status_code == 422


def test_adherence_report(api, patient, session):
    med = session.exec(select(Medication)).one()
    for hours, st in [(30, DoseStatus.TAKEN), (26, DoseStatus.MISSED), (5, DoseStatus.TAKEN)]:
        session.add(DoseEvent(medication_id=med.id, patient_id=patient.id,
                              scheduled_for=utcnow() - timedelta(hours=hours), status=st))
    session.commit()
    rep = api.get(f"/api/patients/{patient.id}/adherence?days=7").json()
    assert rep["overall"]["taken"] == 2 and rep["overall"]["missed"] == 1
    assert rep["byMedication"][0]["medication"] == "Amoxicillin 500mg"
    assert sum(d["taken"] for d in rep["daily"]) == 2
    assert rep["daily"] == sorted(rep["daily"], key=lambda d: d["date"])


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_messages_link_to_traces(api, patient, llm, anyio_backend):
    llm(LLMResult(text="", tool_calls=[{"id": "c1", "name": "log_dose",
                                         "arguments": {"medication": "Amoxicillin",
                                                       "status": "taken"}}]),
        LLMResult(text="Logged, thanks!"))
    await handle_inbound(IncomingMessage(sender_id=patient.phone, text="took it",
                                         message_id="m1"))
    msgs = api.get(f"/api/patients/{patient.id}/messages").json()
    assert [m["direction"] for m in msgs] == ["in", "out"]
    reply = msgs[1]
    assert reply["inReplyToId"] == msgs[0]["id"] and len(reply["traceIds"]) == 2
    traces = api.get(f"/api/patients/{patient.id}/traces").json()
    assert {t["id"] for t in traces} == set(reply["traceIds"])
    assert any(t["toolCalls"] and t["toolCalls"][0]["name"] == "log_dose" for t in traces)
    detail = api.get(f"/api/traces/{reply['traceIds'][0]}").json()
    assert detail["prompt"][0]["role"] == "system" and detail["messageId"] == msgs[0]["id"]
    assert api.get("/api/traces/999").status_code == 404


async def test_stop_messages_blocks_checkins_and_replies(api, patient, llm, session, channel,
                                                         anyio_backend):
    due = session.exec(select(DoseEvent).where(DoseEvent.patient_id == patient.id)).first()
    r = make_reminder(api, patient.id, name="Ibuprofen 200mg")
    future = select(DoseEvent).where(DoseEvent.patient_id == patient.id,
                                     DoseEvent.scheduled_for > utcnow())
    assert session.exec(future).all()

    p = api.patch(f"/api/patients/{patient.id}", json={"messagesStopped": True}).json()
    assert p["messagesStopped"] is True
    assert api.get("/api/patients").json()[0]["messagesStopped"] is True
    session.expire_all()
    assert session.exec(future).all() == []  # upcoming doses cleared, so none count as missed

    await run_checkin(patient.id, [due.id])  # a check-in the scheduler had already queued
    assert api.post(f"/api/reminders/{r['id']}/checkin").status_code == 409
    await handle_inbound(IncomingMessage(sender_id=patient.phone, text="took it",
                                         message_id="s1"))  # llm has nothing queued: not called
    assert channel.sent == []
    assert [m["text"] for m in api.get(f"/api/patients/{patient.id}/messages").json()] == \
        ["took it"]  # still logged for the doctor
    make_reminder(api, patient.id, name="Cetirizine 10mg")  # new reminders stay quiet too
    session.expire_all()
    assert session.exec(future).all() == []

    # Safety: an emergency still gets the fixed escalation, even with messages stopped.
    await handle_inbound(IncomingMessage(sender_id=patient.phone, text="I took the whole pack",
                                         message_id="s2"))
    assert channel.sent[-1]["text"] == ESCALATION_MESSAGE

    api.patch(f"/api/patients/{patient.id}", json={"messagesStopped": False})
    session.expire_all()
    assert session.exec(future).all()  # courses rescheduled


async def test_delete_patient_removes_everything(api, patient, llm, session, channel,
                                                 anyio_backend):
    llm(LLMResult(text="", tool_calls=[{"id": "c1", "name": "log_dose",
                                         "arguments": {"medication": "Amoxicillin",
                                                       "status": "taken"}}]),
        LLMResult(text="Logged, thanks!"))
    await handle_inbound(IncomingMessage(sender_id=patient.phone, text="took it",
                                         message_id="m1"))
    make_reminder(api, patient.id, name="Ibuprofen 200mg")
    session.add(Flag(patient_id=patient.id, kind="side_effect", severity=FlagSeverity.INFO,
                     summary="I feel nauseous"))
    session.commit()
    other = make_patient(api, name="Alex Kim", phone="61400000002")
    make_reminder(api, other["id"])
    pid = patient.id
    assert api.get(f"/api/patients/{pid}/messages").json()
    dose_ids = session.exec(select(DoseEvent.id).where(DoseEvent.patient_id == pid)).all()

    assert api.delete(f"/api/patients/{pid}").status_code == 204
    # A check-in the scheduler queued just before the delete goes nowhere.
    channel.sent.clear()
    await run_checkin(pid, list(dose_ids))
    assert channel.sent == []
    assert api.get(f"/api/patients/{pid}").status_code == 404
    assert api.delete(f"/api/patients/{pid}").status_code == 404
    session.expire_all()
    for model in (DoseEvent, Flag, Message, AgentTrace, Prescription):
        assert session.exec(select(model).where(model.patient_id == pid)).all() == []
    assert session.exec(select(Medication).where(Medication.name == "Ibuprofen 200mg")).all() == []
    # The other patient is untouched.
    assert [p["name"] for p in api.get("/api/patients").json()] == ["Alex Kim"]
    assert len(api.get(f"/api/patients/{other['id']}/reminders").json()) == 1


# --- flags and dashboard -------------------------------------------------------------------

def test_flags_and_dashboard(api, patient, session):
    session.add(Flag(patient_id=patient.id, kind="emergency", severity=FlagSeverity.URGENT,
                     summary='Patient wrote: "took the whole pack"'))
    session.add(Flag(patient_id=patient.id, kind="side_effect", severity=FlagSeverity.INFO,
                     summary="I feel nauseous"))
    session.commit()

    flags = api.get("/api/flags").json()
    assert {f["kind"] for f in flags} == {"emergency", "side_effect"}
    assert flags[0]["patientName"] == "Sam Taylor"
    urgent = api.get("/api/flags?severity=urgent").json()
    assert [f["kind"] for f in urgent] == ["emergency"]

    board = api.get("/api/dashboard").json()
    assert board["patients"] == 1 and board["openFlags"] == {
        "urgent": 1, "warning": 0, "info": 1, "total": 2}
    assert board["needsAttention"][0]["id"] == patient.id
    assert board["recentMessages"] == []

    done = api.patch(f"/api/flags/{urgent[0]['id']}", json={"resolved": True}).json()
    assert done["resolved"] is True and done["resolvedAt"]
    assert [f["kind"] for f in api.get("/api/flags").json()] == ["side_effect"]
    assert len(api.get("/api/flags?status=all").json()) == 2
    assert len(api.get(f"/api/patients/{patient.id}/flags?status=resolved").json()) == 1
    assert api.get("/api/dashboard").json()["needsAttention"] == []
    assert api.patch("/api/flags/999", json={"resolved": True}).status_code == 404


def test_alert_on_missed_off_suppresses_missed_flag(patient, session):
    med = session.exec(select(Medication)).one()
    med.alert_on_missed = False
    session.add(med)
    for hours in (8, 4):
        session.add(DoseEvent(medication_id=med.id, patient_id=patient.id,
                              scheduled_for=utcnow() - timedelta(hours=hours),
                              status=DoseStatus.MISSED))
    session.commit()
    assert [f.kind for f in evaluate_patient(patient.id, session)] == []


# --- access --------------------------------------------------------------------------------

def test_api_key_required_when_set(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "s3cret")
    assert api.get("/api/patients").status_code == 401
    assert api.get("/api/patients", headers={"X-API-Key": "nope"}).status_code == 401
    assert api.get("/api/patients", headers={"X-API-Key": "s3cret"}).status_code == 200
    assert api.get("/health").status_code == 200  # not behind the key


def test_cors_allows_vite_dev_server(api):
    r = api.options("/api/patients", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_openapi_lists_routes(api):
    paths = api.get("/openapi.json").json()["paths"]
    for p in ["/api/dashboard", "/api/patients", "/api/patients/{patient_id}/reminders",
              "/api/reminders/{reminder_id}", "/api/flags", "/api/traces/{trace_id}"]:
        assert p in paths


def test_custom_message_placeholders_cannot_reach_attributes(api, channel):
    p = make_patient(api, name="Sam Taylor")
    r = make_reminder(api, p["id"],
                      customMessage="{name.__class__} {name} {unknown} {{x}} {medication}")
    api.post(f"/api/reminders/{r['id']}/checkin")
    assert channel.sent[-1]["text"] == "{name.__class__} Sam {unknown} {{x}} Amoxicillin 500mg"


def test_demo_clinic_seed(api):
    if not get_settings().database_url.startswith("sqlite"):
        pytest.skip("seed-clinic is SQLite-only")
    from hermod.demo_clinic import clinic, remove_clinic, seed_clinic

    keep = make_patient(api, name="Real Test", phone="61400000009")
    seed_clinic()
    patients = {p["name"]: p for p in api.get("/api/patients").json()}
    assert len(patients) == len(clinic()) + 1
    assert all(p["isSynthetic"] for p in patients.values())
    assert all(p.phone.startswith("614915") for p in clinic())  # ACMA fiction numbers
    eleanor = patients["Eleanor Mitchell"]["adherence"]
    assert (eleanor["taken"], eleanor["missed"], eleanor["pending"]) == (18, 3, 0)
    assert patients["Grace Chen"]["activeReminders"] == 0
    assert patients["Daniel Brooks"]["adherence"]["adherencePct"] == 100
    with pytest.raises(SystemExit):
        seed_clinic()  # already seeded, no --reset
    remove_clinic()  # only the demo patients go
    assert [p["id"] for p in api.get("/api/patients").json()] == [keep["id"]]


def test_demo_clinic_refuses_shared_db_without_flag(monkeypatch):
    from hermod.demo_clinic import _check_target

    _check_target("sqlite:///x.db", shared=False, reset=True)
    with pytest.raises(SystemExit):
        _check_target("postgresql://h/db", shared=False, reset=False)
    with pytest.raises(SystemExit):
        _check_target("postgresql://h/db", shared=True, reset=True)  # never drop shared tables
    _check_target("postgresql://h/db", shared=True, reset=False)
