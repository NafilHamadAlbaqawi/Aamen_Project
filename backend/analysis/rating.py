# Code overview: These functions turn the severity findings into a safety-related rating. The number is only an estimated project score.

"""Evidence-based safety rating. The API risk_score remains 0-100 (higher = more risk)."""

from math import floor

from .schemas import FlaggedClause


HIGH_REMAINING = 0.69
MEDIUM_REMAINING = 0.91
MODERATE_THRESHOLD = 31
HIGH_RISK_THRESHOLD = 61


def calculate_rating(clauses: list[FlaggedClause]) -> tuple[int, str]:
    """Return a heuristic risk score and a label; never a legal-compliance determination.

    The user-facing safety rating is 100 minus this risk score.
    Safety 0-39 = High Risk; 40-69 = Moderate; 70-100 = Safe.
    Low-severity clauses, including protective clauses, do not penalize the score.
    """
    high = sum(clause.severity == "high" for clause in clauses)
    medium = sum(clause.severity == "medium" for clause in clauses)
    concern = 100 * (1 - HIGH_REMAINING ** high * MEDIUM_REMAINING ** medium)
    score = min(100, max(0, floor(concern + 0.5)))
    level = "High Risk" if score >= HIGH_RISK_THRESHOLD else "Moderate" if score >= MODERATE_THRESHOLD else "Safe"
    return score, level
