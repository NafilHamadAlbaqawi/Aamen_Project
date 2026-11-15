# Code overview: This section checks and normalizes the four preference values.
"""WP4 preference contract. WP6 owns persistence and preference retrieval."""

from typing import Mapping
from pydantic import BaseModel, ConfigDict, StrictBool


class PrivacyPreferences(BaseModel):
    """True = give a topic extra attention, not assume the clause is unsafe."""

    model_config = ConfigDict(extra="forbid")

    location: StrictBool = False
    photos: StrictBool = False
    banking_information: StrictBool = False
    third_party_sharing: StrictBool = False


def normalize_preferences(
    preferences: PrivacyPreferences | Mapping[str, object] | None = None,
) -> PrivacyPreferences:
    """Validate WP6 data or return explicit, neutral defaults."""

    if preferences is None:
        return PrivacyPreferences()
    if isinstance(preferences, PrivacyPreferences):
        return preferences
    return PrivacyPreferences.model_validate(dict(preferences))


def selected_topics(preferences: PrivacyPreferences) -> tuple[str, ...]:
    """Return only trusted, predefined labels; never interpolate free-form text."""

    labels = (
        ("location", "location data and tracking"),
        ("photos", "photos and image usage"),
        ("banking_information", "banking and financial information"),
        ("third_party_sharing", "third-party personal-data sharing"),
    )
    return tuple(label for field, label in labels if getattr(preferences, field))
