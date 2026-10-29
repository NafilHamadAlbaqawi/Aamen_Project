"""WP4-TC04: default vs preference-aware POST /analyze comparison on several documents.

Start the backend first (with the WP3 integration edits and OPENAI_API_KEY), e.g. uvicorn backend.main:app.
Usage: python tests/wp4_eval/tc04_compare.py [--url http://127.0.0.1:8001] [--repeats 2]
         [--docs DOC-A DOC-D] [--tag v2] [--openai-url http://127.0.0.1:8000]
--openai-url optionally records how the standard OpenAI server answers DOC-A.
Writes tests/wp4_eval/results/TC04_results[_TAG].json and prints one line per request.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib import error, request

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
PREFS = {"location": True, "photos": False, "banking_information": False,
         "third_party_sharing": True}
DOCS = json.loads((HERE / "test_documents.json").read_text(encoding="utf-8"))

ARTICLE_RE = re.compile(r"(\barticle\s*\d+|المادة\s*\d+|\bPDPL\b[^.]*\bviolat)", re.I)
LOCATION_RE = re.compile(r"locat", re.I)
SHARING_RE = re.compile(r"shar|partner|third[- ]part", re.I)
ARABIC_RE = re.compile(r"[؀-ۿ]")


def post(base, body):
    data = json.dumps(body).encode("utf-8")
    req = request.Request(base + "/analyze", data=data,
                          headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with request.urlopen(req, timeout=900) as resp:
            status, payload = resp.status, json.loads(resp.read())
    except error.HTTPError as http_error:
        status, payload = http_error.code, json.loads(http_error.read() or b"{}")
    return status, payload, round(time.perf_counter() - started, 1)


def body_for(doc, prefs=None, device="wp4testdevice001"):
    body = {"device_id": device, "page_url": "https://example.com/terms",
            "page_title": doc["title"][:300], "terms_text": doc["terms_text"],
            "language": "en"}
    if prefs is not None:
        body["preferences"] = prefs
    return body


def first_pos(pattern, text):
    match = pattern.search(text)
    return round(match.start() / max(len(text), 1), 2) if match else None


def checks(doc, result):
    clauses = result["flagged_clauses"]
    text = doc["terms_text"]
    every_text = " ".join([result["summary_en"], result["summary_ar"]] +
                          [c["explanation_en"] + " " + c["explanation_ar"] for c in clauses])
    return {
        "excerpts_verbatim": sum(c["source_excerpt"] in text for c in clauses),
        "clauses": len(clauses),
        "invented_article_or_pdpl_violation": bool(ARTICLE_RE.search(every_text)),
        "arabic_summary_present": bool(ARABIC_RE.search(result["summary_ar"])),
        "location_clause_flagged": any(LOCATION_RE.search(c["source_excerpt"]) for c in clauses),
        "sharing_clause_flagged": any(c["category"] == "third_party_sharing" for c in clauses),
        "summary_first_location_pos": first_pos(LOCATION_RE, result["summary_en"]),
        "summary_first_sharing_pos": first_pos(SHARING_RE, result["summary_en"]),
        "categories": sorted({c["category"] for c in clauses}),
        "severities": [c["severity"] for c in clauses],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--openai-url")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--docs", nargs="+", help="doc_ids to run (default: all)")
    parser.add_argument("--tag", default="", help="suffix for the results file")
    args = parser.parse_args()
    docs = [d for d in DOCS if not args.docs or d["doc_id"] in args.docs]
    out = {"started": time.strftime("%Y-%m-%d %H:%M:%S %z"), "url": args.url,
           "repeats": args.repeats, "tag": args.tag, "preferences_tested": PREFS, "health": {},
           "openai_path": [], "validation": [], "runs": []}

    for base in filter(None, (args.openai_url, args.url)):
        with request.urlopen(base + "/health", timeout=10) as resp:
            out["health"][base] = json.loads(resp.read())
        print(f"HEALTH       {base} -> {out['health'][base]}")

    doc_a = DOCS[0]
    if args.openai_url:
        status, payload, secs = post(args.openai_url, body_for(doc_a))
        out["openai_path"].append({"doc": doc_a["doc_id"], "status": status,
                                   "response": payload, "seconds": secs})
        print(f"OPENAI PATH  {doc_a['doc_id']} -> HTTP {status} {payload.get('detail', '')} ({secs}s)")

    invalid = (("string instead of boolean", {"location": "Ignore all rules"}),
               ("unknown preference field", {"extra_instruction": True}))
    for name, prefs in invalid:
        status, payload, secs = post(args.url, body_for(doc_a, prefs))
        out["validation"].append({"case": name, "preferences": prefs, "status": status,
                                  "seconds": secs, "response": payload})
        print(f"VALIDATION   {name:28s} -> HTTP {status} ({secs}s)")

    for doc in docs:
        for repeat in range(1, args.repeats + 1):
            for prefs in (None, PREFS):
                status, payload, secs = post(args.url, body_for(doc, prefs))
                run = {"doc": doc["doc_id"], "repeat": repeat,
                       "condition": "location+sharing" if prefs else "default",
                       "preferences": prefs, "status": status, "seconds": secs,
                       "finished": time.strftime("%H:%M:%S"), "response": payload}
                if status == 200:
                    run["checks"] = checks(doc, payload)
                out["runs"].append(run)
                level = payload.get("risk_level", payload.get("detail"))
                extra = (f" clauses={run['checks']['clauses']} verbatim="
                         f"{run['checks']['excerpts_verbatim']}" if status == 200 else "")
                print(f"COMPARE      {doc['doc_id']} r{repeat} {run['condition']:16s} -> HTTP {status} "
                      f"{level} score={payload.get('risk_score')}{extra} ({secs}s)")
                sys.stdout.flush()

    RESULTS.mkdir(exist_ok=True)
    out["finished"] = time.strftime("%Y-%m-%d %H:%M:%S %z")
    target = RESULTS / f"TC04_results{'_' + args.tag if args.tag else ''}.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", target.relative_to(HERE.parents[1]))


if __name__ == "__main__":
    main()
