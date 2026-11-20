"""Which language model (if any) the agent uses, and one call shape for every provider.

Providers (decided 2026-11-18, no paid key):
- Anthropic (Claude), if ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN is set. Not used in this project by choice,
  but the code path is kept. When set, it's the only provider used.
- Otherwise a chain of free providers, tried in order until one answers:
  1. Google Gemini, if GEMINI_API_KEY is set (free tier; usually the most reliable free option), then a second
     Gemini key from another account, if GEMINI_API_KEY_2 is set.
  2. OpenRouter free models, if OPENROUTER_API_KEY is set (often "rate-limited upstream", so several are tried).
  3. Ollama cloud, if OLLAMA_API_KEY is set (needs credits on the account; HTTP 402 otherwise).
- None configured: rules mode.

INTENTGUARD_LLM=off forces rules mode. Keys are read from the environment only, never from files in the repo.
Every call returns (parsed result or None, metadata for the trace); None means "fall back to the rules".
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

ANTHROPIC_MODEL = "claude-opus-5-5"

# Both Gemini and OpenRouter accept the same OpenAI-style "chat completions" request.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
# Checked 2026-11-18: gemini-3.5-flash was often overloaded (HTTP 503, timeouts) on the free tier, so the
# steadier 2.5 Flash goes first.
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Checked 2026-11-18: both Gemma models returned 429 ("rate-limited upstream") and Nemotron answered.
OPENROUTER_FREE_MODELS = ["nvidia/nemotron-3.5-super-vl:free", "google/gemma-4-31b-it:free",
                          "google/gemma-4-26b-a4b-it:free"]
# Ollama's cloud API (OLLAMA_API_KEY), same request shape. Added 2026-11-20 as the 4th fallback. Checked that day:
# the key returns HTTP 402 ("add usage credits"), so it only answers if the account has credits.
OLLAMA_URL = "https://ollama.com/v1/chat/completions"
OLLAMA_MODELS = ["gpt-oss:20b", "gemma4:31b"]


# O-29: a demo can't wait 25 seconds. The whole chain gets one time budget, and a model that says "limit reached"
# (429), is overloaded (503) or times out is skipped for a few minutes instead of being waited on every message.
TOTAL_BUDGET_S = float(os.environ.get("INTENTGUARD_LLM_BUDGET_S", "8"))
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


def _validate_lenient(schema: Type[T], obj: dict) -> tuple[Optional[T], list[str]]:
    """Validate a model reply. If some fields are invalid, drop those fields (they fall back to their defaults)
    and try again, instead of throwing the whole reply away (O-28). Required fields can't be dropped."""
    dropped: list[str] = []
    for _ in range(3):
        try:
            return schema.model_validate(obj), dropped
        except ValidationError as exc:
            bad = {str(e["loc"][0]) for e in exc.errors() if e.get("loc")}
            required = {n for n, f in schema.model_fields.items() if f.is_required()}
            if not bad or bad & required:
                return None, dropped
            obj = {k: v for k, v in obj.items() if k not in bad}
            dropped += sorted(bad)
    return None, dropped


def structured(system: str, user: str, schema: Type[T], max_tokens: int = 1500) -> tuple[Optional[T], dict]:
    """Ask the configured model for a JSON object matching `schema`. Code validates it before use."""
    p = provider()
    meta: dict = {"provider": p, "model": model_name()}
    if p is None:
        meta["error"] = "no model configured"
        return None, meta
    if p == "anthropic":
        return _anthropic(system, user, schema, max_tokens, meta)
    return _free_chain(system, user, schema, max_tokens, meta)


def _free_chain(system: str, user: str, schema: Type[T], max_tokens: int, meta: dict) -> tuple[Optional[T], dict]:
    """Try each free provider and model in order. A busy model, an invalid reply or a reply that doesn't match
    the schema moves on to the next one; only when all fail does the agent fall back to the rules."""
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    sys_prompt = (f"{system}\n\nReply with ONLY one JSON object that matches this JSON Schema. No other text.\n"
                  f"{schema_json}")
    tried: list[str] = []
    deadline = time.monotonic() + TOTAL_BUDGET_S
    for prov, url, key, models in _chain():
        headers = {"Authorization": f"Bearer {key}"}
        if prov == "openrouter":
            headers["X-Title"] = "Nestwise demo"
        for m in models:
            name = f"{prov}/{m}"
            if _is_cooling(name):
                tried.append(f"{name}: skipped (busy recently)")
                continue
            remaining = deadline - time.monotonic()
            if remaining < 1:
                tried.append(f"{name}: skipped (time budget used up)")
                continue
            body = {"model": m, "max_tokens": max_tokens, "temperature": 0,
                    "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user}],
                    "response_format": {"type": "json_object"}}
            try:
                r = _post_with_deadline(url, body, headers, remaining)
            except httpx.HTTPError as exc:
                tried.append(f"{prov}/{m}: {type(exc).__name__}")
                if isinstance(exc, httpx.TimeoutException):
                    _cool(name)
                continue
            if r.status_code != 200:
                tried.append(f"{prov}/{m}: HTTP {r.status_code}")
                if r.status_code in (429, 500, 502, 503, 504):
                    _cool(name)
                if r.status_code in (401, 402, 403):
                    for other in models:            # wrong key or no credits (402): rest this whole provider
                        _cool(f"{prov}/{other}")
                    break
                continue
            data = r.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError):
                tried.append(f"{prov}/{m}: no message in response")
                continue
            obj = _json_from(content)
            if obj is None:
                tried.append(f"{prov}/{m}: reply was not JSON")
                continue
            parsed, dropped = _validate_lenient(schema, obj)
            if parsed is None:
                tried.append(f"{prov}/{m}: reply didn't match the schema")
                continue
            if dropped:
                meta["dropped_fields"] = dropped           # O-28: keep the valid fields, drop the bad ones
            meta.update(provider=prov, model=m)
            if data.get("usage"):
                meta["usage"] = {k: data["usage"].get(k) for k in ("prompt_tokens", "completion_tokens")}
            if tried:
                meta["tried_first"] = tried
            return parsed, meta
    meta["tried"] = tried
    meta["error"] = "no model gave a usable answer"
    return None, meta


def _anthropic(system: str, user: str, schema: Type[T], max_tokens: int, meta: dict) -> tuple[Optional[T], dict]:
    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.parse(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens, betas=["server-side-fallback-2026-07-01"],
            fallbacks="default", output_config={"effort": "low"}, system=system,
            messages=[{"role": "user", "content": user}], output_format=schema)
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        meta["error"] = type(exc).__name__
        return None, meta
    meta["stop_reason"] = response.stop_reason
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        meta["error"] = f"no parsed output (stop_reason={response.stop_reason})"
        return None, meta
    return response.parsed_output, meta
