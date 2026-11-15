# Code overview: This section stores and reads each device’s selected privacy preferences.

"""WP6 persistent user preferences using SQLite and the WP4 preference model."""

import re
from collections.abc import Mapping

from .storage import database_connection, initialize_database
from ..prompt_adjuster.preferences import PrivacyPreferences, normalize_preferences


DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,100}$")

PREFERENCE_FIELDS = (
    "location",
    "photos",
    "banking_information",
    "third_party_sharing",
)


def _validate_device_id(device_id: str) -> str:
    if not isinstance(device_id, str) or DEVICE_ID_PATTERN.fullmatch(device_id) is None:
        raise ValueError(
            "device_id must be 8-100 letters, numbers, underscores or hyphens."
        )

    return device_id


def get_preferences(device_id: str) -> PrivacyPreferences:
    device_id = _validate_device_id(device_id)

    initialize_database()

    with database_connection() as connection:
        row = connection.execute(
            "SELECT location, photos, banking_information, third_party_sharing "
            "FROM user_preferences WHERE device_id = ?",
            (device_id,),
        ).fetchone()

    if row is None:
        return PrivacyPreferences()

    values = {
        field: bool(row[field])
        for field in PREFERENCE_FIELDS
    }

    return PrivacyPreferences(**values)


def save_preferences(
    device_id: str,
    preferences: PrivacyPreferences | Mapping[str, object],
) -> PrivacyPreferences:
    device_id = _validate_device_id(device_id)
    validated = normalize_preferences(preferences)
    values = validated.model_dump()

    initialize_database()

    with database_connection() as connection:
        connection.execute(
            "INSERT INTO user_preferences "
            "(device_id, location, photos, banking_information, third_party_sharing) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET "
            "location = excluded.location, "
            "photos = excluded.photos, "
            "banking_information = excluded.banking_information, "
            "third_party_sharing = excluded.third_party_sharing, "
            "updated_at = CAST(strftime('%s', 'now') AS INTEGER)",
            (
                device_id,
                *(int(values[field]) for field in PREFERENCE_FIELDS),
            ),
        )

    return validated


def reset_preferences(device_id: str) -> PrivacyPreferences:
    device_id = _validate_device_id(device_id)

    initialize_database()

    with database_connection() as connection:
        connection.execute(
            "DELETE FROM user_preferences WHERE device_id = ?",
            (device_id,),
        )

    return PrivacyPreferences()
