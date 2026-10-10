import pytest

from hermod.harness.guardrails import SAFE_FALLBACK, check_outbound, detect_emergency


@pytest.mark.parametrize("text", [
    "I think I overdosed",
    "took the whole pack by accident",
    "i took too many tablets",
    "swallowed 12 pills",
    "my throat is swelling",
    "I can't breathe",
    "I want to kill myself",
    "having chest pains",
])
def test_emergency_detected(text):
    assert detect_emergency(text)


@pytest.mark.parametrize("text", [
    "yes took it",
    "forgot this morning sorry",
    "I have 10 pills left",
    "feeling a bit nauseous",
    "had food poisoning last week",
    "can I end my course early?",
])
def test_ordinary_messages_pass(text):
    assert not detect_emergency(text)


@pytest.mark.parametrize("text", [
    "No worries, just take an extra one now to catch up.",
    "You can double up tonight.",
    "It's fine to skip the next dose.",
])
def test_dosing_advice_replaced(text):
    assert check_outbound(text) == SAFE_FALLBACK


@pytest.mark.parametrize("text", [
    "Great, logged your 8am dose!",
    "Did you take another one after that?",
    "Your doctor will advise on that. I've noted it for them.",
])
def test_normal_replies_kept(text):
    assert check_outbound(text) == text
