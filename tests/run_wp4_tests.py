"""Run WP4 tests from the VS Code Run Python File button; no typed commands."""

from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

suite = unittest.defaultTestLoader.discover(
    start_dir=str(root / "tests"), pattern="test_wp4*.py"
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful() or result.skipped:
    raise SystemExit(1)
