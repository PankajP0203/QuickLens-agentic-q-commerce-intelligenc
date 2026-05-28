from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()

# gemini-1.5-flash: 404 NOT_FOUND on this API key
# gemini-2.0-flash: retired for new users (404 NOT_FOUND)
# gemini-2.5-flash: available but high demand → frequent 503s
# gemini-2.0-flash-lite: confirmed available, lighter, more stable for hackathon
MODEL = "gemini-2.5-flash-lite"

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def call_gemini(
    prompt: str,
    system_instruction: str,
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
) -> str:
    """
    Call Gemini with automatic retry on 503 / UNAVAILABLE errors.

    Non-retryable errors (400, 404, auth) are re-raised immediately.
    Raises RuntimeError if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = _client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction
                ),
            )
            return response.text.strip()

        except Exception as exc:
            err = str(exc)
            retryable = "503" in err or "UNAVAILABLE" in err or "overloaded" in err.lower()

            if not retryable:
                raise

            last_exc = exc
            if attempt < max_retries:
                print(
                    f"[Gemini] 503 on attempt {attempt}/{max_retries} "
                    f"— retrying in {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)

    raise RuntimeError(
        f"Gemini call failed after {max_retries} attempt(s). Last error: {last_exc}"
    )
