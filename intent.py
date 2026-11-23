"""The shopper's requirements as structured data (Intent), used by the search tool and the cart checks,
plus small helpers. The AI agent (agent_llm.py) fills these in through its tool calls."""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

import llm


IntentType = Literal["PRODUCT_DISCOVERY", "PRODUCT_QUESTION", "BUY_THIS", "REFUND_REQUEST", "ORDER_TRACKING",
                     "UNSUPPORTED", "STORE_POLICY"]
PolicyTopic = Literal["delivery_damage", "installation", "returns", "refunds", "cancellation", "order_limits",
                      "payment", "warranty", "delivery_area", "contact"]
MessageKind = Literal["GREETING", "THANKS", "OFF_TOPIC", "UNCLEAR", "ABUSIVE", "TRICK", "COMPARE", "HINGLISH",
                      "CATCH_ALL", "HELP", "STORE_INFO", "CRITICISM"]
RemovableField = Literal["max_total_inr", "max_delivery_days", "seats", "max_width_cm", "max_depth_cm",
                         "max_height_cm", "material"]


class IntentExtraction(BaseModel):
    """What one user message states. Schema handed to the model via structured outputs."""
    intent: IntentType
    category: Optional[Literal["keyboard_mouse_combo", "sofa"]] = None   # synthetic test-fixture categories only
    product_query: Optional[str] = None      # the shopper's own words for the product, e.g. "3 seater sofa"
    question: Optional[str] = None           # for PRODUCT_QUESTION: what they asked about the current product
    policy_topic: Optional[PolicyTopic] = None   # for STORE_POLICY (PRD B41): which store rule is asked about
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
    extractor: str = "agent"
    stated_now: list[str] = Field(default_factory=list)   # constraint fields stated in the latest message only
    approval_required: bool = True  # never buys without explicit approval
    waived: list[str] = Field(default_factory=list)       # requirements the shopper said not to care about

    def constraint_fields(self) -> dict:
        return self.model_dump(include={"category", "product_query", "material", "max_total_inr", "max_delivery_days",
                                        "required_compatibility", "preferred_brands", "seats", "max_width_cm",
                                        "max_depth_cm", "max_height_cm"})


CONSTRAINT_FIELDS = ("max_total_inr", "max_delivery_days", "seats", "max_width_cm", "max_depth_cm", "max_height_cm",
                     "material")


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


def head_term(phrase: Optional[str]) -> Optional[str]:
    """Last word of a product phrase, singular: '3-seater sofas' -> 'sofa'."""
    words = re.findall(r"[a-z]+", (phrase or "").lower())
    if not words:
        return None
    w = words[-1]
    return re.sub(r"(es|s)$", "", w) if len(w) > 3 and not w.endswith("ss") else w


# --------------------------------------------------------------------------- Claude extraction
def llm_available() -> bool:
    return llm.provider() is not None


