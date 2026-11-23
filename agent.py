"""Nestwise session: the shopper's chat, cart, approval and payment.

Every message goes to the AI agent (agent_llm.py): it reads the conversation and the screen, calls the store's
tools and writes the reply. Code keeps the money safe around it: requests to pay never reach the AI, the AI can
fill the cart but never approve or pay, and the cart is re-checked against today's price and stock before
payment. If no model can answer, the shopper is told so plainly.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

import intent as intent_mod
import policy
import payments
import qa
from catalog import STORE_DB_PATH, Catalog, ProductView, SqliteCatalog, _head_noun
from checkout import (MAX_LINES, MAX_QTY_PER_LINE, Approval, Cart, MockOrder, MockOrderService, new_approval,
                      new_cart, new_line)
from intent import Intent
from tracing import Tracer

MAX_TOOL_CALLS_PER_TURN = 40
MAX_CANDIDATES = 200
MAX_RECOMMENDATIONS = 3
# Head words too generic to search on their own when a longer phrase fails (O-24): "dinner set" must not show sets.
_GENERIC_HEADS = {"set", "sets", "pack", "packs", "combo", "piece", "pieces", "item", "items", "cover", "covers",
                  "stand", "stands", "holder", "case", "kit", "box", "thing", "product", "products"}

# Replies to non-shopping messages (PRD §6A). Each comes with the reason label recorded in the trace (§6A.4).

_COLOURS = {"red", "blue", "green", "yellow", "black", "white", "grey", "gray", "brown", "pink", "purple", "orange",
            "beige", "maroon", "navy", "gold", "golden", "silver", "cream", "multicolor", "multicolour"}
_SIZES = {"king", "queen", "single", "double"}


@dataclass
class Response:
    kind: str
    message: str
    recommendations: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    cart: Optional[Cart] = None
    order: Optional[MockOrder] = None
    reason_codes: list[str] = field(default_factory=list)
    cited_fields: list[str] = field(default_factory=list)
    product_id: Optional[str] = None
    about: list[dict] = field(default_factory=list)       # F8: the products this reply is about (shown as a tag)
    choices: list[dict] = field(default_factory=list)     # F2: tap-to-choose buttons instead of "which one?"
    steps: list[str] = field(default_factory=list)        # AI agent: what it did ("Searched sofas → 2 fit")
    model: Optional[str] = None                           # AI agent: which model wrote the reply


def _inr(n: Optional[int]) -> str:
    return "price not listed" if n is None else f"₹{n:,}"


def _plural(name: str, n: int = 2) -> str:
    name = (name or "").strip()
    if n == 1 or not name or name.endswith("s"):
        return name
    return name[:-1] + "ies" if name.endswith("y") and name[-2:-1] not in "aeiou" else name + "s"


_REASON_WORDS = {"OUT_OF_STOCK": "it's out of stock right now", "BUDGET_EXCEEDED": "it's over your budget",
                 "WIDTH_EXCEEDED": "it's wider than your space", "DEPTH_EXCEEDED": "it's deeper than your space",
                 "HEIGHT_EXCEEDED": "it's taller than your space", "SEATS_MISMATCH": "it has a different number of seats",
                 "PRICE_UNKNOWN": "it has no listed price", "DELIVERY_TOO_SLOW": "it would arrive too late",
                 "MATERIAL_MISMATCH": "it isn't made of what you asked for",
                 "WIDTH_UNVERIFIED": "the listing doesn't give its width",
                 "SEATS_UNVERIFIED": "the listing doesn't give its seats",
                 "MATERIAL_UNVERIFIED": "the listing doesn't say what it's made of"}


def _reasons(codes: list[str]) -> str:
    """Reason codes in plain words for the shopper (Phase 3: no codes in shopper text)."""
    words = list(dict.fromkeys(_REASON_WORDS.get(c, "it doesn't meet one of your requirements") for c in codes))
    return " and ".join(words) if words else "it doesn't meet your requirements"


def default_catalog():
    """The real store catalog when it has been built, otherwise the synthetic fixture."""
    return SqliteCatalog() if STORE_DB_PATH.exists() else Catalog()


class Session:
    def __init__(self, catalog=None, tracer: Optional[Tracer] = None, orders: Optional[MockOrderService] = None,
                 source: str = "test"):
        """source (PRD §14): 'store' for a chat in the web store, 'eval' for an eval run, 'test' for automated tests.
        Test sessions keep their trace in memory only, so traces/ grows only from real use and evals."""
        self.catalog = catalog or default_catalog()
        self.source = source
        self.tracer = tracer or Tracer(persist=source != "test")
        self.orders = orders or MockOrderService()
        self.intent: Optional[Intent] = None
        self.eligible_ids: list[str] = []
        self.cart: Optional[Cart] = None
        self.approval: Optional[Approval] = None
        self.history: list[tuple[str, str]] = []
        self.context: dict = {"page": "listing"}
        self._tool_calls = 0
        self._prev_intent: Optional[Intent] = None  # restored when a message turns out not to name a product
        self.shown: list[ProductView] = []          # products in the last recommendation (B34)
        # R11: hold a conversation. The product being talked about, the last product answer, the last unit asked.
        self.current: Optional[ProductView] = None
        self._closest_ids: list[str] = []           # closest options just shown (B21)
        self._rzp_order: Optional[dict] = None      # PRD §13: Razorpay test order for the current approval
        self.focus: list[str] = []                  # FOCUS_DESIGN: the products the conversation is about (max 3)
        self._extras: dict = {}                     # O-87/O-88: min price and left-out material for this product
        self.tracer.event("session", "session.start", catalog_version=self.catalog.meta.get("version"),
                          llm_configured=intent_mod.llm_available(), source=source,
                          payments=payments.mode())

    # ------------------------------------------------------------------ helpers
    def _respond(self, r: Response) -> Response:
        """Every reply goes through here: the "About" tag, the history (with the AI's steps) and the trace."""
        if not r.about and r.product_id and r.kind in ("ANSWER", "CLARIFY"):
            p = self.catalog.get(r.product_id)
            if p is not None:
                r.about = [{"product_id": p.product_id, "title": p.title}]
        if r.recommendations:                          # R11: one product shown -> it's the one being talked about
            self.current = (self._get(r.recommendations[0]["product_id"]) if len(r.recommendations) == 1 else None)
        self.history.append(("assistant", r.message))
        if getattr(r, "steps", None):                  # the AI sees what it did in earlier turns, not just its words
            if not hasattr(self, "history_steps"):
                self.history_steps = {}
            self.history_steps[len(self.history) - 1] = list(r.steps)
        self.tracer.event("agent", "agent.response", response_kind=r.kind, reason_codes=r.reason_codes,
                          message=r.message[:300],
                          recommended_ids=[x["product_id"] for x in r.recommendations],
                          cart_id=r.cart.cart_id if r.cart else None,
                          order_id=r.order.order_id if r.order else None,
                          cited_fields=r.cited_fields, page=self.context.get("page"), focus=list(self.focus),
                          product_id=r.product_id or self.context.get("product_id"))
        return r


    def _count_tool(self) -> None:
        self._tool_calls += 1
        if self._tool_calls > MAX_TOOL_CALLS_PER_TURN:
            raise RuntimeError("tool-call limit reached for this turn")

    def _get(self, pid: str) -> Optional[ProductView]:
        self._count_tool()
        with self.tracer.tool("get_product", product_id=pid) as t:
            p = self.catalog.get(pid)
            t["summary"] = None if p is None else {"version": p.version, "price": p.list_price_inr,
                                                   "shipping": p.shipping_inr, "stock": p.stock}
        if p is not None:
            self._flag_untrusted(p)
        return p

    def _get_many(self, pids: list[str]) -> list[ProductView]:
        """One bounded tool call that loads several products (search results)."""
        self._count_tool()
        with self.tracer.tool("get_products", count=len(pids)) as t:
            products = [p for p in (self.catalog.get(pid) for pid in pids) if p is not None]
            t["summary"] = {"loaded": len(products)}
        for p in products:
            self._flag_untrusted(p)
        return products

    def _flag_untrusted(self, p: ProductView) -> None:
        if p.injection_flag:
            self.tracer.event("guardrail", "untrusted_text_flagged", status="warn", product_id=p.product_id,
                              note="Instruction-like text in product description; treated as data, not instructions.")

    def _invalidate_approval(self, reason: str) -> None:
        if self.approval and self.approval.status == "APPROVED":
            self.approval.status = "INVALIDATED"
            self.approval.invalidated_reason = reason
            self.tracer.event("approval", "approval.invalidated", status="warn",
                              approval_id=self.approval.approval_id, reason=reason)

    def _store_labels(self) -> str:
        labels = [l.lower() for l in self.catalog.category_labels()]
        return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]

    # ------------------------------------------------------------------ user message
    def handle_message(self, text: str, context: Optional[dict] = None) -> Response:
        self._tool_calls = 0
        self.context = dict(context or {"page": "listing"})
        self.history.append(("user", text))
        self.tracer.event("user", "user.message", text=text, page=self.context.get("page"),
                          product_id=self.context.get("product_id"))
        if self._PAY_REQUEST.search(text):          # RZ1: the agent never pays; it can't, by design
            self.tracer.event("guardrail", "payment_request_refused", status="warn", text=text)
            has_cart = self.cart is not None and self.cart.status == "PROPOSED"
            msg = ("I wish I could make this easier, but paying is something only you can do. "
                   + ("When you're ready, just tap the Pay button and Razorpay will take it from there."
                      if has_cart else "Once something's in your cart and approved, you'll see a Pay button to tap."))
            return self._respond(Response("ANSWER", msg, reason_codes=["PAYMENT_IS_MANUAL"]))
        page_pid = self.context.get("product_id") if self.context.get("page") == "product" else None
        if page_pid:                                   # on a product page, that product is in focus
            p = self._get(page_pid)
            if p is not None:
                self.current, self.focus = p, [p.product_id]
        r, self.ai_down_reason = None, ("busy" if intent_mod.llm_available() else "no_key")
        if intent_mod.llm_available():
            import agent_llm
            r = agent_llm.run(self, text, self.context)    # the AI reads the chat, calls store tools, writes the reply
        if r is not None:
            return r
        why = getattr(self, "ai_down_reason", "busy")
        self.tracer.event("model", "agent.unavailable", status="warn", why=why)
        return self._respond(Response("ANSWER", self._AI_DOWN.get(why, self._AI_DOWN["busy"]),
                                      reason_codes=["AI_UNAVAILABLE", f"AI_{why.upper()}"]))

    _AI_DOWN = {
        "quota": "The free AI usage limit for this demo has been used up, so I can't answer chat messages right now. "
                 "You can still browse, add products to your cart, approve and pay. Please try again later.",
        "no_key": "No AI model key is set up, so I can't answer chat messages. Add a free API key (see the README) "
                  "and restart the store. You can still browse, add products to your cart, approve and pay.",
        "busy": "Sorry, the AI models are busy right now and didn't answer in time. Please try again in a moment.",
    }


    def _material_search(self, material: str) -> Response:
        ids = getattr(self.catalog, "material_products", lambda m: [])(material)
        probe = Intent(intent="PRODUCT_DISCOVERY")
        r = self._show_ids(ids, probe, "MATERIAL_MATCH", tail=f"Looking for something in particular, like a "
                                                             f"{material} dining set, bed or table?")
        return r

    def _show_ids(self, ids: list[str], probe: Intent, label: str, tail: str = "") -> Response:
        products = self._get_many(ids[:MAX_CANDIDATES])
        ok = [(p, policy.evaluate(probe, p)) for p in products]
        ok = [(p, e) for p, e in ok if e.eligible]
        ranked = policy.rank(probe, [p for p, _ in ok])[:MAX_RECOMMENDATIONS]
        if not ranked:
            return self._respond(Response("NO_ELIGIBLE", "I found matching products, but none are in stock with a "
                                          "listed price right now.", reason_codes=[label]))
        self.eligible_ids = [p.product_id for p in ranked]
        self.shown = ranked
        recs = [self._rec_dict(p, e) for p, e in ok if p in ranked]
        recs.sort(key=lambda x: self.eligible_ids.index(x["product_id"]))
        msg = self._explain(ranked, [], len(ok), probe) + (f"\n{tail}" if tail else "")
        return self._respond(Response("RECOMMEND", msg, recommendations=recs, reason_codes=[label]))


    # ------------------------------------------------------------------ B34: pointing at shown results


    MAX_FOCUS = 3

    def _focus_products(self) -> list[ProductView]:
        return [p for p in (self.catalog.get(pid) for pid in self.focus) if p is not None]

    def set_focus(self, product_ids: list[str]) -> list[str]:
        """The shopper ticked or unticked products (card checkboxes, focus-bar ×). Only products they've seen."""
        known = {p.product_id for p in self.shown} | ({ln.product_id for ln in self.cart.lines} if self.cart else set())
        if self.current is not None:
            known.add(self.current.product_id)
        if self.context.get("product_id"):
            known.add(self.context["product_id"])
        self.focus = [pid for pid in dict.fromkeys(product_ids) if pid in known][:self.MAX_FOCUS]
        self.current = self.catalog.get(self.focus[0]) if len(self.focus) == 1 else self.current
        self.tracer.event("user", "focus.set", focus=list(self.focus))
        return self.focus


    # ------------------------------------------------------------------ not a shopping message (§6A)


    def _possible_typo(self, query: str) -> Optional[str]:
        """B12: if a word isn't in the store but is close to a product type ('sofaa' -> 'sofa'), return the
        corrected phrase, but only if the corrected phrase actually finds products."""
        vocab = getattr(self.catalog, "vocabulary", None)
        if vocab is None:
            return None
        every, types = vocab()
        words, fixed = re.findall(r"[a-z]+", query.lower()), False
        out = []
        for w in words:
            if w not in every and len(w) >= 4:
                close = difflib.get_close_matches(w, [x for x in types if x[0] == w[0]], n=1, cutoff=0.8)
                if close:
                    out.append(close[0]); fixed = True
                    continue
            out.append(w)
        if not fixed:
            return None
        suggestion = " ".join(out)
        matches, _ = self.catalog.find_products(suggestion)
        return suggestion if matches else None

    # ------------------------------------------------------------------ clarify (rule R2)

    # ------------------------------------------------------------------ discovery
    def _find(self, query: str) -> tuple[list[str], list[str]]:
        self._count_tool()
        with self.tracer.tool("search_catalog", query=query,
                              category=self.intent.category if self.intent else None) as t:
            matches, related = self.catalog.find_products(
                query, product_category=self.intent.category if self.intent else None)
            t["summary"] = {"matches": len(matches), "related": len(related), "first_ids": matches[:10]}
        return matches, related

    def _search_and_recommend(self, exclude: tuple[str, ...] = (), query: Optional[str] = None,
                              probe: Optional[Intent] = None) -> Response:
        it = probe or self.intent
        query = query if query is not None else (it.product_query or "")
        query = re.sub(r"\b(couch|couches|settee|settees)\b", "sofa", query)    # F-019: common synonyms
        colour = next((w for w in re.findall(r"[a-z]+", query.lower()) if w in _COLOURS), None)
        if colour:                                      # O-89: a colour is checked against the details, not the name
            query = re.sub(rf"\b{colour}\b", " ", query, flags=re.I).strip()
        matches, related = self._find(query)
        label = None
        size_note = None
        if not matches and query:
            size = next((w for w in re.findall(r"[a-z]+", query.lower()) if w in _SIZES), None)
            rest = re.sub(rf"\b{size}\b|\bsize[ds]?\b", " ", query, flags=re.I).strip() if size else ""
            if size and rest:
                found, _ = self._find(rest)
                if found:                                 # O-93: "king size bed" -> say so, show the beds we have
                    matches = found
                    head = intent_mod.head_term(rest) or rest
                    size_note = f"Sorry, we don't have a {size} size {head}, so here are the {head}s we do have:"
                    if probe is None:
                        it = self.intent = it.model_copy(update={"product_query": rest})
                    query = rest
        if not matches and query:
            for finder, lab in (("brand_products", "BRAND_MATCH"), ("name_products", "NAME_MATCH")):
                f = getattr(self.catalog, finder, None)
                found = f(query) if f else []
                if found:                                 # B33: a brand or full product name
                    matches, label = found, lab
                    if probe is None:
                        it = self.intent = it.model_copy(update={"product_query": None, "category": None})
                    break
        partial_note = None
        if not matches and query:
            words = re.findall(r"[a-z]+", query.lower())
            head = intent_mod.head_term(query)
            vocab = getattr(self.catalog, "vocabulary", None)
            known = vocab()[0] if vocab else set()
            others = [w for w in words if intent_mod.head_term(w) != head]
            # Only when the extra words are unknown to the store ("shive"); a real word like "dining" or "coffee"
            # names a different product, so "dining table" must not show laptop tables.
            if len(words) > 1 and head and len(head) >= 4 and head not in _GENERIC_HEADS and others \
                    and not any(w in known for w in others):
                found, _ = self._find(head)
                if found:                                 # O-24: "shive temple" -> the store's temples
                    matches, label = found, "PARTIAL_MATCH"
                    partial_note = f"I couldn't find a {query}, but here's what we have in {head}s:"
                    if probe is None:
                        it = self.intent = it.model_copy(update={"product_query": head, "category": None})
        if not matches and not query and it.material:
            return self._material_search(it.material)
        if not matches:
            if probe is None:
                self.intent = self._prev_intent           # B37: a failed search never changes the shopper's thread
            fix = self._possible_typo(query)
            if fix:
                self.tracer.event("agent", "possible_typo", query=query, suggestion=fix)
                return self._respond(Response("NOT_AVAILABLE", "I couldn't find that item. Check the spelling and "
                                              f"try again. Did you mean \u201c{fix}\u201d?",
                                              reason_codes=["POSSIBLE_TYPO"]))
            if not intent_mod.looks_like_product(query):
                # The leftover words aren't a product ("doesn t", "night"): don't claim we don't sell it (B17).
                self.tracer.event("agent", "not_a_product", query=query)
                return self._respond(Response("UNSUPPORTED", "Sorry, I didn't quite get that. I can help you find "
                                              "and buy things for your home.", reason_codes=["CATCH_ALL"]))
            # Rule R1: not sold here. Terminal answer, no follow-up question, same answer every time.
            name = _plural(query.strip()) or "that"
            return self._respond(Response("NOT_AVAILABLE", f"Sorry, we don't sell {name}. We're a home and living "
                                          f"store: {self._store_labels()}.", reason_codes=["NOT_SOLD_HERE"]))
        candidates, colour_note = self._narrow([pid for pid in matches if pid not in exclude], query, colour, it)
        candidates = candidates[:MAX_CANDIDATES]
        partial_note = partial_note or size_note or colour_note
        eligible, rejected = [], []
        for p in self._get_many(candidates):
            e = policy.evaluate(it, p)
            self.tracer.event("policy", "policy.eligibility", status="pass" if e.eligible else "fail",
                              product_id=p.product_id, total_inr=e.total_inr, eligible=e.eligible,
                              checks=[c.to_dict() for c in e.checks])
            (eligible if e.eligible else rejected).append((p, e))

        ranked = policy.rank(it, [p for p, _ in eligible])[:MAX_RECOMMENDATIONS]
        self.eligible_ids = [p.product_id for p in ranked]
        recs = [self._rec_dict(p, e) for p, e in eligible if p in ranked]
        recs.sort(key=lambda r: self.eligible_ids.index(r["product_id"]))
        rej = [{"product_id": p.product_id, "title": p.title, "total_inr": e.total_inr,
                "reason_codes": e.reason_codes, "why": "; ".join(self._differences(e))} for p, e in rejected]
        self.tracer.event("agent", "recommendation", eligible_ids=self.eligible_ids, eligible_count=len(eligible),
                          rejected={r["product_id"]: r["reason_codes"] for r in rej})

        self.focus = []                                  # F4: new results, empty focus bar
        if not ranked:
            return self._closest(rejected, rej, query, it)
        self.shown = ranked
        invite = self._invite(it)
        msg = self._explain(ranked, rej, len(eligible), it, closing=invite,
                            lead=(partial_note if partial_note in (size_note, colour_note) else
                                  partial_note.rstrip(":") + ".") if partial_note else None)
        return self._respond(Response("RECOMMEND", msg, recommendations=recs, rejected=rej,
                                      reason_codes=[label] if label else []))

    def _narrow(self, pids: list[str], query: str, colour: Optional[str], it: Intent) -> tuple[list[str], Optional[str]]:
        """Filters the plain search can't express: pet beds (O-85), colour (O-89), price floor (O-87), and a material
        to leave out (O-88). Returns the narrowed ids and a note for the reply when a filter found nothing."""
        head = intent_mod.head_term(query)
        ex = self._extras if self._extras.get("head") == head else {}
        if not (head == "bed" or colour or ex.get("min_inr") or ex.get("exclude")):
            return pids, None
        # a filter step over search results, not a product lookup: loaded quietly (the products shown are loaded,
        # counted and checked for untrusted text in the normal step that follows)
        ps = [p for p in (self.catalog.get(pid) for pid in pids) if p is not None]
        words = set(re.findall(r"[a-z]+", " ".join(t for r, t in self.history[-1:] if r == "user").lower() + " " +
                               query.lower()))
        if head == "bed" and not words & {"pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten"}:
            real = [p for p in ps if "pet" not in (p.category_path or "").lower()]
            ps = real or ps
        if ex.get("min_inr"):
            ps = [p for p in ps if (p.total_for() or 0) >= ex["min_inr"]]
        if ex.get("exclude"):
            bad = ex["exclude"]
            ps = [p for p in ps if bad not in (p.title + " " + " ".join(
                str(v) for k, v in (p.raw_specs or {}).items() if "material" in k.lower() or "upholstery" in k.lower()
            )).lower()]
        note = None
        if colour:
            def colours(p):
                return (p.title + " " + " ".join(str(v) for k, v in (p.raw_specs or {}).items()
                                                 if "color" in k.lower() or "colour" in k.lower() or k == "Shade")).lower()
            match = [p for p in ps if re.search(rf"\b{colour}", colours(p))]
            if match:
                ps = match
            else:
                note = f"Sorry, I couldn't find a {colour} {query}, so here are the {head}s we have:"
        return [p.product_id for p in ps], note

    def _invite(self, it: Intent) -> Optional[str]:
        """B18: after a broad search, one light line inviting the shopper to narrow down."""
        is_sofa = it.category == "sofa" or intent_mod.head_term(it.product_query) in ("sofa", "couch", "settee")
        if is_sofa and (it.seats is None or it.max_width_cm is None):
            if it.seats is None and it.max_width_cm is None:
                return "Tell me how many seats you need or how much space you have, and I'll narrow these down."
            if it.max_width_cm is None:
                return "Tell me how much space you have, and I'll narrow these down."
            return "Tell me how many people it's for, and I'll narrow these down."
        if not any(getattr(it, f) for f in intent_mod.CONSTRAINT_FIELDS):
            return "Tell me your budget or anything else that matters, and I'll narrow these down."
        return None

    _RELAXABLE = {"BUDGET_EXCEEDED", "WIDTH_EXCEEDED", "DEPTH_EXCEEDED", "HEIGHT_EXCEEDED", "SEATS_MISMATCH",
                  "DELIVERY_TOO_SLOW", "MATERIAL_MISMATCH", "WIDTH_UNVERIFIED", "DEPTH_UNVERIFIED",
                  "HEIGHT_UNVERIFIED", "SEATS_UNVERIFIED", "MATERIAL_UNVERIFIED"}

    def _closest(self, rejected: list, rej: list[dict], query: str, it: Intent) -> Response:
        """B21: nothing meets every requirement: say so, then show the closest options and how each differs."""
        blockers = sorted({c for r in rej for c in r["reason_codes"]})
        near = [(p, e) for p, e in rejected if e.reason_codes and set(e.reason_codes) <= self._RELAXABLE]
        near.sort(key=lambda pe: (len(pe[1].reason_codes), (pe[1].total_inr or 10 ** 9)))
        near = near[:MAX_RECOMMENDATIONS]
        if not near:
            return self._respond(Response("NO_ELIGIBLE", (
                f"Sorry, nothing matches all your requirements for {_plural(query) or 'that'}, and nothing comes close "
                "enough to suggest. You could raise the budget or drop a requirement."), rejected=rej,
                reason_codes=blockers))
        self.shown = [p for p, _ in near]
        self._closest_ids = [p.product_id for p, _ in near]
        shown_ids = set(self._closest_ids)
        rej = [r for r in rej if r["product_id"] not in shown_ids]          # O-50: never "left out" and shown
        recs = [self._rec_dict(p, e) for p, e in near]
        given = []
        if it.max_total_inr:
            given.append("budget")
        if any(getattr(it, f) for f in ("max_width_cm", "max_depth_cm", "max_height_cm")):
            given.append("size")
        if it.seats:
            given.append("seats")
        if getattr(it, "material", None):
            given.append("material")
        adjust = " or ".join(given) if given else "requirements"
        noun = intent_mod.head_term(query) if query else ""
        own = query if query and len(query.split()) <= 3 else noun       # the shopper's words: "home temple"
        if len(near) == 1:
            p, e = near[0]
            msg = (f"Sorry, the closest {noun or 'one'} I have is the {p.title} at {_inr(e.total_inr)}, which is "
                   f"{', '.join(self._differences(e))}. Would you like it anyway?")
            if len(rejected) == 1:                                          # O-49: the store has only this one
                msg = (f"Sorry, our only {own or 'match'} is the {p.title} at {_inr(e.total_inr)}, which is "
                       f"{', '.join(self._differences(e))}. Would you like it anyway?")
        else:
            lines = [f"\u2022 {p.title}: {_inr(e.total_inr)} ({'; '.join(self._differences(e))})" for p, e in near]
            msg = (f"Sorry, none of our {_plural(noun) or 'products'} meet everything you asked for. These come "
                   "closest:\n" + "\n".join(lines) + f"\nWant me to look again with a different {adjust}?")
        return self._respond(Response("NO_ELIGIBLE", msg, recommendations=recs, rejected=rej,
                                      reason_codes=blockers + ["RELAXED_OPTIONS"]))

    def _differences(self, e) -> list[str]:
        diffs = []
        for c in e.checks:
            if c.status == policy.PASS:
                continue
            if c.reason_code == "BUDGET_EXCEEDED":
                diffs.append(f"{_inr(c.observed - c.required)} over your budget")
            elif c.reason_code and c.reason_code.endswith("_EXCEEDED"):
                diffs.append(f"{c.observed:g} cm, over your {c.required:g} cm")
            elif c.reason_code == "SEATS_MISMATCH":
                diffs.append(f"{c.observed} seats, not {c.required}")
            elif c.reason_code and c.reason_code.endswith("_UNVERIFIED"):
                diffs.append(f"{c.constraint.replace('max_', '').replace('_cm', '')} not listed")
            elif c.reason_code == "DELIVERY_TOO_SLOW":
                diffs.append(f"arrives in {c.observed} days")
            elif c.reason_code == "MATERIAL_MISMATCH":
                diffs.append(f"not {c.required}")
        return diffs or ["not a full match"]

    def _similar(self, base: ProductView, cheaper: bool) -> Response:
        """'Anything cheaper like this?' on a product page: same kind of product, the shopper's stated
        requirements (PRD decision D9), and below this product's total if they asked for cheaper."""
        it = self.intent
        query = it.product_query if intent_mod.head_term(it.product_query) == intent_mod.head_term(_head_noun(base.title)) \
            and it.product_query else _head_noun(base.title)
        probe = it.model_copy()
        if cheaper and base.total_for() is not None:
            limit = base.total_for() - 1
            probe.max_total_inr = min(limit, it.max_total_inr) if it.max_total_inr else limit
        self.tracer.event("agent", "similar_search", base_product=base.product_id, query=query, cheaper=cheaper,
                          max_total_inr=probe.max_total_inr)
        return self._search_and_recommend(exclude=(base.product_id,), query=query, probe=probe)

    def _rec_dict(self, p: ProductView, e: Optional[policy.Eligibility] = None) -> dict:
        return {"product_id": p.product_id, "title": p.title, "brand": p.brand, "list_price_inr": p.list_price_inr,
                "shipping_inr": p.shipping_inr, "total_inr": p.total_for(), "delivery_days": p.delivery_days,
                "stock": p.stock, "specs": p.specs, "url": f"/product/{p.product_id}", "image_url": p.image_url,
                "checks": [c.to_dict() for c in e.checks] if e else []}

    def _explain(self, ranked: list[ProductView], rej: list[dict], n_eligible: int, it: Intent,
                 closing: Optional[str] = None, lead: Optional[str] = None) -> str:
        """Template reply built only from retrieved fields (no free-form model text). Phase 3 wording: a warm
        lead-in, one compact line per product (no internal codes), one closing line."""
        noun = intent_mod.head_term(it.product_query) if it.product_query else ("sofa" if it.category == "sofa" else "")
        things = _plural(noun, n_eligible) if noun else ("product" if n_eligible == 1 else "products")
        others = [f for f in intent_mod.CONSTRAINT_FIELDS if f != "max_total_inr" and getattr(it, f)]
        if it.max_total_inr and not others:
            fit = f"{'is' if n_eligible == 1 else 'are'} under {_inr(it.max_total_inr)}"
        elif it.max_total_inr or others:
            fit = f"{'fits' if n_eligible == 1 else 'fit'} what you need"
        else:
            fit = "to choose from"
        if lead is None:
            lead = f"Good news, {n_eligible} {things} {fit}."
        show = (f" Here are the {len(ranked)} best value:" if n_eligible > len(ranked) else
                " Here it is:" if n_eligible == 1 else " Here they are:")
        lines = [lead if lead.endswith(":") else lead + show]
        prefs = {b.lower() for b in it.preferred_brands}
        for p in ranked:
            facts = [f"{_inr(p.total_for())} total", f"arrives in {p.delivery_days} days"]
            if "macOS" in it.required_compatibility:
                facts.append("listed as macOS compatible")
            seats = p.specs.get("seats")
            if seats is not None:
                facts.append(f"{seats} seat{'s' if seats != 1 else ''}")
            if p.specs.get("width_cm") is not None:
                facts.append(f"{p.specs.get('width_cm'):g} cm wide")
            if it.max_depth_cm and p.specs.get("depth_cm") is not None:
                facts.append(f"{p.specs.get('depth_cm'):g} cm deep")
            if it.max_height_cm and p.specs.get("height_cm") is not None:
                facts.append(f"{p.specs.get('height_cm'):g} cm tall")
            if prefs and (p.brand or "").lower() in prefs:
                facts.append(f"your preferred brand ({p.brand})")
            lines.append(f"\u2022 {p.title}: " + ", ".join(facts) + ".")
        if prefs and not any((p.brand or "").lower() in prefs for p in ranked):
            lines.append(f"None of the eligible options are from {', '.join(it.preferred_brands)}; "
                         "these are the closest that meet your other requirements.")
        lines.append(closing or "Tell me which one you'd like, and I'll show you the exact total before anything is "
                                "bought.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ product Q&A (rules R5, R6)


    # ------------------------------------------------------------------ B28 on a product page


    # ------------------------------------------------------------------ B43: browsing a category


    # ------------------------------------------------------------------ B21 option A: add a closest option anyway

    # ------------------------------------------------------------------ B41: store policy questions

    # ------------------------------------------------------------------ PRD §13: payments (Razorpay test mode)
    _PAY_REQUEST = re.compile(
        r"\b(pay (for (me|it|this|that)|now|it)|make (the |my )?payment|initiate (the |my )?payment|"
        r"process (the |my )?payment|charge (my|the) (card|account)|go ahead and (pay|charge)|"
        r"complete (the |my )?(purchase|payment|checkout|order)|place (the |my )?order( for me)?|"
        r"(do|finish) (the )?(checkout|payment) for me|just (pay|charge))\b", re.I)

    def _payment_unavailable(self, why: str) -> Response:
        self.tracer.event("payment", "payment.unavailable", status="warn", reason=why, paused=payments.paused())
        return self._respond(Response("BLOCKED", "Sorry, payments aren't working right now. Nothing was charged or "
                                      "ordered, and your cart is saved. Try again in a few minutes.",
                                      cart=self.cart, reason_codes=["PAYMENT_UNAVAILABLE"]))

    def start_payment(self):
        """The Pay button (never the agent). Returns ('checkout', options) to open Razorpay, or ('reply', Response)."""
        self._tool_calls = 0
        self.tracer.event("user", "user.pay_clicked", cart_id=self.cart.cart_id if self.cart else None)
        if not payments.enabled():
            return "reply", self.checkout()
        if self.cart is None or self.approval is None or self.approval.status != "APPROVED":
            if self.cart is not None and self.cart.status == "ORDERED":
                return "reply", self.checkout()
            return "reply", self._respond(Response("BLOCKED", "Please approve the exact cart first, then tap Pay.",
                                                   reason_codes=["NOT_APPROVED"]))
        rz = self._rzp_order if self._rzp_order and self._rzp_order["approval_id"] == self.approval.approval_id else None
        if rz is not None:                                   # RZ10: maybe it was already paid
            try:
                pid = payments.paid_payment(rz["order"]["id"])
            except payments.PaymentUnavailable as exc:
                return "reply", self._payment_unavailable(str(exc))
            if pid:
                self.tracer.event("payment", "payment.found_already_paid", order_ref=rz["order"]["id"])
                return "reply", self._place_paid(pid)
        currents = {ln.product_id: self._get(ln.product_id) for ln in self.cart.lines}
        current = currents[self.cart.product_id]
        reasons = policy.checkout_gate(intent=self.intent, cart=self.cart, approval=self.approval, currents=currents)
        self.tracer.event("policy", "checkout.gate", status="block" if reasons else "pass", cart_id=self.cart.cart_id,
                          approval_id=self.approval.approval_id, approved_total_inr=self.approval.approved_total_inr,
                          current_total_inr=sum((c.total_for(ln.qty) or 0) for ln in self.cart.lines
                                                for c in [currents[ln.product_id]] if c),
                          lines=len(self.cart.lines), reason_codes=reasons, before="payment")
        if reasons:
            return "reply", self._recover(reasons, current, currents)
        if rz is None:
            try:
                order = payments.create_order(self.approval.approved_total_inr, self.approval.approval_id,
                                              {"cart": self.cart.cart_id, "product": self.cart.product_id})
            except payments.PaymentUnavailable as exc:
                return "reply", self._payment_unavailable(str(exc))
            rz = self._rzp_order = {"approval_id": self.approval.approval_id, "order": order}
            self.tracer.event("payment", "payment.order_created", order_ref=order["id"], amount_paise=order["amount"],
                              approval_id=self.approval.approval_id)
        self.tracer.event("payment", "payment.window_opened", order_ref=rz["order"]["id"])
        return "checkout", payments.checkout_options(rz["order"], self.cart.title)

    def confirm_payment(self, order_id: str, payment_id: str, signature: str) -> Response:
        """Razorpay's success message, sent on by the browser. Verified here before anything is ordered (RZ3)."""
        rz = self._rzp_order
        if self.cart is not None and self.cart.status == "ORDERED":
            return self.checkout()                           # RZ4: the success arrived twice; still one order
        ours = rz["order"]["id"] if rz and self.approval and rz["approval_id"] == self.approval.approval_id else None
        if not ours or order_id != ours or not payments.verify_signature(ours, payment_id, signature):
            self.tracer.event("guardrail", "payment.verification_failed", status="block",
                              matches_our_order=bool(ours and order_id == ours))
            return self._respond(Response("BLOCKED", "Sorry, I couldn't confirm that payment, so nothing was ordered. "
                                          "If money left your account, it's test mode, so nothing real was charged.",
                                          reason_codes=["PAYMENT_NOT_VERIFIED"]))
        self.tracer.event("payment", "payment.verified", order_ref=ours)
        return self._place_paid(payment_id)

    def _place_paid(self, payment_id: str) -> Response:
        order, created = self.orders.place(self.cart, self.approval, payment_id=payment_id)
        self.cart.status = "ORDERED"
        self.approval.status = "USED"
        self.tracer.event("checkout", "order.created" if created else "order.duplicate_suppressed",
                          order_id=order.order_id, idempotency_key=order.idempotency_key, total_inr=order.total_inr,
                          paid=True, test_mode=True)
        return self._respond(Response("ORDER_PLACED", (
            f"Done! You paid {_inr(order.total_inr)} (test mode) and your order for the {self.cart.title} is placed. "
            "Nothing will ship: this is a demo."), cart=self.cart, order=order))

    def payment_not_completed(self, failed: bool, reason: str = "") -> Response:
        self.tracer.event("payment", "payment.failed" if failed else "payment.dismissed",
                          status="warn" if failed else "ok", reason=reason[:120])
        msg = ("Sorry, that payment didn't go through, so nothing was charged or ordered. You can try again with Pay."
               if failed else "No problem, nothing was charged or ordered. Tap Pay whenever you're ready.")
        # Kind ANSWER, not APPROVED: the approval is still valid (state shows it), but no "Approved" label on a failure
        return self._respond(Response("ANSWER", msg, cart=self.cart,
                                      reason_codes=["PAYMENT_FAILED" if failed else "PAYMENT_DISMISSED"]))

    # ------------------------------------------------------------------ RZ8: confirm a quantity above 1
    def confirm_quantity(self) -> Response:
        if self.cart is None or self.cart.status != "PROPOSED":
            return self._respond(Response("BLOCKED", "There's no cart to confirm.", reason_codes=["NO_ACTIVE_CART"]))
        for ln in self.cart.lines:
            ln.qty_confirmed = True
        self.tracer.event("cart", "cart.qty_confirmed", cart_id=self.cart.cart_id,
                          quantities={ln.product_id: ln.qty for ln in self.cart.lines})
        what = (f"{self.cart.qty} it is" if len(self.cart.lines) == 1 else "quantities confirmed")
        return self._respond(Response("CART_PROPOSED", f"Great, {what}: {_inr(self.cart.total_inr)} in total. Tap "
                                      "**Approve this exact cart** when you're ready.", cart=self.cart))

    def set_quantity_one(self) -> Response:
        if self.cart is None or self.cart.status != "PROPOSED":
            return self._respond(Response("BLOCKED", "There's no cart to change.", reason_codes=["NO_ACTIVE_CART"]))
        last = None
        for ln in [ln for ln in self.cart.lines if ln.qty > 1]:
            last = self.set_line_quantity(ln.product_id, 1)
        return last or self.cart_summary()

    # ------------------------------------------------------------------ B26 / B47: cart lines
    @staticmethod
    def _has_requirements(it) -> bool:
        return bool(it) and any(getattr(it, f, None) for f in intent_mod.CONSTRAINT_FIELDS)

    def _added_message(self, p: ProductView, qty: int) -> str:
        n = len(self.cart.lines)
        names = [qa.product_noun_title(ln.title) for ln in self.cart.lines]
        listed = names[0] if n == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        msg = (f"Added! Your cart now has {n} items: {listed}, {_inr(self.cart.total_inr)} in total."
               if n > 1 else f"Added! {_inr(self.cart.total_inr)} in total.")
        return msg + " " + self._next_step()

    def _next_step(self) -> str:
        unconfirmed = [ln for ln in self.cart.lines if ln.qty > 1 and not ln.qty_confirmed]
        if unconfirmed:
            ln = unconfirmed[0]
            return (f"Just checking: you're buying **{ln.qty}** of the {qa.product_noun_title(ln.title)}. "
                    f"Is {ln.qty} right?")
        return "Tap **Approve this exact cart** when you're ready. Nothing is ordered without your approval."

    def set_line_quantity(self, product_id: str, qty: int) -> Response:
        """B26: change how many of one product. Above the limit, offer the limit; any change cancels the approval."""
        if self.cart is None or self.cart.status != "PROPOSED" or self.cart.line(product_id) is None:
            return self._respond(Response("BLOCKED", "That product isn't in your cart.", reason_codes=["NOT_IN_CART"]))
        ln = self.cart.line(product_id)
        p = self._get(product_id)
        limit = min(MAX_QTY_PER_LINE, p.stock if p else MAX_QTY_PER_LINE)
        if qty < 1:
            return self.remove_line(product_id)
        if qty > limit:
            stock = f" ({p.stock} in stock)" if p and p.stock < 100 else ""
            return self._respond(Response("CLARIFY", f"Sorry, you can order up to {limit} of these at a time{stock}. "
                                          f"Shall I make it {limit}?", cart=self.cart, reason_codes=["QTY_LIMIT"]))
        old = ln.qty
        ln.qty, ln.qty_confirmed = qty, False
        if p is not None:                       # quantity changes use today's price
            ln.unit_price_inr, ln.shipping_inr, ln.data_version = p.list_price_inr, p.shipping_inr, p.version
        self._invalidate_approval("quantity changed")
        self.approval = None
        self.tracer.event("cart", "cart.qty_changed", cart_id=self.cart.cart_id, product_id=product_id,
                          qty_from=old, qty_to=qty, total_inr=self.cart.total_inr)
        noun = qa.product_noun_title(ln.title)
        lead = (f"Done, {qty} × {noun}" if len(self.cart.lines) > 1 else f"Done, {qty} of these")
        return self._respond(Response("CART_PROPOSED", f"{lead}: {_inr(self.cart.total_inr)} in total. "
                                      + self._next_step(), cart=self.cart, product_id=product_id,
                                      reason_codes=["QTY_CHANGED"]))

    def remove_line(self, product_id: str) -> Response:
        if self.cart is None or self.cart.status != "PROPOSED" or self.cart.line(product_id) is None:
            return self._respond(Response("BLOCKED", "That product isn't in your cart.", reason_codes=["NOT_IN_CART"]))
        ln = self.cart.line(product_id)
        self.cart.lines.remove(ln)
        self._invalidate_approval("item removed")
        self.approval = None
        self.tracer.event("cart", "cart.item_removed", cart_id=self.cart.cart_id, product_id=product_id)
        noun = qa.product_noun_title(ln.title)
        if not self.cart.lines:
            self.cart.status = "DECLINED"
            return self._respond(Response("ANSWER", f"Removed the {noun}. Your cart is empty now.",
                                          reason_codes=["ITEM_REMOVED"]))
        return self._respond(Response("CART_PROPOSED", f"Removed the {noun}. {_inr(self.cart.total_inr)} in total now. "
                                      + self._next_step(), cart=self.cart, reason_codes=["ITEM_REMOVED"]))

    def cart_summary(self) -> Response:
        if self.cart is None or self.cart.status != "PROPOSED" or not self.cart.lines:
            return self._respond(Response("ANSWER", "Your cart is empty. Tell me what you're looking for, or tap "
                                          "Buy this on a product page.", reason_codes=["CART_SUMMARY"]))
        rows = "\n".join(f"\u2022 {ln.qty} × {ln.title}: {_inr(ln.total_inr)}" for ln in self.cart.lines)
        return self._respond(Response("CART_PROPOSED", f"Here's your cart:\n{rows}\nTotal: **{_inr(self.cart.total_inr)}**. "
                                      + self._next_step(), cart=self.cart, reason_codes=["CART_SUMMARY"]))

    # chat: "make it 2", "I want 2 of these", "add 2 to cart", "remove the bean bag", "what's in my cart?"
    # O-78: typed "approve" / "cancel" while a cart is waiting. The agent never approves (only the button does).
    # O-79: "also add a coffee mug" names a new product to look for (the cart stays as it is).


    # ------------------------------------------------------------------ R11: holding a conversation


    @staticmethod
    def _same_kind(it: Optional[Intent], p: ProductView) -> bool:
        """O-69: is this product the kind the shopper's requirements were stated for? No stated kind counts as yes."""
        if it is None or not (it.product_query or it.category):
            return True
        where = f"{p.title} {p.category_path or ''} {p.category or ''}".lower()
        head = intent_mod.head_term(it.product_query)
        if head and head in where:
            return True
        return bool(it.category) and str(it.category).replace("_", " ") in where


    # ------------------------------------------------------------------ cart / approval / checkout
    def select_product(self, product_id: str, qty: int = 1, from_product_page: bool = False,
                       waived: Optional[list] = None, set_qty: bool = False) -> Response:
        """Propose a cart. From a recommendation list, only products just checked are allowed; from a product
        page ("buy this") the product itself is checked against the shopper's stated requirements."""
        if not from_product_page:
            self._tool_calls = 0
        self.tracer.event("user", "user.select", product_id=product_id, qty=qty, from_product_page=from_product_page)
        if not from_product_page and product_id in self._closest_ids and product_id not in self.eligible_ids:
            # B21 option A (PM 2026-11-19): a closest option can go in the cart after one honest question
            p = self._get(product_id)
            e = policy.evaluate(self.intent, p) if p is not None and self.intent is not None else None
            if p is not None and e is not None:
                diffs = self._differences(e)
                self.tracer.event("policy", "override_offered", product_id=product_id, reasons=e.reason_codes)
                return self._respond(Response("CLARIFY", f"Just so you know, the {p.title} is {', '.join(diffs)}. "
                                              "Add it anyway?", product_id=product_id, reason_codes=["OVERRIDE_OFFERED"]))
        if not from_product_page and (self.intent is None or product_id not in self.eligible_ids):
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id,
                              reason="NOT_IN_ELIGIBLE_RECOMMENDATIONS")
            return self._respond(Response("BLOCKED", "I can only add products from the options I just checked. Pick "
                                          "one of those, or tell me what you're after.", reason_codes=["NOT_ELIGIBLE"]))
        if self.intent is None:
            self.intent = Intent(intent="BUY_THIS")
        p = self._get(product_id)
        if p is None:
            return self._respond(Response("BLOCKED", "I couldn't find that product.", reason_codes=["PRODUCT_NOT_FOUND"]))
        rules_for = self.intent
        if waived or (from_product_page and not self._same_kind(self.intent, p)):
            # O-69: a sofa search's "3 seats, 200 cm" must not block buying a bed. Requirements belong to the kind of
            # product they were stated for (R9); a different kind is checked for stock and a known price only.
            rules_for = Intent(intent="BUY_THIS")
        e = policy.evaluate(rules_for, p, qty)
        if not e.eligible:
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id, reasons=e.reason_codes)
            if from_product_page:
                lead = ("Sorry, this one's out of stock right now." if e.reason_codes == ["OUT_OF_STOCK"]
                        else f"Sorry, I can't add this one: {_reasons(e.reason_codes)}.")
                return self._blocked_with_alternatives(p, e.reason_codes, lead)
            return self._respond(Response("BLOCKED", f"Sorry, that one doesn't work anymore: {_reasons(e.reason_codes)}.",
                                          reason_codes=e.reason_codes))
        checked_with = None if (rules_for is not self.intent or from_product_page and not self._has_requirements(self.intent)) \
            else self.intent.model_copy(deep=True)
        if self.cart is not None and self.cart.status == "PROPOSED":
            line = self.cart.line(p.product_id)
            if line is None and len(self.cart.lines) >= MAX_LINES:
                return self._respond(Response("BLOCKED", f"Your cart can hold up to {MAX_LINES} different products. "
                                              "Remove one to add this.", cart=self.cart, reason_codes=["CART_FULL"]))
            if line is not None:                   # the same product again: more of it, not a second line (B47)
                return self.set_line_quantity(p.product_id, qty if set_qty else line.qty + qty)
            new_qty = min(qty, MAX_QTY_PER_LINE, max(p.stock, 1))
            self.cart.lines.append(new_line(p, new_qty, checked_with))
            self._invalidate_approval("item added to the cart")
            self.approval = None
            self.tracer.event("cart", "cart.item_added", cart_id=self.cart.cart_id, product_id=p.product_id,
                              qty=new_qty, lines=len(self.cart.lines), total_inr=self.cart.total_inr)
            return self._respond(Response("CART_PROPOSED", self._added_message(p, new_qty), cart=self.cart,
                                          product_id=p.product_id, reason_codes=["ITEM_ADDED"]))
        self._invalidate_approval("new cart proposed")
        self.cart = new_cart(p, min(qty, MAX_QTY_PER_LINE, max(p.stock, 1)), checked_with)
        qty = self.cart.qty
        self.approval = None
        self.tracer.event("cart", "cart.created", cart_id=self.cart.cart_id, product_id=p.product_id, qty=qty,
                          unit_price_inr=p.list_price_inr, shipping_inr=p.shipping_inr,
                          total_inr=self.cart.total_inr, data_version=p.version)
        item = f"{qty} \u00d7 {p.title}" if qty > 1 else p.title
        ship = f" + {_inr(p.shipping_inr)} delivery" if p.shipping_inr else " + free delivery"
        return self._respond(Response("CART_PROPOSED", (
            f"Great choice! {item}: {_inr(p.list_price_inr * qty)}{ship} = **{_inr(self.cart.total_inr)}**. "
            f"Arrives in {p.delivery_days} days.\n"
            + (f"Just checking: you're buying **{qty}** of these, {_inr(self.cart.total_inr)} in total. Is {qty} right?"
               if qty > 1 else
               "Tap **Approve this exact cart** when you're ready. Nothing is ordered without your approval.")),
            cart=self.cart, product_id=p.product_id))

    def _blocked_with_alternatives(self, p: ProductView, reasons: list[str], lead: str) -> Response:
        alt = self._similar(p, cheaper=False)
        self.history.pop()          # merge the alternatives into a single blocked response
        tail = ("Here are similar ones you can order today:\n" + alt.message) if alt.kind == "RECOMMEND" \
            else alt.message
        alt.message = lead + "\n\n" + tail
        alt.kind, alt.reason_codes, alt.cart = "BLOCKED", reasons, None
        return self._respond(alt)

    def approve(self) -> Response:
        self.tracer.event("user", "user.approve", cart_id=self.cart.cart_id if self.cart else None)
        if self.cart is None or self.cart.status != "PROPOSED":
            return self._respond(Response("BLOCKED", "There's no cart waiting for approval.",
                                          reason_codes=["NO_ACTIVE_CART"]))
        if self.cart.qty > 1 and not self.cart.qty_confirmed:     # RZ8
            return self._respond(Response("CLARIFY", f"Just checking: you're buying **{self.cart.qty}** of these, "
                                          f"{_inr(self.cart.total_inr)} in total. Is {self.cart.qty} right?",
                                          cart=self.cart, reason_codes=["CONFIRM_QUANTITY"]))
        self.approval = new_approval(self.cart, self.intent.version)
        self.tracer.event("approval", "approval.granted", approval_id=self.approval.approval_id,
                          cart_id=self.cart.cart_id, approved_total_inr=self.approval.approved_total_inr,
                          data_version=self.approval.data_version, intent_version=self.approval.intent_version)
        tail = (" Tap **Pay** when you're ready: I'll double-check the price and stock first, then Razorpay (test mode) "
                "takes the payment." if payments.enabled() else
                " I'll double-check the price and stock before placing the order.")
        return self._respond(Response("APPROVED", f"Approved for {_inr(self.approval.approved_total_inr)}.{tail}",
                                      cart=self.cart))

    def decline(self) -> Response:
        self.tracer.event("user", "user.decline", cart_id=self.cart.cart_id if self.cart else None)
        if self.cart:
            self.cart.status = "DECLINED"
        self._invalidate_approval("customer declined")
        return self._respond(Response("DECLINED", "No problem, nothing was ordered. If you change your mind, I'm "
                                      "right here and happy to pick up where we left off.", cart=self.cart))

    def checkout(self) -> Response:
        """Revalidate against current data, then place at most one mock order."""
        self._tool_calls = 0
        if self.cart is None:
            return self._respond(Response("BLOCKED", "There's nothing in your cart yet.", reason_codes=["NO_ACTIVE_CART"]))
        if self.cart.status == "ORDERED" and self.approval and self.approval.status == "USED":
            order, created = self.orders.place(self.cart, self.approval)
            self.tracer.event("checkout", "order.duplicate_suppressed", status="ok", order_id=order.order_id,
                              idempotency_key=order.idempotency_key)
            return self._respond(Response("ORDER_PLACED", "This order was already placed, so I didn't create a second "
                                          "one.", cart=self.cart, order=order))

        if payments.enabled():                       # with Razorpay on, an order is only placed after payment
            return self._respond(Response("BLOCKED", "Tap **Pay** to complete your order. Nothing is ordered until "
                                          "the payment goes through.", cart=self.cart, reason_codes=["PAYMENT_REQUIRED"]))
        currents = {ln.product_id: self._get(ln.product_id) for ln in self.cart.lines}
        current = currents[self.cart.product_id]
        reasons = policy.checkout_gate(intent=self.intent, cart=self.cart, approval=self.approval, currents=currents)
        self.tracer.event("policy", "checkout.gate", status="block" if reasons else "pass",
                          cart_id=self.cart.cart_id,
                          approval_id=self.approval.approval_id if self.approval else None,
                          approved_total_inr=self.approval.approved_total_inr if self.approval else None,
                          current_total_inr=current.total_for(self.cart.qty) if current else None,
                          approved_version=self.approval.data_version if self.approval else None,
                          current_version=current.version if current else None, reason_codes=reasons)
        if reasons:
            return self._recover(reasons, current, currents)

        order, created = self.orders.place(self.cart, self.approval)
        self.cart.status = "ORDERED"
        self.approval.status = "USED"
        self.tracer.event("checkout", "order.created" if created else "order.duplicate_suppressed",
                          order_id=order.order_id, idempotency_key=order.idempotency_key,
                          total_inr=order.total_inr, simulated=True)
        return self._respond(Response("ORDER_PLACED", (
            f"Done! Your order for the {self.cart.title} ({_inr(order.total_inr)}) is placed. This is a demo, so no "
            "payment was taken and nothing will ship."), cart=self.cart, order=order))

    def _recover(self, reasons: list[str], current: Optional[ProductView], currents: Optional[dict] = None) -> Response:
        if "NO_VALID_APPROVAL" in reasons:
            return self._respond(Response("BLOCKED", "I can't place the order yet: please approve this exact cart "
                                          "first.", cart=self.cart, reason_codes=reasons))
        if currents and len(self.cart.lines) > 1:
            return self._recover_lines(reasons, currents)
        self._invalidate_approval(", ".join(reasons))
        old_total = self.approval.approved_total_inr if self.approval else self.cart.total_inr
        self.cart.status = "SUPERSEDED"
        if current is not None and current.stock < self.cart.qty:
            parts = [f"Heads up: the {current.title} went out of stock after you approved, so I haven't ordered "
                     "anything."]
        elif current is not None and current.total_for(self.cart.qty) != old_total:
            parts = [f"Heads up: the price changed from {_inr(old_total)} to {_inr(current.total_for(self.cart.qty))} "
                     "since you approved, so I haven't ordered anything. If the new total works for you, just approve "
                     "again."]
        else:
            parts = ["Heads up: something changed since you approved, so I haven't ordered anything. Please check "
                     "and approve again."]
        if self.intent.product_query or self.intent.category:
            alt = self._search_and_recommend()
        else:                                   # bought straight from a product page: look for similar ones
            alt = self._search_and_recommend(query=_head_noun(current.title) if current else "")
        self.history.pop()
        alt.message = " ".join(parts) + ("\n\nHere's what meets your requirements right now:\n" + alt.message
                                          if alt.kind == "RECOMMEND" else "")
        alt.kind = "BLOCKED"
        alt.reason_codes = reasons
        alt.cart = None
        return self._respond(alt)

    def _recover_lines(self, reasons: list[str], currents: dict) -> Response:
        """B47: something changed in a cart with several items. Name the item, charge nothing, keep the cart with
        today's prices, and ask for approval of the new total (or offer to remove an item that ran out)."""
        old_total = self.approval.approved_total_inr if self.approval else self.cart.total_inr
        self._invalidate_approval(", ".join(reasons))
        self.approval = None
        notes, gone = [], []
        for ln in self.cart.lines:
            cur = currents.get(ln.product_id)
            noun = qa.product_noun_title(ln.title)
            if cur is None or cur.stock < ln.qty:
                gone.append(ln)
                notes.append(f"the {noun} is out of stock now")
                continue
            if cur.list_price_inr != ln.unit_price_inr or cur.shipping_inr != ln.shipping_inr:
                notes.append(f"the {noun}'s price changed from {_inr(ln.unit_price_inr)} to {_inr(cur.list_price_inr)}")
                ln.unit_price_inr, ln.shipping_inr = cur.list_price_inr, cur.shipping_inr
            ln.data_version = cur.version
        self.tracer.event("policy", "cart.recheck_failed", status="block", reasons=reasons, notes=notes)
        what = "; ".join(notes) or "something in your cart changed"
        if gone:
            names = " and ".join(f"the {qa.product_noun_title(ln.title)}" for ln in gone)
            msg = (f"Heads up: {what}, so I haven't charged anything. Shall I remove {names}? Then you can approve the "
                   "rest.")
        else:
            msg = (f"Heads up: {what}, so I haven't charged anything. The new total is "
                   f"**{_inr(self.cart.total_inr)}** (was {_inr(old_total)}). Approve it if it works for you.")
        return self._respond(Response("BLOCKED", msg, cart=self.cart, reason_codes=reasons))

    # ------------------------------------------------------------------ demo simulation hooks
    def simulate_price_change(self, product_id: str, new_price_inr: int) -> None:
        before = self.catalog.get(product_id)
        self.catalog.set_price(product_id, new_price_inr)
        self.tracer.event("simulation", "sim.price_change", status="warn", product_id=product_id,
                          old_price_inr=before.list_price_inr, new_price_inr=new_price_inr,
                          new_version=self.catalog.get(product_id).version)

    def simulate_out_of_stock(self, product_id: str) -> None:
        self.catalog.set_stock(product_id, 0)
        self.tracer.event("simulation", "sim.out_of_stock", status="warn", product_id=product_id,
                          new_version=self.catalog.get(product_id).version)
