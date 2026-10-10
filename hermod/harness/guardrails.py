"""Deterministic safety checks that run *before* and *after* the LLM.

The agent never gives dosing advice. Overdose / emergency language bypasses the
LLM and gets a fixed escalation message plus an URGENT flag.
"""

ESCALATION_MESSAGE = (
    "Thanks for telling me. I can't give medical advice, so I've flagged this for your "
    "doctor right away. If you feel unwell or took much more than prescribed, call 000 "
    "or the Poisons Information Centre on 13 11 26 now."
)


def detect_emergency(text: str) -> bool:
    raise NotImplementedError


def check_outbound(text: str) -> str:
    """Scrub/replace agent replies that drift into dosing advice."""
    raise NotImplementedError
