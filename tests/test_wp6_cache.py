
"""Offline WP6 cache and FastAPI integration tests. No real AI calls."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.analysis.schemas import AnalysisResponse
from backend.database.cache import (
    CACHE_TTL_SECONDS,
    clear_device_cache,
    get_cached_analysis,
    make_cache_key,
    save_cached_analysis,
)
from backend.database.storage import database_connection
from backend.main import app
from backend.pdpl.schemas import PDPLCheckResult
from backend.prompt_adjuster import PrivacyPreferences


def sample_result(pdpl_status="completed"):
    return AnalysisResponse(
        status="completed",
        analysis_mode="openai",
        risk_score=72,
        risk_level="High Risk",
        summary_en="Sample privacy risk analysis.",
        summary_ar="تحليل تجريبي لمخاطر الخصوصية.",
        flagged_clauses=[],
        pdpl=(
            PDPLCheckResult(status=pdpl_status)
            if pdpl_status is not None
            else None
        ),
    )


class WP6CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.db_path = Path(self.temp_dir.name) / "private" / "aamen.sqlite3"

        self.env_patch = patch.dict(
            os.environ,
            {
                "AAMEN_DB_PATH": str(self.db_path),
                "OPENAI_API_KEY": "mock-key-not-used",
                "OPENAI_MODEL": "test-model-v1",
            },
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        self.device_id = "aamen_wp6_test"
        self.terms = (
            "The example service collects location and photos, shares details "
            "with partners, and retains account information for several years."
        )
        self.preferences = PrivacyPreferences(location=True)

        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def request_body(self, **overrides):
        body = {
            "device_id": self.device_id,
            "terms_text": self.terms,
            "language": "en",
        }
        body.update(overrides)
        return body

    def row_count(self):
        with database_connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM analysis_cache"
            ).fetchone()[0]

    def test_01_missing_cache_returns_none(self):
        self.assertIsNone(
            get_cached_analysis(self.device_id, self.terms, self.preferences, "en")
        )
        self.assertTrue(self.db_path.exists())

    def test_02_save_and_retrieve_full_response(self):
        result = sample_result()

        self.assertTrue(
            save_cached_analysis(self.device_id, self.terms, self.preferences, "en", result)
        )

        self.assertEqual(
            get_cached_analysis(self.device_id, self.terms, self.preferences, "en"),
            result,
        )

    def test_03_cache_key_separates_all_inputs(self):
        baseline = make_cache_key(self.device_id, self.terms, self.preferences, "en")

        changed = (
            ("another_device_001", self.terms, self.preferences, "en"),
            (self.device_id, self.terms + " Extra clause.", self.preferences, "en"),
            (self.device_id, self.terms, PrivacyPreferences(photos=True), "en"),
            (self.device_id, self.terms, self.preferences, "ar"),
        )

        for args in changed:
            with self.subTest(args=args):
                self.assertNotEqual(make_cache_key(*args), baseline)

        with patch.dict(os.environ, {"OPENAI_MODEL": "test-model-v2"}):
            self.assertNotEqual(
                make_cache_key(self.device_id, self.terms, self.preferences, "en"),
                baseline,
            )

    def test_04_surrounding_spaces_do_not_change_key(self):
        self.assertEqual(
            make_cache_key(self.device_id, self.terms, self.preferences, "en"),
            make_cache_key(self.device_id, "  " + self.terms + "  ", self.preferences, "en"),
        )

    def test_05_saving_same_key_updates_single_row(self):
        original = sample_result()
        updated = original.model_copy(update={"risk_score": 45})

        save_cached_analysis(self.device_id, self.terms, self.preferences, "en", original)
        save_cached_analysis(self.device_id, self.terms, self.preferences, "en", updated)

        self.assertEqual(self.row_count(), 1)
        self.assertEqual(
            get_cached_analysis(self.device_id, self.terms, self.preferences, "en"),
            updated,
        )

    def test_06_expired_result_not_used_and_pruned(self):
        with patch("backend.database.cache.time.time", return_value=1000):
            save_cached_analysis(
                self.device_id, self.terms, self.preferences, "en", sample_result()
            )

        with database_connection() as connection:
            expires = connection.execute(
                "SELECT expires_at FROM analysis_cache"
            ).fetchone()[0]

        self.assertEqual(expires, 1000 + CACHE_TTL_SECONDS)

        with patch("backend.database.cache.time.time", return_value=expires):
            self.assertIsNone(
                get_cached_analysis(self.device_id, self.terms, self.preferences, "en")
            )

            save_cached_analysis(
                self.device_id, self.terms + " Updated.",
                self.preferences, "en", sample_result()
            )

        self.assertEqual(self.row_count(), 1)

    def test_07_invalid_cache_json_is_deleted(self):
        for invalid_json in ("{broken", "{}"):
            with self.subTest(content=invalid_json):
                save_cached_analysis(
                    self.device_id, self.terms, self.preferences, "en", sample_result()
                )

                with database_connection() as connection:
                    connection.execute(
                        "UPDATE analysis_cache SET response_json = ?",
                        (invalid_json,),
                    )

                self.assertIsNone(
                    get_cached_analysis(self.device_id, self.terms, self.preferences, "en")
                )
                self.assertEqual(self.row_count(), 0)

    def test_08_incomplete_pdpl_results_not_cached(self):
        # WP8: "partial" is now cached (see CACHEABLE_PDPL_STATUSES); failed or missing screening is not.
        for status in ("unavailable", None):
            with self.subTest(pdpl_status=status):
                self.assertFalse(
                    save_cached_analysis(
                        self.device_id, self.terms, self.preferences,
                        "en", sample_result(status)
                    )
                )
                self.assertFalse(self.db_path.exists())

    def test_09_clearing_one_device_preserves_another(self):
        other = "aamen_other_device"

        for device_id in (self.device_id, other):
            save_cached_analysis(device_id, self.terms, self.preferences, "en", sample_result())

        clear_device_cache(self.device_id)

        self.assertEqual(self.row_count(), 1)
        self.assertIsNone(
            get_cached_analysis(self.device_id, self.terms, self.preferences, "en")
        )
        self.assertIsNotNone(
            get_cached_analysis(other, self.terms, self.preferences, "en")
        )

    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_10_api_first_miss_then_hit(self, mocked_ai):
        first = self.client.post("/analyze", json=self.request_body())
        second = self.client.post("/analyze", json=self.request_body())

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(first.headers["x-aamen-cache"], "MISS")
        self.assertEqual(second.headers["x-aamen-cache"], "HIT")
        self.assertEqual(first.json(), second.json())

        mocked_ai.assert_called_once()

    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_11_saved_preference_change_causes_miss(self, mocked_ai):
        url = f"/preferences/{self.device_id}"

        self.assertEqual(self.client.put(url, json={"location": True}).status_code, 200)

        first = self.client.post("/analyze", json=self.request_body())
        self.assertEqual(first.headers["x-aamen-cache"], "MISS")
        self.assertTrue(mocked_ai.call_args.args[1].location)

        self.assertEqual(self.client.put(url, json={"photos": True}).status_code, 200)

        second = self.client.post("/analyze", json=self.request_body())
        third = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(second.headers["x-aamen-cache"], "MISS")
        self.assertEqual(third.headers["x-aamen-cache"], "HIT")
        self.assertEqual(mocked_ai.call_count, 2)
        self.assertTrue(mocked_ai.call_args.args[1].photos)

    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_12_explicit_preference_override_is_separate(self, mocked_ai):
        url = f"/preferences/{self.device_id}"

        self.client.put(url, json={"location": True})

        override = self.request_body(preferences={"photos": True})
        first = self.client.post("/analyze", json=override)
        second = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(first.headers["x-aamen-cache"], "MISS")
        self.assertEqual(second.headers["x-aamen-cache"], "MISS")
        self.assertEqual(mocked_ai.call_count, 2)
        self.assertTrue(self.client.get(url).json()["location"])
        self.assertFalse(self.client.get(url).json()["photos"])

    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_13_reset_clears_cache_and_preferences(self, mocked_ai):
        first = self.client.post("/analyze", json=self.request_body())
        second = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(first.headers["x-aamen-cache"], "MISS")
        self.assertEqual(second.headers["x-aamen-cache"], "HIT")

        reset = self.client.delete(f"/preferences/{self.device_id}")

        self.assertEqual(reset.status_code, 200)
        self.assertEqual(self.row_count(), 0)

        third = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(third.headers["x-aamen-cache"], "MISS")
        self.assertEqual(mocked_ai.call_count, 2)

    @patch("backend.main.analyze_terms", return_value=sample_result("unavailable"))
    def test_14_api_incomplete_pdpl_is_skipped(self, mocked_ai):
        first = self.client.post("/analyze", json=self.request_body())
        second = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["x-aamen-cache"], "SKIP")
        self.assertEqual(second.headers["x-aamen-cache"], "SKIP")
        self.assertEqual(mocked_ai.call_count, 2)
        self.assertEqual(self.row_count(), 0)

    @patch("backend.main.save_cached_analysis", side_effect=sqlite3.OperationalError("test failure"))
    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_15_api_cache_write_failure_does_not_block_analysis(self, mocked_ai, mocked_save):
        response = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-aamen-cache"], "SKIP")
        mocked_ai.assert_called_once()
        mocked_save.assert_called_once()

    @patch("backend.main.get_cached_analysis", side_effect=sqlite3.OperationalError("test failure"))
    @patch("backend.main.analyze_terms", return_value=sample_result())
    def test_16_api_cache_read_failure_falls_back_to_ai(self, mocked_ai, mocked_get):
        response = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-aamen-cache"], "MISS")
        mocked_ai.assert_called_once()
        mocked_get.assert_called_once()

    @patch("backend.main.analyze_terms")
    def test_17_api_rejects_bad_request_before_ai(self, mocked_ai):
        bad_device = self.client.post(
            "/analyze", json=self.request_body(device_id="bad")
        )
        bad_prefs = self.client.post(
            "/analyze", json=self.request_body(preferences={"location": 1})
        )

        self.assertEqual(bad_device.status_code, 422)
        self.assertEqual(bad_prefs.status_code, 422)
        mocked_ai.assert_not_called()

    @patch("backend.main.analyze_terms")
    def test_18_api_missing_key_returns_503(self, mocked_ai):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            response = self.client.post("/analyze", json=self.request_body())

        self.assertEqual(response.status_code, 503)
        mocked_ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
