"""WP9 offline tests for the evaluation tools themselves (corpus, scorer, spending limit). No API calls."""

import json
import tempfile
import unittest
from pathlib import Path

from backend.analysis.rating import calculate_rating
from backend.analysis.schemas import FlaggedClause
from tests.wp9_eval.budget import BudgetExceeded, Ledger, call_cost
from tests.wp9_eval.corpus import load_corpus, matches
from tests.wp9_eval.score import hedges_in, score_response, summarize


def response_for(doc, shift=0, assessment=None, explanation="The clause allows this."):
    """A response that flags every gold provision, with each severity moved by `shift` levels."""
    order = ["low", "medium", "high"]
    clauses, findings = [], []
    for number, provision in enumerate(doc["provisions"], start=1):
        severity = order[max(0, min(2, order.index(provision["severity"]) + shift))]
        clause_id = f"clause_{number:03d}"
        clauses.append({"clause_id": clause_id, "category": "other", "severity": severity,
                        "source_excerpt": provision["anchor"], "explanation_en": explanation,
                        "explanation_ar": "شرح."})
        if provision.get("pdpl"):
            findings.append({"clause_id": clause_id, "source_excerpt": provision["anchor"],
                             "assessment": assessment or provision["pdpl"], "explanation_en": explanation,
                             "explanation_ar": "شرح.", "legal_references": []})
    score, level = calculate_rating([FlaggedClause.model_validate(c) for c in clauses])
    return {"risk_score": score, "risk_level": level, "summary_en": "One. Two.", "summary_ar": "واحد.",
            "flagged_clauses": clauses, "pdpl": {"status": "completed", "findings": findings}}


class WP9EvalToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = load_corpus()

    def test_01_corpus_is_valid_and_balanced(self):
        self.assertEqual(len(self.docs), 10)
        levels = [d["expected_level"] for d in self.docs]
        self.assertGreaterEqual(levels.count("Safe"), 3, "benign documents are needed to measure over-caution")
        self.assertGreaterEqual(levels.count("High Risk"), 3, "risky documents are needed to measure missed risks")
        self.assertEqual({d["language"] for d in self.docs}, {"en", "ar"})

    def test_02_gold_severities_give_gold_levels(self):
        for doc in self.docs:
            clauses = [FlaggedClause(clause_id="c", category="other", severity=p["severity"],
                                     source_excerpt="x" * 15, explanation_en="e", explanation_ar="ش")
                       for p in doc["provisions"]]
            self.assertEqual(calculate_rating(clauses)[1], doc["expected_level"], doc["doc_id"])

    def test_03_matching_excerpts_to_anchors(self):
        anchor = "share transaction data with credit bureaus and our banking partners"
        self.assertTrue(matches(anchor, "We may share transaction data with credit bureaus and our banking partners to assess eligibility."))
        self.assertTrue(matches(anchor, "transaction data with credit bureaus"))
        self.assertFalse(matches(anchor, "You may close your wallet at any time after withdrawing your balance."))
        self.assertTrue(matches("لمدة غير محددة حتى بعد حذف حسابك", "نحتفظ ببياناتك الشخصية لمدة غير محددة حتى بعد حذف حسابك."))

    def test_04_perfect_response_scores_perfectly(self):
        scored = [score_response(d, response_for(d)) for d in self.docs]
        summary = summarize(scored)
        self.assertEqual(summary["level_exact_pct"], 100.0)
        self.assertEqual(summary["severity_exact_pct"], 100.0)
        self.assertEqual(summary["pdpl_accuracy_pct"], 100.0)
        self.assertEqual((summary["missed_risks"], summary["extra_medium_high_flags"]), (0, 0))
        self.assertEqual(summary["hedged_explanations_pct"], 0.0)

    def test_05_over_and_under_caution_are_both_errors(self):
        over = summarize([score_response(d, response_for(d, shift=1)) for d in self.docs])
        under = summarize([score_response(d, response_for(d, shift=-1)) for d in self.docs])
        self.assertGreater(over["severity_over_pct"], 0)
        self.assertEqual(over["severity_under_pct"], 0)
        self.assertGreater(over["level_over"], 0)
        self.assertGreater(under["severity_under_pct"], 0)
        self.assertGreater(under["level_under"], 0)
        self.assertLess(over["severity_exact_pct"], 100)
        self.assertLess(under["severity_exact_pct"], 100)

    def test_06_needs_context_everywhere_is_measured(self):
        summary = summarize([score_response(d, response_for(d, assessment="needs_context")) for d in self.docs])
        self.assertEqual(summary["pdpl_needs_context_pct"], 100.0)
        self.assertEqual(summary["pdpl_accuracy_pct"], 0.0)

    def test_07_hedging_counts_only_words_not_in_the_clause(self):
        self.assertEqual(hedges_in("This may reduce privacy and is unclear.", "We share your email."), ["may", "unclear"])
        self.assertEqual(hedges_in("The company may share your email.", "We may share your email."), [])
        doc = self.docs[0]
        summary = summarize([score_response(doc, response_for(doc, explanation="Users should be cautious; this could be risky."))])
        self.assertEqual(summary["hedged_explanations_pct"], 100.0)

    def test_08_missed_risk_is_reported(self):
        doc = next(d for d in self.docs if d["doc_id"] == "WP9-LAMHA")
        response = response_for(doc)
        response["flagged_clauses"] = [c for c in response["flagged_clauses"] if c["severity"] != "high"]
        self.assertEqual(len(score_response(doc, response)["missed_risks"]), 2)

    def test_09_spending_limit_stops_before_the_call(self):
        self.assertAlmostEqual(call_cost("gpt-4o-2024-08-06", 1_000_000, 0, 0), 2.50)
        self.assertAlmostEqual(call_cost("gpt-4o-2024-08-06", 1_000_000, 1_000_000, 1_000_000), 11.25)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "usage.json"
            ledger = Ledger(path=path, limit=0.10)
            ledger.run = "test"
            ledger.check()
            ledger.add("gpt-4o", "SummaryOutput", 1.0, 10_000, 0, 1_500)  # 0.025 + 0.015 = 0.04 USD
            ledger.check()
            ledger.add("gpt-4o", "SummaryOutput", 1.0, 10_000, 0, 1_500)
            with self.assertRaises(BudgetExceeded):
                ledger.check()
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["calls"], 2)
            self.assertAlmostEqual(saved["total_usd"], 0.08)
            self.assertEqual(Ledger(path=path, limit=0.10).data["total_usd"], saved["total_usd"])


if __name__ == "__main__":
    unittest.main()
