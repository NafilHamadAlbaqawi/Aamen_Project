
"""Aamen backend: WP2 API contract preserved; WP3 supplies real AI analysis."""
import logging
import os
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from openai import OpenAIError
from .analysis.openai_client import AnalysisFailure
from .analysis.pipeline import analyze_terms
from .analysis.schemas import AnalysisResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Aamen Backend", version="0.2.0")

class AnalyzeRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    page_url: str = Field(default="", max_length=2048)
    page_title: str = Field(default="", max_length=300)
    terms_text: str = Field(min_length=50, max_length=120000)
    language: Literal["en", "ar"] = "en"

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "aamen",
        "ai_enabled": bool(os.getenv("OPENAI_API_KEY")),
    }

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="AI analysis is not configured on this server.")
    try:
        return await run_in_threadpool(analyze_terms, request.terms_text)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AnalysisFailure as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except OpenAIError as error:
        logger.warning("OpenAI request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="AI service unavailable or rejected the request.") from error
    except Exception as error:
        logger.exception("Unexpected analysis failure")
        raise HTTPException(status_code=500, detail="Unexpected analysis error.") from error
