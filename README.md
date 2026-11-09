# Aamen_Project
AI-Powered chrome extension for T&amp;C analysis and KSA PDPL compliance.

Aamen (آمن) is a Chrome extension that reads a website's Terms and Conditions, finds risky clauses with AI,
checks them against Saudi PDPL references, and shows a summary and a safety rating (Safe / Moderate / High Risk)
that follows the user's own privacy preferences. English and Arabic.

| Folder | Contents |
|---|---|
| `extension/` | Chrome extension (Manifest V3): content script (WP1), service worker (WP2), pop-up (WP7) |
| `backend/` | FastAPI server: AI analysis (WP3), prompts (WP4), PDPL checker (WP5), SQLite preferences and cache (WP6) |
| `tests/` | Offline tests for every work package, the WP8 service worker tests and the live browser test |
| `docs/` | Work package reports, screenshots and logs. Start with [`docs/WP8-integration.md`](docs/WP8-integration.md) |

## 1. Run the backend

Needs Python 3.12. If `pip install` fails with *"filename or extension is too long"*, create the virtual
environment in a shorter folder (see WP4 issue I-12).

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
$env:OPENAI_API_KEY = "sk-..."          # keep the key on the server only, never in the extension
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Check it at <http://127.0.0.1:8000/health> or the API docs at <http://127.0.0.1:8000/docs>.
Optional settings: `OPENAI_MODEL` (default `gpt-4o-2024-08-06`) and `AAMEN_DB_PATH` (default
`backend/database/aamen.sqlite3`, created automatically and not committed).

## 2. Load the extension

1. Open `chrome://extensions` and switch on **Developer mode**.
2. Click **Load unpacked** and choose the `extension` folder.
3. Pin Aamen, open a website's Terms or Privacy page and click **Analyze this page**.

The extension uses `http://127.0.0.1:8000` by default and needs no extra permission for it. For a backend on
another computer, open **Server settings** in the pop-up, enter its address (for example
`http://192.168.1.5:8000`) and allow access when Chrome asks.

Preferences are in the **Preferences** tab: choose what you accept and press **Save preferences**. Saved
preferences are used in every new analysis. If a site can't be read, use the **Paste** tab.

## 3. Tests

```powershell
pip install httpx                       # needed by FastAPI's test client
python run_wp8_tests.py                 # all offline tests (WP4-WP8) + service worker tests, needs Node.js 18+
```

No API key is needed and no OpenAI request is made. The live browser test with the real model is described in
[`tests/wp8_e2e/README.md`](tests/wp8_e2e/README.md).
