"""Intent schema, Claude structured extraction, and a deterministic rule-based fallback.

The extractor actually used is recorded on every Intent (`extractor`) and in the trace, so a
fallback run is never presented as AI output.

v2 (PRD rules R1-R4): the agent knows which page the shopper is on (listing or product), can tell a
question about the current product from a request to buy it or to see similar ones, and extracts
*any* product phrase. Whether the store sells that product is decided later by a catalog search,
never by whether this module happens to know the word.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "intent_v2"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt"

IntentType = Literal["PRODUCT_DISCOVERY", "PRODUCT_QUESTION", "BUY_THIS", "REFUND_REQUEST", "ORDER_TRACKING",
                     "UNSUPPORTED"]


class IntentExtraction(BaseModel):
    """What one user message states. Schema handed to the model via structured outputs."""
    intent: IntentType
    category: Optional[Literal["keyboard_mouse_combo", "sofa"]] = None   # synthetic test-fixture categories only
    product_query: Optional[str] = None      # the shopper's own words for the product, e.g. "3 seater sofa"
    question: Optional[str] = None           # for PRODUCT_QUESTION: what they asked about the current product
    wants_similar: bool = False              # "anything like this?" on a product page
    wants_cheaper: bool = False              # "anything cheaper?"
    max_total_inr: Optional[int] = None
    max_delivery_days: Optional[int] = None
    required_compatibility: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    seats: Optional[int] = None
    max_width_cm: Optional[int] = None
    max_depth_cm: Optional[int] = None
    max_height_cm: Optional[int] = None
    missing_info: list[str] = Field(default_factory=list)


class Intent(IntentExtraction):
    """Confirmed session state after merging messages. `version` bumps whenever a constraint changes."""
    version: int = 1
    extractor: str = "rules_fallback"
    stated_now: list[str] = Field(default_factory=list)   # constraint fields stated in the latest message only
    approval_required: bool = True  # never buys without explicit approval

    def constraint_fields(self) -> dict:
        return self.model_dump(include={"category", "product_query", "max_total_inr", "max_delivery_days",
                                        "required_compatibility", "preferred_brands", "seats", "max_width_cm",
                                        "max_depth_cm", "max_height_cm"})


CONSTRAINT_FIELDS = ("max_total_inr", "max_delivery_days", "seats", "max_width_cm", "max_depth_cm", "max_height_cm")

# --------------------------------------------------------------------------- rules fallback
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
              "nine": 9, "ten": 10}
_NUM = r"(\d+|" + "|".join(_NUM_WORDS) + r")"
_SHOP_VERB = (r"\b(?:do you (?:sell|have|stock|carry)|have you got|is there|are there|any|"
              r"(?:what'?s|what is|which is|show me|find|get)?\s*the (?:cheapest|best|biggest|smallest|lowest[- ]priced)|"
              r"find|buy|need|want|looking for|look for|show me|show|get|search for|search|recommend|"
              r"purchase|order|i'?m after|shopping for)\b")
_VAGUE = {"something", "anything", "stuff", "item", "items", "product", "products", "thing", "things",
          "affordable", "cheap", "cheaper", "nice", "good", "great", "best", "actually", "ok", "okay", "also",
          "and", "yes", "no", "maybe", "it", "one", "this", "that", "please", "me", "to", "buy", "a", "an",
          "the", "some", "new", "really", "just", "i", "you", "can", "help", "is", "budget", "my", "price",
          "not", "sure", "dunno", "idk", "don't", "dont", "know", "whatever", "hmm", "um", "no idea"}
_GREETING = re.compile(r"^\s*(hi|hello|hey|hiya|thanks|thank you|good (morning|afternoon|evening)|yo|namaste)\b"
                       r"[\s!.,?]*$", re.I)
_BUY = re.compile(r"\b(buy|order|purchase|add (it |this )?to (my )?cart|checkout|check out|i'?ll take)\b", re.I)
_SIMILAR = re.compile(r"\b(similar|alternatives?|other options|like this|anything else|something else|"
                      r"cheaper|less expensive|lower price)\b", re.I)
_CUT = re.compile(r"\b(under|within|below|not more than|no more than|max(?:imum)?|up ?to|upto|less than|that|"
                  r"which|with|for|arriving|arrive|delivered|delivery|by|including|incl|prefer(?:ably)?|around|"
                  r"budget|costing|priced|in|to fit|fits?|and it|but)\b|[₹,.;!?]")
_MEASURE = re.compile(r"\d+(?:\.\d+)?\s*(?:cm|mm|m|inch|inches|in|ft|feet|kg|l|litres?|liters?)\b"
                      r"(?:\s*(?:wide|long|tall|high|deep))?", re.I)


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


def _cm(value: str, unit: str) -> int:
    return int(round(float(value) * {"cm": 1, "mm": 0.1, "m": 100, "inch": 2.54, "inches": 2.54, "in": 2.54,
                                     "ft": 30.48, "feet": 30.48}[unit.lower()]))


def product_phrase(text: str) -> Optional[str]:
    """The shopper's words for the product, or None if they didn't name one.
    'Find a 3-seater sofa under ₹30,000' -> '3-seater sofa'; 'mobile' -> 'mobile'; 'air fryer?' -> 'air fryer';
    'I need something affordable' -> None."""
    t = text.lower().strip()
    m = re.search(_SHOP_VERB + r"\s+(?:me\s+)?(?:to buy\s+)?(?:(?:a|an|the|some|any)\s+)?(.+)", t)
    if m:
        rest = m.group(1)
    elif len(re.findall(r"[a-z]+", t)) <= 4:
        rest = t                                    # a bare product name: "mobile", "air fryer"
    else:
        return None
    if re.match(r"\s*(something|anything|stuff|things?)\b", rest):
        return None                                  # "something to sit on" names no product (eval CL-03)
    rest = _CUT.split(rest, maxsplit=1)[0]
    rest = _MEASURE.sub(" ", rest)
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9-]*", rest) if w not in _VAGUE]
    words = [w for w in words if re.search(r"[a-z]", w)]
    return " ".join(words) or None


def head_term(phrase: Optional[str]) -> Optional[str]:
    """Last word of a product phrase, singular: '3-seater sofas' -> 'sofa'."""
    words = re.findall(r"[a-z]+", (phrase or "").lower())
    if not words:
        return None
    w = words[-1]
    return re.sub(r"(es|s)$", "", w) if len(w) > 3 and not w.endswith("ss") else w


def extract_rules(text: str, context: Optional[dict] = None) -> IntentExtraction:
    page = (context or {}).get("page", "listing")
    t = text.lower()
    if re.search(r"\b(refund|return|money back)\b", t):
        return IntentExtraction(intent="REFUND_REQUEST")
    if re.search(r"(where is my order|track(ing)?\b|order status|my order\b)", t):
        return IntentExtraction(intent="ORDER_TRACKING")
    if _GREETING.match(text):
        return IntentExtraction(intent="UNSUPPORTED")

    # ---- constraints (any page)
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
    width = depth = height = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(cm|mm|m|inch|inches|ft|feet)\b(?:\s*(wide|width|deep|depth|tall|"
                         r"high|height|long))?", t):
        cm, dim = _cm(m.group(1), m.group(2)), (m.group(3) or "")
        if dim in ("deep", "depth"):
            depth = cm
        elif dim in ("tall", "high", "height"):
            height = cm
        elif dim in ("wide", "width", "long") or re.search(r"wide|width|space|fit|wall", t):
            width = cm

    category = None
    if re.search(r"keyboard", t) and re.search(r"mouse|mice", t):
        category = "keyboard_mouse_combo"
    elif re.search(r"\b(sofa|couch|settee)\b", t) and not re.search(r"\bcover", t):
        category = "sofa"
    phrase = product_phrase(text)
    if phrase is None and category is not None:      # the real catalog searches by words, not fixture categories
        phrase = {"sofa": "sofa", "keyboard_mouse_combo": "keyboard mouse combo"}[category]
    common = dict(max_total_inr=budget, max_delivery_days=days, required_compatibility=compat,
                  preferred_brands=brands, seats=seats, max_width_cm=width, max_depth_cm=depth, max_height_cm=height)
    has_constraint = any([budget, days, compat, brands, seats, width, depth, height])

    # ---- product page: buy this / similar / a question about this product
    if page == "product":
        if _BUY.search(t) and not re.search(r"\b(should i|can i|how do i|is it worth)\b", t):
            return IntentExtraction(intent="BUY_THIS", **common)
        if _SIMILAR.search(t):
            return IntentExtraction(intent="PRODUCT_DISCOVERY", wants_similar=True,
                                    wants_cheaper=bool(re.search(r"cheaper|less expensive|lower price", t)), **common)
        if phrase is None or "?" in text or re.match(r"\s*(what|how|is|does|do|can|will|which|are|has|have|"
                                                     r"tell me|any)\b", t):
            return IntentExtraction(intent="PRODUCT_QUESTION", question=text.strip(), **common)

    if category or phrase or re.search(_SHOP_VERB, t) or has_constraint or re.match(r"\s*(something|anything)\b", t):
        intent = "PRODUCT_DISCOVERY"
    else:
        intent = "UNSUPPORTED"

    missing = []
    if intent == "PRODUCT_DISCOVERY" and not (category or phrase) and not has_constraint:
        missing.append("product")
    if budget is None and re.search(r"\b(affordable|cheap|budget[- ]friendly|inexpensive|low[- ]cost)\b", t):
        missing.append("budget")
    if head_term(phrase) in ("sofa", "couch", "settee") or category == "sofa":
        if seats is None:
            missing.append("seats")
        if width is None:
            missing.append("max_width_cm")
    return IntentExtraction(intent=intent, category=category, product_query=phrase, missing_info=missing, **common)


# --------------------------------------------------------------------------- Claude extraction
def llm_available() -> bool:
    if os.environ.get("INTENTGUARD_LLM", "").lower() in {"off", "0", "false"}:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def extract_llm(text: str, prior: Optional[Intent], context: Optional[dict] = None
                ) -> tuple[Optional[IntentExtraction], dict]:
    """Call Claude with structured outputs. Returns (extraction or None, metadata for the trace)."""
    import anthropic

    client = anthropic.Anthropic()
    prior_json = json.dumps(prior.constraint_fields() if prior else {}, ensure_ascii=False)
    ctx = context or {"page": "listing"}
    page_line = (f"The shopper is on the product page for: {ctx.get('product_title', ctx.get('product_id'))}"
                 if ctx.get("page") == "product" else "The shopper is on the product listing page.")
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
                       f"{page_line}\nConstraints already confirmed: {prior_json}\n\n"
                       f"Shopper's latest message:\n{text}"}],
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
def _same_product(a: Optional[str], b: Optional[str]) -> bool:
    return head_term(a) == head_term(b)


def merge(prior: Optional[Intent], new: IntentExtraction, extractor: str) -> tuple[Intent, list[str]]:
    """Apply a message's stated fields on top of confirmed state. Returns (intent, changed_fields).

    Questions and buy-this requests on a product page also carry constraints ("buy it if it's under
    ₹15,000"); those update the confirmed state like any other message."""
    stated = [f for f in CONSTRAINT_FIELDS if getattr(new, f) is not None]
    if prior is None:
        return Intent(**new.model_dump(), extractor=extractor, stated_now=stated), []
    if new.intent in ("REFUND_REQUEST", "ORDER_TRACKING", "UNSUPPORTED"):
        return Intent(**new.model_dump(), extractor=extractor, stated_now=stated), []

    data = prior.model_dump()
    changed: list[str] = []
    new_product = new.category is not None or new.product_query is not None
    if new_product and not (new.category == prior.category and _same_product(new.product_query, prior.product_query)):
        if new.category is None and new.product_query is None:
            pass
        elif prior.product_query is None and prior.category is None:
            data["category"], data["product_query"] = new.category, new.product_query
            changed.append("product")
        else:
            # A different product is a new search: drop product-specific constraints, keep budget/delivery.
            for f in ("seats", "max_width_cm", "max_depth_cm", "max_height_cm", "required_compatibility",
                      "preferred_brands"):
                data[f] = [] if isinstance(data[f], list) else None
            data["category"], data["product_query"] = new.category, new.product_query
            changed.append("product")
    elif new.product_query and new.product_query != prior.product_query:
        data["product_query"] = new.product_query       # same product, more specific words: not a constraint change
    for f in CONSTRAINT_FIELDS:
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
    missing = [m for m in new.missing_info if m != "product" or not (data["category"] or data["product_query"])]
    if data["category"] == "sofa" or head_term(data["product_query"]) in ("sofa", "couch", "settee"):
        missing = [m for m in missing if m not in ("seats", "max_width_cm")]
        if data["seats"] is None:
            missing.append("seats")
        if data["max_width_cm"] is None:
            missing.append("max_width_cm")
    if "budget" in missing and data["max_total_inr"] is not None:
        missing.remove("budget")
    data["missing_info"] = list(dict.fromkeys(missing))
    for f in ("intent", "question", "wants_similar", "wants_cheaper"):
        data[f] = getattr(new, f)
    data["extractor"] = extractor
    data["stated_now"] = stated
    data["version"] = prior.version + (1 if changed else 0)
    return Intent(**data), changed


def extract(text: str, prior: Optional[Intent], context: Optional[dict] = None) -> tuple[Intent, list[str], dict]:
    """Run Claude if configured, else the rules baseline. Returns (intent, changed_fields, trace metadata)."""
    meta: dict = {}
    extraction, extractor = None, "rules_fallback"
    if llm_available():
        extraction, meta = extract_llm(text, prior, context)
        if extraction is not None:
            extractor = f"llm:{MODEL}:{PROMPT_VERSION}"
        else:
            meta["fallback"] = "rules_fallback used after LLM failure"
    else:
        meta["llm"] = "not configured (no ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN, or INTENTGUARD_LLM=off)"
    if extraction is None:
        extraction = extract_rules(text, context)
    intent, changed = merge(prior, extraction, extractor)
    return intent, changed, meta
