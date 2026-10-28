
"""
Aamen Backend — WP2 Communication

This initial backend supports:
1. GET /health
2. POST /analyze

AI analysis and PDPL screening are not implemented here.
"""

# 1. Import FastAPI and request validation tools.
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Literal

# 2. Create the FastAPI application.
app = FastAPI(title="Aamen Backend", version="0.1.0")

# 3. Define the request structure expected from background.js.
class AnalyzeRequest(BaseModel):
    device_id: str = Field(
        min_length=8,
        max_length=100,
        pattern=r"^[A-Za-z0-9_-]+$"
    )
    page_url: str = Field(default="", max_length=2048)
    page_title: str = Field(default="", max_length=300)
    terms_text: str = Field(min_length=50, max_length=120000)
    language: Literal["en", "ar"] = "en"

# 4. Check whether the backend server is running.
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "aamen",
        "ai_enabled": False
    }

# 5. Receive legal text and return a communication acknowledgment.
@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    character_count = len(request.terms_text)

    english_message = (
        f"Received {character_count} characters successfully. "
        "Legal analysis is not implemented yet."
    )

    arabic_message = (
        f"تم استلام {character_count} حرف بنجاح. "
        "لم يتم تنفيذ التحليل القانوني بعد."
    )

    return {
        "status": "received",
        "risk_score": None,
        "summary_en": english_message,
        "summary_ar": arabic_message,
        "characters_received": character_count,
        "language": request.language
    }
