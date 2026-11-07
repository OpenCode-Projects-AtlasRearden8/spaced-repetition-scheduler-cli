"""Optional LLM polish of card wording via an OpenAI-compatible chat endpoint.

Works offline by default: nothing here runs unless you call the ``polish``
command. Ships with defaults tuned for Ollama (``http://localhost:11434/v1``),
which needs no API key. If your endpoint needs one, name an environment
variable with ``--api-key-env`` (default ``SRS_API_KEY``); the value is read at
call time and never logged, stored or written to disk.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, Optional

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_API_KEY_ENV = "SRS_API_KEY"
DEFAULT_TIMEOUT = 60

SYSTEM_PROMPT = (
    "You are a plain-English flashcard editor. Rewrite the provided card wording "
    "so the front is a single, clear question and the back is a concise answer. "
    "Keep the meaning, do not add facts, do not answer with more than three sentences. "
    "Reply with strict JSON: {\"front\": string, \"back\": string}."
)


def build_payload(model: str, front: str, back: str, temperature: float = 0.2,
                  max_tokens: Optional[int] = None) -> dict:
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"front": front, "back": back}, ensure_ascii=False)},
        ],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _parse_text_response(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"model did not return JSON ({content[:80]!r})")
    data = json.loads(text[start : end + 1])
    front, back = data.get("front"), data.get("back")
    if not isinstance(front, str) or not isinstance(back, str) or not front.strip() or not back.strip():
        raise ValueError("model response missing front/back strings")
    return {"front": front.strip(), "back": back.strip()}


def polish_card(
    front: str,
    back: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    model: str,
    api_key: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    opener: Optional[Callable] = None,
    max_tokens: Optional[int] = None,
) -> dict:
    """Ask an OpenAI-compatible endpoint to rewrite one card; returns front/back."""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(build_payload(model, front, back, max_tokens=max_tokens)).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    open_it = opener or urllib.request.urlopen
    try:
        with open_it(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.fp.read().decode("utf-8", errors="replace")[:200] if err.fp else ""
        raise RuntimeError(f"endpoint returned HTTP {err.code}: {detail}") from err
    except (urllib.error.URLError, OSError) as err:
        raise RuntimeError(f"could not reach {base_url}: {err}") from err

    try:
        message = payload["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            # Some reasoning models (e.g. newer Ollama builds) answer in
            # ``reasoning`` and leave ``content`` empty; look there as a fallback.
            content = message.get("reasoning") or ""
        content = str(content)
    except (AttributeError, IndexError, KeyError, TypeError) as err:
        raise ValueError(f"unexpected response shape: {str(payload)[:200]}") from err
    return _parse_text_response(content)


def api_key_from_env(env_name: str) -> Optional[str]:
    """Read a key from the named env var, if set. Never logged or persisted."""
    return os.environ.get(env_name) or None
