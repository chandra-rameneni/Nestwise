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
    (r"\bwide|width|breadth|\bbroad\b", ["Width"]), (r"\bdeep|depth\b", ["Depth", "Length"]), (r"\btall|height|high\b", ["Height"]),
    (r"\blong|length\b", ["Length", "Depth"]), (r"\bdimension|size|big|measure", ["Width", "Depth", "Height", "Length", "Size"]),
    (r"\bweigh|heavy|weight\b", ["Weight"]), (r"\bmade (of|from|out of)|material|fabric|wood|leather", ["Primary Material", "Primary Material Subtype", "Material",
     "Upholstery Type", "Outer Material", "Body Material", "Frame Material", "Secondary Material"]), (r"\bcolou?r\b", ["Primary Color", "Color",
     "Upholstery Color", "Finish Color"]), (r"\bseat|people|persons?\b|\bsit\b", ["Seating Capacity"]),
    (r"\bprice|cost|how much\b", ["Price"]), (r"\bbrand|who makes|manufacturer\b", ["Brand"]),
    (r"\bwarrant", ["Warranty Summary", "Covered in Warranty", "Not Covered in Warranty", "Warranty Service Type"]),
    (r"\bcapacity|litre|liter\b", ["Capacity"]), (r"\bdeliver|arrive|shipping\b|\bhow soon\b", ["Delivery time", "Delivery charge"]),
    (r"\bstock|available|availability\b|\bhow many (are )?left\b", ["Stock"]),
    (r"\bassembl|install|put (it|this) together", ["Delivery Condition", "Assembly Required", "Pre-assembled",
                                                  "Installation & Demo Details"]),
    (r"\bclean|\bwash|\bcare\b", ["Care Instructions", "Fabric Care", "Wash Care", "Care and Cleaning",
     "Machine Washable", "Hand Washable", "Washable"]),
    (r"\bkids?\b|\bchild|\bsuitable|\bideal for|\bwhich room", ["Suitable For", "Ideal For"]),
]
# Words shared by many field names; on their own they don't say which field is meant
# ("safe" is in both "Microwave Safe" and "Freezer Safe": eval PQ-07).
_GENERIC_KEY_WORDS = {"safe", "type", "number", "model", "name", "code", "pack", "included", "package", "sales",
                      "contents", "suitable", "ideal", "other", "features", "details", "service", "resistant", "machine", "hand",
                      "proof", "free", "all", "come", "comes", "get", "set", "items", "much", "many", "day", "days"}
_STOP = {"is", "it", "the", "a", "an", "does", "do", "this", "what", "how", "can", "will", "of", "for", "to", "in",
         "be", "my", "i", "you", "are", "there", "any", "have", "has", "with", "and", "or", "me", "tell", "about",
         "was", "were", "told", "said", "seller", "someone", "anyone", "actually", "really"}


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
    have = listing_fields(p)
    for c in checks:
        fname, unit = names.get(c.constraint, (c.constraint, ""))
        if fname in have:
            cited.append(fname)
        word = {"Width": "wide", "Depth": "deep", "Height": "high"}.get(fname)
        u = (" " + unit) if unit else ""
        num = isinstance(c.observed, (int, float))
        if c.status == policy.PASS:
            if word and num:
                parts.append(f"Yes, it fits: it's {c.observed:g}{u} {word}, within your {c.required:g}{u}.")
            elif fname == "Price" and num:
                parts.append(f"Yes, it's within budget: ₹{c.observed:,.0f} including delivery.")
            else:
                parts.append(f"Yes, its {fname.lower()} matches what you asked for.")
        elif c.status == policy.FAIL:
            if word and num:
                parts.append(f"Sorry, it won't fit: it's {c.observed:g}{u} {word}, more than your {c.required:g}{u}.")
            elif fname == "Price" and num:
                parts.append(f"Sorry, it's over budget: ₹{c.observed:,.0f} including delivery, more than your "
                             f"₹{c.required:,.0f}.")
            else:
                parts.append(f"Sorry, it has {c.observed} for {fname.lower()}, and you asked for {c.required}.")
        else:
            listed = re.search(r"'([^']+)'", str(c.observed or ""))
            why = ((f" It lists {listed.group(1)}, which doesn't look right for this product." if listed else
                    " The value it lists doesn't look right for this product.")
                   if "implausible" in str(c.observed or "") else "")
            parts.append(f"Sorry, I can't confirm the {fname.lower()}: its details don't give a usable value.{why}")
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
            return "It comes flat-packed, so it needs assembling."
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
    if yes_no:          # "Machine Washable: Yes" -> "Yes, it's machine washable."
        prop = field_name.lower()
        return f"Yes, it's {prop}." if v.lower() == "yes" else f"No, it isn't {prop}."
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
        if key not in ("Name", "Description", "Category") and any(re.search(rf"\b{re.escape(w)}(?:s|es)?\b", key.lower())
                                                                   for w in specific):
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


# ---- questions answered by code from the product's own details, with or without the AI (O-75, O-80 to O-84)
_OVERVIEW_Q = re.compile(r"^\s*(?:can you |could you |please )?(?:tell me (?:more )?about (?:it|this)|describe (?:it|this)|"
                         r"what(?:'s| is) (?:this|it)(?: exactly| product| item)?\??|what exactly is (?:this|it)|"
                         r"give me (?:a |an )?(?:summary|overview)|more about (?:it|this))\b", re.I)
_BOX_Q = re.compile(r"\bin the (?:box|package|pack)\b|\bwhat (?:do|will|would) i (?:get|receive)\b|\bwhat (?:all )?comes (?:in|with)\b|"
                    r"\b(?:box|package) contents?\b|\bsales package\b|\bwhat(?:'s| is) included\b", re.I)
_PIECES_Q = re.compile(r"\bhow many (?:pieces|items|things|pcs|units|in (?:the|a|one) (?:set|pack|box))\b|\bsingle piece or\b|"
                       r"\bis (?:it|this) a (?:set|pack)\b|\bpack of how many\b", re.I)
_HANDMADE_Q = re.compile(r"\bhand ?made\b|\bhand-made\b|\bhandcrafted\b|\bmade by hand\b|\bby hand or\b", re.I)
_COLOUR_Q = re.compile(r"\bcolou?rs?\b", re.I)
_DIMS_Q = re.compile(r"\b(?:dimensions?|measurements?|how big|what(?:'s| is) the size|what size|overall size)\b", re.I)
_INCLUDED = [
    re.compile(r"\b(?:comes?|coming) with (?:a |an |the |any |some )?([a-z][a-z -]{2,30}?)\s*(?:free|too|also|included)?\s*[?.!]*$", re.I),
    re.compile(r"\b(?:get|receive) (?:a |an |the |any |some )?([a-z][a-z -]{2,30}?) (?:with|along with) (?:it|this)\b", re.I),
    re.compile(r"\b(?:will|do|would|can) i (?:actually |really |also )?get (?:a |an |the |any |some )([a-z][a-z -]{2,30}?)\s*[?.!]*$", re.I),
    re.compile(r"^\s*(?:is|are) (?:a |an |the |any |some )?([a-z][a-z -]{2,30}?) (?:included|part of (?:it|this|the deal)|in the box)\b", re.I),
    re.compile(r"^\s*([a-z][a-z -]{2,30}?) included\s*[?.!]*$", re.I),
    re.compile(r"\b(?:includes?|including) (?:a |an |the |any |some )?([a-z][a-z -]{2,30}?)\s*[?.!]*$", re.I),
    re.compile(r"\b(?:said|told me|told|says?)\b.*?\b([a-z]{3,20}(?: [a-z]{3,20})?) (?:comes?|come) (?:free|with it|included)\b", re.I),
]
_NOT_ITEMS = {"installation", "install", "assembly", "warranty", "guarantee", "delivery", "shipping", "emi", "discount",
              "offer", "it", "this", "that", "them", "free installation", "free delivery", "instructions", "manual",
              "colour", "color", "size", "price", "return", "returns", "demo", "cash on delivery", "cod"}


def _singular(w: str) -> str:
    w = w.lower().strip()
    return re.sub(r"(es|s)$", "", w) if len(w) > 3 and not w.endswith("ss") else w


def included_item(question: str) -> Optional[str]:
    """'will I get a mattress with it?' -> 'mattress'; 'I was told it comes with cushions' -> 'cushions'."""
    q = re.sub(r"\b(actually|really|also|please)\b", " ", question.lower())
    q = re.sub(r"\s+", " ", q).strip()
    for pat in _INCLUDED:
        m = pat.search(q)
        if m:
            item = re.sub(r"^(a|an|the|any|some)\s+", "", m.group(1).strip())
            item = re.sub(r"\s+(with it|with this|free|too|also)$", "", item)
            if item and item not in _NOT_ITEMS and not any(w in _NOT_ITEMS for w in item.split()[:1]) \
                    and not re.search(r"\binstall|assembl|warrant|deliver", item):
                return item
    return None


def _box_list(fields: dict) -> Optional[str]:
    """'1 Bedsheet,2 Pillow Cover' -> '1 bedsheet, 2 pillow cover' (said in a sentence, not as a spec line)."""
    v = fields.get("Sales Package")
    if not v:
        return None
    v = re.sub(r"\s*,\s*", ", ", str(v).strip().rstrip("."))
    return v if re.search(r"[a-z]", v) is None else v[0] + v[1:].lower() if not v[:1].isalpha() else v.lower()


_PART_OF = r"(?:cover|covers|case|cases|sheet|sheets|protector|protectors|holder|holders|stand|stands|set|sets)"


def _in_box(item: str, box: str) -> Optional[bool]:
    """True if the box list names the item itself; False if it only names a part or cover of it ('pillow cover'
    when asked about pillows); None if it doesn't mention it at all (O-75: whole words, never 'bed' in 'bedsheet')."""
    it = _singular(item)
    hits = [m for m in re.finditer(rf"\b{re.escape(it)}(?:s|es)?\b(\s+{_PART_OF}\b)?", box.lower())]
    if not hits:
        return None
    return any(not m.group(1) for m in hits)


def _colour_sentence(fields: dict, question: str) -> Optional[QAResult]:
    main_key = next((k for k in ("Primary Color", "Color", "color", "Brand Color", "Shade") if k in fields), None)
    if main_key is None:
        return None
    main = str(fields[main_key]).strip().rstrip(".")
    extras, cited = [], [main_key]
    for k, label in (("Upholstery Color", "upholstery"), ("Finish Color", "finish")):
        v = str(fields.get(k, "")).strip().rstrip(".")
        if v and v.lower() not in main.lower():
            extras.append(f"{v.lower()} {label}")
            cited.append(k)
    asked = re.search(r"\bis (?:it|this) (?:in )?([a-z]+)\b", question.lower())
    lead = ""
    if asked and asked.group(1) not in ("available", "a", "the", "in", "colou", "color", "colour"):
        lead = "Yes, " if asked.group(1) in (main + " " + " ".join(extras)).lower() else "No, "
    sentence = f"it's {main.lower()}" + (f", with a {' and '.join(extras)}" if extras else "") + "."
    return QAResult((lead + sentence) if lead else sentence[0].upper() + sentence[1:], cited, "code")


def summary(p: ProductView) -> QAResult:
    """'Tell me about it': a short plain summary from the product's own details (O-80)."""
    f = listing_fields(p)
    total = (p.list_price_inr or 0) + (p.shipping_inr or 0)
    bits = [f"This is the {p.title}."]
    col = _colour_sentence(f, "")
    mat_key = next((k for k in ("Primary Material", "Material", "Outer Material", "Body Material") if k in f), None)
    cited = ["Name", "Price", "Delivery time"]
    if mat_key:
        bits.append(_say(p, mat_key, f[mat_key]) if mat_key in ("Primary Material", "Material")
                    else f"It's made of {str(f[mat_key]).lower()}.")
        cited.append(mat_key)
    if col:
        bits.append(col.answer)
        cited += col.cited_fields
    seats = re.search(r"\d+", str(f.get("Seating Capacity", "")))
    if seats:
        bits.append(f"It seats {seats.group()}.")
        cited.append("Seating Capacity")
    if measurement_mm(p, "Width") is not None:
        bits.append(_say(p, "Width", f["Width"]).replace(" (", " (").split(" (")[0] + ".")
        cited.append("Width")
    box = _box_list(f)
    if box and box.lower() not in p.title.lower():
        bits.append(f"It comes with {box}.")
        cited.append("Sales Package")
    bits.append(f"It costs ₹{total:,} including delivery and arrives in about {p.delivery_days} days.")
    return QAResult(" ".join(bits), cited, "code")


def direct_answer(p: ProductView, question: str) -> Optional[QAResult]:
    """Questions whose answer is a fixed lookup in the product's details: overview, what's in the box, number of
    pieces, whether something else is included, handmade, colour, dimensions. Answered by code with or without
    the AI, so an answer can never claim box contents the details don't list (O-84). None: not one of these."""
    q = (question or "").strip()
    f = listing_fields(p)
    noun = product_noun_title(p.title) if product_noun(p) == "product" else product_noun(p)
    if _OVERVIEW_Q.search(q):
        return summary(p)
    item = included_item(q)
    if item and not _BOX_Q.search(q):
        it_s, box = _singular(item), (_box_list(f) or "")
        doubt = re.search(r"\b(told|said|says|promised|heard)\b", q, re.I)
        title_words = {_singular(w) for w in re.findall(r"[a-z]+", p.title.lower())}
        if it_s in title_words or it_s == _singular(noun.split()[-1]) or it_s in ("product", "item", "thing"):
            tail = f" It comes with {box}." if box and box.lower() not in p.title.lower() else ""
            return QAResult(f"Yes, this is the {noun} itself.{tail}", ["Name"] + (["Sales Package"] if tail else []),
                            "code")
        flag = next((k for k in f if re.search(rf"^(with {it_s[:5]}\w*|{it_s[:5]}\w* included)$", k, re.I)), None)
        listed = _in_box(item, box) if box else None
        if flag and str(f[flag]).lower() == "yes" or listed:
            what = f"It comes with {box}." if box else f"Yes, the {item} is included."
            return QAResult(("Yes. " + what) if box else what, [flag or "Sales Package"], "code")
        lead = "Sorry, I can only go by its details. " if doubt else "Sorry, "
        if flag and str(f[flag]).lower() == "no":
            msg = f"{lead}the {item} isn't included. This is only the {noun}."
            cited = [flag]
        elif box and listed is False:
            msg = f"{lead}it comes with {box}, but not {item} themselves." if item.endswith("s") else \
                  f"{lead}it comes with {box}, but not a {item} itself."
            cited = ["Sales Package"]
        elif box:
            msg = f"{lead}it only comes with {box}. No {item}."
            cited = ["Sales Package"]
        else:
            msg = (f"{lead}this is only the {noun}. Its details don't mention {('a ' if not item.endswith('s') else '')}"
                   f"{item}, so I can't promise {'one' if not item.endswith('s') else 'them'}.")
            cited = ["Name"]
        msg = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), msg)
        return QAResult(msg[0].upper() + msg[1:], cited, "code")
    if _BOX_Q.search(q) or _PIECES_Q.search(q):
        box = _box_list(f)
        count_key = next((k for k in ("Number of Contents in Sales Package", "Pack of") if k in f), None)
        if _PIECES_Q.search(q) and count_key:
            n = str(f[count_key]).strip()
            n = f"a {n.lower()}" if re.match(r"(?i)pack|set", n) else n.lower() if re.search(r"(?i)piece", n) \
                else f"a pack of {n}"
            return QAResult(f"It's {n}." + (f" It comes with {box}." if box else ""),
                            [count_key] + (["Sales Package"] if box else []), "code")
        if box:
            return QAResult(f"It comes with {box}.", ["Sales Package"], "code")
        return QAResult(f"Sorry, its details don't list what's in the box. The listing is for the {noun} itself, and "
                        "I can't promise anything else with it.", ["Name"], "code")
    if _HANDMADE_Q.search(q):
        k = next((k for k in ("Handcrafted", "Handmade") if k in f), None)
        if k:
            yes = str(f[k]).lower() == "yes"
            return QAResult("Yes, it's handcrafted." if yes else "No, it isn't handmade.", [k], "code")
        return QAResult("Sorry, its details don't say whether it's handmade.", [], "code")
    if _COLOUR_Q.search(q):
        return _colour_sentence(f, q)
    if _DIMS_Q.search(q):
        parts, cited = [], []
        for k, w in (("Width", "wide"), ("Depth", "deep"), ("Length", "long"), ("Height", "high")):
            mm = measurement_mm(p, k)
            if mm is not None:
                parts.append(f"{format_length(mm, 'cm')} {w} ({format_length(mm, 'mm')})")
                cited.append(k)
        if parts:
            joined = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
            return QAResult(f"It's {joined}.", cited, "code")
        if "Size" in f:
            return QAResult(f"Its size is {f['Size']}.", ["Size"], "code")
        return QAResult("Sorry, its details don't give its measurements.", [], "code", status="not_in_listing")
    return None


def answer_about_product(p: ProductView, question: str, extracted: intent_mod.IntentExtraction,
                         use_llm: Optional[bool] = None, history: Optional[list[str]] = None) -> QAResult:
    res = _answer_core(p, question, extracted, use_llm, history)
    # O-73: "does it come with installation?" means "will someone install it?". If this product's details say
    # nothing about installation, say so plainly and point to the store's rule, instead of only "it's flat-packed".
    fields = listing_fields(p)
    if (_INSTALL_Q.search(question or "") and "Installation & Demo Details" not in fields
            and not re.search(r"install", res.answer, re.I)):
        import store_policy
        # Kept short (PM, 2026-11-21: the two-part reply was too long): one sentence on assembly, one on installation.
        cond = fields.get("Delivery Condition")
        if cond:
            lead = _say(p, "Delivery Condition", cond) + " "
        elif res.status == "not_in_listing":
            lead = ""
        else:
            lead = re.split(r"(?<=[.!?])\s+", res.answer.strip())[0] + " "
        cited = [c for c in res.cited_fields if c != "Delivery Condition" or cond] + \
            (["Delivery Condition"] if cond and "Delivery Condition" not in res.cited_fields else [])
        res = QAResult(lead + "Its details don't mention installation, so I can't promise it's included.",
                       cited + [store_policy.label("P2")], res.method, meta=res.meta)
    return res


def _answer_core(p: ProductView, question: str, extracted: intent_mod.IntentExtraction,
                 use_llm: Optional[bool] = None, history: Optional[list[str]] = None) -> QAResult:
    checked = _requirement_check(p, extracted)
    if checked:
        return checked
    direct = direct_answer(p, question)
    if direct is not None:
        return direct
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
