"""Run WP4 prompt-only unit tests from VS Code's Run Python File button."""

from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

suite = unittest.defaultTestLoader.discover(
    start_dir=str(root / "tests"), pattern="test_wp4_prompts.py"
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
