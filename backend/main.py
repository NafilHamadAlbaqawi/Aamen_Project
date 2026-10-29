
"""Aamen backend: WP2-WP5 API preserved; WP6 adds persisted preferences and caching."""

import logging
import os
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException, Path, Response
from fastapi.concurrency import run_in_threadpool
from openai import OpenAIError
from pydantic import BaseModel, Field

from .analysis.openai_client import AnalysisFailure
from .analysis.pipeline import analyze_terms
from .analysis.schemas import AnalysisResponse
from .database.cache import clear_device_cache, get_cached_analysis, save_cached_analysis
from .database.preferences import get_preferences, reset_preferences, save_preferences
from .prompt_adjuster import PrivacyPreferences


logger = logging.getLogger(__name__)
app = FastAPI(title="Aamen Backend", version="0.4.0")


class AnalyzeRequest(BaseModel):
    device_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    page_url: str = Field(default="", max_length=2048)
    page_title: str = Field(default="", max_length=300)
    terms_text: str = Field(min_length=50, max_length=120000)
    language: Literal["en", "ar"] = "en"
    preferences: PrivacyPreferences | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "aamen",
        "ai_enabled": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/preferences/{device_id}", response_model=PrivacyPreferences)
async def read_preferences(
    device_id: str = Path(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
):
    try:
        return await run_in_threadpool(get_preferences, device_id)

    except (sqlite3.Error, OSError) as error:
        logger.exception("WP6 preference retrieval failed")
        raise HTTPException(status_code=503, detail="Preference storage is unavailable.") from error


@app.put("/preferences/{device_id}", response_model=PrivacyPreferences)
async def update_preferences(
    preferences: PrivacyPreferences,
    device_id: str = Path(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
):
    try:
        return await run_in_threadpool(save_preferences, device_id, preferences)

    except (sqlite3.Error, OSError) as error:
        logger.exception("WP6 preference update failed")
        raise HTTPException(status_code=503, detail="Preference storage is unavailable.") from error


@app.delete("/preferences/{device_id}", response_model=PrivacyPreferences)
async def delete_preferences(
    device_id: str = Path(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
):
    try:
        result = await run_in_threadpool(reset_preferences, device_id)
        await run_in_threadpool(clear_device_cache, device_id)
        return result

    except (sqlite3.Error, OSError) as error:
        logger.exception("WP6 preference reset failed")
        raise HTTPException(status_code=503, detail="Preference storage is unavailable.") from error


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest, response: Response):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="AI analysis is not configured on this server.")

    try:
        effective_preferences = request.preferences

        if effective_preferences is None:
            effective_preferences = await run_in_threadpool(
                get_preferences,
                request.device_id,
            )

        try:
            cached = await run_in_threadpool(
                get_cached_analysis,
                request.device_id,
                request.terms_text,
                effective_preferences,
                request.language,
            )

        except (sqlite3.Error, OSError) as error:
            logger.warning("WP6 cache read failed: %s", type(error).__name__)
            cached = None

        if cached is not None:
            response.headers["X-Aamen-Cache"] = "HIT"
            return cached

        result = await run_in_threadpool(
            analyze_terms,
            request.terms_text,
            effective_preferences,
        )

        response.headers["X-Aamen-Cache"] = "MISS"

        try:
            stored = await run_in_threadpool(
                save_cached_analysis,
                request.device_id,
                request.terms_text,
                effective_preferences,
                request.language,
                result,
            )

            if not stored:
                response.headers["X-Aamen-Cache"] = "SKIP"

        except (sqlite3.Error, OSError) as error:
            logger.warning("WP6 cache write failed: %s", type(error).__name__)
            response.headers["X-Aamen-Cache"] = "SKIP"

        return result

    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    except (sqlite3.Error, OSError) as error:
        logger.exception("WP6 preference retrieval failed during analysis")
        raise HTTPException(status_code=503, detail="Preference storage is unavailable.") from error

    except AnalysisFailure as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    except OpenAIError as error:
        logger.warning("OpenAI request failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="AI service unavailable or rejected the request.") from error

    except Exception as error:
        logger.exception("Unexpected analysis failure")
        raise HTTPException(status_code=500, detail="Unexpected analysis error.") from error
