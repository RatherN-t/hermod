"""Deterministic adherence rules, independent of the LLM.

The LLM records what the patient said; these rules decide what's a problem.
"""


def evaluate_patient(patient_id: int) -> list[dict]:
    """Return new flags, e.g. >=2 consecutive missed doses, doses beyond max_daily_doses,
    unanswered check-ins for 24h, course stopped before end_date."""
    raise NotImplementedError


def adherence_summary(patient_id: int) -> dict:
    """Taken / late / missed / extra counts and % adherence for the doctor dashboard."""
    raise NotImplementedError
