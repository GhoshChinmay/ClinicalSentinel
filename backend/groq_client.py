"""
DataSentinel — Groq Cloud Client
Centralised Groq LPU inference client used by all AI engines.
Only schema metadata and computed statistics are ever transmitted — raw row data never leaves the machine.
"""

import os
import json
import requests
from utils import logger

_GROQ_API_KEY = os.getenv("GROQ_API_KEY")
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Model roster — tuned for each engine's needs
MODEL_FAST = "llama-3.1-8b-instant"  # Logic Gate + Insights (speed-critical)
MODEL_REASONING = (
    "llama-3.3-70b-versatile"  # NL Query Engine (needs deep SQL reasoning)
)


def groq_chat(
    messages: list[dict],
    model: str = MODEL_FAST,
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = 2048,
    timeout: int = 15,
) -> str | None:
    """
    Send a chat completion request to Groq LPU Cloud.

    Returns the assistant's response text, or None on failure.
    All errors are logged but never raised — callers should handle None gracefully.
    """
    if not _GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set. AI features are disabled.")
        return None

    headers = {
        "Authorization": f"Bearer {_GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        response = requests.post(
            _GROQ_URL, headers=headers, json=payload, timeout=timeout
        )

        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            return content.strip()
        else:
            logger.error("Groq API %d: %s", response.status_code, response.text[:300])
            return None

    except requests.exceptions.Timeout:
        logger.warning("Groq API request timed out after %ds.", timeout)
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("Groq API connection failed. Check network connectivity.")
        return None
    except Exception as e:
        logger.error("Groq client unexpected error: %s", e)
        return None


def groq_chat_json(
    messages: list[dict],
    model: str = MODEL_FAST,
    temperature: float = 0.1,
    timeout: int = 15,
) -> dict | list | None:
    """
    Convenience wrapper that requests JSON mode and parses the response.
    Returns parsed JSON (dict or list), or None on failure.
    """
    raw = groq_chat(
        messages,
        model=model,
        temperature=temperature,
        json_mode=True,
        timeout=timeout,
    )
    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Groq JSON parse error: %s | Raw: %s", e, raw[:300])
        return None


def check_groq_connectivity() -> bool:
    """Quick connectivity check — sends a minimal request to verify API key + network."""
    if not _GROQ_API_KEY:
        return False
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={
                "Authorization": f"Bearer {_GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL_FAST,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
            },
            timeout=5,
        )
        return resp.status_code == 200
    except Exception:
        return False
