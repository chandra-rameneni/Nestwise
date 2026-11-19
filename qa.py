"""Grounded answers to a shopper's question about ONE product (PRD rules R5, R6).

Order of precedence:
1. Requirement checks ("will it fit a 2 m wall?") are answered by the deterministic policy engine.
2. With Claude configured, the model gets only this product's listing as delimited data and must return
   {answer, cited_fields, not_in_listing}. Code checks every cited field exists on the product; an answer
   citing anything else is rejected (PQ-04).
3. Without Claude, matching spec rows are looked up by keyword. If nothing in the listing mentions the
   topic, the answer is "the listing doesn't say", which is literally true.
Product text is never treated as instructions: it's passed as data, and nothing here can place an order.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

import intent as intent_mod
import llm
import policy
from catalog import ProductView

QA_PROMPT_VERSION = "product_qa_v2"   # v2 (O-33): no verdicts beyond the listing
QA_PROMPT_PATH = Path(__file__).parent / "prompts" / f"{QA_PROMPT_VERSION}.txt"


class ProductAnswer(BaseModel):
    answer: str
    cited_fields: list[str] = Field(default_factory=list)
    not_in_listing: bool = False


@dataclass
class QAResult:
    answer: str
    cited_fields: list[str]
    method: str                      # policy_check | llm | spec_lookup | not_in_listing | rejected_llm_answer
    status: str = "ok"               # ok | not_in_listing | rejected
    meta: dict = field(default_factory=dict)


def listing_fields(p: ProductView) -> dict:
    """Everything the agent may cite, keyed by the name a shopper would see on the product page."""
    out = {"Name": p.title, "Brand": p.brand, "Category": p.category_path or p.category,
           "Price": None if p.list_price_inr is None else f"₹{p.list_price_inr:,} (historical price)",
           "Delivery charge": f"₹{p.shipping_inr:,} (simulated)", "Delivery time": f"{p.delivery_days} days (simulated)",
           "Stock": f"{p.stock} (simulated)", "Description": p.description}
    out.update(p.raw_specs or {k: v for k, v in p.specs.items()})
    return {k: v for k, v in out.items() if v not in (None, "", "NA")}


# keyword -> listing fields that answer it
_TOPICS = [
    (r"\bwide|width|breadth\b", ["Width"]), (r"\bdeep|depth\b", ["Depth"]), (r"\btall|height|high\b", ["Height"]),
    (r"\blong|length\b", ["Length"]), (r"\bdimension|size|big|measure", ["Width", "Depth", "Height", "Length", "Size"]),
    (r"\bweigh|heavy|weight\b", ["Weight"]), (r"\bmade of|material|fabric|wood|leather", ["Primary Material", "Material",
     "Upholstery Type", "Outer Material", "Secondary Material"]), (r"\bcolou?r\b", ["Primary Color", "Color",
     "Upholstery Color", "Finish Color"]), (r"\bseat|people|persons?\b", ["Seating Capacity"]),
    (r"\bprice|cost|how much\b", ["Price"]), (r"\bbrand|who makes|manufacturer\b", ["Brand"]),
    (r"\bwarrant", ["Warranty Summary", "Covered in Warranty", "Not Covered in Warranty", "Warranty Service Type"]),
    (r"\bcapacity|litre|liter\b", ["Capacity"]), (r"\bdeliver|arrive|shipping\b", ["Delivery time", "Delivery charge"]),
    (r"\bstock|available|availability\b", ["Stock"]), (r"\bassembl|install", ["Delivery Condition", "Installation & Demo Details"]),
    (r"\bclean|wash|care\b", ["Care Instructions", "Machine Washable", "Hand Washable"]),
]
# Words shared by many field names; on their own they don't say which field is meant
# ("safe" is in both "Microwave Safe" and "Freezer Safe": eval PQ-07).
_GENERIC_KEY_WORDS = {"safe", "type", "number", "model", "name", "code", "pack", "included", "package", "sales",
                      "contents", "suitable", "ideal", "other", "features", "details", "service"}
_STOP = {"is", "it", "the", "a", "an", "does", "do", "this", "what", "how", "can", "will", "of", "for", "to", "in",
         "be", "my", "i", "you", "are", "there", "any", "have", "has", "with", "and", "or", "me", "tell", "about"}


def _requirement_check(p: ProductView, extracted: intent_mod.IntentExtraction) -> Optional[QAResult]:
    """'Will it fit a 2 m wall?' -> run the same policy check the cart uses, on the requirements stated in
    THIS question only (a limit from an earlier question mustn't turn "how wide is it?" into a fit check)."""
    stated = getattr(extracted, "stated_now", None)
    pick = lambda f: getattr(extracted, f) if stated is None or f in stated else None
    probe = intent_mod.Intent(intent="PRODUCT_DISCOVERY", seats=pick("seats"), max_width_cm=pick("max_width_cm"),
                              max_depth_cm=pick("max_depth_cm"), max_height_cm=pick("max_height_cm"),
                              max_total_inr=pick("max_total_inr"))
    if all(getattr(probe, f) is None for f in ("seats", "max_width_cm", "max_depth_cm", "max_height_cm", "max_total_inr")):
        return None
    e = policy.evaluate(probe, p)
    checks = [c for c in e.checks if c.constraint not in ("in_stock", "listed price")]
    parts, cited = [], []
    names = {"max_width_cm": ("Width", "cm"), "max_depth_cm": ("Depth", "cm"), "max_height_cm": ("Height", "cm"),
             "seats": ("Seating Capacity", ""), "max_total_inr (incl. shipping)": ("Price", "")}
    for c in checks:
        fname, unit = names.get(c.constraint, (c.constraint, ""))
        cited.append(fname)
        if c.status == policy.PASS:
            parts.append(f"Yes on {fname.lower()}: the listing gives {c.observed:g}{(' ' + unit) if unit else ''}, "
                         f"within your {c.required:g}{(' ' + unit) if unit else ''}." if isinstance(c.observed, (int, float))
                         else f"Yes on {fname.lower()}.")
        elif c.status == policy.FAIL:
            parts.append(f"No on {fname.lower()}: the listing gives {c.observed:g}{(' ' + unit) if unit else ''}, "
                         f"more than your {c.required:g}{(' ' + unit) if unit else ''}." if isinstance(c.observed, (int, float))
                         and fname != "Seating Capacity" else f"No on {fname.lower()}: it has {c.observed}, you asked for {c.required}.")
        else:
            why = f" ({c.observed})" if c.observed else ""
            parts.append(f"I can't confirm the {fname.lower()}: the listing doesn't give a usable value{why}.")
    return QAResult(" ".join(parts), cited, "policy_check")


def _spec_lookup(p: ProductView, question: str) -> QAResult:
    fields = listing_fields(p)
    q = question.lower()
    wanted: list[str] = []
    for pattern, keys in _TOPICS:
        if re.search(pattern, q):
            wanted += [k for k in keys if k in fields]
    words = [w for w in re.findall(r"[a-z]+", q) if w not in _STOP and len(w) > 2]
    specific = [w for w in words if w not in _GENERIC_KEY_WORDS]
    for key in fields:  # a word from the question naming a listing field directly, e.g. "microwave safe"
        if key not in ("Name", "Description", "Category") and any(w in key.lower() for w in specific):
            wanted.append(key)
    wanted = list(dict.fromkeys(wanted))
    if wanted:
        rows = []
        for k in wanted:
            v = fields[k]
            note = ""
            attr = {"Width": "width_cm", "Depth": "depth_cm", "Height": "height_cm"}.get(k)
            if attr and attr in p.data_notes:
                note = " That value doesn't look right for this product, so I wouldn't rely on it."
            rows.append(f"{k}: {v}.{note}")
        return QAResult(" ".join(rows), wanted, "spec_lookup")
    topical = [w for w in words if w not in {"listing", "product", "sofa", "item"}]
    desc = (p.description or "").lower()
    if topical and any(w in desc for w in topical):
        return QAResult("The description on this page mentions it, but I can't confirm the details from the "
                        "specs. Take a look at the description.",
                        ["Description"], "spec_lookup")
    return QAResult("The listing doesn't say, so I'd rather not guess.", [], "not_in_listing", status="not_in_listing")


def _ask_llm(p: ProductView, question: str) -> tuple[Optional[ProductAnswer], dict]:
    listing = json.dumps(listing_fields(p), ensure_ascii=False, indent=1)
    ans, meta = llm.structured(QA_PROMPT_PATH.read_text(),
                               f"<product_listing>\n{listing}\n</product_listing>\n\nShopper's question: {question}",
                               ProductAnswer, max_tokens=1000)
    meta["prompt_version"] = QA_PROMPT_VERSION
    return ans, meta


def validate(answer: ProductAnswer, p: ProductView) -> Optional[str]:
    """Returns why an LLM answer must be rejected, or None if it's grounded in this product's fields."""
    fields = listing_fields(p)
    if answer.not_in_listing:
        return None
    if not answer.cited_fields:
        return "answer cites no listing field"
    unknown = [f for f in answer.cited_fields if f not in fields]
    if unknown:
        return f"cites fields this product doesn't have: {unknown}"
    return None


def answer_about_product(p: ProductView, question: str, extracted: intent_mod.IntentExtraction,
                         use_llm: Optional[bool] = None) -> QAResult:
    checked = _requirement_check(p, extracted)
    if checked:
        return checked
    if use_llm is None:
        use_llm = intent_mod.llm_available()
    if use_llm:
        ans, meta = _ask_llm(p, question)
        if ans is not None:
            problem = validate(ans, p)
            if problem:
                fallback = _spec_lookup(p, question)
                fallback.method, fallback.status = "rejected_llm_answer", "rejected"
                fallback.meta = dict(meta, rejected=problem, rejected_answer=ans.answer)
                return fallback
            if ans.not_in_listing:
                return QAResult("The listing doesn't say, so I'd rather not guess.", [], "llm", status="not_in_listing", meta=meta)
            return QAResult(ans.answer, ans.cited_fields, "llm", meta=meta)
        result = _spec_lookup(p, question)
        result.meta = dict(meta, fallback="spec lookup after LLM failure")
        return result
    return _spec_lookup(p, question)
