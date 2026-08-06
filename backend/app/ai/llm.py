"""Thin, swappable wrapper around the local LLM (Ollama).

Everything that needs the model calls `generate_json` — a single choke point.
To swap Ollama for something else later (e.g. OpenRouter), only this file changes.

We force JSON output so extraction/generation returns something we can parse,
and use a low temperature because these are extraction tasks, not creative ones.
"""
import json

import httpx

from app.config import settings

# Ollama defaults a model to a few thousand tokens of context whatever the model
# can actually do, and silently drops what does not fit. Every prompt we send is
# long on purpose — the whole knowledge base, a whole resume section, a whole
# document — so an unset window means the model quietly stops seeing the start
# of its own instructions. Set it once, here, for every call.
CONTEXT_TOKENS = 16384

# Roughly how many characters one token is worth for English prose. Deliberately
# conservative: over-estimating the token count costs a warning, under-estimating
# it costs the front of the prompt with nothing said about it.
_CHARS_PER_TOKEN = 3.5

# Leave room for the reply. num_ctx covers the prompt AND the generation, so a
# prompt that exactly fills the window leaves the model nowhere to answer.
_RESERVED_FOR_REPLY = 2048

# How long Ollama keeps the model in memory after a call. Long enough to cover
# a whole resume, which is several calls with our own work in between.
KEEP_ALIVE = "15m"


def fits_context(system: str, prompt: str, max_tokens: int = 1200) -> bool:
    """Whether this call can be answered without the window silently truncating.

    Ollama does not report truncation. It drops whatever does not fit off the
    front and answers confidently with the rest, which for resume generation
    reads as the model having quietly forgotten the first half of a career.
    Callers that build a prompt from an unbounded list, and there are two of
    them, should ask before sending.
    """
    return estimate_tokens(system, prompt) + max_tokens + _RESERVED_FOR_REPLY <= CONTEXT_TOKENS


def estimate_tokens(system: str, prompt: str) -> int:
    """A character-count approximation. Close enough to decide whether to trim."""
    return int((len(system) + len(prompt)) / _CHARS_PER_TOKEN)


def generate_json(
    system: str, prompt: str, timeout: float | None = 120.0, max_tokens: int = 1200
) -> dict:
    """Send a system+user prompt, get a parsed JSON object back.

    `max_tokens` is not optional in spirit: small models sometimes fall into a
    repetition loop and generate until something kills them. Capping the output
    turns a 10-minute hang into a fast, retryable failure.

    `timeout=None` waits indefinitely. Use it only for work the user has been
    told is slow and can watch progress on — document parsing — never for a
    call made inside a request the browser is holding open.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",  # Ollama guarantees the response is valid JSON.
        # Generating one resume is several calls a minute or two apart. Ollama
        # unloads a model five minutes after the last one by default, and a
        # cold load of a 3b model costs seconds that the user watches.
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": 0.1,
            "num_predict": max_tokens,
            "num_ctx": CONTEXT_TOKENS,
        },
    }
    return json.loads(_chat(payload, timeout))


def generate_text(
    system: str, prompt: str, timeout: float | None = 120.0, max_tokens: int = 1200
) -> str:
    """Same call, without the JSON envelope — for output that *is* the answer.

    LaTeX is the case: wrapping a document full of backslashes in a JSON string
    means every one of them has to survive escaping, which is a needless way to
    lose a resume.
    """
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": 0.1,
            "num_predict": max_tokens,
            "num_ctx": CONTEXT_TOKENS,
        },
    }
    return _chat(payload, timeout)


def _chat(payload: dict, timeout: float | None) -> str:
    """The one HTTP call, and the two ways it fails that are not bugs.

    Both of these used to reach the user as the raw httpx line, which for a
    missing model reads:

        Client error '404 Not Found' for url 'http://localhost:11434/api/chat'
        For more information check: https://developer.mozilla.org/...

    That is a link to a page about the number 404. It says nothing about which
    model is missing or that one command fixes it, and it is the first thing
    someone sees when their setup did not finish. Both cases are ordinary and
    recoverable, so they say what happened and what to type.
    """
    try:
        resp = httpx.post(f"{settings.ollama_url}/api/chat", json=payload, timeout=timeout)
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"Could not reach Ollama at {settings.ollama_url}. "
            "It may not be running - start it with:  ollama serve"
        ) from e

    if resp.status_code == 404:
        # Ollama answers 404 for a model it does not have, which is the normal
        # state of a machine where setup stopped early.
        raise RuntimeError(
            f"The language model '{settings.ollama_model}' is not installed. "
            f"Get it with:  ollama pull {settings.ollama_model}"
        )
    resp.raise_for_status()
    return resp.json()["message"]["content"]
