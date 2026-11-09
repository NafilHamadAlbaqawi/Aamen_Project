"""Run the WP8 integration checks from the VS Code Run Python File button; no typed commands.

1. The full backend test suite (WP4, WP5, WP6 and WP8 tests), so integration did not break earlier work.
2. The service worker tests in tests/wp8_js (needs Node.js 18 or newer).
No OpenAI requests are made. The live browser test is separate: see tests/wp8_e2e/README.md.
"""

from pathlib import Path
import shutil
import subprocess
import sys
import unittest

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

print("== Backend tests (WP4-WP8) ==")
suite = unittest.defaultTestLoader.discover(
    start_dir=str(root / "tests"), pattern="test_*.py", top_level_dir=str(root)
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
failed = not result.wasSuccessful() or bool(result.skipped)

print("\n== Service worker tests (Node.js) ==")
node = shutil.which("node")
if node is None:
    print("Node.js was not found, so the service worker tests could not run.")
    failed = True
else:
    js = subprocess.run([node, "--test", str(root / "tests" / "wp8_js")], cwd=root)
    failed = failed or js.returncode != 0

if failed:
    raise SystemExit(1)
print("\nAll WP8 checks passed.")
