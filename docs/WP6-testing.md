# WP6 — SQLite Persistence, Analysis Cache, and Testing

**Project:** Aamen — AI-powered Terms and Conditions Analyzer  
**Work package:** WP6 — Database and persistent privacy preferences  
**Source reviewed:** `Aamen_Project-main.zip` (user-uploaded main branch export)  
**Verification status:** Automated tests passed on the refined local copy; manual Chrome/Swagger checks were reported by the project team.

## 1. Purpose

WP6 adds SQLite-based persistence for anonymous device privacy preferences and previously completed analyses, connecting the existing WP3 risk-analysis pipeline, WP4 preference adjustments, and WP5 Saudi PDPL screening to FastAPI.

The user-facing Chrome extension continues to be developed separately; full UI exposure of the preference and PDPL features belongs to the subsequent integration work.

## 2. Files and responsibilities

| Path | Purpose |
| --- | --- |
| `backend/database/storage.py` | SQLite connection lifecycle, initialization of the two database tables, and optional `AAMEN_DB_PATH` override |
| `backend/database/preferences.py` | Retrieve, upsert, and reset four per-device privacy preference values |
| `backend/database/cache.py` | SHA-256 cache identifiers, result serialization, expiry checks, cleanup, and per-device cache deletion |
| `backend/main.py` | FastAPI endpoints; preference lookup and cache integration in `/analyze` |
| `tests/test_wp6_preferences.py` | 10 preference persistence and validation tests |
| `tests/test_wp6_cache.py` | 18 cache behavior and HTTP integration tests |
| `.gitignore` | Excludes local secrets, virtual environments, compiled Python files, and SQLite files |

**Database tables:**

- `user_preferences`: stores `device_id`, `location`, `photos`, `banking_information`, `third_party_sharing`, and `updated_at`.
- `analysis_cache`: stores `cache_key`, `device_id`, serialized `response_json`, `created_at`, and `expires_at`.

`device_id` is an anonymous identifier rather than a verified identity. All four preference flags default to `false`; `true` requests greater analysis attention to that topic, not a conclusion that a clause is unsafe.

## 3. REST interface

| Method | Endpoint | Behavior |
| --- | --- | --- |
| GET | `/health` | Basic backend status and whether an OpenAI API key is configured |
| GET | `/preferences/{device_id}` | Returns current preference values or defaults |
| PUT | `/preferences/{device_id}` | Validates and stores the four preference values |
| DELETE | `/preferences/{device_id}` | Resets preferences and clears this device's cached analyses |
| POST | `/analyze` | Uses explicitly provided preferences, or loads saved preferences if omitted; returns a cache hit when available, otherwise runs WP3–WP5 |

The `/analyze` response header `X-Aamen-Cache` reports:

- `HIT`: valid stored response returned without rerunning AI analysis.
- `MISS`: fresh analysis performed because a cache entry was not available.
- `SKIP`: response was not cached, for example because PDPL screening was incomplete or cache storage failed.

## 4. Cache behavior and limitations

- The cache key hashes the trimmed document text together with device ID, preference values, requested language, OpenAI model setting, and `CACHE_VERSION`.
- An entry expires **24 hours** after creation. Expired entries are not returned and are cleaned up on a later successful cache save.
- Cache responses are validated against the existing Pydantic `AnalysisResponse` schema; malformed responses are removed.
- Completed WP3 results with missing, partial, or unavailable PDPL results are **not** cached.
- Results are separated by device; deleting one device's preferences also clears its cached analyses.
- A cache read/write failure does not prevent a fresh, otherwise successful analysis from being returned.
- Cache keys do not contain the full input text, but cached response JSON **can contain excerpts from the analyzed terms** and should be protected accordingly.
- If prompts, business rules, PDPL reference data, or model contracts materially change, increment `CACHE_VERSION` to avoid reusing outdated analyses.
- Concurrent identical requests before the first cache save may still trigger multiple AI requests.

## 5. Automated test evidence

**Local verification of this refined export:** 50 tests executed, **50 passed**, **0 failures**, **0 errors**, **0 skips**.

| Test group | Test files | Tests | Result |
| --- | --- | ---: | --- |
| Previous WP4 / WP5 regression | `tests/test_wp4_*.py`, `tests/test_wp5_*.py` | 22 | Passed |
| WP6 preference persistence | `tests/test_wp6_preferences.py` | 10 | Passed |
| WP6 cache / FastAPI | `tests/test_wp6_cache.py` | 18 | Passed |
| **Total** | | **50** | **Passed** |

**Test conditions:** Automated offline unit/integration tests ran against a temporary SQLite database with `AAMEN_DB_PATH` set to an isolated path. OpenAI SDK import behavior was shimmed in this validation environment because a functioning OpenAI SDK installation was unavailable; tests mocked AI work and **did not call the real OpenAI service**. The Python environment used for verification differed from the pinned runtime dependency versions in `backend/requirements.txt`, so this does not substitute for a clean-install production or live API check.

The test suite checks saved-preference defaults and validation, database isolation, cache-key separation, cache save/load/expiry, corrupted responses, incomplete PDPL results, per-device deletion, `MISS` followed by `HIT`, preference changes, and fallback behavior when cache operations fail.

**Manual verification:** The team reported successful manual FastAPI caching, preference updates and reset, and a real analysis response. The refined ZIP preserves available screenshots, but it cannot independently authenticate all reported manual actions.

## 6. Existing screenshots

The uploaded archive contains these WP6 preference endpoint screenshots (names retained to avoid changing existing evidence):

- `docs/wp6 tests/getting pref working.png`
- `docs/wp6 tests/setting preferance working.png`
- `docs/wp6 tests/pref deletion working.png`

The archive **did not contain** the planned cache `MISS`/`HIT` screenshot pair or a consolidated 50-test Testing-panel screenshot. Do not treat those screenshots as supplied evidence. They can be added later under `docs/screenshots/` if required for the university submission.

## 7. Security and repository cleanup

This refined export removes one committed SQLite database and 25 compiled `.pyc` files / `__pycache__` entries. It preserves the existing `.gitignore` rules, including those for `.env`, `.venv/`, SQLite files, and Python bytecode.

Keep the OpenAI API key in a backend-only `.env` file, never in the Chrome extension or Git repository. The included SQLite schema is created automatically at runtime; the database file does **not** need to be committed or distributed.

**Important:** Cleaning an exported ZIP does not delete previous commits from the GitHub repository. If the original SQLite database contained real information, the committed copy may remain accessible through Git history even after a new cleanup commit. Handle history removal and any affected data separately when necessary.

Anonymous `device_id` values do not authenticate users. The current preference endpoints and cache should not be exposed to untrusted clients without appropriate authentication, authorization, transport protection, and retention controls.

## 8. Acceptance and WP7 handoff

The source-level WP6 files and offline regression suite are complete. Before WP7, merge/upload the cleaned repository changes and verify the GitHub `main` branch no longer tracks runtime-generated files.

For WP7, focus on connecting the Chrome extension to stored preferences, handling backend connectivity securely, presenting bilingual risk clauses and PDPL findings, and displaying loading, error, and cache status correctly. Retain the existing backend API contracts unless there is an explicit change request.
