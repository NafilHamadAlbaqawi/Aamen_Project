"""WP9: count every OpenAI call made by the evaluation scripts and stop before the spending limit.

install() wraps the SDK's Responses.parse, which is the only call the backend uses
(backend/analysis/openai_client.py). Each call's real token usage is added to results/usage.json,
so the total covers all WP9 runs together. Before a call, the script stops with BudgetExceeded if the
total plus a safety margin for that call would pass the limit.
"""

import json
import os
import threading
import time
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
USAGE_FILE = RESULTS / "usage.json"

# US dollars per 1M tokens (published prices). Unknown models use the gpt-4o row.
PRICES = {
    "gpt-4o-2024-08-06": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
}
DEFAULT_LIMIT_USD = float(os.getenv("WP9_BUDGET_USD", "3.00"))
CALL_MARGIN_USD = 0.06   # the largest single call seen (PDPL screening) costs less than this


class BudgetExceeded(RuntimeError):
    """Raised before a call that could pass the spending limit."""


def call_cost(model, input_tokens, cached_tokens, output_tokens):
    price = PRICES.get(model, PRICES["gpt-4o"])
    fresh = max(0, input_tokens - cached_tokens)
    return (fresh * price["input"] + cached_tokens * price["cached_input"]
            + output_tokens * price["output"]) / 1_000_000


class Ledger:
    """The running total, kept in results/usage.json between script runs."""

    def __init__(self, path=USAGE_FILE, limit=DEFAULT_LIMIT_USD):
        self.path = Path(path)
        self.limit = limit
        self.lock = threading.Lock()
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {"limit_usd": limit, "total_usd": 0.0, "calls": 0, "tokens": {"input": 0, "output": 0},
                         "by_run": {}}
        self.run = "unnamed"
        self.log = []   # (stage schema, seconds, usd) of each call in this process, read by run_eval.py

    def check(self):
        with self.lock:
            if self.data["total_usd"] + CALL_MARGIN_USD > self.limit:
                raise BudgetExceeded(
                    f"Stopped before the spending limit: {self.data['total_usd']:.3f} of {self.limit:.2f} USD used.")

    def add(self, model, schema, seconds, input_tokens, cached_tokens, output_tokens):
        cost = call_cost(model, input_tokens, cached_tokens, output_tokens)
        with self.lock:
            run = self.data["by_run"].setdefault(self.run, {"calls": 0, "usd": 0.0, "stages": {}})
            stage = run["stages"].setdefault(schema, {"calls": 0, "usd": 0.0, "seconds": 0.0})
            for bucket in (run, stage):
                bucket["calls"] += 1
                bucket["usd"] = round(bucket["usd"] + cost, 6)
            stage["seconds"] = round(stage["seconds"] + seconds, 2)
            self.data["calls"] += 1
            self.data["tokens"]["input"] += input_tokens
            self.data["tokens"]["output"] += output_tokens
            self.data["total_usd"] = round(self.data["total_usd"] + cost, 6)
            self.data["limit_usd"] = self.limit
            self.data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            self.log.append((schema, round(seconds, 2), round(cost, 6)))
        return cost


_installed = None


def install(run_name, ledger=None):
    """Track and limit every Responses.parse call in this process. Returns the ledger."""
    global _installed
    from openai.resources.responses import Responses

    led = ledger or Ledger()
    led.run = run_name
    if _installed is None:
        original = Responses.parse

        def tracked_parse(self, *args, **kwargs):
            _installed.check()
            start = time.perf_counter()
            response = original(self, *args, **kwargs)
            seconds = time.perf_counter() - start
            usage = getattr(response, "usage", None)
            schema = getattr(kwargs.get("text_format"), "__name__", "unknown")
            if usage is not None:
                details = getattr(usage, "input_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) or 0
                _installed.add(kwargs.get("model", "gpt-4o"), schema, seconds,
                               usage.input_tokens, cached, usage.output_tokens)
            return response

        Responses.parse = tracked_parse
    _installed = led
    return led
