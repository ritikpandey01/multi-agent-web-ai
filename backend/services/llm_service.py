"""Wrapper for all Groq LLM calls.

Uses the Groq API.
Every call is wrapped in asyncio.run_in_executor because the SDK
is synchronous and would block FastAPI's event loop otherwise.
Every prompt enforces JSON-only output.
Includes retry logic with exponential backoff for rate limits.
"""

import asyncio
import json
import os
import time
import functools
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# The user defined GroqAPIKey in .env
groq_api_key = os.getenv("GroqAPIKey")
if groq_api_key and groq_api_key.startswith('"') and groq_api_key.endswith('"'):
    groq_api_key = groq_api_key[1:-1]

_client = Groq(api_key=groq_api_key)

# Model cascade — try in order, fall back on rate limit or errors
_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
]
_MAX_RETRIES = 3
_RETRY_DELAY = 5  # seconds


def _call_llm_sync(prompt: str) -> str:
    """Synchronous Groq call with retry + model fallback."""
    last_error = None

    for model in _MODELS:
        for attempt in range(_MAX_RETRIES):
            try:
                chat_completion = _client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant. You must always return raw JSON and nothing else. No markdown fences."
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=model,
                    temperature=0.1,
                )
                return chat_completion.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if "429" in error_str or "rate limit" in error_str:
                    wait = _RETRY_DELAY * (attempt + 1)
                    print(f"[Groq] Rate limited on {model}, retrying in {wait}s... (attempt {attempt+1})")
                    time.sleep(wait)
                    continue
                else:
                    print(f"[Groq] Error on {model}: {e}")
                    break  # Try next model

    print(f"[Groq] All models failed. Last error: {last_error}")
    raise last_error or Exception("All Groq models failed")


async def call_llm(prompt: str) -> str:
    """Async wrapper that runs the sync Groq call in a thread pool."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, functools.partial(_call_llm_sync, prompt)
    )
    return result


async def call_llm_json(prompt: str) -> dict:
    """Call Groq and parse the response as JSON.
    
    The prompt should already instruct the LLM to return raw JSON.
    This function strips markdown fences if present, then parses.
    """
    raw = await call_llm(prompt)

    # Strip markdown code fences if LLM wraps the response
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        else:
            cleaned = cleaned.replace("```json", "").replace("```", "")
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Return a fallback structure so the pipeline doesn't crash
        return {"error": f"Failed to parse LLM response: {str(e)}", "raw": raw[:500]}
