"""What a patient's reply says about a dose, decided by rules, not the LLM.

A dose is only marked taken when the patient's message is a plain report that they took it
("yes", "took it", "yep, had it at 8, thanks"), and only marked missed when it plainly says
they missed it ("forgot", "skipped it today"). This is an allowlist: anything with more in it
("yes tonight", "of course not", "took it out of the box", "I should have taken it") is
"unclear" and changes nothing, so Hermod asks again rather than guess. A wrongly refused
"yes" costs one extra question; a wrongly logged one is a false record the doctor trusts.

A bare "yes" only means "I took it" as an answer to a dose question; the caller checks that
(see `is_bare_yes`). English, plus a little Spanish for the clinic's Spanish speakers.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Intent = Literal["taken", "missed", "not_yet", "unclear"]

_YES = (r"(ye+s+|yep+|yup+|yeah|yea|ya|yh|ys|y|ye|yas|sure|sure did|of course|absolutely|"
        r"definitely|for sure|mhm+|uh huh|sorted|s[ií]|claro|listo)")
# Words that may name the dose: "it", "my tablet", "the morning one", "both", the med name.
_DOSE = (r"(it|them|them all|both|all of them|one|mine|that one|this one|today'?s|another( one)?|"
         r"(an )?extra( one)?|two|2|a second one|"
         r"((my|the|this|today'?s|this morning'?s|tonight'?s) )?((morning|lunch|lunchtime|"
         r"evening|night|afternoon|bedtime|first|second|last|\d{1,2}(:\d{2})? ?(am|pm)?) )?"
         r"(dose|doses|tablet|tablets|pill|pills|capsule|capsules|meds?|medication|"
         r"medications|medicine|medicines|antibiotics?|one|ones)|((my|the) )?({med})( \w+)?)")
_TOOK = (r"((i|i've|i have|ive|just|already|i just|i already|i've just|i've already|"
         r"i did|ok|okay|all) )*(took|taken|had|swallowed|done|did|did take|finished)")
# When, said plainly: "at 8", "this morning", "with breakfast", "just now", "on time".
_WHEN = (r"(at \d{1,2}(:\d{2})? ?(am|pm)?|around \d{1,2}(:\d{2})? ?(am|pm)?|\d{1,2}(:\d{2})? ?"
         r"(am|pm)|this (morning|afternoon|evening)|tonight|earlier|just now|now|already|"
         r"on time|late|a (bit|while|few minutes) ago|\d+ (min|mins|minutes|hours?) ago|"
         r"an hour ago|with (breakfast|lunch|dinner|food|water|my (breakfast|lunch|dinner))|"
         r"after (breakfast|lunch|dinner|food|eating)|before (breakfast|bed|food))")
# After a bare "yes", only times that are clearly in the past ("yes tonight" may be a plan).
_PAST = (r"(earlier|just now|already|this morning|a (bit|while|few minutes) ago|"
         r"\d+ (min|mins|minutes|hours?) ago|an hour ago|with (breakfast|lunch|dinner|food))")
# Harmless extras: thanks, how they feel, sign-offs.
_FILLER = (r"(thanks|thank you|thank u|thx|ty|cheers|ta|all good|no problems?|no worries|"
           r"no side effects|no issues|feeling (fine|good|ok|okay|well|great)|all fine|"
           r"(i )?(feel|am|'m|i'm) (fine|good|ok|okay|well|great)|"
           r"fine|good|great|done|all done|sorted|as usual|as prescribed|as told|"
           r"don'?t worry|haha|lol|:\)|x+|by mistake|by accident|accidentally|"
           r"(but )?(i )?(feel|feeling|felt) (a bit |a little |kinda |quite |very )?(sick|"
           r"nauseous|queasy|dizzy|tired|unwell|off|funny|rough))")
_SEP = r"[\s,.!-]*"


def _taken_re(med: str) -> re.Pattern:
    dose = _DOSE.replace("{med}", med or r"(?!x)x")
    spanish = r"(ya )?(la|lo|las|los) (he )?tom[eé]|ya me la tom[eé]|tomad[oa]s?"
    report = (rf"({_YES}{_SEP})?({_TOOK}( ((just|only) )?{dose})?( {_WHEN})*|{spanish})"
              rf"|{_YES}({_SEP}{_PAST})?")                               # "yes", "yep earlier"
    lead = rf"((oops|oh|um|uh|hmm|well|actually|so|hi|hey|morning){_SEP})*"
    return re.compile(rf"^{lead}({report})(({_SEP}| and ){_FILLER})*{_SEP}$")


_MISSED_RE = re.compile(
    rf"^((no|nope|nah|sorry|oops|ah)({_SEP}))*"
    r"((i )?(forgot|forgot to take it|forgot it|forgot my (dose|tablet|pill|meds?)|"
    r"missed it|missed (my |the |this morning'?s |today'?s )?(dose|tablet|pill|one)|"
    r"missed (my |the )?(\d{1,2}(:\d{2})? ?(am|pm)|morning|lunch|lunchtime|afternoon|evening|"
    r"night|bedtime)( one| dose| tablet| pill)?|"
    r"skipped it|skipped (my |the )?(dose|tablet|pill)|didn'?t take it|did not take it|"
    r"ran out( of (my )?(pills|tablets|capsules|meds?|medication|medicine))?|run out|not taking it|won'?t take it|will not take it|"
    r"not going to take it|i'?m not going to take it)( (today|tonight|this morning|"
    r"this time|again))?|se me olvid[oó]|no la tom[eé]|no lo tom[eé])"
    rf"(({_SEP}| and ){_FILLER})*{_SEP}$")
# Not taken yet, or a plan: only used to pick the right advice for the model.
_NOT_YET = re.compile(
    r"\b(no|nope|nah|not yet|haven'?t|have not|later|soon|will|i'?ll|gonna|going to|"
    r"about to|tonight|tomorrow|tmrw|when|once|before|in a|in \d+|need to|have to|should|"
    r"todav[ií]a no|a[uú]n no|luego|despu[eé]s|voy a)\b")


def _normalise(text: str) -> str:
    t = (text or "").lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"\b(didnt|havent|hasnt|wont|cant|couldnt|wasnt|dont)\b",
               lambda m: m.group(1)[:-1] + "'t", t)
    t = re.sub(r"(👍|✅|✔️|☑️|🙂|😊|👌)+", " done ", t)
    return " ".join(t.split())


def _med_word(medication_names: tuple[str, ...]) -> str:
    words = {w for n in medication_names for w in n.lower().split()[:1] if len(w) >= 3}
    return "|".join(re.escape(w) for w in sorted(words))


# A separate question after the report ("Yes. When is the next one?", "took it, is that ok?").
_TRAILING_QUESTION = re.compile(
    r"^(?P<report>[^?]+?)(\. |\! |, )(?P<question>(is|can|should|do|does|did|when|what|how|"
    r"will|was|which|why|could|any|so)\b[^?]*\?)\s*$")
_ABOUT_DOSING = re.compile(r"\b(no|not|nah|nope|never|later|yet|tonight|tomorrow|will|i'?ll|"
                           r"forgot|missed|skip)\b")


def classify_dose_reply(text: str, medication_names: tuple[str, ...] = ()) -> Intent:
    """Classify the patient's message about their dose."""
    t = _normalise(text)
    if not t:
        return "unclear"
    med = _med_word(medication_names)
    report = t
    if "?" in t:
        m = _TRAILING_QUESTION.match(t)
        # The question must be a real follow-up, not "taken? no" or "yes, will I...?"
        if not m or _ABOUT_DOSING.search(m.group("question")):
            return "not_yet" if _NOT_YET.search(t) else "unclear"
        report = m.group("report")
    if _taken_re(med).match(report):
        return "taken"
    if _MISSED_RE.match(report):
        return "missed"
    if _NOT_YET.search(t):
        return "not_yet"
    return "unclear"


def is_bare_yes(text: str, medication_names: tuple[str, ...] = ()) -> bool:
    """A "taken" that rests only on yes/👍/ok, with no "took it": only meaningful as an
    answer to "have you taken it?"."""
    t = _normalise(text)
    return (classify_dose_reply(text, medication_names) == "taken"
            and not re.search(r"\b(took|taken|had|swallowed|tom[eé]|tomad[oa])\b", t))


_EARLIER_DAY = re.compile(r"\b(yesterday|last night|days? ago|the other day|ayer|anoche)\b")
_STATES_TIME = re.compile(r"\d|\b(morning|afternoon|evening|night|noon|midday|lunch|breakfast|"
                          r"dinner|bed|bedtime|ago|earlier|yesterday)\b")


def mentions_earlier_day(text: str) -> bool:
    """"I took it yesterday": about an older dose, not the current one."""
    return bool(_EARLIER_DAY.search(_normalise(text)))


def states_a_time(text: str) -> bool:
    """Whether the patient said when they took it (otherwise ignore the model's guess)."""
    return bool(_STATES_TIME.search(_normalise(text)))


def names_medications(text: str, medication_names: tuple[str, ...]) -> set[str]:
    """Which of `medication_names` the message mentions by name (first word, whole word)."""
    t = _normalise(text)
    return {n for n in medication_names
            if n.split() and re.search(rf"\b{re.escape(n.lower().split()[0])}\b", t)}


# --- several reports in one message ("taken just the 2 pm one, missed 8 am") -----------------

Slot = tuple[str, int | str] | None  # ("hour", 14) or ("part", "morning"), or no time given


@dataclass(frozen=True)
class Report:
    intent: Intent  # "taken" or "missed"
    slot: Slot      # which dose time the patient named, if any


_SLOT_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))? ?(am|pm)\b|\b(morning|lunch|lunchtime|midday|"
                      r"noon|afternoon|evening|night|bedtime)\b")
_PARTS = {"morning": range(4, 12), "lunch": range(11, 15), "lunchtime": range(11, 15),
          "midday": range(11, 15), "noon": range(11, 15), "afternoon": range(12, 18),
          "evening": range(17, 22), "night": [19, 20, 21, 22, 23, 0, 1, 2],
          "bedtime": [19, 20, 21, 22, 23, 0, 1, 2]}
_SPLIT = re.compile(r"\s*[,;]\s*|\.\s+|\s+(?:and|but|then|though|however|also)\s+")
_REPORT_VERBS = {"missed", "forgot", "skipped", "took", "taken", "had", "didn't"}
_LEADS_INTO_VERB = {"i", "i've", "ive", "have", "has", "just", "already", "only", "also", "not"}


def _split_reports(t: str) -> list[str]:
    """Split on punctuation and "and/but", and where a new report starts mid-sentence
    ("...the 2 pm one missed 8 am")."""
    clauses = []
    for part in _SPLIT.split(t):
        words, current = part.split(), []
        for w in words:
            if w in _REPORT_VERBS and current and current[-1] not in _LEADS_INTO_VERB:
                clauses.append(" ".join(current))
                current = []
            current.append(w)
        if current:
            clauses.append(" ".join(current))
    return [c.strip(" .!-") for c in clauses if c.strip(" .!-")]


_FILLER_ONLY = re.compile(rf"^({_FILLER}{_SEP})+$|^$")


def _slot(clause: str) -> Slot:
    m = _SLOT_RE.search(clause)
    if not m:
        return None
    if m.group(4):
        return ("part", m.group(4))
    hour = int(m.group(1)) % 12 + (12 if m.group(3) == "pm" else 0)
    return ("hour", hour)


def slot_matches(slot: Slot, local: datetime) -> bool:
    """Whether a dose at local time `local` is the one the patient named."""
    if slot is None:
        return True
    kind, value = slot
    if kind == "hour":
        return abs(local.hour - value) <= 1 or abs(local.hour - value) >= 23
    return local.hour in _PARTS[value]


def dose_reports(text: str, medication_names: tuple[str, ...] = ()) -> list[Report]:
    """The taken/missed reports in a message. Usually one; "taken the 2 pm one, missed 8 am"
    is two. Every part must itself be a plain report (or "thanks"-style filler), otherwise
    there are none and nothing can be logged."""
    t = _normalise(text)
    whole = classify_dose_reply(text, medication_names)
    if whole in ("taken", "missed"):
        return [Report(whole, _slot(t))]
    clauses = _split_reports(t)
    if len(clauses) < 2 or "?" in t:
        return []
    reports = []
    for clause in clauses:
        intent = classify_dose_reply(clause, medication_names)
        if intent in ("taken", "missed"):
            reports.append(Report(intent, _slot(clause)))
        elif not _FILLER_ONLY.match(clause):
            return []
    # With several reports, each must say which dose it is about.
    if len(reports) > 1 and any(r.slot is None for r in reports):
        return []
    return reports
