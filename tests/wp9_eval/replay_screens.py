"""WP9: before/after screenshots of the pop-up from saved results. No API calls.

"Before" shows a baseline result in the pop-up as it was before WP9 (the extension files from git commit
f4ee584, the WP8 branch head); "after" shows the final result in the current pop-up. In both, the pop-up's
WP2_ANALYZE message is answered from results/*.json instead of the backend, so nothing else changes.

Needs Playwright with Chromium (see tests/wp8_e2e/README.md). Run from the project folder:
    python tests/wp9_eval/replay_screens.py
Writes docs/screenshots/WP9-*.png.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHOTS = ROOT / "docs" / "screenshots"
BEFORE_COMMIT = "f4ee584"
EXTENSION_FILES = ("manifest.json", "background.js", "content.js", "popup.html", "popup.css", "popup.js", "ui-strings.js")

# (document, screenshot name, also open View Details)
SHOTS_TO_TAKE = [
    ("WP8-RIHLA-PRIVACY", "privacy-policy", False),
    ("WP9-SANAD", "fitness-policy", False),
    ("WP8-RIHLA-TERMS", "risky-terms", True),
]

STUB = """
(() => {
  const RESULT = %s;
  const realSend = chrome.runtime.sendMessage.bind(chrome.runtime);
  chrome.runtime.sendMessage = async message => {
    if (message && message.type === 'WP2_ANALYZE') return { ok: true, data: RESULT };
    return realSend(message);
  };
})();
"""


def extension_at(commit, folder):
    folder.mkdir(parents=True)
    for name in EXTENSION_FILES:
        content = subprocess.run(["git", "show", f"{commit}:extension/{name}"], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        (folder / name).write_bytes(content)
    return folder


def saved_result(tag, doc_id):
    runs = json.loads((HERE / "results" / f"{tag}.json").read_text(encoding="utf-8"))["runs"]
    return next(r["response"] for r in runs if r["doc_id"] == doc_id and r["repeat"] == 1 and r["status"] == "ok")


def capture(playwright, extension, label, tag, work):
    context = playwright.chromium.launch_persistent_context(
        str(work / f"profile-{label}"), channel="chromium", headless=True, device_scale_factor=2,
        args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
    try:
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        extension_id = worker.url.split("/")[2]
        for doc_id, name, report in SHOTS_TO_TAKE:
            page = context.new_page()
            page.set_viewport_size({"width": 390, "height": 600})
            page.add_init_script(STUB % json.dumps(saved_result(tag, doc_id), ensure_ascii=False))
            page.goto(f"chrome-extension://{extension_id}/popup.html")
            page.click('[data-focus-key="nav-paste"]')
            page.fill("#paste-input", "Saved WP9 evaluation result, replayed for a screenshot. " * 2)
            page.click('[data-focus-key="paste-go"]')
            page.wait_for_selector(".gauge-card")
            page.screenshot(path=str(SHOTS / f"WP9-{label}-{name}.png"))
            print(f"WP9-{label}-{name}.png  ({doc_id}, {tag})")
            if report:
                page.click('[data-focus-key="view-details"]')
                page.wait_for_selector(".sheet")
                first_ref = page.locator(".sheet .assess >> nth=0")
                first_ref.scroll_into_view_if_needed()
                page.screenshot(path=str(SHOTS / f"WP9-{label}-{name}-report.png"))
                print(f"WP9-{label}-{name}-report.png")
            page.close()
    finally:
        context.close()


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="aamen_wp9_replay_"))
    try:
        before = extension_at(BEFORE_COMMIT, work / "before")
        after = work / "after"
        shutil.copytree(ROOT / "extension", after)
        with sync_playwright() as playwright:
            capture(playwright, before, "before", "baseline", work)
            capture(playwright, after, "after", "final", work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
