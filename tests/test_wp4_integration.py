"""Optional integration tests; require merging the WP3 integration overlay first."""

import unittest
from unittest.mock import patch
from backend.prompt_adjuster import PrivacyPreferences

try:
    from backend.analysis.pipeline import analyze_terms
    from backend.analysis.schemas import ExtractedClause, FlaggedClause, SummaryOutput
    CAN_IMPORT = True
except ImportError:
    CAN_IMPORT = False


@unittest.skipUnless(CAN_IMPORT, "WP3 modules/OpenAI SDK not installed")
class TestWp4PipelineIntegration(unittest.TestCase):
    def test_prompts_reach_three_wp3_stages(self):
        excerpt = "We may share your personal data with our advertising partners."
        clause = ExtractedClause(category="third_party_sharing", source_excerpt=excerpt)
        finding = FlaggedClause(
            clause_id="clause_001", category="third_party_sharing", severity="medium",
            source_excerpt=excerpt, explanation_en="Sharing with advertisers.",
            explanation_ar="مشاركة المعلومات مع المعلنين.",
        )
        summary = SummaryOutput(summary_en="Data may be shared.",
                                summary_ar="قد تتم مشاركة البيانات.")
        with (
            patch('backend.analysis.pipeline.extract_clauses', return_value=[clause]) as extract,
            patch('backend.analysis.pipeline.classify_clauses', return_value=[finding]) as classify,
            patch('backend.analysis.pipeline.generate_summary', return_value=summary) as summarize,
            patch('backend.analysis.pipeline.calculate_rating', return_value=(34, "Moderate")),
        ):
            result = analyze_terms(
                "This is a sample Terms and Conditions agreement for testing. " + excerpt,
                PrivacyPreferences(location=True, third_party_sharing=True),
            )
        self.assertIn('location data and tracking', extract.call_args.args[1])
        self.assertIn('third-party personal-data sharing', classify.call_args.args[1])
        self.assertIn('third-party personal-data sharing', summarize.call_args.args[1])
        self.assertEqual(result.risk_level, 'Moderate')
        self.assertEqual(result.summary_en, 'Data may be shared.')


if __name__ == '__main__':
    unittest.main()
