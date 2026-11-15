# Code overview: This section searches the PDPL reference file and returns the articles connected to each clause.

"""WP5: bilingual, source-grounded lexical retrieval from the local PDPL dataset."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

KNOWLEDGE_BASE_PATH = Path(__file__).with_name("knowledge_base.json")
ARABIC_MARKS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
ARABIC_LETTERS = re.compile(r"[\u0621-\u064a]")
ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه",
})

CATEGORY_TOPICS = {
    "data_collection": ("purpose_limitation", "data_minimization", "collection_disclosures"),
    "third_party_sharing": ("collection_disclosures", "privacy_notice"),
    "data_retention": ("retention_and_destruction", "data_minimization"),
    "consent": ("consent", "consent_withdrawal"),
    "account_termination": ("data_subject_rights", "retention_and_destruction"),
    "sensitive_data": ("data_minimization", "security_safeguards"),
}


def _normalize(text: str) -> str:
    """Normalize English, Arabic spelling, punctuation, and whitespace."""
    text = ARABIC_MARKS.sub("", text.casefold()).translate(ARABIC_TRANSLATION)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _keyword_found(normalized_text: str, keyword: str) -> bool:
    """Match whole words/phrases; allow common Arabic prefixes."""
    words = _normalize(keyword).split()
    if not words:
        return False
    parts = []
    for word in words:
        prefix = r"(?:[وفبلك])?(?:ال)?" if ARABIC_LETTERS.search(word) else ""
        parts.append(prefix + re.escape(word))
    pattern = r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


@lru_cache(maxsize=1)
def load_knowledge_base() -> dict[str, Any]:
    """Load Step 2 JSON once, validating the source and article identifiers."""
    with KNOWLEDGE_BASE_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list) or not isinstance(data.get("articles"), list):
        raise ValueError("Invalid PDPL knowledge_base.json structure.")
    sources = {item["source_id"]: item for item in data["sources"]}
    if len(sources) != len(data["sources"]):
        raise ValueError("Duplicate PDPL source IDs.")
    article_ids = set()
    for article in data["articles"]:
        required = ("id", "source_id", "article_id", "topic", "summary_en", "summary_ar", "keywords_en", "keywords_ar")
        if not all(key in article for key in required):
            raise ValueError("PDPL article record is missing required fields.")
        if article["source_id"] not in sources or article["id"] in article_ids:
            raise ValueError("PDPL article has an unknown source or duplicate ID.")
        article_ids.add(article["id"])
    return data


def retrieve_articles(clause_text: str, category: str = "", limit: int = 5) -> list[dict[str, Any]]:
    """Rank relevant PDPL entries; results are context, not compliance judgments."""
    if not isinstance(clause_text, str):
        raise TypeError("clause_text must be a string.")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 13:
        raise ValueError("limit must be an integer between 1 and 13.")
    normalized_text = _normalize(clause_text)
    if not normalized_text:
        return []
    database = load_knowledge_base()
    sources = {item["source_id"]: item for item in database["sources"]}
    related_topics = CATEGORY_TOPICS.get(category, ())
    matches = []
    for article in database["articles"]:
        found_en = [term for term in article["keywords_en"] if _keyword_found(normalized_text, term)]
        found_ar = [term for term in article["keywords_ar"] if _keyword_found(normalized_text, term)]
        category_match = article["topic"] in related_topics
        if not (found_en or found_ar or category_match):
            continue
        source = sources[article["source_id"]]
        matches.append({
            "id": article["id"],
            "source_id": article["source_id"],
            "title": source["title"],
            "article_id": article["article_id"],
            "topic": article["topic"],
            "source_url": source["source_url"],
            "summary_en": article["summary_en"],
            "summary_ar": article["summary_ar"],
            "matched_keywords_en": found_en,
            "matched_keywords_ar": found_ar,
            "matched_by_category": category_match,
            "relevance_score": 3 * (len(found_en) + len(found_ar)) + (2 if category_match else 0),
        })
    matches.sort(key=lambda item: (-item["relevance_score"], item["id"]))
    return matches[:limit]
