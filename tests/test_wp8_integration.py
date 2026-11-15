"""WP8 offline integration tests: the whole backend through HTTP, checked against what the extension uses.

The four model calls (WP3 extract, classify, summarize and WP5 PDPL) are replaced by a fake model that
answers with the real Pydantic schemas, so WP2 -> WP6 -> WP4 -> WP3 -> WP5 -> WP6 run for real without any
OpenAI request. The tests also read the extension files to make sure both sides use the same names and limits.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import get_args
from unittest.mock import patch

from fastapi.testclient import TestClient
from openai import OpenAIError

from backend.analysis.openai_client import AnalysisFailure
from backend.analysis.rating import calculate_rating
from backend.analysis.schemas import (
    Category,
    ClassificationOutput,
    ClassifiedClause,
    ExtractedClause,
    ExtractionOutput,
    FlaggedClause,
    SummaryOutput,
)
from backend.main import AnalyzeRequest, app
from backend.pdpl.checker import AIClauseFinding, AIReviewBatch
from backend.prompt_adjuster import PrivacyPreferences


ROOT = Path(__file__).resolve().parent.parent
EXTENSION = ROOT / "extension"

TERMS = (
    "Rihla Delivery Terms of Service. "
    "We collect your precise location even when the app is closed. "
    "We may share your personal information with advertising partners and affiliates. "
    "We keep copies of your uploaded photos on our servers for as long as we decide. "
    "You can delete your account at any time from the settings page. "
    "Rihla is not liable for late, missing or damaged orders."
)

# The clauses the fake model "finds". Every excerpt is copied from TERMS, as WP3 requires.
FAKE_CLAUSES = [
    ("data_collection", "We collect your precise location even when the app is closed.", "high"),
    ("third_party_sharing", "We may share your personal information with advertising partners and affiliates.", "high"),
    ("data_retention", "We keep copies of your uploaded photos on our servers for as long as we decide.", "medium"),
    ("account_termination", "You can delete your account at any time from the settings page.", "low"),
]

# Same rules as errorCodeFor() in extension/background.js. If the backend changes a message, these tests fail.
SW_RULES = {
    "ai_not_configured": (503, re.compile(r"not configured", re.I)),
    "storage_unavailable": (503, re.compile(r"preference storage", re.I)),
    "no_clauses": (502, re.compile(r"source-grounded", re.I)),
}


class FakeModel:
    """Stands in for request_structured() and remembers the instructions each stage received."""

    def __init__(self, clauses=FAKE_CLAUSES, omit_classification=False):
        self.clauses = clauses
        self.omit_classification = omit_classification
        self.instructions = {}
        self.calls = []

    def __call__(self, schema, instructions, text, output_limit=2500):
        self.calls.append(schema.__name__)
        self.instructions[schema.__name__] = instructions

        if schema is ExtractionOutput:
            return ExtractionOutput(clauses=[
                ExtractedClause(category=category, source_excerpt=excerpt)
                for category, excerpt, _ in self.clauses
            ])

        if schema is ClassificationOutput:
            numbers = [item["clause_number"] for item in json.loads(text)]
            if self.omit_classification:
                numbers = numbers[:-1]
            severity = {i + 1: c[2] for i, c in enumerate(self.clauses)}
            return ClassificationOutput(clauses=[
                ClassifiedClause(
                    clause_number=n,
                    severity=severity[n],
                    explanation_en=f"Test explanation {n}.",
                    explanation_ar=f"شرح اختباري {n}.",
                )
                for n in numbers
            ])

        if schema is SummaryOutput:
            return SummaryOutput(
                summary_en="The terms allow location tracking and sharing with advertisers.",
                summary_ar="تسمح الشروط بتتبع الموقع والمشاركة مع المعلنين.",
            )

        if schema is AIReviewBatch:
            return AIReviewBatch(findings=[
                AIClauseFinding(
                    clause_id=task["clause_id"],
                    assessment="needs_context",
                    explanation_en="More context is needed.",
                    explanation_ar="يلزم سياق إضافي.",
                    reference_ids=[task["legal_context"][0]["id"]],
                )
                for task in json.loads(text)
            ])

        raise AssertionError(f"Unexpected schema {schema!r}")


def patch_model(fake):
    """Patch the model call in all four stages at once."""
    targets = (
        "backend.analysis.clause_extractor.request_structured",
        "backend.analysis.risk_classifier.request_structured",
        "backend.analysis.summary_generator.request_structured",
        "backend.pdpl.checker.request_structured",
    )
    patchers = [patch(target, side_effect=fake) for target in targets]
    for patcher in patchers:
        patcher.start()
    return patchers


class WP8IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        env = patch.dict(os.environ, {
            "AAMEN_DB_PATH": str(Path(self.temp_dir.name) / "wp8" / "aamen.sqlite3"),
            "OPENAI_API_KEY": "mock-key-not-used",
            "OPENAI_MODEL": "test-model-wp8",
        })
        env.start()
        self.addCleanup(env.stop)

        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.device_id = "wp8_device_0001"

    def use_model(self, fake):
        for patcher in patch_model(fake):
            self.addCleanup(patcher.stop)
        return fake

    def analyze(self, device_id=None, **extra):
        body = {"device_id": device_id or self.device_id, "terms_text": TERMS, "language": "en"}
        body.update(extra)
        return self.client.post("/analyze", json=body)

    # ---- The full flow and the response the popup reads ---------------------------------------------

    def test_01_full_flow_returns_everything_the_popup_reads(self):
        fake = self.use_model(FakeModel())
        response = self.analyze()

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["x-aamen-cache"], "MISS")
        self.assertEqual(fake.calls, ["ExtractionOutput", "ClassificationOutput", "SummaryOutput", "AIReviewBatch"])

        data = response.json()
        clauses = data["flagged_clauses"]
        self.assertEqual(len(clauses), 4)
        for clause in clauses:
            # isUsableResult() in popup.js needs these, and the screens show the rest.
            self.assertIn(clause["severity"], ("high", "medium", "low"))
            self.assertIn(clause["category"], get_args(Category))
            self.assertIn(clause["source_excerpt"], TERMS)
            self.assertTrue(clause["explanation_en"] and clause["explanation_ar"])
            self.assertRegex(clause["clause_id"], r"^clause_\d{3}$")

        self.assertTrue(data["summary_en"] and data["summary_ar"])
        self.assertIn(data["risk_level"], ("Safe", "Moderate", "High Risk"))
        expected_score, expected_level = calculate_rating(
            [FlaggedClause.model_validate(c) for c in clauses]
        )
        self.assertEqual((data["risk_score"], data["risk_level"]), (expected_score, expected_level))
        self.assertIsInstance(data["input_truncated"], bool)
        self.assertTrue(data["disclaimer"])

        # The popup finds the PDPL part of a warning by clause_id (pdplFinding() in popup.js).
        pdpl = data["pdpl"]
        self.assertEqual(pdpl["status"], "completed")
        ids = {c["clause_id"] for c in clauses}
        self.assertEqual({f["clause_id"] for f in pdpl["findings"]}, ids)
        for finding in pdpl["findings"]:
            self.assertIn(finding["assessment"], ("potential_concern", "needs_context", "no_concern_identified"))
            for ref in finding["legal_references"]:
                self.assertTrue(ref["title"] and ref["article_id"] and ref["excerpt"])
                self.assertTrue(ref["source_url"].startswith("https://"))

    def test_02_every_backend_category_has_popup_text(self):
        strings = (EXTENSION / "ui-strings.js").read_text(encoding="utf-8")
        english, arabic = strings.split("ar: {", 1)
        for category in get_args(Category):
            self.assertIn(f"cat_{category}:", english, f"English label missing for {category}")
            self.assertIn(f"cat_{category}:", arabic, f"Arabic label missing for {category}")

    def test_03_extension_and_backend_use_the_same_limits_and_fields(self):
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        background = (EXTENSION / "background.js").read_text(encoding="utf-8")

        limits = AnalyzeRequest.model_fields["terms_text"].metadata
        min_length = next(m.min_length for m in limits if hasattr(m, "min_length"))
        max_length = next(m.max_length for m in limits if hasattr(m, "max_length"))
        self.assertIn(f"PASTE_MIN = {min_length}, PASTE_MAX = {max_length}", popup)
        self.assertIn(f"terms_text.length < {min_length} || terms_text.length > {max_length}", background)

        fields = list(PrivacyPreferences.model_fields)
        background_fields = re.search(r"PREFERENCE_FIELDS = \[([^\]]*)\]", background).group(1)
        self.assertEqual(re.findall(r"'([a-z_]+)'", background_fields), fields)
        popup_topics = re.findall(r"\{ id: '([a-z_]+)', label:", popup)
        self.assertEqual(popup_topics, fields)

    # ---- Preferences: extension -> WP6 database -> WP4 prompts --------------------------------------

    def test_04_saved_preferences_reach_all_three_wp4_prompts(self):
        fake = self.use_model(FakeModel())

        # What background.js sends when the user accepts photos and banking, and does not accept the other two.
        saved = self.client.put(f"/preferences/{self.device_id}", json={
            "location": True, "photos": False, "banking_information": False, "third_party_sharing": True,
        })
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get(f"/preferences/{self.device_id}").json()["location"], True)

        self.assertEqual(self.analyze().status_code, 200)
        for stage in ("ExtractionOutput", "ClassificationOutput", "SummaryOutput"):
            prompt = fake.instructions[stage]
            self.assertIn("location data and tracking", prompt, stage)
            self.assertIn("third-party personal-data sharing", prompt, stage)
            self.assertNotIn("photos and image usage", prompt, stage)
            self.assertNotIn("banking and financial information", prompt, stage)

    def test_05_device_without_saved_preferences_uses_defaults(self):
        fake = self.use_model(FakeModel())
        self.assertEqual(self.analyze(device_id="wp8_device_never_saved").status_code, 200)
        self.assertIn("No user-selected topic priorities", fake.instructions["ClassificationOutput"])

    def test_06_cache_miss_hit_and_preference_change(self):
        fake = self.use_model(FakeModel())

        first = self.analyze()
        second = self.analyze()
        self.assertEqual((first.headers["x-aamen-cache"], second.headers["x-aamen-cache"]), ("MISS", "HIT"))
        self.assertEqual(first.json(), second.json())
        self.assertEqual(len(fake.calls), 4, "a cache HIT must not call the model again")

        self.client.put(f"/preferences/{self.device_id}", json={"photos": True})
        third = self.analyze()
        self.assertEqual(third.headers["x-aamen-cache"], "MISS")
        self.assertEqual(len(fake.calls), 8)

    def test_06b_partial_pdpl_result_is_cached(self):
        # A liability clause has no PDPL article, so WP5 returns "partial", as it does for most real terms pages.
        clauses = FAKE_CLAUSES + [("liability", "Rihla is not liable for late, missing or damaged orders.", "medium")]
        fake = self.use_model(FakeModel(clauses=clauses))

        first = self.analyze()
        self.assertEqual(first.json()["pdpl"]["status"], "partial")
        self.assertEqual(len(first.json()["pdpl"]["findings"]), 4)
        second = self.analyze()
        self.assertEqual((first.headers["x-aamen-cache"], second.headers["x-aamen-cache"]), ("MISS", "HIT"))
        self.assertEqual(len(fake.calls), 4)

    # ---- Errors: what background.js turns into error codes ------------------------------------------

    def assert_sw_code(self, response, code):
        status, rule = SW_RULES[code]
        self.assertEqual(response.status_code, status, response.text)
        self.assertRegex(response.json()["detail"], rule)

    def test_07_missing_key_is_ai_not_configured(self):
        self.use_model(FakeModel())
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assert_sw_code(self.analyze(), "ai_not_configured")

    def test_08_no_grounded_clauses_is_no_clauses(self):
        self.use_model(FakeModel(clauses=[("other", "This sentence is not in the document at all.", "low")]))
        self.assert_sw_code(self.analyze(), "no_clauses")

    def test_09_model_failures_are_502(self):
        self.use_model(FakeModel(omit_classification=True))
        response = self.analyze()
        self.assertEqual(response.status_code, 502)
        self.assertIn("classifier omitted", response.json()["detail"])

    def test_10_openai_error_is_502_with_safe_message(self):
        with patch("backend.analysis.clause_extractor.request_structured", side_effect=OpenAIError("secret detail")):
            response = self.analyze()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "AI service unavailable or rejected the request.")

    def test_11_storage_failure_is_storage_unavailable(self):
        self.use_model(FakeModel())
        # The backend logs these failures; assertLogs keeps the output clean and checks that they are logged.
        with self.assertLogs("backend.main", level="ERROR"), \
                patch("backend.main.get_preferences", side_effect=sqlite3.OperationalError("locked")):
            self.assert_sw_code(self.analyze(), "storage_unavailable")
        with self.assertLogs("backend.main", level="ERROR"), \
                patch("backend.main.save_preferences", side_effect=sqlite3.OperationalError("locked")):
            response = self.client.put(f"/preferences/{self.device_id}", json={"location": True})
            self.assert_sw_code(response, "storage_unavailable")

    def test_12_short_text_validation_names_terms_text(self):
        response = self.client.post("/analyze", json={"device_id": self.device_id, "terms_text": "too short"})
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertIsInstance(detail, list)
        self.assertIn("terms_text", detail[0]["loc"])

    def test_13_analysis_failure_class_is_handled(self):
        with patch("backend.main.analyze_terms", side_effect=AnalysisFailure("The model did not return a complete structured response.")):
            response = self.analyze()
        self.assertEqual(response.status_code, 502)

    # ---- The popup's own copy of the rating formula ----------------------------------------------

    @unittest.skipUnless(shutil.which("node"), "Node.js is needed to run the popup's rating code")
    def test_14_popup_rating_matches_backend_rating(self):
        popup = (EXTENSION / "popup.js").read_text(encoding="utf-8")
        match = re.search(r"function backendRating\(severities\) \{.*?\n  \}", popup, re.S)
        self.assertIsNotNone(match, "backendRating() not found in popup.js")

        mixes = [(h, m, l) for h in range(7) for m in range(7) for l in range(7)]
        script = (
            match.group(0)
            + "\nconst mixes = JSON.parse(process.argv[1]);"
            + "\nconsole.log(JSON.stringify(mixes.map(([h, m, l]) => backendRating("
            + "[...Array(h).fill('high'), ...Array(m).fill('medium'), ...Array(l).fill('low')]))));"
        )
        output = subprocess.run(
            ["node", "-e", script, json.dumps(mixes)],
            capture_output=True, text=True, check=True, timeout=60,
        ).stdout
        popup_results = json.loads(output)

        for (h, m, l), js in zip(mixes, popup_results):
            clauses = [
                FlaggedClause(clause_id="c", category="other", severity=s, source_excerpt="x" * 15,
                              explanation_en="e", explanation_ar="ش")
                for s in ["high"] * h + ["medium"] * m + ["low"] * l
            ]
            self.assertEqual((js["score"], js["level"]), calculate_rating(clauses), (h, m, l))


if __name__ == "__main__":
    unittest.main()
