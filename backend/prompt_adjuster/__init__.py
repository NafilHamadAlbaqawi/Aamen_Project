"""WP4 public interface for prompts and preference-based personalization."""

from .preferences import PrivacyPreferences, normalize_preferences
from .prompt_adjuster import PromptBundle, build_prompt_bundle

__all__ = [
    "PrivacyPreferences",
    "normalize_preferences",
    "PromptBundle",
    "build_prompt_bundle",
]
