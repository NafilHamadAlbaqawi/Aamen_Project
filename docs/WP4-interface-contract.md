# WP4 Interface Contract for WP3 and WP6

## Scope and ownership

| Work package | Owner of functionality |
|---|---|
| WP3 | FastAPI, OpenAI SDK, clause extraction, classification, summary generation, safety rating |
| WP4 | Prompt design, few-shot examples, preference adjustment, prompt quality evaluation |
| WP5 | PDPL RAG and compliance checker |
| WP6 | Persistent user preferences, database, caching |

## WP6 → WP4 stored preference schema

WP6 should return a Python mapping with these exact boolean fields:

```json
{
  "location": false,
  "photos": false,
  "banking_information": false,
  "third_party_sharing": false
}
```

Values are strict `true`/`false`. **Note:** the Senior Project I class diagram and ERD name these fields `allowLocation`, `allowPhotos`, `allowBankingInfo`, `allowThirdPartySharing`. The name suggests consent, but WP4's `true` means "emphasize this risk". WP6 and WP4 must agree on the mapping (issue I-09). Unknown fields and strings are rejected; missing fields use `false` defaults. **These defaults are an engineering choice for this starter module and must be approved by the team; they are not stated in the official implementation plan.**

Semantics: `true` means "pay extra attention to this topic if document evidence supports it." False is not "safe" and is not consent. A preference selection cannot by itself make a clause high risk.

Do not pass `device_id` or source Terms & Conditions directly into prompt instructions. WP6's lookup should happen before calling WP4; do not store data in WP4.

## WP4 → WP3 interface

```python
from backend.prompt_adjuster import build_prompt_bundle, PrivacyPreferences

prefs = PrivacyPreferences(location=True)
bundle = build_prompt_bundle(prefs)
extract = bundle.extraction_instructions
classify = bundle.classification_instructions
summarize = bundle.summary_instructions
```

WP3 passes each string to its current `request_structured(...)` helper, preserving WP3's Pydantic output models and HTTP response fields.

`PromptBundle` fields: `extraction_instructions`, `classification_instructions`, `summary_instructions`, and `preferences`.

## Optional short-term testing before WP6 is ready

The integration overlay adds an **optional** `preferences` object to `POST /analyze`; existing WP2 requests remain valid without it. This is for testing only and is NOT an authenticated saved-preference mechanism. **Once WP6 is ready, replace this testing override with trusted server-side lookup** and include preferences in any cache-key design. Do not assume client-supplied `device_id` authenticates a person.

## Compatibility warning

The integration files were derived from the WP3 starter package used to prepare WP4, not from the live repository. They were later checked against the live WP3 branch: after the 5 minimal edits the files are identical apart from whitespace (`docs/wp4_logs/TC03_patch_vs_overlay.log`). Review the diff on GitHub. If Ahmed changed WP3 since, edit only the indicated lines and preserve his new changes; DO NOT overwrite entire files blindly.
