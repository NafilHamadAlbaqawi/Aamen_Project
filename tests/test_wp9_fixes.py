"""WP9 offline tests for the fixes made after the evaluation. No API calls."""

import threading
import time
import unittest
from unittest.mock import patch

from backend.analysis.clause_extractor import extract_clauses, locate_excerpt
from backend.analysis.pipeline import analyze_terms
from backend.analysis.schemas import ExtractedClause, ExtractionOutput, FlaggedClause, SummaryOutput
from backend.pdpl.schemas import PDPLCheckResult
from backend.prompt_adjuster import build_prompt_bundle

SOURCE = ("We collect your location only with permission, and we may share your email with advertising "
          "partners to provide promotions. We store data for up to two years after account closure.")


def flagged(text):
    return [FlaggedClause(clause_id="clause_001", category="data_collection", severity="low",
                          source_excerpt=text, explanation_en="e", explanation_ar="ش")]


class LocateExcerptTests(unittest.TestCase):
    def test_exact_excerpt_is_kept(self):
        self.assertEqual(locate_excerpt("We store data for up to two years", SOURCE), "We store data for up to two years")

    def test_added_full_stop_is_recovered_from_the_source(self):
        # Seen in the WP9 baseline: the model ended the quote with "." where the sentence continues.
        self.assertEqual(locate_excerpt("We collect your location only with permission.", SOURCE),
                         "We collect your location only with permission")

    def test_capitalized_first_word_uses_the_source_spelling(self):
        got = locate_excerpt("We may share your email with advertising partners", SOURCE)
        self.assertEqual(got, "we may share your email with advertising partners")
        self.assertIn(got, SOURCE)

    def test_line_breaks_inside_a_sentence_are_matched(self):
        # Found in the WP9 browser regression: the extension keeps the HTML source's line breaks, so
        # "collect your\nlocation" was quoted as "collect your location" and the clause was dropped.
        page = ("The app collects your precise GPS location while it is open. We may also collect your\n"
                "       location in the background, even when the app is closed.")
        got = locate_excerpt("We may also collect your location in the background, even when the app is closed.", page)
        self.assertEqual(got, "We may also collect your\n       location in the background, even when the app is closed")
        self.assertIn(got, page)

    def test_quotes_are_removed(self):
        self.assertEqual(locate_excerpt("“We store data for up to two years”", SOURCE), "We store data for up to two years")

    def test_text_that_is_not_in_the_source_is_rejected(self):
        self.assertIsNone(locate_excerpt("We sell your data to anyone who asks.", SOURCE))
        self.assertIsNone(locate_excerpt("permission.", SOURCE), "too short after trimming")

    def test_extraction_keeps_recovered_clauses(self):
        model = ExtractionOutput(clauses=[
            ExtractedClause(category="data_collection", source_excerpt="We collect your location only with permission."),
            ExtractedClause(category="third_party_sharing", source_excerpt="We may share your email with advertising partners to provide promotions."),
            ExtractedClause(category="other", source_excerpt="This sentence was invented by the model."),
        ])
        with patch("backend.analysis.clause_extractor.request_structured", return_value=model):
            clauses = extract_clauses(SOURCE)
        self.assertEqual(len(clauses), 2)
        for clause in clauses:
            self.assertIn(clause.source_excerpt, SOURCE)


class ParallelPipelineTests(unittest.TestCase):
    def run_pipeline(self, summary_effect=None, pdpl_effect=None):
        def slow_summary(*args):
            time.sleep(0.4)
            if summary_effect:
                raise summary_effect
            return SummaryOutput(summary_en="Summary.", summary_ar="ملخص.")

        def slow_pdpl(*args):
            time.sleep(0.4)
            if pdpl_effect:
                raise pdpl_effect
            return PDPLCheckResult(status="completed")

        excerpt = "We store data for up to two years after account closure."
        with patch("backend.analysis.pipeline.extract_clauses", return_value=[]), \
                patch("backend.analysis.pipeline.classify_clauses", return_value=flagged(excerpt)), \
                patch("backend.analysis.pipeline.generate_summary", side_effect=slow_summary), \
                patch("backend.analysis.pipeline.check_pdpl", side_effect=slow_pdpl):
            start = time.perf_counter()
            result = analyze_terms(SOURCE)
            return result, time.perf_counter() - start

    def test_summary_and_pdpl_run_at_the_same_time(self):
        result, seconds = self.run_pipeline()
        self.assertLess(seconds, 0.75, "two 0.4 s stages should overlap")
        self.assertEqual(result.summary_en, "Summary.")
        self.assertEqual(result.pdpl.status, "completed")

    def test_pdpl_failure_still_keeps_the_analysis(self):
        with self.assertLogs("backend.analysis.pipeline", level="ERROR"):
            result, _ = self.run_pipeline(pdpl_effect=RuntimeError("PDPL down"))
        self.assertEqual(result.pdpl.status, "unavailable")
        self.assertEqual(result.summary_en, "Summary.")

    def test_summary_failure_still_fails_the_analysis(self):
        with self.assertRaises(ValueError):
            self.run_pipeline(summary_effect=ValueError("summary failed"))

    def test_no_threads_left_running(self):
        before = threading.active_count()
        self.run_pipeline()
        self.assertEqual(threading.active_count(), before)


class PdplRetryTests(unittest.TestCase):
    def test_rejected_answer_is_retried_once(self):
        from backend.analysis.openai_client import AnalysisFailure
        from backend.analysis.pipeline import screen_pdpl
        good = PDPLCheckResult(status="completed")
        with patch("backend.analysis.pipeline.check_pdpl",
                   side_effect=[AnalysisFailure("PDPL model cited an unverified or duplicate reference ID."), good]) as check, \
                self.assertLogs("backend.analysis.pipeline", level="WARNING"):
            self.assertIs(screen_pdpl([]), good)
        self.assertEqual(check.call_count, 2)

    def test_second_rejection_gives_unavailable_pdpl_but_keeps_the_analysis(self):
        from backend.analysis.openai_client import AnalysisFailure
        failure = AnalysisFailure("PDPL model returned missing or duplicate clause findings.")
        with patch("backend.analysis.pipeline.extract_clauses", return_value=[]), \
                patch("backend.analysis.pipeline.classify_clauses", return_value=flagged("We store data for two years.")), \
                patch("backend.analysis.pipeline.generate_summary", return_value=SummaryOutput(summary_en="S.", summary_ar="م.")), \
                patch("backend.analysis.pipeline.check_pdpl", side_effect=failure) as check, \
                self.assertLogs("backend.analysis.pipeline", level="WARNING"):
            result = analyze_terms(SOURCE)
        self.assertEqual(check.call_count, 2)
        self.assertEqual(result.pdpl.status, "unavailable")

    def test_service_errors_are_not_retried(self):
        from openai import OpenAIError
        from backend.analysis.pipeline import screen_pdpl
        with patch("backend.analysis.pipeline.check_pdpl", side_effect=OpenAIError("down")) as check:
            with self.assertRaises(OpenAIError):
                screen_pdpl([])
        self.assertEqual(check.call_count, 1)

    def test_prompt_keeps_references_to_the_clause_itself(self):
        from backend.pdpl.checker import INSTRUCTIONS
        self.assertIn("that same clause's own legal_context list", INSTRUCTIONS)


class CalibratedPromptTests(unittest.TestCase):
    def test_classification_has_a_two_sided_severity_rubric(self):
        prompt = build_prompt_bundle().classification_instructions
        for text in ("- low:", "- medium:", "- high:", "accurate matters more than being cautious",
                     "over-rating a normal clause is as wrong as under-rating"):
            self.assertIn(text, prompt)
        self.assertIn("Do not hedge", prompt)

    def test_examples_show_plain_wording_and_a_protective_clause(self):
        prompt = build_prompt_bundle().classification_instructions
        self.assertIn('"severity":"low"', prompt)
        self.assertNotIn("may reduce privacy", prompt)

    def test_summary_is_proportionate_and_short(self):
        prompt = build_prompt_bundle().summary_instructions
        self.assertIn("2-4 clear sentences", prompt)
        self.assertIn("mostly standard or user-friendly", prompt)

    def test_pdpl_needs_context_is_no_longer_the_default(self):
        from backend.pdpl.checker import INSTRUCTIONS
        self.assertNotIn("Use needs_context whenever", INSTRUCTIONS)
        self.assertNotIn("cautious, specific", INSTRUCTIONS)
        self.assertIn("aim to be accurate, not cautious", INSTRUCTIONS)
        self.assertIn("only when the answer truly depends on a fact the clause cannot show", INSTRUCTIONS)
        self.assertIn("Do not invent articles or legal quotations", INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
