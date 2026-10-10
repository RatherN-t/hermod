import pytest
from sqlmodel import select

from hermod.agent.agent import handle_inbound, run_checkin
from hermod.channels.base import IncomingMessage
from hermod.channels.telegram import TelegramChannel
from hermod.config import Settings, get_settings
from hermod.db.models import DoseEvent, Patient
from hermod.llm.client import LLMResult

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def telegram(monkeypatch, channel):
    """Route the agent as if CHANNEL=telegram, but capture sends in the console channel."""
    monkeypatch.setattr(get_settings(), "channel", "telegram")
    monkeypatch.setattr("hermod.agent.agent.get_channel", lambda: channel)
    return channel


def update(text, chat_id=555, msg_id=1, chat_type="private"):
    return {"update_id": 9, "message": {
        "message_id": msg_id, "chat": {"id": chat_id, "type": chat_type},
        "from": {"id": chat_id, "first_name": "Sam"}, "text": text}}


def tg(text, chat_id="555", msg_id=1):
    [m] = TelegramChannel(Settings(telegram_bot_token="x")).parse_update(
        update(text, int(chat_id), msg_id))
    return m


def test_parse_private_message():
    m = tg("yes took it")
    assert (m.sender_id, m.text, m.message_id) == ("555", "yes took it", "tg-555-1")


def test_group_chats_and_edits_ignored():
    ch = TelegramChannel(Settings(telegram_bot_token="x"))
    assert ch.parse_update(update("hi", chat_type="group")) == []
    assert ch.parse_update({"update_id": 1, "edited_message": {}}) == []


async def test_start_link_connects_chat_and_onboards(patient, session, telegram, llm):
    code = session.get(Patient, patient.id).link_code
    fake = llm(LLMResult(text="Hi Sam! I'm Hermod..."))

    await handle_inbound(tg(f"/start {code}"))

    session.expire_all()
    assert session.get(Patient, patient.id).telegram_chat_id == "555"
    assert telegram.sent[-1] == {"id": telegram.sent[-1]["id"], "to": "555",
                                 "text": "Hi Sam! I'm Hermod..."}
    assert "first message" in fake.calls[0][0]["content"]
    assert fake.calls[0][-1] == {"role": "user", "content": "Hi"}

    # Later messages from the same chat find the patient without the code.
    llm(LLMResult(text="Logged!"))
    await handle_inbound(tg("took it", msg_id=2))
    assert telegram.sent[-1]["text"] == "Logged!"


async def test_wrong_code_is_not_linked(patient, session, telegram, llm):
    fake = llm()
    await handle_inbound(tg("/start not-a-real-code"))
    assert fake.calls == []
    assert "clinic" in telegram.sent[-1]["text"]
    assert session.get(Patient, patient.id).telegram_chat_id is None


async def test_checkin_is_plain_text_on_telegram(patient, session, telegram):
    p = session.get(Patient, patient.id)
    p.telegram_chat_id = "555"
    session.add(p)
    session.commit()
    dose = session.exec(select(DoseEvent)).one()

    await run_checkin(patient.id, [dose.id])

    assert telegram.sent[-1]["to"] == "555"
    assert "Amoxicillin" in telegram.sent[-1]["text"]


async def test_checkin_skipped_until_linked(patient, session, telegram):
    dose = session.exec(select(DoseEvent)).one()
    await run_checkin(patient.id, [dose.id])
    assert telegram.sent == []


async def test_poll_errors_dont_leak_token(monkeypatch, caplog):
    ch = TelegramChannel(Settings(telegram_bot_token="SECRET-TOKEN"))
    calls = 0

    async def fake_call(method, http_timeout=15, **params):
        nonlocal calls
        calls += 1
        if method == "getUpdates":
            import httpx
            raise httpx.ConnectError(f"failed {ch.base_url}/getUpdates")
        return {}

    async def stop(_):
        raise RuntimeError("stop")

    monkeypatch.setattr(ch, "_call", fake_call)
    monkeypatch.setattr("hermod.channels.telegram.asyncio.sleep", stop)
    with pytest.raises(RuntimeError, match="stop"):
        await ch.poll_forever(lambda m: None)
    assert "SECRET-TOKEN" not in caplog.text
    assert "ConnectError" in caplog.text


async def test_poller_hands_messages_to_handler(monkeypatch):
    ch = TelegramChannel(Settings(telegram_bot_token="x"))
    batches = [[update("hello", msg_id=7)]]
    handled: list[IncomingMessage] = []

    async def fake_call(method, http_timeout=15, **params):
        if method == "getUpdates":
            if batches:
                return batches.pop()
            raise RuntimeError("done")
        return {}

    async def handle(m):
        handled.append(m)

    async def stop(_):
        raise SystemExit

    monkeypatch.setattr(ch, "_call", fake_call)
    monkeypatch.setattr("hermod.channels.telegram.asyncio.sleep", stop)
    with pytest.raises(SystemExit):
        await ch.poll_forever(handle)
    assert [m.text for m in handled] == ["hello"]


async def test_bare_code_links_when_start_payload_was_dropped(patient, session, telegram, llm):
    code = session.get(Patient, patient.id).link_code
    llm()
    await handle_inbound(tg("/start"))  # chat already started: Telegram sent no payload
    assert "send me the code" in telegram.sent[-1]["text"]

    fake = llm(LLMResult(text="Welcome Sam!"))
    await handle_inbound(tg(code, msg_id=2))
    session.expire_all()
    assert session.get(Patient, patient.id).telegram_chat_id == "555"
    assert fake.calls[0][-1] == {"role": "user", "content": "Hi"}
    assert telegram.sent[-1]["text"] == "Welcome Sam!"
