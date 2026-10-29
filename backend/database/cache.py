
"""WP6 SQLite cache for completed WP3-WP5 analysis responses."""

import hashlib
import json
import os
import time

from pydantic import ValidationError

from ..analysis.schemas import AnalysisResponse
from ..prompt_adjuster import PrivacyPreferences
from .storage import database_connection, initialize_database


CACHE_VERSION = "wp6-v1"
CACHE_TTL_SECONDS = 24 * 60 * 60


def make_cache_key(
    device_id: str,
    terms_text: str,
    preferences: PrivacyPreferences,
    language: str,
) -> str:
    payload = {
        "cache_version": CACHE_VERSION,
        "device_id": device_id,
        "terms_text": terms_text.strip(),
        "preferences": preferences.model_dump(),
        "language": language,
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06"),
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_cached_analysis(
    device_id: str,
    terms_text: str,
    preferences: PrivacyPreferences,
    language: str,
) -> AnalysisResponse | None:
    key = make_cache_key(device_id, terms_text, preferences, language)

    initialize_database()
    now = int(time.time())

    with database_connection() as connection:
        row = connection.execute(
            "SELECT response_json FROM analysis_cache "
            "WHERE cache_key = ? AND device_id = ? AND expires_at > ?",
            (key, device_id, now),
        ).fetchone()

        if row is None:
            return None

        try:
            return AnalysisResponse.model_validate_json(row["response_json"])

        except (ValidationError, ValueError):
            connection.execute(
                "DELETE FROM analysis_cache WHERE cache_key = ?",
                (key,),
            )
            return None


def save_cached_analysis(
    device_id: str,
    terms_text: str,
    preferences: PrivacyPreferences,
    language: str,
    result: AnalysisResponse,
) -> bool:
    if result.pdpl is None or result.pdpl.status != "completed":
        return False

    key = make_cache_key(device_id, terms_text, preferences, language)
    now = int(time.time())

    initialize_database()

    with database_connection() as connection:
        connection.execute(
            "DELETE FROM analysis_cache WHERE expires_at <= ?",
            (now,),
        )

        connection.execute(
            "INSERT INTO analysis_cache "
            "(cache_key, device_id, response_json, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET "
            "response_json = excluded.response_json, "
            "created_at = excluded.created_at, "
            "expires_at = excluded.expires_at",
            (
                key,
                device_id,
                result.model_dump_json(),
                now,
                now + CACHE_TTL_SECONDS,
            ),
        )

    return True


def clear_device_cache(device_id: str) -> None:
    initialize_database()

    with database_connection() as connection:
        connection.execute(
            "DELETE FROM analysis_cache WHERE device_id = ?",
            (device_id,),
        )
