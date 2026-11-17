"""Intent schema, Claude structured extraction, and a deterministic rule-based fallback.

The extractor actually used is recorded on every Intent (`extractor`) and in the trace, so a
fallback run is never presented as AI output.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "intent_v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt"

IntentType = Literal["PRODUCT_DISCOVERY", "REFUND_REQUEST", "ORDER_TRACKING", "UNSUPPORTED"]


class IntentExtraction(BaseModel):
    """What one user message states. Schema handed to the model via structured outputs."""
    intent: IntentType
    category: Optional[Literal["keyboard_mouse_combo", "sofa"]] = None
    product_query: Optional[str] = None
    max_total_inr: Optional[int] = None
    max_delivery_days: Optional[int] = None
    required_compatibility: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    seats: Optional[int] = None
    max_width_cm: Optional[int] = None
    missing_info: list[str] = Field(default_factory=list)


class Intent(IntentExtraction):
    """Confirmed session state after merging messages. `version` bumps whenever a constraint changes."""
    version: int = 1
    extractor: str = "rules_fallback"
    approval_required: bool = True  # P0 never buys without explicit approval

    def constraint_fields(self) -> dict:
        return self.model_dump(include={"category", "product_query", "max_total_inr", "max_delivery_days",
                                        "required_compatibility", "preferred_brands", "seats", "max_width_cm"})


# --------------------------------------------------------------------------- rules fallback
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
              "nine": 9, "ten": 10}
_NUM = r"(\d+|" + "|".join(_NUM_WORDS) + r")"
_OTHER_PRODUCTS = ["laptop", "phone", "smartphone", "tv", "television", "headphones", "earbuds", "monitor",
                   "tablet", "camera", "watch", "shoes", "chair", "table", "bed", "printer"]


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _NUM_WORDS[s.lower()]


def _money(text: str) -> Optional[int]:
    m = re.search(r"(?:under|within|below|not more than|no more than|max(?:imum)?|budget(?: is| of)?|up ?to|"
                  r"less than|make it|upto)\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b", text, re.I)
    if not m:
        m = re.search(r"(?:₹|rs\.?\s*|inr\s*)([\d,]+(?:\.\d+)?)\s*(k)?\b", text, re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    return int(value * 1000) if m.group(2) else int(value)


def extract_rules(text: str) -> IntentExtraction:
    t = text.lower()
    if re.search(r"\b(refund|return|money back)\b", t):
        return IntentExtraction(intent="REFUND_REQUEST")
    if re.search(r"(where is my order|track(ing)?\b|order status|my order\b)", t):
        return IntentExtraction(intent="ORDER_TRACKING")

    category = None
    if re.search(r"keyboard", t) and re.search(r"mouse|mice", t):
        category = "keyboard_mouse_combo"
    elif re.search(r"\b(sofa|couch|settee|loveseat)\b", t):
        category = "sofa"
    product_query = None
    if category is None:
        for word in _OTHER_PRODUCTS:
            if re.search(rf"\b{word}s?\b", t):
                q = re.search(rf"((?:\w+\s){{0,2}}{word}s?)\b", t)
                product_query = q.group(1).strip() if q else word
                break

    budget = _money(text)
    days = None
    m = re.search(rf"(?:in|within|by|arriv\w* in|delivered in)\s+{_NUM}\s+days?", t)
    if m:
        days = _num(m.group(1))
    compat = ["macOS"] if re.search(r"\b(mac|macos|macbook|imac)\b", t) else []
    brands = [b.strip().title() for b in re.findall(r"prefer(?:ably)?\s+([a-z][\w-]+)", t)]
    seats = None
    m = re.search(rf"{_NUM}[- ]?seat(?:er|s)?", t)
    if m:
        seats = _num(m.group(1))
    width = None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(cm|m)\b(?:\s*(?:wide|width|space|long))?", t)
    if m and (category == "sofa" or re.search(r"wide|width|space|fit", t)):
        width = int(float(m.group(1)) * (100 if m.group(2) == "m" else 1))

    has_constraint = any([budget, days, compat, brands, seats, width])
    shopping_words = re.search(r"\b(find|buy|need|want|looking|get|show|recommend|search|purchase)\b", t)
    if category or product_query or shopping_words or has_constraint:
        intent = "PRODUCT_DISCOVERY"
    else:
        intent = "UNSUPPORTED"

    missing = []
    if intent == "PRODUCT_DISCOVERY" and not (category or product_query) and not has_constraint:
        missing.append("product")
    if budget is None and re.search(r"\b(affordable|cheap|budget[- ]friendly|inexpensive|low[- ]cost)\b", t):
        missing.append("budget")
    if category == "sofa":
        if seats is None:
            missing.append("seats")
        if width is None:
            missing.append("max_width_cm")

    return IntentExtraction(intent=intent, category=category, product_query=product_query, max_total_inr=budget,
                            max_delivery_days=days, required_compatibility=compat, preferred_brands=brands,
                            seats=seats, max_width_cm=width, missing_info=missing)


# --------------------------------------------------------------------------- Claude extraction
def llm_available() -> bool:
    if os.environ.get("INTENTGUARD_LLM", "").lower() in {"off", "0", "false"}:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def extract_llm(text: str, prior: Optional[Intent]) -> tuple[Optional[IntentExtraction], dict]:
    """Call Claude with structured outputs. Returns (extraction or None, metadata for the trace)."""
    import anthropic

    client = anthropic.Anthropic()
    prior_json = json.dumps(prior.constraint_fields() if prior else {}, ensure_ascii=False)
    meta: dict = {"model": MODEL, "prompt_version": PROMPT_VERSION}
    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            system=PROMPT_PATH.read_text(),
            messages=[{"role": "user", "content":
                       f"Constraints already confirmed: {prior_json}\n\nShopper's latest message:\n{text}"}],
            output_format=IntentExtraction,
        )
    except anthropic.APIStatusError as exc:
        meta["error"] = f"APIStatusError {exc.status_code}"
        return None, meta
    except anthropic.APIConnectionError as exc:
        meta["error"] = f"APIConnectionError: {exc}"
        return None, meta
    meta["stop_reason"] = response.stop_reason
    meta["served_by"] = response.model
    meta["usage"] = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    if response.stop_reason in ("refusal", "max_tokens") or response.parsed_output is None:
        meta["error"] = f"no parsed output (stop_reason={response.stop_reason})"
        return None, meta
    return response.parsed_output, meta


# --------------------------------------------------------------------------- merge
def merge(prior: Optional[Intent], new: IntentExtraction, extractor: str) -> tuple[Intent, list[str]]:
    """Apply a message's stated fields on top of confirmed state. Returns (intent, changed_fields)."""
    if prior is None or new.intent != "PRODUCT_DISCOVERY" or prior.intent != "PRODUCT_DISCOVERY":
        return Intent(**new.model_dump(), extractor=extractor), []

    data = prior.model_dump()
    changed: list[str] = []
    new_product = new.category is not None or new.product_query is not None
    if new_product and (new.category, new.product_query) != (prior.category, prior.product_query):
        # A different product is a new search: drop product-specific constraints, keep budget/delivery.
        for f in ("seats", "max_width_cm", "required_compatibility", "preferred_brands"):
            data[f] = [] if isinstance(data[f], list) else None
        data["category"], data["product_query"] = new.category, new.product_query
        changed += ["category"]
    for f in ("max_total_inr", "max_delivery_days", "seats", "max_width_cm"):
        v = getattr(new, f)
        if v is not None and v != data[f]:
            data[f] = v
            changed.append(f)
    for f in ("required_compatibility", "preferred_brands"):
        v = getattr(new, f)
        if v and v != data[f]:
            data[f] = sorted(set(data[f]) | set(v)) if f == "required_compatibility" else v
            changed.append(f)

    # Recompute what is still missing from the merged state.
    missing = [m for m in new.missing_info if m not in ("product",) or not (data["category"] or data["product_query"])]
    if data["category"] == "sofa":
        missing = [m for m in missing if m not in ("seats", "max_width_cm")]
        if data["seats"] is None:
            missing.append("seats")
        if data["max_width_cm"] is None:
            missing.append("max_width_cm")
    if "budget" in missing and data["max_total_inr"] is not None:
        missing.remove("budget")
    data["missing_info"] = list(dict.fromkeys(missing))
    data["extractor"] = extractor
    data["version"] = prior.version + (1 if changed else 0)
    return Intent(**data), changed


def extract(text: str, prior: Optional[Intent]) -> tuple[Intent, list[str], dict]:
    """Run Claude if configured, else the rules baseline. Returns (intent, changed_fields, trace metadata)."""
    meta: dict = {}
    extraction, extractor = None, "rules_fallback"
    if llm_available():
        extraction, meta = extract_llm(text, prior)
        if extraction is not None:
            extractor = f"llm:{MODEL}:{PROMPT_VERSION}"
        else:
            meta["fallback"] = "rules_fallback used after LLM failure"
    else:
        meta["llm"] = "not configured (no ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN, or INTENTGUARD_LLM=off)"
    if extraction is None:
        extraction = extract_rules(text)
    intent, changed = merge(prior, extraction, extractor)
    return intent, changed, meta
