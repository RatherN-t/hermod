"""A dose is only marked taken when the patient says they took it, and it lands on the dose
Hermod asked about."""
import json
from datetime import timedelta

import pytest
from sqlmodel import select

from hermod.agent.agent import build_system_prompt, handle_inbound
from hermod.agent.replies import classify_dose_reply
from hermod.channels.base import IncomingMessage
from hermod.db.models import DoseEvent, DoseStatus, Medication
from hermod.llm.client import LLMResult
from hermod.timeutil import utcnow

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


TAKEN = ["yes", "Yep took it", "done", "Taken", "👍", "took it late", "had it with breakfast",
         "I took it at 9", "y", "yess", "taken ✅", "okay done", "mhm", "sorted", "already done",
         "did it", "yes, no side effects", "yep had it at 8, thanks", "took my amoxicillin",
         "took another one by mistake", "I took it, is that ok?", "Yes. When is the next one?",
         "yes but I feel sick", "sí, ya la tomé"]
MISSED = ["I forgot", "missed it", "no I forgot", "I didn't take it this morning",
          "skipped it today", "ran out of pills", "not going to take it today", "se me olvidó"]
# Nothing may be logged for these (from both logic reviews).
NO_LOG = ["no", "not yet", "haven't taken it yet", "I'll take it after dinner", "remind me later",
          "ok", "ok thanks", "did I take it?", "have I taken my evening one?", "I feel sick", "",
          "yes, will take it after lunch", "yeah in a sec", "yeah nah", "yes no", "I did not",
          "taken? no", "took a nap, will take it after", "I'll take it now", "I took a shower",
          "I took ibuprofen instead", "I think I took it", "yes tonight", "yes in 5",
          "yes when I get home", "yes before bed", "yes tomorrow", "yes i should",
          "of course not", "I should have taken it", "I was meant to have taken it", "took it?",
          "had it? no", "no me la he tomado", "took it out of the box", "took it to work",
          "mum took it", "I didn't skip it", "not missed", "took it yesterday? no",
          "took the amoxicillin, not the paracetamol yet"]


@pytest.mark.parametrize("text", TAKEN)
def test_plain_reports_of_taking_it(text):
    assert classify_dose_reply(text, ("Amoxicillin 500mg",)) == "taken"


@pytest.mark.parametrize("text", MISSED)
def test_plain_reports_of_missing_it(text):
    assert classify_dose_reply(text, ("Amoxicillin 500mg",)) == "missed"


@pytest.mark.parametrize("text", NO_LOG)
def test_anything_else_logs_nothing(text):
    assert classify_dose_reply(text, ("Amoxicillin 500mg",)) in ("not_yet", "unclear")


def call(name, **args):
    return {"id": f"c-{name}", "name": name, "arguments": args}


def inbound(text, mid):
    return IncomingMessage(sender_id="61400000000", text=text, message_id=mid)


def tool_result(fake) -> dict:
    return json.loads(fake.calls[1][-1]["content"])


@pytest.mark.parametrize("text, status", [
    ("ok thanks", "taken"),     # polite, not a report
    ("not yet", "taken"),       # the model jumping the gun
    ("not yet", "missed"),      # "not yet" is not a missed dose
    ("did I take it?", "taken"),
    ("I forgot", "taken"),      # says missed, can't become taken
])
async def test_dose_not_logged_unless_patient_says_so(patient, session, llm, text, status):
    dose = session.exec(select(DoseEvent)).one()
    fake = llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id,
                                                    medication="Amoxicillin", status=status)]),
               LLMResult(text="No worries, let me know once you've taken it."))
    await handle_inbound(inbound(text, "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.PENDING
    assert tool_result(fake)["ok"] is False


async def test_missed_logged_when_patient_says_they_forgot(patient, session, llm):
    dose = session.exec(select(DoseEvent)).one()
    llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id,
                                            medication="Amoxicillin", status="missed")]),
        LLMResult(text="Thanks for telling me."))
    await handle_inbound(inbound("no I forgot", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.MISSED


def _two_open_doses(session, patient):
    """08:00-style dose Hermod asked about 3h ago, and the next one due in an hour."""
    med = session.exec(select(Medication)).one()
    for d in session.exec(select(DoseEvent)).all():
        session.delete(d)
    asked = DoseEvent(medication_id=med.id, patient_id=patient.id,
                      scheduled_for=utcnow() - timedelta(hours=3),
                      checkin_sent_at=utcnow() - timedelta(hours=3))
    upcoming = DoseEvent(medication_id=med.id, patient_id=patient.id,
                         scheduled_for=utcnow() + timedelta(hours=1))
    session.add_all([asked, upcoming])
    session.commit()
    return asked, upcoming


async def test_plain_yes_goes_to_the_dose_hermod_asked_about(patient, session, llm):
    asked, upcoming = _two_open_doses(session, patient)
    # Model leaves out dose_id: the code picks the dose, not the closest one in time.
    fake = llm(LLMResult(text="", tool_calls=[call("log_dose", medication="Amoxicillin",
                                                    status="taken")]),
               LLMResult(text="Thanks!"))
    await handle_inbound(inbound("yes", "m1"))
    session.refresh(asked)
    session.refresh(upcoming)
    assert asked.status == DoseStatus.LATE  # confirmed 3h after it was due
    assert upcoming.status == DoseStatus.PENDING
    assert f"- {asked.id}: Amoxicillin 500mg" in fake.calls[0][0]["content"]
    assert "DUE NOW" in next(line for line in fake.calls[0][0]["content"].splitlines()
                             if line.startswith(f"- {asked.id}:"))


async def test_on_time_yes_is_taken_not_late(patient, session, llm):
    dose = session.exec(select(DoseEvent)).one()  # due 10 minutes ago
    llm(LLMResult(text="", tool_calls=[call("log_dose", medication="Amoxicillin",
                                            status="late")]),  # model's guess is ignored
        LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took it", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.TAKEN


async def test_future_dose_cannot_be_logged(patient, session, llm):
    med = session.exec(select(Medication)).one()
    later = DoseEvent(medication_id=med.id, patient_id=patient.id,
                      scheduled_for=utcnow() + timedelta(hours=5))
    session.add(later)
    session.commit()
    fake = llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=later.id,
                                                    medication="Amoxicillin", status="taken")]),
               LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took it", "m1"))
    session.refresh(later)
    assert later.status == DoseStatus.PENDING
    assert "isn't due yet" in tool_result(fake)["error"]


def test_prompt_never_marks_a_later_dose_due_ahead_of_an_open_one(patient, session):
    asked, upcoming = _two_open_doses(session, patient)
    prompt = build_system_prompt(session, patient)
    line = {d.id: next(x for x in prompt.splitlines() if x.startswith(f"- {d.id}:"))
            for d in (asked, upcoming)}
    assert "DUE NOW" in line[asked.id] and "DUE NOW" not in line[upcoming.id]


def _checkin(session, patient, *doses):
    """Hermod sent one check-in covering `doses` a moment ago."""
    from hermod.db.models import Direction, Message
    now = utcnow()
    for d in doses:
        d.checkin_sent_at = now
        session.add(d)
    session.add(Message(patient_id=patient.id, direction=Direction.OUTBOUND,
                        text="Hi Sam, it's your dose. Have you taken it?", created_at=now))
    session.commit()


async def test_bare_yes_to_another_question_is_not_a_dose(patient, session, llm):
    from hermod.db.models import Direction, Message
    dose = session.exec(select(DoseEvent)).one()
    _checkin(session, patient, dose)
    session.add(Message(patient_id=patient.id, direction=Direction.OUTBOUND,
                        text="Any side effects so far?", created_at=utcnow()))
    session.commit()
    fake = llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id,
                                                    medication="Amoxicillin", status="taken")]),
               LLMResult(text="Sorry to hear that."))
    await handle_inbound(inbound("yes", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.PENDING
    assert "answers your last question" in tool_result(fake)["error"]


async def test_one_yes_logs_one_dose_not_a_backlog(patient, session, llm):
    med = session.exec(select(Medication)).one()
    old = [DoseEvent(medication_id=med.id, patient_id=patient.id,
                     scheduled_for=utcnow() - timedelta(hours=h), status=DoseStatus.UNKNOWN,
                     checkin_sent_at=utcnow() - timedelta(hours=h)) for h in (18, 24, 30)]
    session.add_all(old)
    session.commit()
    current = session.exec(select(DoseEvent).where(DoseEvent.status == "pending")).one()
    _checkin(session, patient, current)
    calls = [call("log_dose", dose_id=d.id, medication="Amoxicillin", status="taken",
                  when=d.scheduled_for.isoformat()) for d in [current, *old]]
    for i, c in enumerate(calls):
        c["id"] = f"c{i}"
    llm(LLMResult(text="", tool_calls=calls), LLMResult(text="Thanks!"))
    await handle_inbound(inbound("yes", "m1"))
    session.expire_all()
    statuses = [session.get(DoseEvent, d.id).status for d in [current, *old]]
    assert statuses == [DoseStatus.TAKEN, DoseStatus.UNKNOWN, DoseStatus.UNKNOWN,
                        DoseStatus.UNKNOWN]


async def test_last_nights_unanswered_dose_doesnt_take_todays_yes(patient, session, llm):
    med = session.exec(select(Medication)).one()
    today = session.exec(select(DoseEvent)).one()  # due 10 minutes ago
    last_night = DoseEvent(medication_id=med.id, patient_id=patient.id,
                           scheduled_for=utcnow() - timedelta(hours=12),
                           status=DoseStatus.UNKNOWN,
                           checkin_sent_at=utcnow() - timedelta(hours=12))
    session.add(last_night)
    session.commit()
    llm(LLMResult(text="", tool_calls=[call("log_dose", medication="Amoxicillin",
                                            status="taken")]),
        LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took it", "m1"))
    session.refresh(today)
    session.refresh(last_night)
    assert today.status == DoseStatus.TAKEN and last_night.status == DoseStatus.UNKNOWN


def test_one_checkin_for_two_medications_marks_both_due(patient, session):
    from hermod.db.models import Medication as Med
    first = session.exec(select(DoseEvent)).one()
    para = Med(prescription_id=session.exec(select(Medication)).one().prescription_id,
               name="Paracetamol 500mg", dose="1 tablet", times_of_day="08:00")
    session.add(para)
    session.commit()
    second = DoseEvent(medication_id=para.id, patient_id=patient.id,
                       scheduled_for=first.scheduled_for)
    session.add(second)
    session.commit()
    _checkin(session, patient, first, second)
    prompt = build_system_prompt(session, patient)
    for d in (first, second):
        assert "DUE NOW" in next(x for x in prompt.splitlines() if x.startswith(f"- {d.id}:"))


async def test_patient_time_only_used_when_they_said_one(patient, session, llm):
    dose = session.exec(select(DoseEvent)).one()  # due 10 minutes ago
    dose.scheduled_for = utcnow() - timedelta(hours=5)
    session.add(dose)
    session.commit()
    _checkin(session, patient, dose)
    # The model back-dates to make it look on time; the patient never said a time.
    llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id, medication="Amoxicillin",
                                            status="taken", when="2020-01-01T08:00")]),
        LLMResult(text="Thanks!"))
    await handle_inbound(inbound("yes", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.LATE


async def test_dose_older_than_a_day_cant_be_changed_from_chat(patient, session, llm):
    med = session.exec(select(Medication)).one()
    old = DoseEvent(medication_id=med.id, patient_id=patient.id,
                    scheduled_for=utcnow() - timedelta(days=3), status=DoseStatus.UNKNOWN)
    session.add(old)
    session.commit()
    fake = llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=old.id,
                                                    medication="Amoxicillin", status="taken")]),
               LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took it", "m1"))
    session.refresh(old)
    assert old.status == DoseStatus.UNKNOWN and "more than a day old" in tool_result(fake)["error"]


def test_medication_matching_is_whole_word():
    from hermod.agent.tools import _match_medication
    d, b12, iron = (Medication(name=n, dose="", times_of_day="08:00")
                    for n in ("Vitamin D 1000 IU", "Vitamin B12 500 mcg", "Iron 65 mg"))
    assert _match_medication([d, b12, iron], "vitamin b12") is b12
    assert _match_medication([d, b12, iron], "good for the environment") is None
    assert _match_medication([d, iron], "vitamin b12") is None  # B12 isn't prescribed
    assert _match_medication([d, iron], "vitamin c") is None
    assert _match_medication([d, iron], "d") is None
    assert _match_medication([d, iron], "500mg") is None
    assert _match_medication([d, iron], "the whole pack of iron tablets") is iron


@pytest.mark.parametrize("text, overdose", [
    ("yes took all of them", False), ("took all my meds this morning", False),
    ("took the rest of my antibiotics today", False), ("I took the whole course as told", False),
    ("took all my tablets this morning", False), ("took all 3 tablets as prescribed", False),
    ("Took all the capsules prescribed for today", False), ("took them at once with water", False),
    ("I took all my pills", True), ("took the rest of the pack", True),
    ("took them all at once", True), ("I took the whole pack", True), ("took 20 tablets", True),
])
def test_everyday_took_all_is_not_an_overdose(text, overdose):
    from hermod.harness.guardrails import detect_overdose
    assert detect_overdose(text) is overdose


async def test_unasked_doses_dont_become_missed(patient, session):
    from hermod.scheduler.jobs import tick
    med = session.exec(select(Medication)).one()
    never_asked = DoseEvent(medication_id=med.id, patient_id=patient.id,
                            scheduled_for=utcnow() - timedelta(hours=8))
    asked = DoseEvent(medication_id=med.id, patient_id=patient.id,
                      scheduled_for=utcnow() - timedelta(hours=9),
                      checkin_sent_at=utcnow() - timedelta(hours=9))
    session.add_all([never_asked, asked])
    session.commit()
    await tick()
    session.refresh(never_asked)
    session.refresh(asked)
    assert never_asked.status == DoseStatus.PENDING and asked.status == DoseStatus.UNKNOWN


def test_reminder_counts_match_the_adherence_card(patient, session):
    from hermod.api.views import patient_meds, reminder, summary
    med = session.exec(select(Medication)).one()
    for status in (DoseStatus.TAKEN, DoseStatus.TAKEN):
        session.add(DoseEvent(medication_id=med.id, patient_id=patient.id, status=status,
                              scheduled_for=utcnow() - timedelta(hours=20)))
    session.commit()  # plus the fixture's pending dose due 10 minutes ago
    m, rx = patient_meds(session, patient.id)[0]
    r = reminder(session, m, rx)
    a = summary(session, patient.id)
    due = a.taken + a.late + a.missed + a.unknown
    assert (r.doses_confirmed, r.doses_sent) == (a.taken + a.late, due) == (2, 2)



async def test_done_after_hermods_let_me_know_reply_is_logged(patient, session, llm):
    from hermod.db.models import Direction, Message
    dose = session.exec(select(DoseEvent)).one()
    _checkin(session, patient, dose)
    session.add_all([
        Message(patient_id=patient.id, direction=Direction.INBOUND, text="not yet"),
        Message(patient_id=patient.id, direction=Direction.OUTBOUND,
                text="No worries, let me know once you've taken it."),
    ])
    session.commit()
    llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id, medication="Amoxicillin",
                                            status="taken")]),
        LLMResult(text="Great, thanks!"))
    await handle_inbound(inbound("done", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.TAKEN


async def test_extra_doses_follow_the_same_checks(patient, session, llm):
    from hermod.db.models import Direction, Message
    session.add(Message(patient_id=patient.id, direction=Direction.OUTBOUND,
                        text="Any side effects so far?"))
    session.commit()
    extra = [call("log_dose", medication="Amoxicillin", status="extra") for _ in range(3)]
    for i, c in enumerate(extra):
        c["id"] = f"c{i}"
    llm(LLMResult(text="", tool_calls=extra), LLMResult(text="Ok."))
    await handle_inbound(inbound("yes", "m1"))
    assert session.exec(select(DoseEvent).where(DoseEvent.status == "extra")).all() == []
    llm(LLMResult(text="", tool_calls=extra), LLMResult(text="Ok."))
    await handle_inbound(inbound("took another one by mistake", "m2"))
    assert len(session.exec(select(DoseEvent).where(DoseEvent.status == "extra")).all()) == 1


async def test_yesterday_never_lands_on_todays_dose(patient, session, llm):
    dose = session.exec(select(DoseEvent)).one()  # today's, due 10 minutes ago
    _checkin(session, patient, dose)
    llm(LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id, medication="Amoxicillin",
                                            status="taken")]),
        LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took it yesterday", "m1"))
    session.refresh(dose)
    assert dose.status == DoseStatus.PENDING


async def test_only_the_named_medication_is_logged(patient, session, llm):
    first = session.exec(select(DoseEvent)).one()
    para = Medication(prescription_id=session.exec(select(Medication)).one().prescription_id,
                      name="Paracetamol 500mg", dose="1 tablet", times_of_day="08:00")
    session.add(para)
    session.commit()
    second = DoseEvent(medication_id=para.id, patient_id=patient.id,
                       scheduled_for=first.scheduled_for)
    session.add(second)
    session.commit()
    _checkin(session, patient, first, second)
    calls = [call("log_dose", dose_id=first.id, medication="Amoxicillin", status="taken"),
             call("log_dose", dose_id=second.id, medication="Paracetamol", status="taken")]
    calls[1]["id"] = "c2"
    llm(LLMResult(text="", tool_calls=calls), LLMResult(text="Thanks!"))
    await handle_inbound(inbound("took my amoxicillin", "m1"))
    session.refresh(first)
    session.refresh(second)
    assert first.status == DoseStatus.TAKEN and second.status == DoseStatus.PENDING


def _at_local_hour(hours_ago: int):
    """A UTC datetime on the hour, `hours_ago` hours back, plus its "2 pm"-style label."""
    from hermod.timeutil import to_local, to_utc
    local = to_local(utcnow() - timedelta(hours=hours_ago)).replace(minute=0, second=0,
                                                                     microsecond=0)
    label = f"{local.hour % 12 or 12} {'pm' if local.hour >= 12 else 'am'}"
    return to_utc(local), label


@pytest.mark.parametrize("swap", [False, True])
async def test_one_message_reporting_one_taken_and_one_missed(patient, session, llm, swap):
    """Regression: "I've taken just the 2 pm one missed 8 am" logged nothing."""
    med = session.exec(select(Medication)).one()
    for d in session.exec(select(DoseEvent)).all():
        session.delete(d)
    early_at, early = _at_local_hour(6)
    late_at, late = _at_local_hour(1)
    missed = DoseEvent(medication_id=med.id, patient_id=patient.id, scheduled_for=early_at,
                       status=DoseStatus.UNKNOWN, checkin_sent_at=early_at)
    taken = DoseEvent(medication_id=med.id, patient_id=patient.id, scheduled_for=late_at,
                      checkin_sent_at=late_at)
    session.add_all([missed, taken])
    session.commit()
    ids = (taken.id, missed.id) if not swap else (missed.id, taken.id)
    calls = [call("log_dose", dose_id=ids[1], medication="Amoxicillin", status="missed"),
             call("log_dose", dose_id=ids[0], medication="Amoxicillin", status="taken")]
    calls[1]["id"] = "c2"
    llm(LLMResult(text="", tool_calls=calls), LLMResult(text="Thanks for letting me know."))
    await handle_inbound(inbound(f"I’ve taken just the {late} one missed {early}", "m1"))
    session.refresh(missed)
    session.refresh(taken)
    if swap:  # the model mixed the doses up: each report only fits the dose at its time
        assert (missed.status, taken.status) == (DoseStatus.UNKNOWN, DoseStatus.PENDING)
    else:
        assert (missed.status, taken.status) == (DoseStatus.MISSED, DoseStatus.TAKEN)
