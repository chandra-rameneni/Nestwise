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

QA_PROMPT_VERSION = "product_qa_v3"   # v3 (round 2): human voice, related facts, conversation context; v2: no verdicts
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
           # The page labels prices as historical and stock/delivery as simulated; the values here are plain so
           # answers don't repeat "(simulated)" in every sentence (round 2, O-40).
           "Price": None if p.list_price_inr is None else f"₹{p.list_price_inr:,}",
           "Delivery charge": "free" if not p.shipping_inr else f"₹{p.shipping_inr:,}",
           "Delivery time": f"{p.delivery_days} days", "Stock": f"{p.stock} in stock", "Description": p.description,
           "Photos": "1" if p.image_url else None}
    out.update(p.raw_specs or {k: v for k, v in p.specs.items()})
    return {k: v for k, v in out.items() if v not in (None, "", "NA")}


# keyword -> listing fields that answer it
_TOPICS = [
    (r"\bwide|width|breadth\b", ["Width"]), (r"\bdeep|depth\b", ["Depth"]), (r"\btall|height|high\b", ["Height"]),
    (r"\blong|length\b", ["Length", "Depth"]), (r"\bdimension|size|big|measure", ["Width", "Depth", "Height", "Length", "Size"]),
    (r"\bweigh|heavy|weight\b", ["Weight"]), (r"\bmade of|material|fabric|wood|leather", ["Primary Material", "Primary Material Subtype", "Material",
     "Upholstery Type", "Outer Material", "Secondary Material"]), (r"\bcolou?r\b", ["Primary Color", "Color",
     "Upholstery Color", "Finish Color"]), (r"\bseat|people|persons?\b", ["Seating Capacity"]),
    (r"\bprice|cost|how much\b", ["Price"]), (r"\bbrand|who makes|manufacturer\b", ["Brand"]),
    (r"\bwarrant", ["Warranty Summary", "Covered in Warranty", "Not Covered in Warranty", "Warranty Service Type"]),
    (r"\bcapacity|litre|liter\b", ["Capacity"]), (r"\bdeliver|arrive|shipping\b", ["Delivery time", "Delivery charge"]),
    (r"\bstock|available|availability\b", ["Stock"]), (r"\bassembl|install", ["Delivery Condition", "Installation & Demo Details"]),
    (r"\bclean|wash|care\b", ["Care Instructions", "Machine Washable", "Hand Washable"]),
    (r"\bkids?\b|\bchild|\bsuitable|\bideal for|\bwhich room", ["Suitable For", "Ideal For"]),
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


def product_noun(p: ProductView) -> str:
    """'Ethnic Handicrafts Solid Wood Queen Bed' -> 'bed'; used in warm replies ("this bed")."""
    words = re.findall(r"[A-Za-z]+", p.title or "")
    last = words[-1].lower() if words else ""
    return last if last and len(last) > 2 and last not in {"set", "pack", "combo", "piece"} else "product"


def product_noun_title(title: str) -> str:
    """A short name for a product in replies: 'Ethnic Handicrafts Solid Wood Queen Bed' -> 'queen bed',
    'ABCD XL Bean Bag With Foam Filling' -> 'bean bag' (the part after "with"/"for" is a feature, not the product)."""
    head = re.split(r"\s+(?:with|for|-|\(|\|)\s*", title or "", maxsplit=1, flags=re.I)[0]
    words = [w for w in re.findall(r"[A-Za-z]+", head) if len(w) > 1]
    if not words:
        return "item"
    return " ".join(words[-2:]).lower() if len(words) >= 2 else words[-1].lower()


def not_in_listing_reply(p: ProductView) -> str:
    """B5, round 2: warm, honest, and offers what it can answer (never "I'd rather not guess")."""
    return (f"Sorry, I don't have that detail for this {product_noun(p)}. "
            "I can tell you about its size, materials, delivery or care.")


def _say(p: ProductView, field_name: str, value: str) -> str:
    """One listing fact in plain words (rules mode). Falls back to 'Field: value.' for uncommon fields."""
    v = str(value).strip().rstrip(".")
    mm = measurement_mm(p, field_name) if field_name in MEASURE_FIELDS else None
    if mm is not None:
        word = {"Width": "wide", "Depth": "deep", "Height": "high", "Length": "long"}[field_name]
        return f"It's {format_length(mm, 'cm')} {word} ({format_length(mm, 'mm')})."
    if field_name == "Delivery time":
        return f"It'll arrive in about {v}."
    if field_name == "Delivery charge":
        return "Delivery is free." if v == "free" else f"Delivery costs {v}."
    if field_name == "Price":
        return f"It costs {v}."
    if field_name == "Stock":
        return f"There are {v}."
    if field_name == "Weight":
        return f"It weighs {v}."
    if field_name in ("Primary Material", "Material"):
        return f"It's made of {v.lower()}."
    if field_name == "Primary Material Subtype":
        return f"Specifically, {v}."
    if field_name == "Care Instructions":              # O-64: plain words, not "Care: Handle with Care, …"
        v = v.split("...View More")[0]
        tips = [t.strip().rstrip(".") for t in v.split(",") if t.strip()]
        tips = [t.lower() for t in tips if t.lower() != "handle with care"][:4] or ["handle it with care"]
        joined = tips[0] if len(tips) == 1 else ", ".join(tips[:-1]) + " and " + tips[-1]
        return f"To look after it, {joined}."
    if field_name == "Delivery Condition":             # O-64
        low = v.lower()
        if "knock" in low:
            return "It comes unassembled (flat-packed)."
        if "diy" in low or "do-it-yourself" in low:
            return "It comes unassembled, for you to put together."
        if "assembled" in low:
            return "It comes already assembled."
        return f"It's delivered {low}."
    if field_name == "Installation & Demo Details":    # O-64: already a sentence, so no field label
        return v + "."
    if field_name == "Photos":
        return "There's one photo of it."
    if field_name in ("Suitable For", "Ideal For"):
        return f"It's made for {v.lower()}."
    yes_no = v.lower() in ("yes", "no")
    m = re.match(r"(?i)with (.+)", field_name) or re.match(r"(?i)(.+?) included$", field_name)
    if yes_no and m:                    # "With Mattress: No" -> "Sorry, the mattress isn't included." (O-35)
        thing = m.group(1).strip().lower()
        return (f"Yes, the {thing} is included." if v.lower() == "yes"
                else f"Sorry, the {thing} isn't included.")
    if yes_no:
        return f"{'Yes' if v.lower() == 'yes' else 'No'}, {field_name.lower()}: {v.lower()}."
    # Any other field, said as a sentence rather than a spec-sheet line ("Outer Material: Cotton." reads like a
    # table; coverage tests, 2026-11-20).
    if field_name.lower().endswith("material"):
        return f"Its {field_name.lower()} is {v.lower()}."
    return f"Its {field_name[0].lower() + field_name[1:]} is {v}."


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
            rows.append(f"{_say(p, k, v)}{note}")
        return QAResult(" ".join(rows), wanted, "spec_lookup")
    # The description mentions a word from the question (O-45: only real topic words, never units or filler,
    # and the reply names the word so the shopper can check it).
    units = {w for pat in UNIT_WORDS.values() for w in re.findall(r"[a-z]+", pat)} | {"meters", "metres", "inches"}
    topical = [w for w in words if len(w) >= 5 and w not in units and w not in _GENERIC_KEY_WORDS
               and w not in {"listing", "product", "sofa", "item", "about", "there", "would", "could", "should",
                             "which", "where", "convert", "answer", "question"}]
    desc = (p.description or "").lower()
    hit = next((w for w in topical if re.search(rf"\b{re.escape(w)}", desc)), None)
    if hit:
        return QAResult(f"Sorry, the specs don't cover that, though the description on this page mentions "
                        f"\u201c{hit}\u201d. Have a look there.", ["Description"], "spec_lookup")
    return QAResult(not_in_listing_reply(p), [], "not_in_listing", status="not_in_listing")


def _ask_llm(p: ProductView, question: str, history: Optional[list[str]] = None
             ) -> tuple[Optional[ProductAnswer], dict]:
    listing = json.dumps(listing_fields(p), ensure_ascii=False, indent=1)
    recent = ""
    if history:                      # R11: the last few turns, so "that", "it" and follow-ups make sense
        recent = ("Recent conversation (context only; answer the latest question about this product):\n"
                  + "\n".join(history) + "\n\n")
    ans, meta = llm.structured(QA_PROMPT_PATH.read_text(),
                               f"<product_listing>\n{listing}\n</product_listing>\n\n{recent}Shopper's question: {question}",
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


# O-59 (MM-01/02): "is it waterproof?" -> the model said "not waterproof" because the care text mentions spills.
# A citation proves the field exists, not that it says so. A yes/no on a property must use the property's own word.
_PROPERTY_Q = re.compile(r"^\s*(?:is|are|does|will|would)\s+(?:it|this|they|these|that)\s+(?:be\s+)?(?:a\s+)?([a-z-]{4,})\b")
_NOT_PROPERTIES = {"made", "come", "have", "include", "fit", "need", "work", "available", "safe", "good", "easy"}


def unsupported_verdict(question: str, answer: ProductAnswer, p: ProductView) -> Optional[str]:
    m = _PROPERTY_Q.match((question or "").lower())
    if not m or m.group(1) in _NOT_PROPERTIES or answer.not_in_listing:
        return None
    word = m.group(1)
    stem = word[:6]
    fields = listing_fields(p)
    cited_text = " ".join(str(fields.get(f, "")) for f in answer.cited_fields).lower()
    if stem in cited_text:
        return None                      # the listing really talks about it
    verdict = re.compile(rf"(?:\b(?:not|no|is|it's|are|yes|fully|definitely)|n't)\s+(?:\w+\s+)?{re.escape(word)}\b")
    if verdict.search(answer.answer.lower().replace("’", "'")):
        return f"says yes/no on {word!r} but the cited fields never mention it"
    return None


# ---- measurements and unit conversion (PRD B38): done in code, so it works even when no model answers
MEASURE_FIELDS = ("Width", "Depth", "Height", "Length")
_TO_MM = {"mm": 1, "cm": 10, "m": 1000, "in": 25.4, "inch": 25.4, "inches": 25.4}


def measurement_mm(p: ProductView, field_name: str) -> Optional[float]:
    """A listed measurement in millimetres, or None if missing or flagged as implausible (data_notes)."""
    attr = {"Width": "width_cm", "Depth": "depth_cm", "Height": "height_cm"}.get(field_name)
    if attr and attr in p.data_notes:
        return None
    raw = str(listing_fields(p).get(field_name) or "")
    m = re.match(r"\s*([\d.]+)\s*(mm|cm|m|inches|inch|in)\b", raw.lower())
    return float(m.group(1)) * _TO_MM[m.group(2)] if m else None


UNIT_WORDS = {"m": r"met(?:er|re)s?|m", "cm": r"cm|centimet(?:er|re)s?", "mm": r"mm|millimet(?:er|re)s?",
              "ft": r"feet|foot|ft", "in": r"inch(?:es)?|in"}


def unit_asked(text: str) -> Optional[str]:
    t = text.lower()
    for unit, pat in UNIT_WORDS.items():
        if re.search(rf"(?:\bin|\binto|\bto|\bas)\s+(?:{pat})\b|^\s*(?:{pat})\s*\??\s*$", t):
            return unit
    return None


def format_length(mm: float, unit: str) -> str:
    if unit == "m":
        return f"{mm / 1000:.2f}".rstrip("0").rstrip(".") + " m"
    if unit == "cm":
        return f"{mm / 10:.0f} cm"
    if unit == "mm":
        return f"{mm:.0f} mm"
    if unit == "ft":
        return f"{mm / 304.8:.1f} ft"
    return f"{mm / 25.4:.1f} in"


_PHOTO_Q = re.compile(r"\b(images?|photos?|pictures?|pics?)\b", re.I)


_INSTALL_Q = re.compile(r"\b(install|installation|installed|assembl|assemble|set (it )?up|fit (it|this) for me|"
                        r"put (it|this) together|technician|carpenter)", re.I)


def answer_about_product(p: ProductView, question: str, extracted: intent_mod.IntentExtraction,
                         use_llm: Optional[bool] = None, history: Optional[list[str]] = None) -> QAResult:
    res = _answer_core(p, question, extracted, use_llm, history)
    # O-73: "does it come with installation?" means "will someone install it?". If this product's details say
    # nothing about installation, say so plainly and point to the store's rule, instead of only "it's flat-packed".
    fields = listing_fields(p)
    if (_INSTALL_Q.search(question or "") and "Installation & Demo Details" not in fields
            and not re.search(r"install", res.answer, re.I)):
        import store_policy
        lead = "" if res.status == "not_in_listing" else res.answer.rstrip() + " "
        res = QAResult(lead + "Its details don't say whether someone will install it for you. Free installation is "
                       "only included when a product's page says so, so I can't promise it for this one.",
                       [c for c in res.cited_fields] + [store_policy.label("P2")], res.method, meta=res.meta)
    return res


def _answer_core(p: ProductView, question: str, extracted: intent_mod.IntentExtraction,
                 use_llm: Optional[bool] = None, history: Optional[list[str]] = None) -> QAResult:
    checked = _requirement_check(p, extracted)
    if checked:
        return checked
    if _PHOTO_Q.search(question or "") and re.search(r"\bhow many|number of|more\b", question.lower()):
        n = 1 if p.image_url else 0
        return QAResult(("There's one photo of it. Tap the card to see it larger on its page." if n
                         else "Sorry, there's no photo of this one."), ["Photos"] if n else [], "photo_count")
    if use_llm is None:
        use_llm = intent_mod.llm_available()
    if use_llm:
        ans, meta = _ask_llm(p, question, history)
        if ans is not None:
            problem = validate(ans, p) or unsupported_verdict(question, ans, p)
            if problem:
                fallback = _spec_lookup(p, question)
                fallback.method, fallback.status = "rejected_llm_answer", "rejected"
                fallback.meta = dict(meta, rejected=problem, rejected_answer=ans.answer)
                return fallback
            if ans.not_in_listing:
                # Uncited model text is where guesses slip in, so the "don't know" reply is always ours (R5).
                return QAResult(not_in_listing_reply(p), [], "llm", status="not_in_listing", meta=meta)
            return QAResult(ans.answer, ans.cited_fields, "llm", meta=meta)
        result = _spec_lookup(p, question)
        result.meta = dict(meta, fallback="spec lookup after LLM failure")
        return result
    return _spec_lookup(p, question)
