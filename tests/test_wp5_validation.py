
"""WP5 validation tests using simulated AI responses; no API calls."""

import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from backend.analysis.openai_client import AnalysisFailure
from backend.analysis.schemas import FlaggedClause
from backend.pdpl.checker import AIClauseFinding, AIReviewBatch, check_pdpl
from backend.pdpl.retriever import load_knowledge_base


def make_clause(clause_id, category, text):
    return FlaggedClause(
        clause_id=clause_id,
        category=category,
        severity="medium",
        source_excerpt=text,
        explanation_en="Fictional test explanation.",
        explanation_ar="شرح اختباري تجريبي.",
    )


def simulated_ai(schema, instructions, text, output_limit):
    tasks = json.loads(text)
    findings = []
    for task in tasks:
        findings.append(AIClauseFinding(
            clause_id=task["clause_id"],
            assessment="needs_context",
            explanation_en="More context is required.",
            explanation_ar="يلزم المزيد من السياق.",
            reference_ids=[task["legal_context"][0]["id"]],
        ))
    return AIReviewBatch(findings=findings)


class WP5ValidationTests(unittest.TestCase):

    def setUp(self):
        self.retention = make_clause(
            "clause_001", "data_retention",
            "We retain your personal data for five years after account closure.",
        )
        self.unmatched = make_clause(
            "clause_002", "other",
            "This document discusses clouds, trees, chairs, and yellow bicycles.",
        )

    @patch("backend.pdpl.checker.request_structured", side_effect=simulated_ai)
    def test_verified_reference_matches_local_index(self, mocked):
        result = check_pdpl([self.retention])
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.findings[0].source_excerpt, self.retention.source_excerpt)
        reference = result.findings[0].legal_references[0]
        knowledge = load_knowledge_base()
        entries = [a for a in knowledge["articles"] if a["source_id"] == reference.source_id and a["article_id"] == reference.article_id]
        self.assertEqual(len(entries), 1)
        self.assertEqual(reference.excerpt, entries[0]["source_anchor"])
        sources = {s["source_id"]: s["source_url"] for s in knowledge["sources"]}
        self.assertEqual(str(reference.source_url), sources[reference.source_id])
        mocked.assert_called_once()

    @patch("backend.pdpl.checker.request_structured", side_effect=simulated_ai)
    def test_arabic_retention_matches_article_18(self, mocked):
        arabic = make_clause(
            "clause_003", "data_retention",
            "نحتفظ بالبيانات الشخصية لمدة خمس سنوات بعد إغلاق الحساب.",
        )
        result = check_pdpl([arabic])
        self.assertEqual(result.findings[0].legal_references[0].article_id, "Article 18")
        mocked.assert_called_once()

    @patch("backend.pdpl.checker.request_structured", side_effect=simulated_ai)
    def test_partial_when_clause_has_no_legal_context(self, mocked):
        result = check_pdpl([self.retention, self.unmatched])
        self.assertEqual(result.status, "partial")
        self.assertEqual(len(result.findings), 1)
        mocked.assert_called_once()

    @patch("backend.pdpl.checker.request_structured")
    def test_no_context_never_calls_openai(self, mocked):
        result = check_pdpl([self.unmatched])
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.findings, [])
        mocked.assert_not_called()

    @patch("backend.pdpl.checker.request_structured")
    def test_hallucinated_article_id_is_rejected(self, mocked):
        mocked.return_value = AIReviewBatch(findings=[AIClauseFinding(
            clause_id="clause_001",
            assessment="needs_context",
            explanation_en="More context.",
            explanation_ar="يلزم سياق.",
            reference_ids=["nonexistent-article"],
        )])
        with self.assertRaises(AnalysisFailure):
            check_pdpl([self.retention])

    @patch("backend.pdpl.checker.request_structured")
    def test_duplicate_article_citations_are_rejected(self, mocked):
        mocked.return_value = AIReviewBatch(findings=[AIClauseFinding(
            clause_id="clause_001",
            assessment="needs_context",
            explanation_en="More context.",
            explanation_ar="يلزم سياق.",
            reference_ids=["pdpl-18", "pdpl-18"],
        )])
        with self.assertRaises(AnalysisFailure):
            check_pdpl([self.retention])

    @patch("backend.pdpl.checker.request_structured")
    def test_missing_ai_finding_is_rejected(self, mocked):
        mocked.return_value = AIReviewBatch(findings=[])
        with self.assertRaises(AnalysisFailure):
            check_pdpl([self.retention])

    def test_duplicate_clause_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            check_pdpl([self.retention, self.retention])

    def test_more_than_twelve_clauses_are_rejected(self):
        clauses = [
            make_clause(
                f"clause_{i:03d}",
                "data_retention",
                self.retention.source_excerpt,
            )
            for i in range(13)
        ]
        with self.assertRaises(ValueError):
            check_pdpl(clauses)

    def test_confirmed_violation_is_not_allowed_assessment(self):
        with self.assertRaises(ValidationError):
            AIClauseFinding(
                clause_id="clause_001",
                assessment="confirmed_violation",
                explanation_en="Example.",
                explanation_ar="مثال.",
                reference_ids=["pdpl-18"],
            )


if __name__ == "__main__":
    unittest.main()
