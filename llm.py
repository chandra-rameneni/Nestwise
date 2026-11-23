"""The language models behind the AI agent, and the one tool-calling chat it uses (chat_tools).

Free providers only (no paid key), tried in order until one answers: NVIDIA's developer API (two keys), Google
Gemini (two keys), OpenRouter free models, Mistral, Ollama. A model that fails or is slow rests for a few
minutes and the next one answers. Keys are read from the environment only, never from files in the repo.
INTENTGUARD_LLM=off turns the AI off; the store then says it can't answer right now.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Optional

import httpx


ANTHROPIC_MODEL = "claude-opus-5-5"

# Both Gemini and OpenRouter accept the same OpenAI-style "chat completions" request.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
# Checked 2026-11-18: gemini-3.5-flash was often overloaded (HTTP 503, timeouts) on the free tier, so the
# steadier 2.5 Flash goes first.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# Added 2026-11-21 (PM's free NVIDIA developer key). Checked that day: both called the store tools correctly in ~2.5 s;
# z-ai/glm-5.3-flash timed out, so it isn't used.
# MiniMax M3.1 Flash added at the PM's request (2026-11-21): called the tools correctly in 1.5-2.4 s.
# Nemotron 3 Ultra (PM's request): correct tool calls but ~4.5 s per step, so it's the last NVIDIA choice.
# z-ai/glm-5.3-flash: no answer within 30 s twice (2026-11-21), not used.
NVIDIA_MODELS = ["nvidia/nemotron-3.5-super-vl-120b-a12b", "minimaxai/minimax-m3.1-flash",
                 "mistralai/mistral-large-4-1t-a52b", "nvidia/nemotron-3-ultra-550b-a55b",
                 # GLM 5.3 Flash: added at the PM's request; it didn't answer within 45 s in tests, so it's last.
                 # A timeout rests it for 5 minutes (COOLDOWN_S), so it can't hold up every message.
                 "z-ai/glm-5.3-flash"]
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
# Added 2026-11-21 (PM's own free "Experiment" key): same request shape, supports tool calls.
MISTRAL_MODELS = ["mistral-small-latest"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Checked 2026-11-18: both Gemma models returned 429 ("rate-limited upstream") and Nemotron answered.
OPENROUTER_FREE_MODELS = ["nvidia/nemotron-3.5-super-vl:free", "google/gemma-4-31b-it:free",
                          "google/gemma-4-26b-a4b-it:free"]
# Ollama's cloud API (OLLAMA_API_KEY), same request shape. Added 2026-11-20 as the 4th fallback. Checked that day:
# the key returns HTTP 402 ("add usage credits"), so it only answers if the account has credits.
OLLAMA_URL = "https://ollama.com/v1/chat/completions"
OLLAMA_MODELS = ["gpt-oss:20b", "gemma4:31b"]


COOLDOWN_S = float(os.environ.get("INTENTGUARD_LLM_COOLDOWN_S", "300"))
_cooling: dict[str, float] = {}              # "provider/model" -> time when it may be tried again
_pool = ThreadPoolExecutor(max_workers=4)


def _post_with_deadline(url: str, body: dict, headers: dict, remaining: float):
    """httpx's timeout limits each wait for data, not the whole call, so a slow model can trickle past it.
    Running the call in a worker thread gives a hard deadline: past it, we stop waiting (the thread finishes
    on its own and its answer is ignored)."""
    fut = _pool.submit(httpx.post, url, json=body, headers=headers, timeout=min(remaining, 20))
    try:
        return fut.result(timeout=remaining)
    except FutureTimeout:
        raise httpx.ReadTimeout("hard deadline reached")


def _cool(name: str) -> None:
    _cooling[name] = time.monotonic() + COOLDOWN_S


def _is_cooling(name: str) -> bool:
    return _cooling.get(name, 0) > time.monotonic()


def _off() -> bool:
    return os.environ.get("INTENTGUARD_LLM", "").lower() in {"off", "0", "false"}


def _chain() -> list[tuple[str, str, str, list[str]]]:
    """(provider, url, key, models) for each free provider that has a key, in order of preference."""
    out = []
    gem_models = ([os.environ["INTENTGUARD_GEMINI_MODEL"]] if os.environ.get("INTENTGUARD_GEMINI_MODEL")
                  else GEMINI_MODELS)
    # A second Gemini key (another account) has its own free quota: tried after the first, with its own
    # cool-down ("gemini2/..."). Added 2026-11-19 when the first key's daily quota ran out during testing.
    for name, var in (("gemini", "GEMINI_API_KEY"), ("gemini2", "GEMINI_API_KEY_2")):
        if os.environ.get(var):
            out.append((name, GEMINI_URL, os.environ[var], gem_models))
    for name, var in (("nvidia", "NVIDIA_API_KEY"), ("nvidia2", "NVIDIA_API_KEY_2")):   # second key = more free quota
        if os.environ.get(var):
            out.append((name, NVIDIA_URL, os.environ[var], NVIDIA_MODELS))
    if os.environ.get("MISTRAL_API_KEY"):
        out.append(("mistral", MISTRAL_URL, os.environ["MISTRAL_API_KEY"], MISTRAL_MODELS))
    if os.environ.get("OPENROUTER_API_KEY"):
        chosen = os.environ.get("INTENTGUARD_OPENROUTER_MODEL")
        out.append(("openrouter", OPENROUTER_URL, os.environ["OPENROUTER_API_KEY"],
                    [chosen] if chosen else OPENROUTER_FREE_MODELS))
    if os.environ.get("OLLAMA_API_KEY"):
        out.append(("ollama", OLLAMA_URL, os.environ["OLLAMA_API_KEY"], OLLAMA_MODELS))
    return out


def provider() -> Optional[str]:
    if _off():
        return None
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    chain = _chain()
    return chain[0][0] if chain else None


def model_name() -> Optional[str]:
    p = provider()
    if p == "anthropic":
        return ANTHROPIC_MODEL
    chain = _chain()
    return chain[0][3][0] if p and chain else None


def _json_from(text: str) -> Optional[dict]:
    """The JSON object in a model reply, tolerating code fences or a sentence around it."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------- tool-using agent calls (2026-11-21)
# PM, 2026-11-23: keep waiting rather than give up; the screen shows each step meanwhile.
AGENT_BUDGET_S = float(os.environ.get("INTENTGUARD_AGENT_BUDGET_S", "180"))
# One slow model can't use up the budget. 12 s was too short for writing an answer after several searches (N18).
AGENT_CALL_S = float(os.environ.get("INTENTGUARD_AGENT_CALL_S", "60"))
# Live run 2026-11-22: Gemini 3.5 hung for 20+ s and the fast NVIDIA models were never tried. For the agent, the
# models that answered tool calls fastest go first.
AGENT_ORDER = ["nvidia", "nvidia2", "gemini", "gemini2", "openrouter", "mistral", "ollama"]


def chat_tools(messages: list[dict], tools: list[dict], deadline: float,
               avoid: Optional[set] = None) -> tuple[Optional[dict], dict]:
    """One step of the agent loop: the model reads the conversation and either calls tools or replies.
    Tries the free providers in order (busy ones are skipped for a while). Returns (assistant message, meta),
    or (None, meta) when no model answered in time."""
    meta: dict = {}
    tried: list[str] = []
    if _off():
        return None, {"error": "AI off"}
    chain = sorted(_chain(), key=lambda c: AGENT_ORDER.index(c[0]) if c[0] in AGENT_ORDER else 99)
    for prov, url, key, models in chain:
        headers = {"Authorization": f"Bearer {key}"}
        if prov == "openrouter":
            headers["X-Title"] = "Nestwise demo"
        for m in models:
            name = f"{prov}/{m}"
            if avoid and m in avoid:              # this model just came back empty: let another one write
                tried.append(f"{name}: skipped (gave an empty reply)")
                continue
            remaining = min(deadline - time.monotonic(), AGENT_CALL_S)
            if _is_cooling(name) or remaining < 2:
                tried.append(f"{name}: skipped")
                continue
            body = {"model": m, "messages": messages, "tools": tools, "temperature": 0.2, "max_tokens": 1600}
            try:
                r = _post_with_deadline(url, body, headers, remaining)
            except httpx.HTTPError as exc:
                tried.append(f"{name}: {type(exc).__name__}")
                _cool(name)
                continue
            if r.status_code != 200:
                tried.append(f"{name}: HTTP {r.status_code}")
                if r.status_code in (429, 500, 502, 503, 504):
                    _cool(name)
                if r.status_code in (401, 402, 403):
                    for other in models:
                        _cool(f"{prov}/{other}")
                    break
                continue
            try:
                msg = r.json()["choices"][0]["message"]
            except (KeyError, IndexError, TypeError, ValueError):
                tried.append(f"{name}: no message")
                continue
            meta.update(provider=prov, model=m)
            if tried:
                meta["tried_first"] = tried
            return msg, meta
    meta.update(tried=tried, error="no model answered")
    return None, meta


def forgive_cooling() -> None:
    """Let resting models be tried again now (the agent is retrying instead of giving up)."""
    _cooling.clear()
