"""Intent schema, Claude structured extraction, and a deterministic rule-based fallback.

The extractor actually used is recorded on every Intent (`extractor`) and in the trace, so a
fallback run is never presented as AI output.

v2 (PRD rules R1-R4): the agent knows which page the shopper is on (listing or product), can tell a
question about the current product from a request to buy it or to see similar ones, and extracts
*any* product phrase. Whether the store sells that product is decided later by a catalog search,
never by whether this module happens to know the word.

v3 (PRD §6A, Phase 1 of BUILD_PLAN.md): non-shopping messages are sorted into kinds (greeting, thanks,
off-topic, nonsense, rude, trick, compare, Hinglish, catch-all) so they never reach the product search,
follow-ups refine the current product ("2 seater", "2", "for 2 people"), and requirements can be removed
("forget the width").
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

import llm

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "intent_v4"
PROMPT_PATH = Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt"

IntentType = Literal["PRODUCT_DISCOVERY", "PRODUCT_QUESTION", "BUY_THIS", "REFUND_REQUEST", "ORDER_TRACKING",
                     "UNSUPPORTED"]
# For UNSUPPORTED messages: which kind of non-shopping message it is (PRD §6A blocks B3, B12, B14-B17, B27).
MessageKind = Literal["GREETING", "THANKS", "OFF_TOPIC", "UNCLEAR", "ABUSIVE", "TRICK", "COMPARE", "HINGLISH",
                      "CATCH_ALL", "HELP", "STORE_INFO"]
RemovableField = Literal["max_total_inr", "max_delivery_days", "seats", "max_width_cm", "max_depth_cm",
                         "max_height_cm", "material"]


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
    message_kind: Optional[MessageKind] = None              # set only when intent is UNSUPPORTED
    remove_fields: list[RemovableField] = Field(default_factory=list)   # "forget the width" -> ["max_width_cm"]
    material: Optional[str] = None           # "only leather", "solid wood" (B33)
    show_results: bool = False               # "show me the results" (B31)
    frustrated: bool = False                 # "are you not capable…", "I already told you" (B36)
    quantity: Optional[int] = None           # "buy 2 of these" (B26)
    vague_quality: Optional[str] = None      # "is it wide?" with no number (B28)
    other_products: list[str] = Field(default_factory=list)   # "bedsheets and curtains" -> ["curtains"] (B13)


class Intent(IntentExtraction):
    """Confirmed session state after merging messages. `version` bumps whenever a constraint changes."""
    version: int = 1
    extractor: str = "rules_fallback"
    stated_now: list[str] = Field(default_factory=list)   # constraint fields stated in the latest message only
    approval_required: bool = True  # never buys without explicit approval
    waived: list[str] = Field(default_factory=list)       # requirements the shopper said not to care about

    def constraint_fields(self) -> dict:
        return self.model_dump(include={"category", "product_query", "material", "max_total_inr", "max_delivery_days",
                                        "required_compatibility", "preferred_brands", "seats", "max_width_cm",
                                        "max_depth_cm", "max_height_cm"})


CONSTRAINT_FIELDS = ("max_total_inr", "max_delivery_days", "seats", "max_width_cm", "max_depth_cm", "max_height_cm",
                     "material")

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
                       r"(\s+(there|all|team|everyone|folks))?[\s!.,?]*$", re.I)
_BUY = re.compile(r"\b(buy|order|purchase|add (it |this )?to (my )?cart|checkout|check out|i'?ll take)\b", re.I)
_SIMILAR = re.compile(r"\b(similar|alternatives?|other options|like this|anything else|something else|"
                      r"cheaper|less expensive|lower price)\b", re.I)
_CUT = re.compile(r"\b(under|within|below|not more than|no more than|max(?:imum)?|up ?to|upto|less than|that|"
                  r"which|with|for|arriving|arrive|delivered|delivery|by|including|incl|prefer(?:ably)?|around|"
                  r"budget|costing|priced|in|to fit|fits?|and it|but)\b|[₹,.;!?]")
# Words that describe a requirement, not a product: "2 seater" refines the current product, it isn't one.
_REQ_WORDS = {"seater", "seaters", "seat", "seats", "people", "persons", "person", "wide", "width", "size",
              "limit", "budget", "rupees", "rs", "inr", "cm", "make", "change", "forget", "remove", "drop",
              "instead", "only", "any", "price", "delivery", "days", "deep", "tall", "high", "long", "smaller",
              "bigger", "larger", "space", "room", "matter", "fine", "ok", "okay", "please", "works", "matter", "matters"}
_THANKS = re.compile(r"^\s*(thanks|thank you|thank u|thx|ty|cheers)\b[\s\w!.,]{0,20}$", re.I)
_TRICK = re.compile(r"ignore (?:all |your |the |previous |my |any )*(?:rules|instructions|policy|policies|limits)|"
                    r"without (?:my |any |an )?approval|skip (?:the )?approval|you(?:'re| are) allowed to|"
                    r"\bpretend\b|act as if|\boverride\b|\bbypass\b|(?:set|change|make) the price|jailbreak|"
                    r"developer mode|system prompt", re.I)
_COMPARE = re.compile(r"\bcompare\b|\bcomparison\b|which (?:one )?is better|\bvs\.?\b|\bversus\b|"
                      r"difference between|pros and cons|which (?:\w+ )?is (?:the )?best between", re.I)
_INSULTS = {"useless", "stupid", "idiot", "idiotic", "dumb", "rubbish", "trash", "pathetic", "moron", "garbage",
            "crap", "sucks", "suck", "worst", "hate", "shut", "bloody", "nonsense", "fool", "loser"}
_OFF_TOPIC = re.compile(r"^\s*(?:please\s+|can you\s+|could you\s+)?(?:write|compose|sing|translate|calculate|"
                        r"solve|summari[sz]e|draw|tell me a (?:joke|story))\b|"
                        r"\b(?:song|songs|poem|joke|essay|homework|weather|news|movie|movies|film|films|music)\b|"
                        r"\d+\s*[x×*+/-]\s*\d+|^\s*(?:who|what) are you\b|\byour name\b|"
                        r"\bare you (?:a |an )?(?:bot|human|robot|ai|real)\b", re.I)
_NONSENSE_WORDS = {"bla", "blah", "asdf", "qwerty", "lol", "hmm", "hmmm", "xyz", "abc", "test", "testing", "jk",
                   "lorem", "ipsum", "zzz", "aaa", "sdf", "jkl", "hjkl", "zxcv", "qwer", "asd", "fgh"}
# Common Hinglish words (B16). Rules mode only recognises these; anything else falls to the catch-all.
_HINGLISH = {"chahiye", "chaiye", "chahie", "dikhao", "dikha", "dikhana", "mujhe", "muje", "tak", "kuch", "accha",
             "acha", "achha", "wala", "wali", "liye", "sasta", "sasti", "batao", "kya", "hai", "hain", "nahi",
             "aur", "mein", "dena", "chahta", "chahti", "bhai", "yaar", "kitna", "kitne"}
_REMOVE = re.compile(r"\b(?:forget|remove|drop|ignore|clear|never mind|don'?t care about|no)\s+(?:the\s+|my\s+|about\s+)?"
                     r"(width|size|budget|price|seats?|delivery|space|room|material)(?:\s+limit)?\b|"
                     r"\bany (width|size|price|budget|material)\b", re.I)
_REMOVE_MAP = {"width": "max_width_cm", "size": "max_width_cm", "space": "max_width_cm", "room": "max_width_cm",
               "budget": "max_total_inr", "price": "max_total_inr", "seat": "seats", "seats": "seats",
               "delivery": "max_delivery_days", "material": "material"}
# A non-answer to the agent's question about seats or width drops that requirement (B32).
_NON_ANSWER = re.compile(r"^\s*(no (?:space|limit|preference|idea)|doesn'?t matter|does not matter|any|anything|whatever|"
                         r"not sure|don'?t know|dunno|idk|no)\b", re.I)


_HELP = re.compile(r"\bwhat (?:else )?can you (?:do|help)|how can you help|\bwhat do you do\b|^\s*help\s*[.!?]*$|"
                   r"how does this work|what are you capable|what can i (?:ask|do|buy)|what can you help", re.I)
_STORE_INFO = re.compile(r"how many (?:products|items|things)|what (?:categories|kind of (?:products|things|items))|"
                         r"which categories|what (?:do you|does this store) sell|which brands|what brands|how many brands|"
                         r"\bpay(?:ment)?\b|cash on delivery|\bcod\b|\bemi\b|\bpolicy\b", re.I)
_SHOW = re.compile(r"\b(?:show|share|give|see|display|list)\b[^.?!]*\b(?:results?|what you (?:have|got)|options|"
                   r"everything|all of them|them)\b|\bjust show\b|\bshow (?:me )?(?:now|already)\b", re.I)
_FRUSTRATED = re.compile(r"are you not capable|aren'?t you capable|can'?t you understand|don'?t you understand|"
                         r"i already told you|i told you|not listening|are you even listening|i just said", re.I)
_MATERIALS = ["solid wood", "engineered wood", "leatherette", "leather", "fabric", "wooden", "wood", "metal",
              "cotton", "velvet", "cane", "bamboo", "rattan", "jute", "marble"]
_MATERIAL_RE = re.compile(r"\b(" + "|".join(_MATERIALS) + r")\b", re.I)
_QTY = re.compile(rf"\b(?:buy|order|get|add|want|take)\s+{_NUM}\b(?![- ]?seat)|\b{_NUM}\s+(?:of (?:these|them|this|it)|"
                  r"pieces|units|nos|pcs)\b", re.I)
_VAGUE_Q = re.compile(r"\b(?:is|are|will|would)\b.*\b(wide|big|small|large|long|tall|spacious|comfortable|comfy|roomy)\b",
                      re.I)
_OUTPUT_WORDS = {"results", "result", "options", "option", "query", "queries", "asked", "have", "got", "first",
                 "them", "everything", "list", "share", "what", "now", "already", "capable", "understanding",
                 "understand", "only", "made"}


def material_of(text: str) -> Optional[str]:
    m = _MATERIAL_RE.search(text or "")
    if not m:
        return None
    w = m.group(1).lower()
    return {"wooden": "wood"}.get(w, w)


def message_kind(text: str) -> Optional[str]:
    """Kinds of non-shopping message that the rules can recognise on their own (B3, B12, B14, B15, B16, B27).
    Returns None for anything that may be a shopping request."""
    t = text.lower().strip()
    words = re.findall(r"[a-z]+", t)
    if _THANKS.match(t):
        return "THANKS"
    if _GREETING.match(text):
        return "GREETING"
    if _TRICK.search(t):
        return "TRICK"
    if _HELP.search(t):
        return "HELP"
    if _STORE_INFO.search(t):
        return "STORE_INFO"
    if _COMPARE.search(t):
        return "COMPARE"
    if set(words) & _INSULTS:
        return "ABUSIVE"
    if _OFF_TOPIC.search(t):
        return "OFF_TOPIC"
    if words and not re.search(r"\d", t) and all(w in _NONSENSE_WORDS or not re.search(r"[aeiouy]", w)
                                                 for w in words):
        return "UNCLEAR"
    if not words and t and not re.search(r"\d", t):
        return "UNCLEAR"
    if set(words) & _HINGLISH:
        return "HINGLISH"
    return None


# Common English words that are never a product. If any is left in the product phrase, the message wasn't
# really naming a product ("width doesn't matter" -> "doesn t"; "good night" -> "night"), so the agent must not
# answer "We don't sell …" (R1); it gives the catch-all reply instead (B17). Found by the held-out set.
_NOT_PRODUCT = {
    "i", "me", "you", "we", "they", "he", "she", "it", "us", "them", "one", "ones", "everything", "nothing",
    "someone", "everyone", "all", "these", "those", "there", "here", "what", "why", "how", "when", "where", "who",
    "give", "take", "place", "put", "do", "does", "doesn", "don", "didn", "isn", "aren", "wasn", "won", "can",
    "could", "would", "should", "will", "shall", "may", "might", "must", "go", "come", "see", "tell", "say",
    "know", "think", "let", "try", "keep", "start", "stop", "matter", "matters", "mind", "care", "approve", "pay",
    "talk", "speak", "call", "wait", "work", "works", "now", "today", "tonight", "tomorrow", "yesterday", "night",
    "morning", "evening", "later", "soon", "again", "ever", "never", "always", "very", "really", "too", "still",
    "already", "advance", "maybe", "thanks", "discount", "offer", "free", "money", "cash", "problem", "issue",
    "question", "answer", "reason", "way", "time", "day", "week", "year", "t", "s", "ll", "ve", "re", "d", "m"}


def looks_like_product(phrase: Optional[str]) -> bool:
    """False when the leftover phrase contains words that are never products, or single letters."""
    words = re.findall(r"[a-z]+", (phrase or "").lower())
    return bool(words) and not any(w in _NOT_PRODUCT or len(w) == 1 for w in words)


def _without_insults(text: str) -> str:
    """'you are useless, just show me a sofa' -> 'show me a sofa' (B15: help with the request inside)."""
    parts = re.split(r"[,.;!]+|\bjust\b|\bbut\b", text, flags=re.I)
    keep = [p for p in parts if not (set(re.findall(r"[a-z]+", p.lower())) & _INSULTS)]
    return " ".join(p.strip() for p in keep if p.strip())


_MEASURE = re.compile(r"\d+(?:\.\d+)?\s*(?:cms?|centimet(?:er|re)s?|mm|metres?|meters?|mtrs?|m|inch|inches|in|ft|feet|foot|"
                      r"kg|l|litres?|liters?)\b"
                      r"(?:\s*(?:wide|long|tall|high|deep))?", re.I)


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _NUM_WORDS[s.lower()]


def _money(text: str) -> Optional[int]:
    m = re.search(r"(?:under|within|below|not more than|no more than|max(?:imum)?|budget(?: is| of)?|up ?to|"
                  r"less than|make it|upto)\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b", text, re.I)
    if not m:   # Hinglish "20000 tak" = up to ₹20,000
        m = re.search(r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\s+tak\b", text, re.I)
    if not m:
        m = re.search(r"(?:₹|rs\.?\s*|inr\s*)([\d,]+(?:\.\d+)?)\s*(k)?\b", text, re.I)
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    return int(value * 1000) if m.group(2) else int(value)


_UNIT = (r"(cms?|centimet(?:er|re)s?|mm|millimet(?:er|re)s?|metres?|meters?|mtrs?|m|inch(?:es)?|in|ft|feet|foot)")


def _cm(value: str, unit: str) -> int:
    u = unit.lower()
    f = (1 if u.startswith("c") else 0.1 if u.startswith("mm") or u.startswith("milli") else
         2.54 if u.startswith("in") else 30.48 if u in ("ft", "feet", "foot") else 100)
    return int(round(float(value) * f))


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
    if re.match(r"\s*to\s+(?!buy\b)", rest):
        return None                                  # "I want to talk to a human" is an action, not a product
    rest = _CUT.split(rest, maxsplit=1)[0]
    rest = _MEASURE.sub(" ", rest)
    rest = _MATERIAL_RE.sub(" ", rest)           # a material is a requirement, not the product ("leather sofa")
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9-]*", rest)
             if w not in _VAGUE and w not in _REQ_WORDS and w not in _NUM_WORDS and w not in _OUTPUT_WORDS]
    words = [w for w in words if re.search(r"[a-z]", w)]
    return " ".join(words) or None


def head_term(phrase: Optional[str]) -> Optional[str]:
    """Last word of a product phrase, singular: '3-seater sofas' -> 'sofa'."""
    words = re.findall(r"[a-z]+", (phrase or "").lower())
    if not words:
        return None
    w = words[-1]
    return re.sub(r"(es|s)$", "", w) if len(w) > 3 and not w.endswith("ss") else w


def extract_rules(text: str, context: Optional[dict] = None, prior: Optional[Intent] = None) -> IntentExtraction:
    page = (context or {}).get("page", "listing")
    t = text.lower()
    if re.search(r"\b(refund|return|money back)\b", t) and not re.search(r"\bpolicy\b", t):
        return IntentExtraction(intent="REFUND_REQUEST")
    if re.search(r"(where is my order|track(ing)?\b|order status|my order\b)", t):
        return IntentExtraction(intent="ORDER_TRACKING")
    if page == "listing":
        parts = [s for s in re.split(r"\s+and\s+|\s*&\s*|\s*,\s*", text) if s.strip()]
        phrases = [product_phrase(s) for s in parts]
        combo = re.search(r"keyboard", text, re.I) and re.search(r"mouse|mice", text, re.I)
        refers = re.search(r"\b(these|those|them|both|two|it|pros|cons)\b", text, re.I)
        if len(parts) >= 2 and all(phrases) and all(looks_like_product(ph) for ph in phrases) \
                and message_kind(text) is None and not combo and not refers:
            first = extract_rules(parts[0], context, prior)
            budget = _money(text)
            return first.model_copy(update={"other_products": [x for x in phrases[1:]],
                                            "max_total_inr": first.max_total_inr or budget})     # B13
    kind = message_kind(text)
    if kind == "ABUSIVE":
        rest = _without_insults(text)
        if rest and message_kind(rest) is None:
            inner = extract_rules(rest, context, prior)
            if inner.intent != "UNSUPPORTED" and (inner.product_query or inner.category or inner.question):
                return inner                         # B15: help with the real request inside a rude message
    if kind == "HINGLISH":
        cand = " ".join(w for w in re.findall(r"[a-z]+", t) if w not in _HINGLISH and w not in _VAGUE
                        and w not in _REQ_WORDS and w not in ("rs", "inr", "k"))
        return IntentExtraction(intent="UNSUPPORTED", message_kind="HINGLISH", product_query=cand or None,
                                max_total_inr=_money(text))
    show, frustrated = bool(_SHOW.search(t)), bool(_FRUSTRATED.search(t))
    if (show or frustrated) and kind not in ("TRICK", "HELP", "STORE_INFO", "COMPARE"):
        phrase = product_phrase(text)
        return IntentExtraction(intent="PRODUCT_DISCOVERY", show_results=True, frustrated=frustrated,
                                product_query=phrase if phrase and looks_like_product(phrase) else None,
                                max_total_inr=_money(text))
    if kind is not None:
        return IntentExtraction(intent="UNSUPPORTED", message_kind=kind)
    if page == "listing" and re.match(r"\s*(who|what|why|when|where|how|can you|could you|will you|are you|do you)\b", t) \
            and not re.search(_SHOP_VERB, t) and not re.search(r"\b(sofa|couch|price|cost|cheap)", t) \
            and len(re.findall(r"[a-z]+", t)) >= 3:
        return IntentExtraction(intent="UNSUPPORTED", message_kind="OFF_TOPIC")

    # ---- constraints (any page)
    budget = _money(text)
    days = None
    m = re.search(rf"(?:in|within|by|arriv\w* in|delivered in)\s+{_NUM}\s+days?", t)
    if m:
        days = _num(m.group(1))
    compat = ["macOS"] if re.search(r"\b(mac|macos|macbook|imac)\b", t) else []
    brands = [b.strip().title() for b in re.findall(r"prefer(?:ably)?\s+([a-z][\w-]+)", t)]
    seats = None
    m = re.search(rf"{_NUM}[- ]?seat(?:er|s)?", t) or re.search(rf"\bfor {_NUM} (?:people|persons|person)\b", t)
    if m:
        seats = _num(m.group(1))
    pending = list((context or {}).get("pending_question") or (prior.missing_info if prior is not None else []))
    m = re.fullmatch(rf"\s*{_NUM}\s*[.!]?\s*", t)
    if m:
        n = _num(m.group(1))
        if "seats" in pending and n <= 10:
            seats = n                                # a bare "2" answers our seats question (B19)
        elif "max_width_cm" in pending and n >= 40:
            width = n                                # a bare "200" answers our width question (B32)
    removed = list(dict.fromkeys(_REMOVE_MAP[(g1 or g2).lower()] for g1, g2 in
                                 (mm.groups() for mm in _REMOVE.finditer(t))))
    if not removed and _NON_ANSWER.match(t) and any(f in pending for f in ("seats", "max_width_cm")):
        removed = [f for f in ("seats", "max_width_cm") if f in pending]       # "no space" to our question (B32)
    width = depth = height = None
    lone_measure = bool(re.fullmatch(rf"\s*(?:about|around|max|upto|up to)?\s*\d+(?:\.\d+)?\s*{_UNIT}\s*[.!]?\s*", t))
    for m in re.finditer(rf"(\d+(?:\.\d+)?)\s*{_UNIT}\b(?:\s*(wide|width|deep|depth|tall|high|height|long))?", t):
        cm, dim = _cm(m.group(1), m.group(2)), (m.group(3) or "")
        if dim in ("deep", "depth"):
            depth = cm
        elif dim in ("tall", "high", "height"):
            height = cm
        elif dim in ("wide", "width", "long") or re.search(r"wide|width|space|fit|wall", t) or lone_measure:
            width = cm                               # a lone "200cms" is a width (B32)
    material = material_of(text)
    quantity = None
    mq = _QTY.search(t)
    if mq:
        quantity = _num(next(g for g in mq.groups() if g))
    category = None
    if re.search(r"keyboard", t) and re.search(r"mouse|mice", t):
        category = "keyboard_mouse_combo"
    elif re.search(r"\b(sofa|couch|settee)\b", t) and not re.search(r"\bcover", t):
        category = "sofa"
    phrase = product_phrase(text)
    if phrase is None and category is not None:      # the real catalog searches by words, not fixture categories
        phrase = {"sofa": "sofa", "keyboard_mouse_combo": "keyboard mouse combo"}[category]
    common = dict(max_total_inr=budget, max_delivery_days=days, required_compatibility=compat,
                  preferred_brands=brands, seats=seats, max_width_cm=width, max_depth_cm=depth, max_height_cm=height,
                  remove_fields=removed, material=material, quantity=quantity)
    has_constraint = any([budget, days, compat, brands, seats, width, depth, height, removed, material])

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
    if intent == "PRODUCT_DISCOVERY" and not (category or phrase or has_constraint) \
            and re.search(r"\bto\s+(?!buy\b)[a-z]+", t) and not re.match(r"\s*(something|anything)\b", t):
        # "I want to talk to a human": a shopping verb, but no product and no requirement (B17)
        return IntentExtraction(intent="UNSUPPORTED", message_kind="CATCH_ALL")

    vague = None
    mv = _VAGUE_Q.search(t)
    if mv and page == "listing" and width is None and not re.search(r"\d", t):
        vague = mv.group(1).lower()                  # "is the hometown sofa wide?" (B28)
    missing = []
    if intent == "PRODUCT_DISCOVERY" and not (category or phrase) and not has_constraint:
        missing.append("product")
    if budget is None and re.search(r"\b(affordable|cheap|budget[- ]friendly|inexpensive|low[- ]cost)\b", t):
        missing.append("budget")
    # B18 (search first): sofas no longer require seats and width before a search.
    return IntentExtraction(intent=intent, category=category, product_query=phrase, missing_info=missing,
                            vague_quality=vague,
                            message_kind="CATCH_ALL" if intent == "UNSUPPORTED" and page == "listing" else None,
                            **common)


# --------------------------------------------------------------------------- Claude extraction
def llm_available() -> bool:
    return llm.provider() is not None


def extract_llm(text: str, prior: Optional[Intent], context: Optional[dict] = None
                ) -> tuple[Optional[IntentExtraction], dict]:
    """Ask the configured model (llm.py) for the structured fields. Returns (extraction or None, trace metadata)."""
    prior_json = json.dumps(prior.constraint_fields() if prior else {}, ensure_ascii=False)
    ctx = context or {"page": "listing"}
    page_line = (f"The shopper is on the product page for: {ctx.get('product_title', ctx.get('product_id'))}"
                 if ctx.get("page") == "product" else "The shopper is on the product listing page.")
    asked = ctx.get("pending_question")
    asked_line = (f"\nThe assistant just asked the shopper for: {', '.join(asked)}. Read the reply as an answer to "
                  "that first (a bare number, a measurement, or 'no limit' / 'doesn't matter')." if asked else "")
    user = (f"{page_line}\nConstraints already confirmed: {prior_json}{asked_line}\n\n"
            f"Shopper's latest message:\n{text}")
    extraction, meta = llm.structured(PROMPT_PATH.read_text(), user, IntentExtraction, max_tokens=1500)
    meta["prompt_version"] = PROMPT_VERSION
    return extraction, meta


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
            # A different product starts a fresh thread: no requirement carries over (R9, F-021).
            for f in CONSTRAINT_FIELDS + ("required_compatibility", "preferred_brands", "waived"):
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
    for f in new.remove_fields:                       # "forget the width" (B10)
        if f not in data["waived"]:
            data["waived"] = data["waived"] + [f]
        if data[f] is not None:
            data[f] = None
            changed.append(f)
    for f in CONSTRAINT_FIELDS:                       # stating a value again un-waives it
        if getattr(new, f) is not None and f in data["waived"]:
            data["waived"] = [w for w in data["waived"] if w != f]

    # Recompute what is still missing from the merged state.
    missing = [m for m in new.missing_info if m != "product" or not (data["category"] or data["product_query"])]
    missing = [m for m in missing if m not in ("seats", "max_width_cm")]     # B18: search first, never required
    if "budget" in missing and data["max_total_inr"] is not None:
        missing.remove("budget")
    data["missing_info"] = list(dict.fromkeys(missing))
    for f in ("intent", "question", "wants_similar", "wants_cheaper", "message_kind", "remove_fields", "show_results",
              "frustrated", "quantity", "vague_quality", "other_products"):
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
            extractor = f"llm:{meta.get('model')}:{PROMPT_VERSION}"     # the model that actually answered
        else:
            meta["fallback"] = "rules_fallback used after LLM failure"
    else:
        meta["llm"] = "not configured (no ANTHROPIC_API_KEY or OPENROUTER_API_KEY, or INTENTGUARD_LLM=off)"
    if extraction is None:
        extraction = extract_rules(text, context, prior)
    intent, changed = merge(prior, extraction, extractor)
    return intent, changed, meta
