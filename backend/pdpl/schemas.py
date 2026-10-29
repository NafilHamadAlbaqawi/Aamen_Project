
"""Structured data models for Aamen PDPL screening."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PDPLReference(BaseModel):
    """A reference to a verified PDPL source."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    article_id: str = Field(min_length=1)
    source_url: HttpUrl
    excerpt: str = Field(min_length=1)


class PDPLFinding(BaseModel):
    """PDPL screening assessment linked to one WP3 clause."""

    model_config = ConfigDict(extra="forbid")

    clause_id: str = Field(min_length=1)
    source_excerpt: str = Field(min_length=15)
    assessment: Literal[
        "potential_concern",
        "needs_context",
        "no_concern_identified",
    ]
    explanation_en: str = Field(min_length=1)
    explanation_ar: str = Field(min_length=1)
    legal_references: list[PDPLReference] = Field(min_length=1)


class PDPLCheckResult(BaseModel):
    """Validated result of the PDPL screening process."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "partial", "unavailable"]
    findings: list[PDPLFinding] = Field(default_factory=list)
    disclaimer: str = (
        "Automated PDPL screening only; not a legal compliance determination."
    )
