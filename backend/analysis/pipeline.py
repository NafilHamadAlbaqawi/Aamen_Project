
"""Orchestrate WP3, WP4, and WP5 while preserving the WP2 response fields."""

import logging
from concurrent.futures import ThreadPoolExecutor

from .clause_extractor import extract_clauses
from .openai_client import AnalysisFailure
from .risk_classifier import classify_clauses
from .summary_generator import generate_summary
from .rating import calculate_rating
from .schemas import AnalysisResponse

from ..prompt_adjuster import PrivacyPreferences, build_prompt_bundle
from ..pdpl.checker import check_pdpl
from ..pdpl.schemas import PDPLCheckResult


logger = logging.getLogger(__name__)
MAX_MODEL_INPUT_CHARS = 60000


def screen_pdpl(classified):
    """Run WP5, with one retry when the model's answer fails WP5's own checks.

    WP9: in the evaluation some answers cited a reference that was supplied for a different clause, so WP5
    correctly rejected the whole answer and the user saw no PDPL result. A second answer is usually valid.
    Other errors (for example the AI service being down) are not retried.
    """
    try:
        return check_pdpl(classified)
    except AnalysisFailure as error:
        logger.warning("WP5 answer failed validation (%s); retrying once.", error)
        return check_pdpl(classified)


def analyze_terms(
    terms_text: str, preferences: PrivacyPreferences | None = None
) -> AnalysisResponse:
    cleaned = terms_text.strip()

    if len(cleaned) < 50:
        raise ValueError(
            "At least 50 characters of Terms and Conditions are required."
        )

    truncated = len(cleaned) > MAX_MODEL_INPUT_CHARS
    working_text = cleaned[:MAX_MODEL_INPUT_CHARS]

    prompts = build_prompt_bundle(preferences)

    verified = extract_clauses(
        working_text,
        prompts.extraction_instructions
    )

    classified = classify_clauses(
        verified,
        prompts.classification_instructions
    )

    score, level = calculate_rating(classified)

    # WP9: the summary and the PDPL screening both need only the classified clauses, so they run at the
    # same time (about 3 seconds faster). A summary failure still fails the analysis; a PDPL failure does not.
    with ThreadPoolExecutor(max_workers=1) as pool:
        summary_job = pool.submit(
            generate_summary,
            classified,
            prompts.summary_instructions
        )

        try:
            pdpl_result = screen_pdpl(classified)

        except Exception:
            logger.exception(
                "WP5 PDPL screening failed; WP3 results are preserved."
            )

            pdpl_result = PDPLCheckResult(
                status="unavailable",
                disclaimer=(
                    "PDPL screening failed; no PDPL conclusion is available."
                ),
            )

        summary = summary_job.result()

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
        pdpl=pdpl_result,
    )
