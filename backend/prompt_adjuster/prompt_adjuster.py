# Code overview: This section builds the instructions used to focus the analysis on selected user concerns.

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
            "User-priority topics: " + priorities + ". When a clause directly affects "
            "any of these topics, include it if it has a practical effect on the user, "
            "and keep its original conditions and safeguards. Still cover other major "
            "risks and protective terms. Never invent a clause to satisfy a preference."
        )
        classification_priority = (
            "User-priority topics: " + priorities + ". Explain the specific effect of "
            "clauses related to these topics in clear language. Keep the standard evidence-based "
            "severity rubric unchanged: never increase severity just because a topic is selected, "
            "and do not lower severity on other topics. Mention consent, limits, and protections "
            "when they are present in the excerpt."
        )
        summary_priority = (
            "User-priority topics: " + priorities + ". If one or more classified "
            "findings involve these topics, explicitly summarize the most important such finding "
            "near the beginning in both languages, including any stated consent or protection. "
            "If no finding concerns a selected topic, do not fabricate one; summarize other "
            "actual findings instead. Keep the summary concise and factual."
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
