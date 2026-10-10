"""Scripted conversations against the agent with the LLM mocked."""

import pytest
from sqlmodel import select

from hermod.agent.agent import handle_inbound, run_checkin
from hermod.channels.base import IncomingMessage
from hermod.db.models import AgentTrace, DoseEvent, DoseStatus, Flag, Message
from hermod.harness.guardrails import ESCALATION_MESSAGE, SAFE_FALLBACK
from hermod.llm.client import LLMResult

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def inbound(text, mid="wamid.1", phone="61400000000"):
    return IncomingMessage(sender_id=phone, text=text, message_id=mid)


def call(name, **args):
    return {"id": f"call_{name}", "name": name, "arguments": args}


async def test_logs_taken_dose_via_tool(patient, session, channel, llm):
    dose = session.exec(select(DoseEvent)).one()
    fake = llm(
        LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id,
                                            medication="Amoxicillin", status="taken")]),
        LLMResult(text="Lovely, logged it. Thanks Sam!"),
    )
    await handle_inbound(inbound("yep took it"))

    session.refresh(dose)
    assert dose.status == DoseStatus.TAKEN
    assert channel.sent[-1]["text"] == "Lovely, logged it. Thanks Sam!"
    # System prompt lists the dose by id so the model can reference it.
    assert f"- {dose.id}: Amoxicillin 500mg" in fake.calls[0][0]["content"]
    # Second call saw the tool result.
    assert fake.calls[1][-1]["role"] == "tool"
    assert len(session.exec(select(AgentTrace)).all()) == 2
    msgs = session.exec(select(Message)).all()
    assert [m.direction for m in msgs] == ["in", "out"]


async def test_first_message_gets_onboarding_prompt(patient, llm):
    fake = llm(LLMResult(text="Hi Sam! I'm Hermod..."))
    await handle_inbound(inbound("Hi"))
    assert "first message" in fake.calls[0][0]["content"]


async def test_emergency_bypasses_llm(patient, session, channel, llm):
    fake = llm()
    await handle_inbound(inbound("I took the whole bottle"))
    assert fake.calls == []
    assert channel.sent[-1]["text"] == ESCALATION_MESSAGE
    flag = session.exec(select(Flag).where(Flag.kind == "emergency")).one()
    assert flag.severity == "urgent"


async def test_dosing_advice_is_scrubbed(patient, channel, llm):
    llm(LLMResult(text="Just double up tonight and you'll be fine."))
    await handle_inbound(inbound("I missed lunch dose, what do I do?"))
    assert channel.sent[-1]["text"] == SAFE_FALLBACK


async def test_unknown_number_gets_fixed_reply(llm, channel, session):
    fake = llm()
    await handle_inbound(inbound("hello", phone="61499999999"))
    assert fake.calls == []
    assert "clinic" in channel.sent[-1]["text"]
    assert session.exec(select(Message)).all() == []


async def test_duplicate_delivery_is_ignored(patient, channel, llm):
    fake = llm(LLMResult(text="Got it"))
    await handle_inbound(inbound("yes", mid="wamid.dup"))
    await handle_inbound(inbound("yes", mid="wamid.dup"))
    assert len(fake.calls) == 1


async def test_llm_failure_sends_apology_and_traces_error(patient, session, channel,
                                                          monkeypatch):
    async def boom(messages, tools=None):
        raise RuntimeError("quota")

    monkeypatch.setattr("hermod.llm.client.complete", boom)
    await handle_inbound(inbound("yes"))
    assert "trouble replying" in channel.sent[-1]["text"]
    assert "quota" in session.exec(select(AgentTrace)).one().error


async def test_extra_dose_creates_event_and_flag(patient, session, llm):
    llm(
        LLMResult(text="", tool_calls=[call("log_dose", medication="Amoxicillin",
                                            status="extra", note="took two by mistake")]),
        LLMResult(text="Thanks for telling me, I've let Dr Lee know."),
    )
    await handle_inbound(inbound("oops I took two this morning"))
    assert session.exec(select(DoseEvent).where(DoseEvent.status == "extra")).one()
    assert session.exec(select(Flag).where(Flag.kind == "extra_dose")).one()


async def test_checkin_sends_text_and_marks_dose(patient, session, channel):
    dose = session.exec(select(DoseEvent)).one()

    await run_checkin(patient.id, [dose.id])

    assert "Amoxicillin 500mg" in channel.sent[-1]["text"]
    session.refresh(dose)
    assert dose.checkin_sent_at is not None


async def test_extra_dose_never_overwrites_a_taken_dose(patient, session, llm):
    dose = session.exec(select(DoseEvent)).one()
    dose.status = DoseStatus.TAKEN
    session.add(dose)
    session.commit()
    llm(
        LLMResult(text="", tool_calls=[call("log_dose", dose_id=dose.id, medication="Amoxicillin",
                                            status="extra")]),
        LLMResult(text="Noted."),
    )
    await handle_inbound(inbound("took another one by mistake"))
    session.refresh(dose)
    assert dose.status == DoseStatus.TAKEN
    assert session.exec(select(DoseEvent).where(DoseEvent.status == "extra")).one()


def test_log_dose_refuses_to_overwrite_reported_dose(patient, session):
    from hermod.agent.tools import execute_tool

    dose = session.exec(select(DoseEvent)).one()
    dose.status = DoseStatus.TAKEN
    session.add(dose)
    session.commit()
    out = execute_tool("log_dose", {"dose_id": dose.id, "medication": "Amoxicillin",
                                    "status": "missed"}, patient.id, session)
    assert out["ok"] is False and "already logged" in out["error"]
    session.refresh(dose)
    assert dose.status == DoseStatus.TAKEN


async def test_escalation_is_marked_handled_in_next_turn(patient, llm):
    llm()
    await handle_inbound(inbound("I took the whole pack", mid="e1"))
    fake = llm(LLMResult(text="You logged..."))
    await handle_inbound(inbound("did I take my meds today?", mid="e2"))
    history = fake.calls[0]
    escalation = [m for m in history if m["role"] == "assistant"][-1]["content"]
    assert escalation.startswith("[Automatic safety reply.") and ESCALATION_MESSAGE in escalation
