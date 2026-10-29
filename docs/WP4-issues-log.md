# WP4 — Issues Log (testing and integration)

**Project:** Aamen (آمن) · **Work package:** WP4 (inputs for WP9) · **Responsible:** Abdullah Alasker  
**Branch:** feature/wp4-prompt-personalization · **Date:** 2026-10-29  
Test results: [`WP4-testing.md`](WP4-testing.md) · Raw logs: [`wp4_logs/`](wp4_logs/) · Raw results: `tests/wp4_eval/results/`

| ID | Issue | Found in | Severity | Status | Owner |
|---|---|---|---|---|---|
| I-01 | Integration test fails until WP3 accepts preferences | TC03 | Medium | Resolved locally; commit awaits Ahmed's review | WP3 + WP4 |
| I-02 | `/health` reports `ai_enabled: true` with an invalid key | TC04 | Low | Open | WP3 |
| I-03 | `analysis_mode` is always `"openai"` | TC04 | Low | Open | WP3 |
| I-04 | Classifier omitted clauses → whole analysis fails (502) | TC04 v1 | Medium | Fixed in WP4 prompts; WP3 retry suggested | WP4 (+WP3) |
| I-05 | Preferences lowered the severity of other topics | TC04 v2 | Medium | Fixed in WP4 prompts | WP4 |
| I-06 | Overstated / "missing" claims from short, context-free excerpts | LLM judge | Medium | Reduced in WP4 prompts; WP3 context suggested | WP4 + WP3 |
| I-07 | Analysis takes ≈19.3 s, but the requirement is "a few seconds" | TC04 | Medium | Open | WP3 / WP8 |
| I-08 | Rating changes level when one clause changes severity | TC04 | Low | Open | WP3 |
| I-09 | Preference names and meaning differ from the Senior Project I design | Design review | Medium | Open | WP4 + WP6 |
| I-10 | Repository has no `.gitignore` | Commit prep | Medium | Open (mitigated) | WP8 |
| I-11 | Integration overlay files differ from the repo's WP3 files | TC03 | Low | Fixed | WP4 |
| I-12 | `pip install` fails in deep Windows folders (path too long) | Setup | Low | Workaround | All |
| I-13 | Some summaries are longer than the 2–5 sentence rule | TC04 | Low | Open | WP4 (+WP7) |

## Details

### I-01 — Integration test fails until WP3 accepts preferences
- **Symptom:** `run_wp4_tests.py` gives 9 tests with 1 ERROR: `TypeError: analyze_terms() takes 1 positional argument but 2 were given`.
- **Cause:** WP3's `analyze_terms()` does not take `preferences` yet. This is expected before integration, and the runner reports it on purpose.
- **Fix:** Apply the 5-file patch (optional `instructions=` in the 3 stages, `preferences` in `pipeline.py` and `main.py`; +21/−11 lines). Result: 9/9 OK with 0 skipped. The patch is identical to the leader's overlay apart from whitespace.
- **Status:** Verified on a local copy only. **Not committed**; Ahmed must approve it.
- **Evidence:** `screenshots/WP4-TC03-before-integration.png`, `screenshots/WP4-TC03.png`

### I-02 — `/health` reports `ai_enabled: true` even with an invalid key
- **Symptom:** With the invalid key, `GET /health` returns `"ai_enabled": true`, but every `/analyze` call fails with 502.
- **Cause:** `/health` only checks that the variable is set.
- **Suggestion (WP3):** Rename the field to `key_configured`, or check the key once at startup.
- **Evidence:** `screenshots/WP4-TC04-error-handling.png`, `wp4_logs/error_handling/`

### I-03 — `analysis_mode` is always `"openai"`
- **Symptom:** `analysis_mode` is fixed to `"openai"` in `pipeline.py`, so a result does not show which model produced it. During TC04 it still read `"openai"`.
- **Suggestion (WP3):** Report the model actually used, for example in `analysis_mode` or a separate `model` field.
- **Evidence:** `screenshots/WP4-TC04-docs-default.png`

### I-04 — Classifier omitted clauses, so the whole analysis failed
- **Symptom:** With the committed prompts (v1), 2 of 24 analyses returned **502 "The classifier omitted one or more clauses."**, both on DOC-D. The model returned 5 items for 9 clauses and left out the harmless ones.
- **Cause:** The prompt asked for one item per clause, but did not say that ordinary clauses must be included as well.
- **Fix (WP4):** The classification prompt now says *"Never skip a clause, including ordinary ones: the output must have exactly as many items as the input."* Since then: 0 failures in 72 analyses (v2–v4).
- **Suggestion (WP3):** Retry the classification once before returning 502.
- **Evidence:** `screenshots/issues/ISSUE-04-classifier-omitted-clauses.png`, `screenshots/WP4-TC04-prompt-iterations.png`

### I-05 — Preference emphasis lowered other topics' severity
- **Symptom:** On DOC-D, which has no location or sharing clauses, the location + sharing preferences gave **Safe in 6/6 runs** with prompt v2 (default: 3/6). With v1 it was already 1/5 vs 0/5. The cause was the v2 wording "ordinary clauses get low", together with no rule protecting non-priority topics.
- **Fix (WP4):** The completeness rule was made neutral, and when preferences are set the classification prompt adds *"Do not lower the severity of clauses on other topics."* Since then (v3, v4), DOC-D's level has been the same in both conditions (see the iteration table).
- **Evidence:** `screenshots/issues/ISSUE-05-preference-severity-downgrade.png`, `screenshots/WP4-TC04-prompt-iterations.png`

### I-06 — Overstated or "missing" claims from short excerpts
- **Symptom:** The LLM judge flagged statements the source does not support. Example: *"continued use counts as accepting updated terms with no stated notice"*, although DOC-C says *"will notify you in the application"*. In DOC-B, *"While an order is active"* was dropped from background location tracking. With v3, 4/16 runs needed review.
- **Cause:** Extraction picks short excerpts that can cut off conditions. The classifier and summary see only those excerpts, then describe something as missing.
- **Fix (WP4, v4):** Excerpts keep the conditions and limits that change their meaning. The classifier may not claim the terms "lack" a notice, purpose, limit or choice, and the summary may only if a finding states it. Result: evidence accuracy 4.19 → 4.94 / 5; runs needing review 4 → 0 of 16.
- **Suggestion (WP3):** Pass the surrounding sentence or section of each excerpt to the classifier.
- **Evidence:** `screenshots/issues/ISSUE-06-judge-overstatements.png`, `screenshots/WP4-TC04-judge.png`

### I-07 — Analysis time
- **Symptom:** The final comparison runs took 14.0–25.4 s (mean 19.3 s) for 3 sequential model calls. One classification call during v1 took 126.6 s (a provider-side delay). The requirement is "results appear within a few seconds".
- **Suggestion:** Re-measure with OpenAI. Consider result caching (WP6) or merging stages (WP3/WP8).
- **Evidence:** `screenshots/WP4-TC04-console.png`

### I-08 — Rating is sensitive to a single clause
- **Symptom:** WP3's provisional formula goes from 18 (all low) to 50 (one medium) on DOC-D, which changes the level from Safe to Moderate.
- **Suggestion (WP3):** Smooth the formula, or weight by clause importance. WP4's fixes (I-05) make the severity more stable.
- **Evidence:** `screenshots/WP4-TC04-prompt-iterations.png`

### I-09 — Preference names and meaning differ from the Senior Project I design
- **Symptom:** The class diagram (Fig. 18) and ERD (Fig. 19) use `allowLocation`, `allowPhotos`, `allowBankingInfo` and `allowThirdPartySharing`, which reads as **consent**. WP4 uses `location`, `photos`, `banking_information` and `third_party_sharing`, where `true` means **emphasize this risk**. The all-`false` defaults are a proposal; the design does not define them (UC-1 only says "default settings").
- **Action:** Agree the mapping and defaults with Mazen (WP6). For example, `allowLocation = false` could map to emphasizing location. The WP4 schema stays strict.
- **Evidence:** `screenshots/issues/ISSUE-09-design-ERD-preferences.png`, `screenshots/issues/ISSUE-09-design-class-diagram.png`

### I-10 — Repository has no `.gitignore`
- **Risk:** `.env` (the API key), `.venv/` and `__pycache__/` could be committed by accident.
- **Mitigation:** Tests ran with bytecode writing disabled, and the upload set was checked for secrets and caches.
- **Suggestion (WP8):** Add a shared `.gitignore` containing `.env`, `.venv/`, `__pycache__/` and `*.pyc`. WP4 did not add it because it is a shared file.
- **Evidence:** `screenshots/issues/ISSUE-10-no-gitignore.png`

### I-11 — Overlay files differ from the repository's WP3 files
- **Symptom:** The leader's overlay copies are missing the repo files' leading blank line. Copying whole files would also overwrite any newer WP3 changes.
- **Fix:** Only the minimal edits were applied, as a patch. After patching, the files are identical to the overlay apart from whitespace.
- **Evidence:** `screenshots/issues/ISSUE-11-overlay-vs-repo.png`, `wp4_logs/TC03_patch_vs_overlay.log`

### I-12 — `pip install` fails in deep Windows folders
- **Symptom:** `OSError [WinError 206] The filename or extension is too long` when the virtual environment sat in a deep folder under the user profile. The non-ASCII user name makes the path longer.
- **Workaround:** Create the virtual environment in a short path (for example `%LOCALAPPDATA%\aamen_wp4_venv`), or enable Windows long paths.
- **Evidence:** `screenshots/issues/ISSUE-12-pip-long-path.png`

### I-13 — Summaries sometimes exceed 5 sentences
- **Symptom:** The summary prompt asks for 2–5 sentences per language. With the final prompts, 6/24 English and 6/24 Arabic summaries had 6–7 sentences, all on DOC-D, which has many low-risk clauses. On the same basis in English: final 3/16 comparison runs (6/24 with stress runs), v1 1/14 (2/22), v3 2/16 (3/24). The content stayed accurate (judge clarity 5.0 EN / 4.94 AR).
- **Suggestion:** WP4 could set a word limit or require "the 3–5 most important findings". WP7 could also cap the text shown in the popup. Not changed yet, to avoid another untested prompt change.
- **Evidence:** `tests/wp4_eval/results/TC04_results.json` (`summary_en`/`summary_ar`)
