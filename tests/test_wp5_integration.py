
"""WP5 integration tests without real OpenAI requests."""

import unittest
from unittest.mock import patch

from backend.analysis.pipeline import analyze_terms
from backend.analysis.schemas import ExtractedClause, FlaggedClause, SummaryOutput
from backend.pdpl.schemas import PDPLCheckResult
from backend.prompt_adjuster import PrivacyPreferences

TEXT = "Our terms allow us to retain your personal data for five years after you close your account."
CLAUSE = ExtractedClause(category="data_retention", source_excerpt=TEXT)
FINDING = FlaggedClause(
    clause_id="clause_001",
    category="data_retention",
    severity="medium",
    source_excerpt=TEXT,
    explanation_en="Retention risk.",
    explanation_ar="مخاطر الاحتفاظ.",
)
SUMMARY = SummaryOutput(
    summary_en="Retention is discussed.",
    summary_ar="تم ذكر الاحتفاظ.",
)


class WP5IntegrationTests(unittest.TestCase):

    @patch("backend.analysis.pipeline.check_pdpl")
    @patch("backend.analysis.pipeline.calculate_rating", return_value=(34, "Moderate"))
    @patch("backend.analysis.pipeline.generate_summary", return_value=SUMMARY)
    @patch("backend.analysis.pipeline.classify_clauses", return_value=[FINDING])
    @patch("backend.analysis.pipeline.extract_clauses", return_value=[CLAUSE])
    def test_success_preserves_wp3_and_wp4(self, extract, classify, summarize, rating, pdpl):
        pdpl.return_value = PDPLCheckResult(status="completed")
        result = analyze_terms(TEXT, PrivacyPreferences(location=True))
        self.assertEqual(result.risk_score, 34)
        self.assertEqual(result.pdpl.status, "completed")
        self.assertEqual(result.flagged_clauses[0].clause_id, "clause_001")
        self.assertIn("location data and tracking", extract.call_args.args[1])
        pdpl.assert_called_once_with([FINDING])

    @patch("backend.analysis.pipeline.logger.exception")
    @patch("backend.analysis.pipeline.check_pdpl", side_effect=RuntimeError("Test PDPL failure"))
    @patch("backend.analysis.pipeline.calculate_rating", return_value=(34, "Moderate"))
    @patch("backend.analysis.pipeline.generate_summary", return_value=SUMMARY)
    @patch("backend.analysis.pipeline.classify_clauses", return_value=[FINDING])
    @patch("backend.analysis.pipeline.extract_clauses", return_value=[CLAUSE])
    def test_pdpl_failure_does_not_erase_wp3(self, extract, classify, summarize, rating, pdpl, log):
        result = analyze_terms(TEXT)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.risk_level, "Moderate")
        self.assertEqual(result.pdpl.status, "unavailable")
        self.assertEqual(result.pdpl.findings, [])
        log.assert_called_once()

    def test_invalid_text_still_rejected(self):
        with self.assertRaises(ValueError):
            analyze_terms("short")


if __name__ == "__main__":
    unittest.main()
