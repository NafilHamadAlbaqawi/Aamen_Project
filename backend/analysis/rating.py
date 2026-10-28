
"""Provisional, deterministic WP3 rating; WP4/WP6 must agree on preference adjustments."""
from .schemas import FlaggedClause


def calculate_rating(clauses: list[FlaggedClause]) -> tuple[int, str]:
    """Higher score means more concern; this is NOT an official legal metric."""
    high = sum(c.severity == "high" for c in clauses)
    medium = sum(c.severity == "medium" for c in clauses)
    low = sum(c.severity == "low" for c in clauses)
    baseline = 67 if high else 34 if medium else 0
    bonus = max(0, high - 1) * 12 + max(0, medium - 1) * 7 + low * 2
    score = min(100, baseline + bonus)
    level = "High Risk" if score >= 67 else "Moderate" if score >= 34 else "Safe"
    return score, level
