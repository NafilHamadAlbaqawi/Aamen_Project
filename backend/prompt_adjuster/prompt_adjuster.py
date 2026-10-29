"""Build safe, deterministic WP4 prompts with optional WP6 preferences."""

from dataclasses import dataclass
from typing import Mapping

from .few_shot_examples import (
    CLASSIFICATION_EXAMPLE,
    EXTRACTION_EXAMPLE,
    SUMMARY_EXAMPLE,
)
from .preferences import PrivacyPreferences, normalize_preferences, selected_topics
from .prompts import CLASSIFICATION_BASE, EXTRACTION_BASE, SUMMARY_BASE


@dataclass(frozen=True)
class PromptBundle:
    """Three standalone instructions strings, one for each existing WP3 API call."""

    extraction_instructions: str
    classification_instructions: str
    summary_instructions: str
    preferences: PrivacyPreferences


def build_prompt_bundle(
    preferences: PrivacyPreferences | Mapping[str, object] | None = None,
) -> PromptBundle:
    """Apply only fixed, validated preference labels; never place T&C text in prompts."""

    saved = normalize_preferences(preferences)
    topics = selected_topics(saved)
    if topics:
        priorities = ", ".join(topics)
        extraction_priority = (
            "User-priority topics: " + priorities + ". When those topics appear, "
            "prioritize relevant source-grounded clauses, but still cover other major risks."
        )
        classification_priority = (
            "User-priority topics: " + priorities + ". Pay extra attention when a "
            "clause directly affects these topics, but never label it high risk solely "
            "because a preference is selected; severity must reflect the actual evidence."
        )
        summary_priority = (
            "User-priority topics: " + priorities + ". Mention these topics earlier "
            "ONLY when they are supported by the classified findings."
        )
    else:
        extraction_priority = "No user-selected topic priorities; apply broad default coverage."
        classification_priority = (
            "No user-selected topic priorities; use evidence-based default classification."
        )
        summary_priority = (
            "No user-selected topic priorities; summarize the most significant findings."
        )
    return PromptBundle(
        extraction_instructions="\n\n".join(
            (EXTRACTION_BASE, EXTRACTION_EXAMPLE, extraction_priority)
        ),
        classification_instructions="\n\n".join(
            (CLASSIFICATION_BASE, CLASSIFICATION_EXAMPLE, classification_priority)
        ),
        summary_instructions="\n\n".join(
            (SUMMARY_BASE, SUMMARY_EXAMPLE, summary_priority)
        ),
        preferences=saved,
    )
