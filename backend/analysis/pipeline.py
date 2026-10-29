
"""Orchestrate the three distinct AI stages while keeping the WP2 response compatible."""
from .clause_extractor import extract_clauses
from .risk_classifier import classify_clauses
from .summary_generator import generate_summary
from .rating import calculate_rating
from .schemas import AnalysisResponse
from ..prompt_adjuster import PrivacyPreferences, build_prompt_bundle

MAX_MODEL_INPUT_CHARS = 60000


def analyze_terms(
    terms_text: str, preferences: PrivacyPreferences | None = None
) -> AnalysisResponse:
    cleaned = terms_text.strip()
    if len(cleaned) < 50:
        raise ValueError("At least 50 characters of Terms and Conditions are required.")
    truncated = len(cleaned) > MAX_MODEL_INPUT_CHARS
    working_text = cleaned[:MAX_MODEL_INPUT_CHARS]
    prompts = build_prompt_bundle(preferences)
    verified = extract_clauses(working_text, prompts.extraction_instructions)
    classified = classify_clauses(verified, prompts.classification_instructions)
    summary = generate_summary(classified, prompts.summary_instructions)
    score, level = calculate_rating(classified)
    return AnalysisResponse(
        status="completed",
        analysis_mode="openai",
        risk_score=score,
        risk_level=level,
        summary_en=summary.summary_en,
        summary_ar=summary.summary_ar,
        flagged_clauses=classified,
        input_truncated=truncated,
        disclaimer=(
            "Partial-document AI screening; not a legal compliance determination."
            if truncated else
            "AI-generated screening, not a legal compliance determination."
        ),
    )
