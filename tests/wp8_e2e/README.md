# WP8 live end-to-end test

Runs the real extension, the real backend and the real OpenAI model together in Chromium, and uses the
popup the way a user would. It is separate from the offline tests (`run_wp8_tests.py`) because it needs
an API key and makes real model calls (about 7 analyses, under one US dollar with `gpt-4o-2024-08-06`).

## Setup (once)

```powershell
pip install -r backend/requirements.txt
pip install -r tests/wp8_e2e/requirements-e2e.txt
python -m playwright install chromium
```

Google Chrome 137 and newer no longer loads unpacked extensions from the command line, so the test uses
Playwright's Chromium. Ports 8000, 8001 and 8765 must be free.

## Run

```powershell
$env:OPENAI_API_KEY = "sk-..."      # backend only, never put it in the extension
python tests/wp8_e2e/run_e2e.py      # add --headed to watch the browser
```

Output:

- `docs/screenshots/WP8-E2E-*.png`: one or more screenshots per scenario
- `docs/wp8_logs/e2e_results.json`: expected / actual / pass for every scenario and the analysis times
- `docs/wp8_logs/e2e_backend.log`, `e2e_backend_no_key.log`: the backend's request log

## What it covers

| ID | Scenario | Use case |
|---|---|---|
| E2E-01 | Server settings → Check connection with the default server | Integration |
| E2E-02 | Analyze an open Terms page (content script → service worker → backend → AI → PDPL → popup) | UC-2 |
| E2E-03 | View Details report with PDPL references, closed with Esc | UC-3 |
| E2E-04 | Homepage: the popup follows the site's Terms and Privacy links | UC-2 |
| E2E-05 | Save preferences → stored in the WP6 database with the right meaning | UC-1 |
| E2E-06 | Change a preference and close without saving → nothing is updated | UC-1 alt. 2 |
| E2E-07 | Saved preferences give a new, personalized analysis; the same request again is a cache hit | UC-1 / WP6 |
| E2E-08 | Close the popup during an analysis and open it again → the result still appears | Integration |
| E2E-09 | Arabic interface with pasted text, result and report right-to-left | UC-2 |
| E2E-10 | Errors: server down, no API key (EN/AR), text too short, no legal text, offline | UC-2 alt. 1-3 |
| E2E-11 | Preferences saved while the server is down are sent before the next analysis | UC-1 |

## Fixture website

`site/` is a small fictional website ("Rihla Delivery") with a homepage, a Terms page, a Privacy page and
an About page with no legal text. It is served on `http://127.0.0.1:8765` only while the test runs.

## Test-only shim

Chrome opens the real popup only from the toolbar button, which a script can't press. The test opens
`popup.html` as a tab and adds a small script (only in that tab) so that
`chrome.tabs.query({active: true, currentWindow: true})` returns the fixture tab named in `?e2e_target=`.
Nothing in `extension/` is changed for the test; the extension folder is copied to a temporary folder
before Chromium loads it.
