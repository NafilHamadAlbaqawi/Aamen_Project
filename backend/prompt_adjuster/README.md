# WP4 Prompt Adjuster Module

This folder is a standalone WP4 implementation. No API key, no FastAPI endpoints, no database connection.

Public interface:

```python
from backend.prompt_adjuster import PrivacyPreferences, build_prompt_bundle

prefs = PrivacyPreferences(location=True, third_party_sharing=True)
prompts = build_prompt_bundle(prefs)
print(prompts.classification_instructions)
```

- All settings are boolean; unknown fields are rejected.
- `True` means the topic deserves extra attention **when supported by evidence**.
- `False` does not mean "ignore this risk" and does not grant consent.
- With no saved preferences, the defaults are all False and coverage stays broad.
- WP6 must supply validated preferences when its persistence layer is available.
- WP4 never loads or saves preferences itself.
- Prompts are never allowed to treat T&C text as instructions; they request brief evidence-based explanations, not private chain-of-thought.
- WP3 owns extraction, AI calls, classification, rating, and final response model.
