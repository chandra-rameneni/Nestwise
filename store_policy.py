"""Store policy answers (PRD B41). The source is STORE_POLICY.md, approved by the PM; nothing here invents policy.

Routing (PRD B41, PM requirement 2026-11-19): the policy is used only for questions about the store's rules on a
fixed list of topics. `topic_of()` recognises clear policy questions; anything else (product details, general
knowledge, requests to act on an order) never reaches this module.

Answers:
- Order limits, and "can I return this?" for a no-return product, are answered by code from store data.
- Otherwise the model gets only the matching section(s) and must cite them; code checks the citations.
- Without a model (or if its answer fails the check), the most relevant sentences of the section are used.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

import llm

POLICY_PATH = Path(__file__).parent / "STORE_POLICY.md"
POLICY_PROMPT_VERSION = "store_policy_v1"
POLICY_PROMPT_PATH = Path(__file__).parent / "prompts" / f"{POLICY_PROMPT_VERSION}.txt"
MAX_PER_ORDER = 5                     # P6


def _delivery_range() -> tuple[int, int, int]:
    """Delivery days (shortest, longest) and the share with free delivery, from the catalog (simulated values)."""
    import sqlite3
    try:
        con = sqlite3.connect(Path(__file__).parent / "data" / "catalog.sqlite")
        lo, hi, free = con.execute("SELECT min(delivery_days), max(delivery_days), "
                                   "round(100.0 * sum(shipping_inr = 0) / count(*)) FROM inventory").fetchone()
        return int(lo), int(hi), int(free)
    except Exception:
        return 2, 10, 50


DELIVERY_RANGE = _delivery_range()

TOPICS = {"delivery_damage": ["P1"], "installation": ["P2"], "returns": ["P3"], "refunds": ["P4"],
          "cancellation": ["P5"], "order_limits": ["P6"], "payment": ["P7"], "warranty": ["P8", "P2"],
          "delivery_area": ["P9"], "contact": ["P10"]}

# Clear policy questions only. Each needs a rule-ish word AND a question/hypothetical shape, so "I want a refund"
# (a request: B9/B45) and "does it come with installation?" (a listing fact: B4) don't match.
_Q = r"(\?|^\s*(what|how|can|could|do|does|is|are|will|would|when|which|who)\b|\bwhat if\b|\bpolicy\b)"
_PATTERNS = [
    ("delivery_damage", r"\b(refund|replace\w*|money back|exchange)\b.*\b(damag\w*|broken|defect\w*|cracked)\b|"
                        r"\b(damag\w*|broken|defect\w*|cracked)\b.*\b(refund|replace\w*|money back)\b|"
                        r"\b(damag\w*|broken|breaks?|cracked|dent\w*)\b.*\b(deliver\w*|shipping|shipped|transit|arriv\w*)\b|"
                        r"\b(deliver\w*|shipping|transit|arriv\w*)\b.*\b(damag\w*|broken|breaks?)\b"),
    ("warranty", r"\bwarranty\b"),
    ("installation", r"\binstall\w*\b.*\b(myself|my ?self|break\w*|damag\w*|who)\b|\b(install|assemble)\w* (it|this) (myself|my ?self)\b|"
                     r"\binstallation (person|guy|man|technician|team)\b"),
    ("returns", r"\bwhat if i (don'?t|do not) like (it|this)\b|\bif i (don'?t|do not) like (it|this)\b|\breturn (policy|window)\b|\bcan i (return|send (it|this) back)\b|\bsend (it|this) back\b|\breturnable\b|"
                r"\bexchange (it|this)\b|\bcan (it|this) be returned\b"),
    ("refunds", r"\b(get|have) (my |the )?money back\b|\bwill i get a refund\b|\brefunds? (take|policy|time)\b|\bhow long\b.*\brefunds?\b|\bwhen (will|do) i get (my )?refund"),
    ("cancellation", r"\bcancel\w*\b"),
    ("order_limits", r"\b(min(imum)?|max(imum)?)\b.*\border\b|\border limit\b|\bhow many\b.*\b(can i|at once|per order)\b"),
    ("payment", r"\bcash on delivery\b|\bcod\b|\bpayment (method|option)s?\b|\bpay (by|with|using|via)\b|\bupi\b|\bemi\b"),
    ("delivery_area", r"\bdeliver (to|in|across)\b|\bwhich (cities|areas|pincodes?)\b|"
                      r"\bhow long (does|will|do) (the )?(delivery|shipping|it take to deliver)\b|\bdelivery (time|charges?|fees?|cost)\b|"
                      r"\b(charge|pay) (for|extra for) (delivery|shipping)\b|\bis (delivery|shipping) free\b|\bfree (delivery|shipping)\b"),
    ("contact", r"\b(contact|customer (care|support|service))\b|\btalk to (a |someone|a person|a human)"),
]


def topic_of(text: str) -> Optional[str]:
    t = text.lower()
    if not re.search(_Q, t):
        return None
    for topic, pat in _PATTERNS:
        if re.search(pat, t):
            return topic
    return None


@dataclass
class PolicyAnswer:
    answer: str
    cited: list[str]
    method: str                       # code | llm | sentences
    meta: dict = field(default_factory=dict)


def sections() -> dict[str, tuple[str, str]]:
    """{'P1': ('Damaged in delivery', text), ...}, with markdown and the review markers removed."""
    out, cur, title, buf = {}, None, "", []
    for line in POLICY_PATH.read_text().splitlines():
        m = re.match(r"###\s+(P\d+)\.\s+(.*)", line)
        if m:
            if cur:
                out[cur] = (title, _clean("\n".join(buf)))
            cur, title, buf = m.group(1), m.group(2).strip(), []
        elif line.startswith("---") and cur:
            out[cur] = (title, _clean("\n".join(buf)))
            cur = None
        elif cur:
            buf.append(line)
    if cur:
        out[cur] = (title, _clean("\n".join(buf)))
    return out


def _clean(text: str) -> str:
    text = re.sub(r"\*\(Demo:.*?\)\*", "", text)             # internal notes stay out of answers
    text = re.sub(r"\*\(When .*?\)\*", "", text)
    text = text.replace("⚙", "").replace("**", "").replace("*", "")
    text = re.sub(r"^\s*-\s+", "", text, flags=re.M)
    return re.sub(r"[ \t]+", " ", text).strip()


def label(sec_id: str) -> str:
    return f"{sec_id} {sections()[sec_id][0]}"


class _ModelAnswer(BaseModel):
    answer: str
    cited_sections: list[str] = Field(default_factory=list)


def answer(topic: str, question: str, product=None, use_llm: bool = False) -> PolicyAnswer:
    secs = sections()
    ids = [i for i in TOPICS[topic] if i in secs]
    if topic == "order_limits":
        if product is not None:
            most = min(MAX_PER_ORDER, max(product.stock, 0))
            return PolicyAnswer(f"You can order from 1 up to {most} of these at a time"
                                + (f" ({product.stock} in stock)." if product.stock < 100 else ".")
                                + " For more, contact us.", [label("P6")], "code")
        return PolicyAnswer(f"You can order from 1 up to {MAX_PER_ORDER} of the same product at a time, as long as "
                            "it's in stock. For more, contact us.", [label("P6")], "code")
    if topic == "returns" and product is not None and not product.returnable:
        return PolicyAnswer("Sorry, this one can't be returned: it's one of our small no-return items. If it arrives "
                            "broken, send us a photo within 48 hours and we'll review it and send a replacement "
                            "(no refunds on these).", [label("P3")], "code")
    if topic == "delivery_area" and re.search(r"how long|days?|when|charge|cost|fee|free|pay", question.lower()):
        # O-95: delivery time and charge are facts in the data, so code answers them (P9)
        if product is not None:
            charge = "free" if not product.shipping_inr else f"₹{product.shipping_inr:,}"
            return PolicyAnswer(f"This one arrives in about {product.delivery_days} days, and delivery is {charge}. "
                                "We deliver across India.", [label("P9")], "code")
        lo, hi, free = DELIVERY_RANGE
        return PolicyAnswer(f"Most products arrive in {lo} to {hi} days, and about {free}% have free delivery. Each "
                            "product shows its own delivery time and charge, and I can tell you for any product you "
                            "pick. We deliver across India.", [label("P9")], "code")
    if topic == "returns" and product is not None:
        # O-104: the rule for this product's category only, said by code (furniture differs from everything else)
        text = secs.get("P3", ("", ""))[1]
        want = "Furniture" if product.category == "furniture" else "Home décor"
        line = next((ln.strip(" -") for ln in text.splitlines() if ln.strip(" -").startswith(want)), None)
        if line:
            rule = line.split(":", 1)[1].strip()
            rule = rule[0].upper() + rule[1:]
            return PolicyAnswer(rule, [label("P3")], "code")
    if use_llm:
        given = "\n\n".join(f"[{i}] {secs[i][0]}\n{secs[i][1]}" for i in ids)
        extra = ""
        if product is not None and topic in ("installation", "warranty"):
            inst = (product.raw_specs or {}).get("Installation & Demo Details")
            if inst:
                extra = f"\n\nThis product's listing says about installation: {inst}"
        ans, meta = llm.structured(POLICY_PROMPT_PATH.read_text(),
                                   f"<store_policy>\n{given}{extra}\n</store_policy>\n\nShopper's question: {question}",
                                   _ModelAnswer, max_tokens=600)
        meta["prompt_version"] = POLICY_PROMPT_VERSION
        if ans is not None and ans.cited_sections and set(ans.cited_sections) <= set(ids):
            return PolicyAnswer(ans.answer, [label(i) for i in ans.cited_sections], "llm", meta)
        fb = _sentences(ids, question, secs)
        fb.meta = dict(meta, fallback="sentences after model failure or a bad citation")
        return fb
    return _sentences(ids, question, secs)


_SAME = {"break": "damag", "broke": "damag", "broken": "damag", "breaks": "damag", "crack": "damag",
         "installer": "install", "installation": "install", "assembles": "install", "assemble": "install",
         "carpenter": "install", "myself": "yourself", "money": "refund"}


def _stem(w: str) -> str:
    """Tiny normaliser so "breaks" meets "damages" and "installation" meets "installer" (rules mode only)."""
    w = _SAME.get(w, w)
    for suf in ("ation", "ing", "es", "ed", "er", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    return _SAME.get(w, w)


def _sentences(ids: list[str], question: str, secs: dict) -> PolicyAnswer:
    """Rules mode: the two sentences of the section(s) that share the most words with the question."""
    words = {_stem(w) for w in re.findall(r"[a-z]+", question.lower()) if len(w) > 3}
    cands = []
    for i in ids:
        for k, sent in enumerate(re.split(r"(?<=[.!?])\s+|\n+", secs[i][1])):
            sent = sent.strip()
            if len(sent) > 15:
                score = len(words & {_stem(w) for w in re.findall(r"[a-z]+", sent.lower())})
                cands.append((score, ids.index(i), k, sent, i))
    best = sorted(sorted(cands, key=lambda c: (-c[0], c[1], c[2]))[:2], key=lambda c: (c[1], c[2]))
    used = list(dict.fromkeys(c[4] for c in best))
    return PolicyAnswer(" ".join(c[3] for c in best), [label(i) for i in used], "sentences")
