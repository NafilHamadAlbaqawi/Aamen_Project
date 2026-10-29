
"""WP6 SQLite preference tests using isolated temporary databases."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from backend.database.preferences import (
    get_preferences,
    save_preferences,
    reset_preferences,
)
from backend.database.storage import database_connection
from backend.prompt_adjuster.preferences import PrivacyPreferences


class WP6PreferencesTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.db_path = Path(self.temp_dir.name) / "nested" / "test.sqlite3"

        self.env_patch = patch.dict(
            os.environ,
            {"AAMEN_DB_PATH": str(self.db_path)},
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

        self.device_id = "aamen_test_001"

    def test_01_defaults_create_database(self):
        self.assertFalse(self.db_path.exists())

        result = get_preferences(self.device_id)

        self.assertEqual(result, PrivacyPreferences())
        self.assertTrue(self.db_path.is_file())

    def test_02_save_model_roundtrip(self):
        expected = PrivacyPreferences(location=True, photos=True)

        self.assertEqual(save_preferences(self.device_id, expected), expected)
        self.assertEqual(get_preferences(self.device_id), expected)

    def test_03_save_dict_roundtrip(self):
        values = {
            "banking_information": True,
            "third_party_sharing": True,
        }

        expected = PrivacyPreferences(**values)

        self.assertEqual(save_preferences(self.device_id, values), expected)
        self.assertEqual(get_preferences(self.device_id), expected)

    def test_04_upsert_without_duplicates(self):
        save_preferences(
            self.device_id,
            PrivacyPreferences(location=True),
        )

        updated = PrivacyPreferences(third_party_sharing=True)

        save_preferences(self.device_id, updated)

        self.assertEqual(get_preferences(self.device_id), updated)

        with database_connection() as connection:
            row_count = connection.execute(
                "SELECT COUNT(*) FROM user_preferences WHERE device_id = ?",
                (self.device_id,),
            ).fetchone()[0]

        self.assertEqual(row_count, 1)

    def test_05_devices_are_isolated(self):
        another = "aamen_test_002"

        first = PrivacyPreferences(location=True)
        second = PrivacyPreferences(photos=True)

        save_preferences(self.device_id, first)
        save_preferences(another, second)

        self.assertEqual(get_preferences(self.device_id), first)
        self.assertEqual(get_preferences(another), second)

    def test_06_reset_deletes_saved_record(self):
        save_preferences(
            self.device_id,
            PrivacyPreferences(location=True),
        )

        self.assertEqual(
            reset_preferences(self.device_id),
            PrivacyPreferences(),
        )

        self.assertEqual(
            get_preferences(self.device_id),
            PrivacyPreferences(),
        )

        with database_connection() as connection:
            row_count = connection.execute(
                "SELECT COUNT(*) FROM user_preferences WHERE device_id = ?",
                (self.device_id,),
            ).fetchone()[0]

        self.assertEqual(row_count, 0)

    def test_07_reset_unknown_device(self):
        self.assertEqual(
            reset_preferences(self.device_id),
            PrivacyPreferences(),
        )

    def test_08_reject_invalid_device_ids(self):
        invalid_ids = (
            "abc",
            "contains space",
            "a" * 101,
            "bad/path/001",
            "device;DROP",
        )

        for invalid in invalid_ids:
            with self.subTest(device_id=invalid):
                with self.assertRaises(ValueError):
                    get_preferences(invalid)

                with self.assertRaises(ValueError):
                    save_preferences(invalid, PrivacyPreferences())

                with self.assertRaises(ValueError):
                    reset_preferences(invalid)

    def test_09_reject_non_boolean_preferences(self):
        with self.assertRaises(ValidationError):
            save_preferences(self.device_id, {"location": 1})

        self.assertEqual(
            get_preferences(self.device_id),
            PrivacyPreferences(),
        )

    def test_10_reject_unknown_preference_without_overwrite(self):
        saved = PrivacyPreferences(location=True)

        save_preferences(self.device_id, saved)

        with self.assertRaises(ValidationError):
            save_preferences(self.device_id, {"new_setting": True})

        self.assertEqual(get_preferences(self.device_id), saved)


if __name__ == "__main__":
    unittest.main()
