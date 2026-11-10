"""WP9: run the analysis pipeline on the test corpus and save everything for scoring.

Full run (all four model stages per document, like POST /analyze but without the cache):
    python tests/wp9_eval/run_eval.py --tag baseline
Stage re-run (after changing one prompt, re-run only that stage on the saved outputs of an earlier run):
    python tests/wp9_eval/run_eval.py --tag v2 --from baseline --rerun classify   # classify + summary
    python tests/wp9_eval/run_eval.py --tag v2b --from v2 --rerun pdpl
Options: --docs WP9-SANAD WP4-DOC-D, --repeats 2.
Needs OPENAI_API_KEY. Every call is counted in results/usage.json and the run stops before the spending limit
(see budget.py). Output: results/<tag>.json. Score it with score.py (no API calls).
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from openai import OpenAIError  # noqa: E402

from backend.analysis.openai_client import AnalysisFailure  # noqa: E402
from backend.analysis.pipeline import analyze_terms, screen_pdpl  # noqa: E402
from backend.analysis.rating import calculate_rating  # noqa: E402
from backend.analysis.risk_classifier import classify_clauses  # noqa: E402
from backend.analysis.schemas import AnalysisResponse, ExtractedClause, FlaggedClause  # noqa: E402
from backend.analysis.summary_generator import generate_summary  # noqa: E402
from backend.pdpl.schemas import PDPLCheckResult  # noqa: E402
from backend.prompt_adjuster import build_prompt_bundle  # noqa: E402
from tests.wp9_eval.budget import BudgetExceeded, install  # noqa: E402
from tests.wp9_eval.corpus import load_corpus  # noqa: E402

RESULTS = HERE / "results"
STAGES = ("extract", "classify", "summary", "pdpl")


class _FailureLog(logging.Handler):
    """Keeps the reason when the pipeline logs a PDPL failure, so it is saved with the run."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.reasons = []

    def emit(self, record):
        if record.exc_info and record.exc_info[1] is not None:
            self.reasons.append(f"{type(record.exc_info[1]).__name__}: {record.exc_info[1]}")
        else:
            self.reasons.append(record.getMessage())


FAILURES = _FailureLog()
logging.getLogger("backend.analysis.pipeline").addHandler(FAILURES)
logging.getLogger("backend.analysis.pipeline").propagate = False


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def rerun_stages(saved, rerun):
    """Rebuild an AnalysisResponse from a saved one, running only the requested stages again."""
    prompts = build_prompt_bundle(None)
    classified = [FlaggedClause.model_validate(c) for c in saved["flagged_clauses"]]
    summary_en, summary_ar = saved["summary_en"], saved["summary_ar"]
    pdpl = PDPLCheckResult.model_validate(saved["pdpl"]) if saved.get("pdpl") else None

    if "classify" in rerun:
        extracted = [ExtractedClause(category=c.category, source_excerpt=c.source_excerpt) for c in classified]
        classified = classify_clauses(extracted, prompts.classification_instructions)
    if "summary" in rerun:
        summary = generate_summary(classified, prompts.summary_instructions)
        summary_en, summary_ar = summary.summary_en, summary.summary_ar
    if "pdpl" in rerun:
        try:
            pdpl = screen_pdpl(classified)  # same as the backend, including its retry
        except BudgetExceeded:
            raise
        except Exception as error:  # same fallback as backend/analysis/pipeline.py
            FAILURES.reasons.append(f"{type(error).__name__}: {error}")
            pdpl = PDPLCheckResult(status="unavailable", disclaimer="PDPL screening failed; no PDPL conclusion is available.")

    score, level = calculate_rating(classified)
    return AnalysisResponse(
        status="completed", analysis_mode="openai", risk_score=score, risk_level=level,
        summary_en=summary_en, summary_ar=summary_ar, flagged_clauses=classified,
        input_truncated=saved.get("input_truncated", False), disclaimer=saved.get("disclaimer", ""), pdpl=pdpl,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--docs", nargs="+")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--from", dest="source", help="tag of an earlier run to re-use")
    parser.add_argument("--rerun", nargs="+", choices=STAGES, help="stages to run again (needs --from)")
    args = parser.parse_args()

    rerun = set(args.rerun or [])
    if rerun and not args.source:
        parser.error("--rerun needs --from")
    if "extract" in rerun:
        rerun = set(STAGES)
    if "classify" in rerun:
        rerun.add("summary")  # the summary is written from the classified clauses

    documents = [d for d in load_corpus() if not args.docs or d["doc_id"] in args.docs]
    source = {}
    if args.source:
        saved = json.loads((RESULTS / f"{args.source}.json").read_text(encoding="utf-8"))
        source = {(r["doc_id"], r["repeat"]): r for r in saved["runs"] if r["status"] == "ok"}

    ledger = install(args.tag)
    out = {"tag": args.tag, "from": args.source, "rerun": sorted(rerun) if rerun else "all",
           "commit": git_commit(), "started": time.strftime("%Y-%m-%d %H:%M:%S %z"), "runs": []}
    target = RESULTS / f"{args.tag}.json"
    RESULTS.mkdir(exist_ok=True)

    def save():
        out["finished"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
        out["usd_total_so_far"] = ledger.data["total_usd"]
        target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    stopped = False
    for doc in documents:
        for repeat in range(1, args.repeats + 1):
            if stopped:
                break
            run = {"doc_id": doc["doc_id"], "repeat": repeat}
            ledger.log.clear()
            FAILURES.reasons.clear()
            start = time.perf_counter()
            try:
                if rerun and rerun != set(STAGES):
                    base = source.get((doc["doc_id"], repeat)) or source.get((doc["doc_id"], 1))
                    if base is None:
                        raise ValueError(f"no saved run for {doc['doc_id']} in {args.source}")
                    response = rerun_stages(base["response"], rerun)
                else:
                    response = analyze_terms(doc["terms_text"])
                run.update(status="ok", response=response.model_dump(mode="json"))
            except BudgetExceeded as error:
                run.update(status="stopped", error=str(error))
                stopped = True
            except (AnalysisFailure, OpenAIError, ValueError) as error:
                run.update(status="error", error=f"{type(error).__name__}: {error}")
            run["seconds"] = round(time.perf_counter() - start, 1)
            run["calls"] = [{"stage": s, "seconds": t, "usd": c} for s, t, c in ledger.log]
            if FAILURES.reasons:
                run["pdpl_failure"] = list(FAILURES.reasons)
            out["runs"].append(run)
            level = run.get("response", {}).get("risk_level", run.get("error", ""))
            note = f" [PDPL failed: {run['pdpl_failure'][0]}]" if run.get("pdpl_failure") else ""
            print(f"{doc['doc_id']:18s} r{repeat} -> {run['status']:7s} {level} ({run['seconds']}s, "
                  f"total {ledger.data['total_usd']:.3f} USD){note}", flush=True)
            save()

    save()
    print(f"saved {target.relative_to(ROOT)}; spent so far {ledger.data['total_usd']:.3f} of "
          f"{ledger.limit:.2f} USD")
    if stopped:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
