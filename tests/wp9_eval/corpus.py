"""WP9 test corpus: documents with hand-written expected results (gold labels).

Documents come from corpus.json. Reused ones point to their source instead of copying it:
  wp4:DOC-B          -> tests/wp4_eval/test_documents.json
  wp8:terms.html     -> tests/wp8_e2e/site/terms.html (text of <main>, like the extension reads it)
load_corpus() checks that every anchor is really in its document, so a label can't silently point at nothing.
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEVERITIES = ("low", "medium", "high")
ASSESSMENTS = ("potential_concern", "needs_context", "no_concern_identified")
LEVELS = ("Safe", "Moderate", "High Risk")
BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "section", "article"}
BREAK = "\u2029"  # marks the end of a paragraph; line breaks inside the HTML source are only spaces


class _MainText(HTMLParser):
    """Collects the text inside <main>, one line per paragraph or heading."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "main":
            self.depth += 1
        elif self.depth and tag in BLOCKS:
            self.parts.append(BREAK)

    def handle_endtag(self, tag):
        if tag == "main":
            self.depth -= 1
        elif self.depth and tag in BLOCKS:
            self.parts.append(BREAK)

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def html_main_text(html):
    parser = _MainText()
    parser.feed(html)
    lines = (" ".join(block.split()) for block in "".join(parser.parts).split(BREAK))
    return "\n\n".join(line for line in lines if line)


def _source_text(reference):
    kind, name = reference.split(":", 1)
    if kind == "wp4":
        documents = json.loads((ROOT / "tests" / "wp4_eval" / "test_documents.json").read_text(encoding="utf-8"))
        return next(d["terms_text"] for d in documents if d["doc_id"] == name)
    if kind == "wp8":
        return html_main_text((ROOT / "tests" / "wp8_e2e" / "site" / name).read_text(encoding="utf-8"))
    raise ValueError(f"Unknown text source {reference!r}")


def load_corpus(path=HERE / "corpus.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    documents = []
    for doc in data["documents"]:
        doc = dict(doc)
        if "text_from" in doc:
            doc["terms_text"] = _source_text(doc["text_from"])
        text = doc["terms_text"]
        if doc["expected_level"] not in LEVELS:
            raise ValueError(f"{doc['doc_id']}: bad expected_level")
        for provision in doc["provisions"]:
            if provision["anchor"] not in text:
                raise ValueError(f"{doc['doc_id']}: anchor not in text: {provision['anchor']!r}")
            if provision["severity"] not in SEVERITIES:
                raise ValueError(f"{doc['doc_id']}: bad severity for {provision['anchor']!r}")
            if provision.get("pdpl") not in (None,) + ASSESSMENTS:
                raise ValueError(f"{doc['doc_id']}: bad pdpl label for {provision['anchor']!r}")
        if doc.get("injection_line") and doc["injection_line"] not in text:
            raise ValueError(f"{doc['doc_id']}: injection_line not in text")
        documents.append(doc)
    return documents


def normalize(text):
    """Lower-case, no punctuation or Arabic diacritics, single spaces. Used to match excerpts to anchors."""
    text = re.sub(r"[ً-ٰٟـ]", "", text.casefold())
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def matches(anchor, excerpt):
    """True if a flagged excerpt is about the same provision as a gold anchor."""
    a, e = normalize(anchor), normalize(excerpt)
    if not a or not e:
        return False
    if a in e or e in a:
        return True
    anchor_words = a.split()
    found = sum(word in e.split() for word in anchor_words)
    return found / len(anchor_words) >= 0.7
