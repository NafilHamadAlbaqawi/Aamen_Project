
"""Centralized, backend-only OpenAI API wrapper. Never expose API keys to Chrome."""
import os
from typing import TypeVar
from pydantic import BaseModel
from openai import OpenAI

T = TypeVar("T", bound=BaseModel)

class AnalysisFailure(Exception):
    """An analysis stage could not produce a trustworthy result."""


def request_structured(schema: type[T], instructions: str, text: str, output_limit: int = 2500) -> T:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AnalysisFailure("OpenAI API key is not configured on the backend.")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-2024-08-06")
    client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
    response = client.responses.parse(
        model=model,
        instructions=instructions,
        input=text,
        text_format=schema,
        max_output_tokens=output_limit,
        store=False,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise AnalysisFailure("The model did not return a complete structured response.")
    return parsed
