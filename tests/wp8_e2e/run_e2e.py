"""WP8 live end-to-end test: the real extension, the real backend and the real OpenAI model together.

What it does:
1. Serves the fictional "Rihla Delivery" website in ./site on http://127.0.0.1:8765.
2. Starts the FastAPI backend on http://127.0.0.1:8000 with a temporary SQLite database
   (and, for one error case, a second backend on port 8001 without an API key).
3. Opens Chromium with the unpacked extension and uses the popup like a user would:
   analyze a terms page, a homepage, pasted text, View Details, preferences, errors, and closing the popup early.
4. Saves screenshots to docs/screenshots/WP8-E2E-*.png and the results to docs/wp8_logs/.

Needs: OPENAI_API_KEY in the environment, `pip install -r tests/wp8_e2e/requirements-e2e.txt`
and `python -m playwright install chromium`. Run from the project folder:
    python tests/wp8_e2e/run_e2e.py

Test-only shim: Chrome opens the real popup only from the toolbar button, which a script can't press. So the popup
is opened as a tab, and a small script added only in this test makes chrome.tabs.query({active, currentWindow})
return the fixture tab given in ?e2e_target=. The extension files are not changed.
"""

import argparse
import functools
import http.server
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "extension"
SITE = Path(__file__).resolve().with_name("site")
SITE_URL = "http://127.0.0.1:8765"
API_URL = "http://127.0.0.1:8000"
NO_KEY_URL = "http://127.0.0.1:8001"
DEAD_URL = "http://127.0.0.1:8009"
RIYADH = timezone(timedelta(hours=3))

SHIM = """
(() => {
  const target = new URLSearchParams(location.search).get('e2e_target');
  if (!target || !window.chrome || !chrome.tabs) return;
  const realQuery = chrome.tabs.query.bind(chrome.tabs);
  chrome.tabs.query = async info => {
    if (info && info.active && info.currentWindow) {
      const tabs = await realQuery({});
      return tabs.filter(tab => tab.url === target).slice(0, 1);
    }
    return realQuery(info);
  };
})();
"""


def now():
    return datetime.now(RIYADH).strftime("%Y-%m-%d %H:%M:%S %z")


def http_json(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read() or b"{}")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_site():
    handler = functools.partial(QuietHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_backend(port, db_path, log_file, with_key=True):
    env = os.environ.copy()
    env["AAMEN_DB_PATH"] = str(db_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if not with_key:
        env.pop("OPENAI_API_KEY", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT,
    )
    for _ in range(60):
        try:
            if http_json("GET", f"http://127.0.0.1:{port}/health")[0] == 200:
                return process
        except OSError:
            time.sleep(0.5)
    process.kill()
    raise RuntimeError(f"Backend on port {port} did not start")


class Run:
    """Keeps the browser, the results and the screenshots for one test run."""

    def __init__(self, context, shots_dir, db_path):
        self.context = context
        self.shots_dir = shots_dir
        self.db_path = db_path
        self.results = []
        self.timings = []
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        self.extension_id = worker.url.split("/")[2]
        self.site = context.new_page()

    # ---- helpers -------------------------------------------------------------------------------------

    def storage(self, script, arg=None):
        """Run a chrome.storage call inside the extension (service worker, or a popup page if it is asleep)."""
        for worker in self.context.service_workers:
            try:
                return worker.evaluate(script, arg)
            except Exception:
                pass
        page = self.context.new_page()
        try:
            page.goto(f"chrome-extension://{self.extension_id}/popup.html")
            return page.evaluate(script, arg)
        finally:
            page.close()

    def set_server(self, url):
        self.storage("url => chrome.storage.local.set({ server_url: url })", url)

    def clear_run(self):
        self.storage("() => chrome.storage.session.clear()")

    def device_id(self):
        return self.storage("() => chrome.storage.local.get('device_id').then(v => v.device_id)")

    def cache_rows(self):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute("SELECT COUNT(*) FROM analysis_cache").fetchone()[0]

    def open_site(self, path):
        self.site.goto(SITE_URL + path)
        self.site.wait_for_load_state("load")
        return SITE_URL + path

    def open_popup(self, target=None):
        page = self.context.new_page()
        page.set_viewport_size({"width": 390, "height": 600})
        page.add_init_script(SHIM)
        query = f"?e2e_target={quote(target, safe='')}" if target else ""
        page.goto(f"chrome-extension://{self.extension_id}/popup.html{query}")
        page.wait_for_selector("header.top")
        return page

    def shot(self, page, name):
        path = self.shots_dir / f"WP8-E2E-{name}.png"
        page.screenshot(path=str(path))
        return f"docs/screenshots/{path.name}"

    @staticmethod
    def click(page, key):
        page.click(f'[data-focus-key="{key}"]')

    def wait_outcome(self, page, label, timeout=200):
        start = time.monotonic()
        page.wait_for_selector(".gauge-card, .panel.error", timeout=timeout * 1000)
        seconds = round(time.monotonic() - start, 1)
        outcome = "result" if page.query_selector(".gauge-card") else "error"
        self.timings.append({"analysis": label, "seconds": seconds, "outcome": outcome})
        return outcome, seconds

    @staticmethod
    def error_title(page):
        return page.inner_text(".panel.error h2")

    @staticmethod
    def summary_facts(page):
        return {
            "safety": page.inner_text(".gauge-num b"),
            "level": page.inner_text(".gauge-card .level"),
            "warnings": page.inner_text(".list-head span"),
            "analyzed_page": page.inner_text("p.page") if page.query_selector("p.page") else "",
        }

    def scenario(self, number, title, use_case, expected, body):
        print(f"[{now()}] E2E-{number:02d} {title} ...", flush=True)
        record = {"id": f"WP8-E2E-{number:02d}", "title": title, "use_case": use_case, "expected": expected}
        start = time.monotonic()
        try:
            actual, screenshots = body()
            record.update(passed=True, actual=actual, screenshots=screenshots)
        except Exception as error:
            record.update(passed=False, actual=f"{type(error).__name__}: {error}", screenshots=[])
            traceback.print_exc()
        record["seconds"] = round(time.monotonic() - start, 1)
        print(f"    -> {'PASS' if record['passed'] else 'FAIL'}: {record['actual']}", flush=True)
        self.results.append(record)

    # ---- scenarios -------------------------------------------------------------------------------

    def e01_connection(self):
        page = self.open_popup()
        self.click(page, "settings")
        self.click(page, "server-check")
        page.wait_for_selector('.msg[data-state="success"]', timeout=20000)
        text = page.inner_text('.msg[data-state="success"]')
        assert "Connected" in text, text
        shots = [self.shot(page, "01-connection")]
        page.close()
        return f'Server settings -> Check connection: "{text}" (default server, no permission prompt needed)', shots

    def e02_terms_page(self):
        self.clear_run()
        target = self.open_site("/terms.html")
        page = self.open_popup(target)
        self.click(page, "analyze")
        outcome, seconds = self.wait_outcome(page, "terms page (first run)")
        assert outcome == "result", self.error_title(page)
        facts = self.summary_facts(page)
        shots = [self.shot(page, "02-terms-summary")]
        page.locator(".accs").scroll_into_view_if_needed()
        page.click(".acc-h >> nth=0")
        page.wait_for_selector(".acc-b")
        page.locator(".acc-b").scroll_into_view_if_needed()
        shots.append(self.shot(page, "02-warning-open"))
        self.e02_page = page
        self.e02_facts = facts
        assert self.cache_rows() == 1, "the completed analysis should be cached once"
        return f"Result in {seconds}s: safety {facts['safety']}/100, {facts['level']}, {facts['warnings']}; cache rows = 1", shots

    def e03_report(self):
        page = self.e02_page
        page.evaluate("document.querySelector('[data-scroll^=\"body\"]').scrollTop = 0")
        self.click(page, "view-details")
        page.wait_for_selector(".sheet")
        sections = page.locator(".sheet section.rep").count()
        references = page.locator(".sheet .ref").count()
        shots = [self.shot(page, "03-report")]
        if references:
            page.locator(".sheet .ref >> nth=0").scroll_into_view_if_needed()
            shots.append(self.shot(page, "03-report-pdpl"))
        page.keyboard.press("Escape")
        page.wait_for_selector(".sheet", state="detached")
        page.close()
        assert sections > 0
        return f"View Details opened: {sections} clauses, {references} Saudi PDPL references with official links; Esc closes it", shots

    def e04_homepage(self):
        self.clear_run()
        target = self.open_site("/")
        page = self.open_popup(target)
        self.click(page, "analyze")
        outcome, seconds = self.wait_outcome(page, "homepage (terms + privacy links)")
        assert outcome == "result", self.error_title(page)
        facts = self.summary_facts(page)
        shots = [self.shot(page, "04-homepage")]
        page.close()
        return (f"Homepage has no legal text; the popup followed its Terms and Privacy links and analyzed both in "
                f"{seconds}s: {facts['level']}, {facts['warnings']}"), shots

    def e05_save_preferences(self):
        page = self.open_popup()
        self.click(page, "nav-prefs")
        self.click(page, "p-seg-photos-yes")
        self.click(page, "p-seg-banking_information-yes")
        page.wait_for_selector('.save-bar[data-dirty="true"]')
        shots = [self.shot(page, "05-prefs-unsaved")]
        self.click(page, "prefs-save")
        page.wait_for_selector('.save-bar .msg[data-state="success"]', timeout=20000)
        shots.append(self.shot(page, "05-prefs-saved"))
        page.close()
        status, saved = http_json("GET", f"{API_URL}/preferences/{self.device_id()}")
        expected = {"location": True, "photos": False, "banking_information": False, "third_party_sharing": True}
        assert status == 200 and saved == expected, saved
        local = self.storage("() => chrome.storage.local.get(['accepted_topics', 'preferences_synced'])")
        assert local["preferences_synced"] is True, local
        return f"Accepted photos + banking and pressed Save. GET /preferences = {json.dumps(saved)}", shots

    def e06_exit_without_saving(self):
        page = self.open_popup()
        self.click(page, "nav-prefs")
        self.click(page, "p-seg-location-yes")
        page.wait_for_selector('.save-bar[data-dirty="true"]')
        page.close()
        page = self.open_popup()
        self.click(page, "nav-prefs")
        location_pressed = page.get_attribute('[data-focus-key="p-seg-location-no"]', "aria-pressed")
        photos_pressed = page.get_attribute('[data-focus-key="p-seg-photos-yes"]', "aria-pressed")
        shots = [self.shot(page, "06-exit-without-saving")]
        page.close()
        _, saved = http_json("GET", f"{API_URL}/preferences/{self.device_id()}")
        assert location_pressed == "true" and photos_pressed == "true", (location_pressed, photos_pressed)
        assert saved["location"] is True, saved
        return "Changed Location to Accept, closed without saving, reopened: Location is still Don't accept, the server is unchanged", shots

    def e07_personalized_and_cache(self):
        self.clear_run()
        rows_before = self.cache_rows()
        target = self.open_site("/terms.html")
        page = self.open_popup(target)
        self.click(page, "analyze")
        outcome, first = self.wait_outcome(page, "terms page with saved preferences")
        assert outcome == "result", self.error_title(page)
        rows_after = self.cache_rows()
        facts = self.summary_facts(page)
        delta = page.inner_text(".delta") if page.query_selector(".delta") else "(no change)"
        shots = [self.shot(page, "07-personalized")]
        self.click(page, "again")
        outcome, second = self.wait_outcome(page, "same page again (cache)")
        assert outcome == "result"
        rows_final = self.cache_rows()
        page.close()
        assert rows_after == rows_before + 1, (rows_before, rows_after)
        assert rows_final == rows_after, "the second run should be a cache HIT"
        return (f"New preferences -> new analysis (cache MISS, rows {rows_before}->{rows_after}) in {first}s: "
                f"{facts['level']}, \"{delta}\". Same page again: cache HIT in {second}s (rows unchanged)"), shots

    def e08_close_popup_early(self):
        self.clear_run()
        target = self.open_site("/privacy.html")
        page = self.open_popup(target)
        self.click(page, "analyze")
        page.wait_for_selector("text=Analyzing the terms", timeout=20000)
        page.close()
        time.sleep(2)
        page = self.open_popup()
        page.wait_for_selector('.panel[role="status"]', timeout=5000)
        shots = [self.shot(page, "08-reopened-loading")]
        outcome, seconds = self.wait_outcome(page, "privacy page (popup closed and reopened)")
        assert outcome == "result", self.error_title(page)
        facts = self.summary_facts(page)
        shots.append(self.shot(page, "08-restored-result"))
        page.close()
        assert "Privacy Policy" in facts["analyzed_page"], facts
        return (f"Popup closed right after the analysis started and reopened 2 s later: it showed the running analysis, then the result "
                f"({facts['level']}, {facts['warnings']}) for \"{facts['analyzed_page']}\""), shots

    def e09_arabic_paste(self):
        self.clear_run()
        documents = json.loads((ROOT / "tests" / "wp4_eval" / "test_documents.json").read_text(encoding="utf-8"))
        text = next(d["terms_text"] for d in documents if d["doc_id"] == "DOC-C")
        page = self.open_popup()
        self.click(page, "lang-ar")
        self.click(page, "nav-paste")
        page.fill("#paste-input", text)
        self.click(page, "paste-go")
        outcome, seconds = self.wait_outcome(page, "pasted DOC-C, Arabic interface")
        assert outcome == "result", self.error_title(page)
        assert page.get_attribute("html", "dir") == "rtl"
        facts = self.summary_facts(page)
        shots = [self.shot(page, "09-arabic-paste")]
        self.click(page, "view-details")
        page.wait_for_selector(".sheet")
        shots.append(self.shot(page, "09-arabic-report"))
        page.keyboard.press("Escape")
        self.click(page, "lang-en")
        page.close()
        return f"Pasted fictional DOC-C (PayNest Wallet) with the Arabic interface: {facts['level']}, {facts['warnings']} in {seconds}s", shots

    def e10_errors(self, no_key_url):
        shots, notes = [], []
        terms = (SITE / "terms.html").read_text(encoding="utf-8")

        # a) server not running
        self.clear_run()
        self.set_server(DEAD_URL)
        page = self.open_popup()
        self.click(page, "nav-paste")
        page.fill("#paste-input", terms)
        self.click(page, "paste-go")
        assert self.wait_outcome(page, "server down")[0] == "error"
        title = self.error_title(page)
        assert "reach the server" in title and page.query_selector('[data-focus-key="to-settings"]'), title
        shots.append(self.shot(page, "10a-server-down"))
        notes.append(f'server down -> "{title}" + Open server settings')
        page.close()

        # b) backend without an API key, shown in Arabic
        self.clear_run()
        self.set_server(no_key_url)
        page = self.open_popup()
        self.click(page, "nav-paste")
        page.fill("#paste-input", terms)
        self.click(page, "paste-go")
        assert self.wait_outcome(page, "no API key")[0] == "error"
        title_en = self.error_title(page)
        self.click(page, "lang-ar")
        title_ar = self.error_title(page)
        assert "set up" in title_en and title_ar == "التحليل غير مفعّل بعد", (title_en, title_ar)
        shots.append(self.shot(page, "10b-no-key-arabic"))
        self.click(page, "lang-en")
        notes.append(f'no API key (HTTP 503) -> "{title_en}" / "{title_ar}"')
        page.close()
        self.set_server(API_URL)

        # c) pasted text too short: stopped in the popup, nothing is sent
        page = self.open_popup()
        self.click(page, "nav-paste")
        page.fill("#paste-input", "Too short to analyze.")
        self.click(page, "paste-go")
        message = page.inner_text("#paste-error")
        assert "at least 50" in message, message
        shots.append(self.shot(page, "10c-too-short"))
        notes.append(f'too short -> "{message}"')
        page.close()

        # d) a page with no legal text
        self.clear_run()
        target = self.open_site("/about.html")
        page = self.open_popup(target)
        self.click(page, "analyze")
        assert self.wait_outcome(page, "page without legal text")[0] == "error"
        title = self.error_title(page)
        assert "No legal text" in title and page.query_selector('.panel.error [data-focus-key="to-paste"]'), title
        shots.append(self.shot(page, "10d-no-legal-text"))
        notes.append(f'no legal text -> "{title}" + Paste text instead')
        page.close()

        # e) no internet connection
        self.clear_run()
        page = self.open_popup(target)
        self.context.set_offline(True)
        try:
            self.click(page, "analyze")
            page.wait_for_selector(".panel.error", timeout=10000)
            title = self.error_title(page)
            assert "internet" in title, title
            shots.append(self.shot(page, "10e-offline"))
            notes.append(f'offline -> "{title}"')
        finally:
            self.context.set_offline(False)
            page.close()
        return "; ".join(notes), shots

    def e11_offline_save_then_sync(self):
        self.set_server(DEAD_URL)
        page = self.open_popup()
        self.click(page, "nav-prefs")
        self.click(page, "p-seg-location-yes")
        self.click(page, "prefs-save")
        page.wait_for_selector('.save-bar .msg[data-state="warn"]', timeout=20000)
        message = page.inner_text(".save-bar .msg")
        shots = [self.shot(page, "11-saved-locally")]
        page.close()
        _, before = http_json("GET", f"{API_URL}/preferences/{self.device_id()}")
        assert before["location"] is True, "the server must not have changed yet"

        self.set_server(API_URL)
        self.clear_run()
        documents = json.loads((ROOT / "tests" / "wp4_eval" / "test_documents.json").read_text(encoding="utf-8"))
        text = next(d["terms_text"] for d in documents if d["doc_id"] == "DOC-A")
        page = self.open_popup()
        self.click(page, "nav-paste")
        page.fill("#paste-input", text)
        self.click(page, "paste-go")
        outcome, seconds = self.wait_outcome(page, "pasted DOC-A after an offline save")
        page.close()
        _, after = http_json("GET", f"{API_URL}/preferences/{self.device_id()}")
        assert outcome == "result" and after["location"] is False, after
        return (f'Saved with the server down: "{message}". Next analysis sent them first: '
                f"location {before['location']} -> {after['location']}, then analyzed in {seconds}s"), shots


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--out", default=str(ROOT / "docs"), help="where screenshots/ and wp8_logs/ go")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running the live end-to-end test.")

    out = Path(args.out)
    shots_dir = out / "screenshots"
    logs_dir = out / "wp8_logs"
    shots_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="aamen_wp8_e2e_"))
    extension_copy = work / "extension"
    shutil.copytree(EXTENSION, extension_copy)  # Chromium writes nothing into the project folder
    db_path = work / "aamen.sqlite3"
    started = now()

    site = start_site()
    backend_log = open(logs_dir / "e2e_backend.log", "w", encoding="utf-8")
    no_key_log = open(logs_dir / "e2e_backend_no_key.log", "w", encoding="utf-8")
    backend = start_backend(8000, db_path, backend_log)
    no_key = start_backend(8001, work / "no_key.sqlite3", no_key_log, with_key=False)

    try:
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(work / "profile"),
                channel="chromium",
                headless=not args.headed,
                device_scale_factor=2,
                args=[f"--disable-extensions-except={extension_copy}", f"--load-extension={extension_copy}"],
            )
            run = Run(context, shots_dir, db_path)
            agent = run.site.evaluate("navigator.userAgent")
            browser_version = re.search(r"Chrome/([\d.]+)", agent).group(1)

            run.scenario(1, "Backend connection from Server settings", "Integration",
                         "Default server works without a permission step; /health reports ok", run.e01_connection)
            run.scenario(2, "Analyze an open Terms and Conditions page", "UC-2",
                         "Extract -> service worker -> backend -> AI -> PDPL -> result with rating, summary and warnings",
                         run.e02_terms_page)
            if hasattr(run, "e02_page"):
                run.scenario(3, "View Details report with PDPL references", "UC-3",
                             "Full report of every clause with PDPL assessment and official links; closes back to the popup",
                             run.e03_report)
            run.scenario(4, "Homepage: follow the site's legal links", "UC-2",
                         "Terms and Privacy links are found and both documents analyzed", run.e04_homepage)
            run.scenario(5, "Save preferences (popup -> WP6 database)", "UC-1",
                         "Unsaved changes shown; Save stores them; not-accepted topics are stored as extra attention",
                         run.e05_save_preferences)
            run.scenario(6, "Exit without saving", "UC-1 alt. 2",
                         "Preferences are not updated", run.e06_exit_without_saving)
            run.scenario(7, "Saved preferences used in the next analysis, then cache", "UC-1 step 5 / WP6",
                         "New analysis with WP4 personalization (cache MISS); same request again is a cache HIT",
                         run.e07_personalized_and_cache)
            run.scenario(8, "Popup closed during the analysis", "Integration",
                         "Reopened popup shows the running analysis and then its result", run.e08_close_popup_early)
            run.scenario(9, "Arabic interface with pasted text", "UC-2 (manual paste)",
                         "Pasted text analyzed; result and report shown right-to-left in Arabic", run.e09_arabic_paste)
            run.scenario(10, "Error messages", "UC-2 alt. 1-3",
                         "Clear messages for server down, no API key (EN/AR), short text, no legal text, offline",
                         lambda: run.e10_errors(NO_KEY_URL))
            run.scenario(11, "Preferences saved while the server is down", "UC-1 / Integration",
                         "Saved on the device, then sent to the server before the next analysis",
                         run.e11_offline_save_then_sync)
            context.close()
    finally:
        for process in (backend, no_key):
            process.terminate()
            process.wait(timeout=20)
        backend_log.close()
        no_key_log.close()
        site.shutdown()

    passed = sum(r["passed"] for r in run.results)
    report = {
        "started": started,
        "finished": now(),
        "browser": f"Chromium {browser_version} (Playwright, unpacked extension)",
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06"),
        "passed": passed,
        "total": len(run.results),
        "scenarios": run.results,
        "analysis_timings": run.timings,
    }
    (logs_dir / "e2e_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    results_file = logs_dir / "e2e_results.json"
    shown = results_file.relative_to(ROOT) if results_file.is_relative_to(ROOT) else results_file
    print(f"\n{passed}/{len(run.results)} scenarios passed. Results: {shown}")
    if passed != len(run.results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
