"""Deterministic safety checks that run *before* and *after* the LLM.

The agent never gives dosing advice. Overdose / emergency language bypasses the
LLM and gets a fixed escalation message plus an URGENT flag.
"""
import re

ESCALATION_MESSAGE = (
    "Thanks for telling me. I can't give medical advice, so I've flagged this for your "
    "doctor right away. If you feel unwell or took much more than prescribed, call 000 "
    "or the Poisons Information Centre on 13 11 26 now."
)

SAFE_FALLBACK = (
    "I can't advise on doses, sorry. Please check with your doctor or pharmacist. "
    "I've noted your question so your doctor sees it."
)

# Err on the side of escalating: a false positive costs one canned message and a flag.
# Reports of taking more than prescribed. These also get an "extra" dose logged.
_OVERDOSE = [
    r"\boverdos",
    # "took all the pills", "took the rest of the pack", "took them all at once"; but not
    # everyday replies like "yes took all of them", "took the rest of my antibiotics today"
    # (finishing a course) or "took all 3 tablets as prescribed" / "...this morning" (today's
    # doses), which have a small count or a normal-schedule phrase.
    (r"\btook (?:all|the rest) (?:of )?(?:the |my |of my |them )?(?!\d\b|two |three |four )"
     r"(?:\w+ )?(?:pills|tablets|capsules|pack|packet|box|bottle|strip)\b"
     r"(?!\s+(?:prescribed|as (?:prescribed|directed|told)|for (?:today|the day|this morning|tonight)|"
     r"this morning|today|tonight|with (?:breakfast|lunch|dinner|food|water)))"),
    r"\btook (?:them |it )?all at once\b|\btook all (?:of )?them at once\b",
    r"\btook (?:the whole (?:pack|packet|box|bottle|strip|lot)|a handful|a (?:whole|full) (?:pack|packet|box|bottle|strip))",
    r"\b(?:took|taken|swallowed) (?:way |far )?too (?:many|much)\b",
    (r"\b(?:took|taken|swallowed) (?:\d{2,}|ten|twenty|lots of|a lot of|loads of|several|"
     r"a bunch of) (?:pills|tablets|capsules)\b"),
    r"\bhandful of (?:pills|tablets|capsules)\b",
    r"\b(?:whole|entire) (?:bottle|pack|box|strip)\b",
]
_EMERGENCY = _OVERDOSE + [
    r"(?<!food )\bpoison",
    r"\bsuicid",
    r"\bkill (?:my ?self|me)\b",
    r"\bend (?:my life|it all)\b",
    r"\b(?:want|wanna) to die\b",
    r"\bself[- ]?harm",
    r"\bcan'?t breathe\b",
    r"\b(?:trouble|difficulty|struggling) breathing\b",
    r"\bchest pain",
    r"\b(?:throat|tongue|lips?|face) (?:is |are )?(?:swelling|swollen|closing)",
    r"\banaphyla",
    r"\bseizure",
    r"\bpassed out\b|\bfainted\b|\bunconscious\b|\bcollapsed\b",
]
_EMERGENCY_RE = re.compile("|".join(_EMERGENCY), re.IGNORECASE)
_OVERDOSE_RE = re.compile("|".join(_OVERDOSE), re.IGNORECASE)

# Agent replies that tell the patient to change what they take. Questions like
# "did you take another one?" must still pass, so match instructions, not mentions.
_DOSING_ADVICE = [
    r"\btake (?:an? )?(?:another|extra|double|more)\b",
    r"\bdouble (?:up|the dose|your dose)\b",
    r"\bmake up for (?:it|the missed)\b",
    (r"\b(?:skip|stop taking|halve|increase|reduce|lower|raise) (?:the |your |next )?(?:dose|"
     r"medication|tablet|pill|capsule)"),
    r"\byou (?:should|can|could) (?:safely )?(?:skip|stop|double|increase|reduce)\b",
    r"\b(?:it'?s|it is) (?:fine|ok|okay|safe) to (?:take|skip|double|stop)\b",
]
_DOSING_RE = re.compile("|".join(_DOSING_ADVICE), re.IGNORECASE)


def detect_emergency(text: str) -> bool:
    return bool(_EMERGENCY_RE.search(text or ""))


def detect_overdose(text: str) -> bool:
    return bool(_OVERDOSE_RE.search(text or ""))


def check_outbound(text: str) -> str:
    """Scrub/replace agent replies that drift into dosing advice."""
    if not text or not text.strip():
        return "Thanks, got it."
    # Only statements count: "did you take another one?" is a fair question.
    statements = [x for x in re.split(r"(?<=[.!?])\s+", text) if not x.rstrip().endswith("?")]
    if any(_DOSING_RE.search(x) for x in statements):
        return SAFE_FALLBACK
    return text.strip()
