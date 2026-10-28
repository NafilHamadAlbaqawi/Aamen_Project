"""Pydantic contracts used between WP3 pipeline stages and the Chrome extension."""
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal[
    "data_collection", "third_party_sharing", "data_retention",
    "consent", "account_termination", "terms_changes",
    "liability", "sensitive_data", "other",
]
Severity = Literal["low", "medium", "high"]

class ExtractedClause(BaseModel):
    category: Category
    source_excerpt: str

class ExtractionOutput(BaseModel):
    clauses: list[ExtractedClause]

class ClassifiedClause(BaseModel):
    clause_number: int
    severity: Severity
    explanation_en: str
    explanation_ar: str

class ClassificationOutput(BaseModel):
    clauses: list[ClassifiedClause]

class SummaryOutput(BaseModel):
    summary_en: str
    summary_ar: str

class FlaggedClause(BaseModel):
    clause_id: str
    category: Category
    severity: Severity
    source_excerpt: str
    explanation_en: str
    explanation_ar: str

class AnalysisResponse(BaseModel):
    status: Literal["completed"]
    analysis_mode: Literal["openai"]
    risk_score: int = Field(ge=0, le=100)
    risk_level: Literal["Safe", "Moderate", "High Risk"]
    summary_en: str
    summary_ar: str
    flagged_clauses: list[FlaggedClause]
    input_truncated: bool = False
    disclaimer: str = "AI-generated screening, not a legal compliance determination."
