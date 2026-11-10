"""WP9: score saved runs against the gold labels. No API calls.

    python tests/wp9_eval/score.py baseline            # one run
    python tests/wp9_eval/score.py baseline final      # side by side

Accuracy is checked in both directions: rating something worse than it is (over-cautious) and better than it
is (missed risk) are both errors. Writes results/score_<tag>.json and prints a Markdown table.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from tests.wp9_eval.corpus import load_corpus, matches, normalize  # noqa: E402

RESULTS = HERE / "results"
RANK = {"low": 0, "medium": 1, "high": 2}
LEVEL_RANK = {"Safe": 0, "Moderate": 1, "High Risk": 2}

# Words that make an explanation sound unsure or warning-like without adding facts. A word that is also in
# the clause itself (for example "may" in "We may share") is not counted: then it is accurate, not hedging.
HEDGES = [
    "may", "might", "could", "potentially", "possibly", "perhaps", "unclear", "ambiguous", "vague",
    "not specified", "does not specify", "not clear", "lack of clarity", "it is advisable", "users should",
    "be cautious", "caution", "be aware", "consult", "review carefully", "it is important to",
    "raises concerns", "could be a concern",
]
HEDGE_RE = re.compile(r"\b(" + "|".join(re.escape(h) for h in HEDGES) + r")\b", re.I)
ARTICLE_RE = re.compile(r"(\barticle\s*\d+|المادة\s*\d+|\bPDPL\b[^.]*\bviolat)", re.I)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+(?=\s|$)")


def hedges_in(explanation, excerpt):
    clause = normalize(excerpt)
    return [h for h in HEDGE_RE.findall(explanation) if normalize(h) not in clause]


def score_response(doc, response):
    clauses = response["flagged_clauses"]
    findings = {f["clause_id"]: f for f in ((response.get("pdpl") or {}).get("findings") or [])}
    out = {"doc_id": doc["doc_id"], "expected_level": doc["expected_level"], "level": response["risk_level"],
           "score": response["risk_score"], "clauses": len(clauses)}
    out["level_diff"] = LEVEL_RANK[response["risk_level"]] - LEVEL_RANK[doc["expected_level"]]

    severity, pdpl, missed = [], [], []
    for provision in doc["provisions"]:
        hits = [c for c in clauses if matches(provision["anchor"], c["source_excerpt"])]
        if not hits:
            if provision["severity"] != "low":
                missed.append(provision["anchor"])
            continue
        worst = max(hits, key=lambda c: RANK[c["severity"]])
        severity.append({"anchor": provision["anchor"], "expected": provision["severity"],
                         "got": worst["severity"], "diff": RANK[worst["severity"]] - RANK[provision["severity"]]})
        if provision.get("pdpl"):
            got = next((findings[c["clause_id"]]["assessment"] for c in hits if c["clause_id"] in findings), None)
            pdpl.append({"anchor": provision["anchor"], "expected": provision["pdpl"], "got": got})
    out.update(severity=severity, pdpl=pdpl, missed_risks=missed)

    matched_ids = {c["clause_id"] for c in clauses
                   if any(matches(p["anchor"], c["source_excerpt"]) for p in doc["provisions"])}
    out["extra_flags"] = [{"excerpt": c["source_excerpt"], "severity": c["severity"]}
                          for c in clauses if c["clause_id"] not in matched_ids and c["severity"] != "low"]

    explanations = [(c["explanation_en"], c["source_excerpt"]) for c in clauses]
    explanations += [(f["explanation_en"], f["source_excerpt"]) for f in findings.values()]
    hedged = [(text, hedges_in(text, excerpt)) for text, excerpt in explanations]
    out["explanations"] = len(explanations)
    out["hedged_explanations"] = sum(bool(h) for _, h in hedged)
    out["hedge_examples"] = [{"text": t, "words": h} for t, h in hedged if h][:3]
    out["assessments"] = dict(Counter(f["assessment"] for f in findings.values()))
    out["pdpl_status"] = (response.get("pdpl") or {}).get("status")
    out["summary_sentences_en"] = len(SENTENCE_RE.findall(response["summary_en"]))
    out["verbatim"] = sum(c["source_excerpt"] in doc["terms_text"] for c in clauses)
    texts = [response["summary_en"], response["summary_ar"]] + [c["explanation_en"] + " " + c["explanation_ar"] for c in clauses]
    out["invented_article"] = bool(ARTICLE_RE.search(" ".join(texts)))
    return out


def summarize(scored):
    sev = [s for d in scored for s in d["severity"]]
    pdpl = [p for d in scored for p in d["pdpl"] if p["got"] is not None]
    assessments = Counter()
    for d in scored:
        assessments.update(d["assessments"])
    findings = sum(assessments.values())
    benign = [d for d in scored if d["expected_level"] == "Safe"]
    risky = [d for d in scored if d["expected_level"] == "High Risk"]
    pct = lambda n, total: round(100 * n / total, 1) if total else None  # noqa: E731
    return {
        "documents": len(scored),
        "level_exact_pct": pct(sum(d["level_diff"] == 0 for d in scored), len(scored)),
        "level_over": sum(d["level_diff"] > 0 for d in scored),
        "level_under": sum(d["level_diff"] < 0 for d in scored),
        "benign_rated_safe": f"{sum(d['level'] == 'Safe' for d in benign)}/{len(benign)}",
        "risky_rated_high": f"{sum(d['level'] == 'High Risk' for d in risky)}/{len(risky)}",
        "severity_matched": len(sev),
        "severity_exact_pct": pct(sum(s["diff"] == 0 for s in sev), len(sev)),
        "severity_within_one_pct": pct(sum(abs(s["diff"]) <= 1 for s in sev), len(sev)),
        "severity_over_pct": pct(sum(s["diff"] > 0 for s in sev), len(sev)),
        "severity_under_pct": pct(sum(s["diff"] < 0 for s in sev), len(sev)),
        "missed_risks": sum(len(d["missed_risks"]) for d in scored),
        "extra_medium_high_flags": sum(len(d["extra_flags"]) for d in scored),
        "pdpl_labelled_found": len(pdpl),
        "pdpl_accuracy_pct": pct(sum(p["got"] == p["expected"] for p in pdpl), len(pdpl)),
        "pdpl_needs_context_pct": pct(assessments["needs_context"], findings),
        "pdpl_assessments": dict(assessments),
        "hedged_explanations_pct": pct(sum(d["hedged_explanations"] for d in scored),
                                       sum(d["explanations"] for d in scored)),
        "summaries_over_4_sentences": sum(d["summary_sentences_en"] > 4 for d in scored),
        "verbatim_pct": pct(sum(d["verbatim"] for d in scored), sum(d["clauses"] for d in scored)),
        "invented_article_runs": sum(d["invented_article"] for d in scored),
    }


def score_tag(tag, documents=None):
    documents = {d["doc_id"]: d for d in (documents or load_corpus())}
    data = json.loads((RESULTS / f"{tag}.json").read_text(encoding="utf-8"))
    ok = [r for r in data["runs"] if r["status"] == "ok"]
    scored = [dict(score_response(documents[r["doc_id"]], r["response"]), repeat=r["repeat"],
                   seconds=r["seconds"]) for r in ok]
    seconds = sorted(r["seconds"] for r in ok if data["rerun"] == "all")
    summary = summarize(scored)
    summary["runs_ok"] = f"{len(ok)}/{len(data['runs'])}"
    if seconds:
        summary["seconds_mean"] = round(sum(seconds) / len(seconds), 1)
        summary["seconds_range"] = [seconds[0], seconds[-1]]
    return {"tag": tag, "summary": summary, "documents": scored}


def main():
    tags = sys.argv[1:] or ["baseline"]
    results = [score_tag(tag) for tag in tags]
    for result in results:
        (RESULTS / f"score_{result['tag']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    keys = list(results[0]["summary"])
    print("| Metric | " + " | ".join(r["tag"] for r in results) + " |")
    print("|---|" + "---|" * len(results))
    for key in keys:
        print(f"| {key} | " + " | ".join(str(r["summary"].get(key)) for r in results) + " |")
    print()
    print("| Document | expected | " + " | ".join(r["tag"] for r in results) + " |")
    print("|---|---|" + "---|" * len(results))
    for doc in results[0]["documents"]:
        if doc["repeat"] != 1:
            continue
        cells = []
        for r in results:
            d = next((x for x in r["documents"] if x["doc_id"] == doc["doc_id"] and x["repeat"] == 1), None)
            cells.append(f"{d['level']} {d['score']}" if d else "-")
        print(f"| {doc['doc_id']} | {doc['expected_level']} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
