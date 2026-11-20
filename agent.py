"""Nestwise session: page-aware routing, bounded tool use, grounded recommendations and answers,
approval and checkout.

The flow is code-driven (a workflow, not a free-running model loop). The model is used only to
interpret language and to phrase product answers from listing data; every search outcome,
eligibility, approval and checkout decision is deterministic code.

Every turn ends in exactly one outcome (PRD rule R4):
RECOMMEND | ANSWER | CLARIFY | NOT_AVAILABLE | NO_ELIGIBLE | CART_PROPOSED | APPROVED | DECLINED |
ORDER_PLACED | BLOCKED | DEFER | UNSUPPORTED
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
import store_policy
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
_YES = re.compile(r"^\s*(yes|yeah|yep|yup|haan|han|ha|sure|correct|right|ok|okay)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|nahi|nah)\b", re.I)

_ASK = {
    "product": "Happy to help! What kind of product do you have in mind, for example a sofa, a bedsheet or a dining set?",
    "budget": "What's the most you'd like to spend, including delivery?",
    "seats": "How many seats do you need?",
    "max_width_cm": "How much space do you have for it, in cm?",
}
_NEED = {"product": "the product you want", "budget": "your maximum budget in ₹", "seats": "the number of seats",
         "max_width_cm": "the maximum width in cm"}


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


def _apologise(msg: str) -> str:
    return re.sub(r"^(Good news|Sure|Here)[,!]?\s*", "Sorry about that. ", msg, count=1) if msg else msg


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
        self._last_clarify: Optional[tuple] = None
        self._pending_confirm: Optional[intent_mod.IntentExtraction] = None   # B16: "Are you searching for a sofa?"
        self._turn_labels: list[str] = []          # REQUIREMENT_ADDED / _CHANGED / _REMOVED for this turn's results
        self._prev_intent: Optional[Intent] = None  # restored when a message turns out not to name a product
        self.shown: list[ProductView] = []          # products in the last recommendation (B34)
        self._no_progress = 0                       # unhelpful replies in a row (B36)
        self._in_recovery = False
        self._last_invite: Optional[list] = None    # what the last "search first" reply invited (B18, B32)
        # R11: hold a conversation. The product being talked about, the last product answer, the last unit asked.
        self.current: Optional[ProductView] = None
        self._last_answer: Optional[dict] = None
        self._last_unit: Optional[str] = None
        self._challenges = 0                        # challenges in a row (B39), so the second reply differs
        self._pending_fit: Optional[str] = None     # B28 on a product page: asked for the shopper's space
        self._pending_override: Optional[dict] = None   # B21 option A: "over your budget, add it anyway?"
        self._closest_ids: list[str] = []           # closest options just shown (B21)
        self._rzp_order: Optional[dict] = None      # PRD §13: Razorpay test order for the current approval
        self._pending_qty: Optional[dict] = None    # B26: "Shall I make it 5?"
        self.tracer.event("session", "session.start", catalog_version=self.catalog.meta.get("version"),
                          llm_configured=intent_mod.llm_available(), source=source,
                          payments=payments.mode())

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _is_no_progress(r: Response) -> bool:
        return r.kind == "CLARIFY" or (r.kind == "UNSUPPORTED" and bool({"CATCH_ALL", "UNCLEAR"} & set(r.reason_codes)))

    _SHORT = {"OFF_TOPIC": "Still can't help with that one, sorry! Ask me about anything for your home.",
              "UNCLEAR": "Sorry, still not sure what you mean. Try a product, like \u201csofas under \u20b920,000\u201d.",
              "CATCH_ALL": "Sorry, still not getting it. Try a product, like \u201cbedsheets under \u20b91,000\u201d."}

    def _respond(self, r: Response) -> Response:
        last = next((m for role, m in reversed(self.history) if role == "assistant"), None)
        if r.kind == "UNSUPPORTED" and r.message == last:          # O-20: never the same long reply twice
            short = next((self._SHORT[c] for c in r.reason_codes if c in self._SHORT), None)
            if short:
                r.message = short
        if self._is_no_progress(r) and self._no_progress >= 2 and not self._in_recovery:
            return self._recover_stuck()            # B36: never a third unhelpful reply in a row
        if not self._in_recovery:
            self._no_progress = self._no_progress + 1 if self._is_no_progress(r) else 0
        if r.kind != "CLARIFY":
            self._last_clarify = None
        if r.kind in ("RECOMMEND", "NO_ELIGIBLE") and self._turn_labels:
            r.reason_codes = list(dict.fromkeys(r.reason_codes + self._turn_labels))
        self._turn_labels = []
        if r.recommendations:                          # R11: one product shown -> it's the one being talked about
            self.current = (self._get(r.recommendations[0]["product_id"]) if len(r.recommendations) == 1 else None)
        if r.kind != "ANSWER" or "CHALLENGE" not in r.reason_codes:
            self._challenges = 0
        self.history.append(("assistant", r.message))
        self.tracer.event("agent", "agent.response", response_kind=r.kind, reason_codes=r.reason_codes,
                          message=r.message[:300],
                          recommended_ids=[x["product_id"] for x in r.recommendations],
                          cart_id=r.cart.cart_id if r.cart else None,
                          order_id=r.order.order_id if r.order else None,
                          cited_fields=r.cited_fields, page=self.context.get("page"),
                          product_id=r.product_id or self.context.get("product_id"))
        return r

    def _recover_stuck(self) -> Response:
        """B36: after two unhelpful replies, change approach: show what's known so far, or give examples."""
        self._in_recovery = True
        self._no_progress = 0
        self.tracer.event("agent", "stuck_recovery", status="warn")
        try:
            if self.intent is not None and (self.intent.product_query or self.intent.category):
                r = self._search_and_recommend()
                r.message = _apologise(r.message)
                r.reason_codes = list(dict.fromkeys(r.reason_codes + ["STUCK_RECOVERY"]))
                return r
            return self._respond(Response("UNSUPPORTED", self._help_text(sorry=True), reason_codes=["STUCK_RECOVERY"]))
        finally:
            self._in_recovery = False

    def _help_text(self, sorry: bool = False) -> str:
        lead = "Sorry, I'm not getting it. Let's try another way. " if sorry else ""
        return (f"{lead}I can find products in this store ({self._store_labels()}), answer questions about a product, "
                "and place an order once you approve it. Try: \u201cFind a 3-seater sofa under \u20b930,000\u201d, "
                "\u201cBedsheets under \u20b91,000\u201d, or on a product page, \u201cHow wide is it?\u201d")

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
        pend_qty, self._pending_qty = self._pending_qty, None
        if pend_qty is not None and _YES.match(text):        # "Shall I make it 5?" -> yes
            return self.set_line_quantity(pend_qty["pid"], pend_qty["qty"])
        page_pid = self.context.get("product_id") if self.context.get("page") == "product" else None
        cart_r = (None if intent_mod._TRICK.search(text)       # safety first: a trick is never a cart command
                  else self._cart_chat(text, self._get(page_pid) if page_pid else None))
        if cart_r is not None:
            return cart_r
        override, self._pending_override = self._pending_override, None
        if override is not None:                       # B21 option A: answer to "add it anyway?"
            if _YES.match(text):
                return self._add_anyway(override)
            if _NO.match(text):
                return self._respond(Response("ANSWER", "No problem, I haven't added it. Want me to keep looking with "
                                              "a different budget?", reason_codes=["OVERRIDE_DECLINED"]))

        current: Optional[ProductView] = None
        if self.context.get("page") == "product" and self.context.get("product_id"):
            current = self._get(self.context["product_id"])
            if current is None:
                return self._respond(Response("BLOCKED", "I couldn't find this product in the store.",
                                              reason_codes=["PRODUCT_NOT_FOUND"]))
            self.context["product_title"] = current.title
            if self.current is None or self.current.product_id != current.product_id:
                self.current, self._last_answer = current, None
            fit = self._fit(text, current)                 # B28 on a product page: "will this fit in my room?"
            if fit is not None:
                return fit
            convo = self._conversation(text, current)      # R11: follow-ups and challenges (B38, B39)
            if convo is not None:
                return convo
            browse = self._browse(text)                   # O-63: a store-wide "what home decor items do you have?"
            if browse is not None:
                return browse
        else:
            self.context["page"] = "listing"
            convo = self._conversation(text, self.current)
            if convo is not None:
                return convo
            if self.shown:
                ref = self._shown_reference(text)        # B34: "the fabric one", "the first one"
                if ref is not None:
                    return ref
            about = self._about_current(text)            # B40: a question about the product just shown
            if about is not None:
                return about
            browse = self._browse(text)                   # B43: "what home decor items do you have?"
            if browse is not None:
                return browse

        pending, self._pending_confirm = self._pending_confirm, None
        if pending is not None and _NO.match(text):
            return self._respond(Response("CLARIFY", "No problem. Tell me in English what you're looking for, "
                                          "and I'll find it for you.", reason_codes=["NEEDS_PRODUCT"]))
        if pending is not None and _YES.match(text):
            new_intent, changed = intent_mod.merge(self.intent, pending, "rules_fallback")
            meta = {"confirmed": "shopper confirmed the product after a Hinglish message (B16)"}
        else:
            if self._last_clarify:
                self.context["pending_question"] = list(self._last_clarify)
            elif self._last_invite:
                self.context["pending_question"] = list(self._last_invite)
            new_intent, changed, meta = intent_mod.extract(text, self.intent, self.context)
        self.tracer.event("model" if new_intent.extractor.startswith("llm") else
                          "fast_path" if new_intent.extractor == intent_mod.FAST_PATH else "rules", "intent.extracted",
                          status="ok" if "error" not in meta else "warn", extractor=new_intent.extractor,
                          intent=new_intent.intent, constraints=new_intent.constraint_fields(),
                          question=new_intent.question, wants_similar=new_intent.wants_similar,
                          missing_info=new_intent.missing_info, changed_fields=changed,
                          intent_version=new_intent.version, **meta)

        if new_intent.intent == "STORE_POLICY" and new_intent.policy_topic:
            return self._policy(new_intent.policy_topic, text, current)
        if new_intent.intent == "REFUND_REQUEST":
            return self._respond(Response("DEFER", "Sorry, I can't handle refunds or returns just yet. I can help you "
                                          "find and buy products, though.", reason_codes=["WORKFLOW_NOT_AVAILABLE"]))
        if new_intent.intent == "ORDER_TRACKING":
            return self._respond(Response("DEFER", "Sorry, I can't track orders just yet. I can help you find and buy "
                                          "products, though.", reason_codes=["WORKFLOW_NOT_AVAILABLE"]))
        kind = new_intent.message_kind
        if new_intent.intent == "UNSUPPORTED" and kind in (None, "CATCH_ALL") and self._last_clarify:
            # A non-answer ("not sure") to our last question: rule R2, say what's still needed and stop.
            return self._clarify(list(self._last_clarify))
        if new_intent.intent == "UNSUPPORTED":
            return self._not_shopping(kind, new_intent, text)

        self._turn_labels = self._requirement_labels(self.intent, new_intent, changed)
        self._prev_intent = self.intent
        if changed and self.intent is not None:
            # R7: a changed requirement cancels the approval. The cart itself is kept (B47): each line was checked
            # against its own requirements when it was added, and is checked again before payment.
            self._invalidate_approval(f"constraints changed: {', '.join(changed)}")
        self.intent = new_intent

        if current is not None:
            if new_intent.intent == "PRODUCT_QUESTION":
                return self._answer(current, new_intent)
            if new_intent.intent == "BUY_THIS":
                return self.select_product(current.product_id, qty=new_intent.quantity or 1, from_product_page=True)
            if new_intent.wants_similar:
                return self._similar(current, cheaper=new_intent.wants_cheaper)

        if current is None:
            r = self._listing_decisions(new_intent, text)
            if r is not None:
                return r
        if new_intent.missing_info:
            return self._clarify(new_intent.missing_info)
        return self._search_and_recommend()

    # ------------------------------------------------------------------ Phase 2 listing decisions
    def _listing_decisions(self, it: Intent, text: str) -> Optional[Response]:
        has_product = bool(it.product_query or it.category)
        if it.vague_quality:                             # B28
            self._last_clarify = ("max_width_cm",)
            r = self._respond(Response("CLARIFY", f"Happy to check! How much space do you have for it? Then I'll "
                                       "tell you which ones fit.", reason_codes=["VAGUE_REQUIREMENT"]))
            self._last_clarify = ("max_width_cm",)
            return r
        if it.other_products:                            # B13
            return self._several(it)
        if it.show_results and not has_product:          # B31 with nothing searched yet
            self.intent = self._prev_intent
            return self._respond(Response("CLARIFY", "Happy to! What would you like to see? For example sofas, "
                                          "bedsheets or curtains.", reason_codes=["NEEDS_PRODUCT"]))
        if it.show_results or it.frustrated:             # B31, B36
            r = self._search_and_recommend()
            if it.frustrated:
                r.message = _apologise(r.message)
            r.reason_codes = list(dict.fromkeys(r.reason_codes + ["SHOW_RESULTS"]))
            return r
        if not has_product:
            named = self._name_or_brand(text)            # B33: a product name copied from the page
            if named is not None:
                return named
            if it.material:                              # B33: "solid wood" with no product
                return self._material_search(it.material)
        return None

    def _name_or_brand(self, text: str) -> Optional[Response]:
        for finder, label in (("brand_products", "BRAND_MATCH"), ("name_products", "NAME_MATCH")):
            f = getattr(self.catalog, finder, None)
            ids = f(text) if f else []
            if ids:
                probe = (self.intent or Intent(intent="PRODUCT_DISCOVERY")).model_copy(
                    update={"product_query": None, "category": None, "material": None})
                return self._show_ids(ids, probe, label)
        return None

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

    def _several(self, it: Intent) -> Response:
        """B13: results for each product named, in its own group."""
        groups, recs, ids, shown, any_rec = [], [], [], [], False
        for q in [it.product_query or ""] + list(it.other_products):
            probe = it.model_copy(update={"product_query": q, "category": None, "other_products": []})
            r = self._search_and_recommend(probe=probe, query=q)
            self.history.pop()
            if r.kind == "RECOMMEND":
                any_rec = True
                lines = [x["title"] + f" \u2014 {_inr(x['total_inr'])}" for x in r.recommendations]
                groups.append(f"{q.capitalize()}:\n" + "\n".join(f"\u2022 {l}" for l in lines))
                recs += r.recommendations
                ids += [x["product_id"] for x in r.recommendations]
                shown += list(self.shown)
            elif r.kind == "NOT_AVAILABLE":
                groups.append(f"Sorry, we don't sell {q}.")
            else:
                groups.append(f"{q.capitalize()}: {r.message}")
        self.eligible_ids, self.shown = ids, shown
        return self._respond(Response("RECOMMEND" if any_rec else "NOT_AVAILABLE", "\n\n".join(groups),
                                      recommendations=recs, reason_codes=["MULTIPLE_PRODUCTS"]))

    # ------------------------------------------------------------------ B34: pointing at shown results
    _REF = re.compile(r"\b(?:the|that|this)\s+(?:\w+\s+){0,2}one\b|\b(?:first|second|third|1st|2nd|3rd|last)\s+one\b|"
                      r"^\s*(?:the\s+)?(?:first|second|third|1st|2nd|3rd|last|cheaper|cheapest)(?:\s+one)?\s*[.!]?\s*$|"
                      r"\bthe (?:cheaper|cheapest) one\b", re.I)
    _Q = re.compile(r"\?|\b(when|how|what|is|does|do|can|will|which|are)\b", re.I)
    _TAKE = re.compile(r"\b(i want|i'll take|i will take|take|buy|order|add)\b", re.I)
    _COMMON = {"the", "one", "and", "for", "with", "sofa", "seater", "set", "want", "when", "can", "delivered", "will",
               "how", "what", "this", "that", "first", "second", "third", "last", "take", "buy", "order", "it", "be"}

    def _shown_reference(self, text: str) -> Optional[Response]:
        low = text.lower()
        words = [w for w in re.findall(r"[a-z0-9]+", low) if len(w) >= 3 and w not in self._COMMON]
        titles = {p.product_id: set(re.findall(r"[a-z0-9]+", p.title.lower())) for p in self.shown}
        everywhere = set.intersection(*titles.values()) if titles else set()
        hits = []
        for p in self.shown:
            toks = titles[p.product_id] - everywhere
            if any(w in toks or difflib.get_close_matches(w, list(toks), n=1, cutoff=0.85) for w in words):
                hits.append(p)
        if intent_mod._SHOW.search(low):
            return None                                  # "first show me the results" is B31, not a pick
        ref = self._REF.search(low)
        target = None
        if len(hits) == 1:
            target = hits[0]
        elif ref and not hits:
            word = next((w for w in ("first", "1st", "second", "2nd", "third", "3rd", "last", "cheapest", "cheaper")
                         if re.search(rf"\b{w}\b", low)), "")
            order = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}
            if word in order and len(self.shown) > abs(order[word]) - (1 if word == "last" else 0):
                target = self.shown[order[word]]
            elif word in ("cheaper", "cheapest"):
                target = min(self.shown, key=lambda p: p.total_for() or 10 ** 9)
            elif re.search(r"\bone\b", low):
                names = "; ".join(f"{i}. {p.title}" for i, p in enumerate(self.shown, 1))
                return self._respond(Response("CLARIFY", f"Which one do you mean? I showed: {names}.",
                                              reason_codes=["FROM_SHOWN_RESULTS"]))
        if target is None or not (ref or self._Q.search(low) or self._TAKE.search(low)):
            return None
        self.tracer.event("agent", "shown_reference", product_id=target.product_id, text=text)
        if self._Q.search(low):
            result = qa.answer_about_product(target, text, Intent(intent="PRODUCT_QUESTION", question=text))
            return self._respond(Response("ANSWER", f"{target.title}: {result.answer}", cited_fields=result.cited_fields,
                                          product_id=target.product_id, reason_codes=["FROM_SHOWN_RESULTS"]))
        r = self.select_product(target.product_id)
        r.reason_codes = list(dict.fromkeys(r.reason_codes + ["FROM_SHOWN_RESULTS"]))
        return r

    # ------------------------------------------------------------------ not a shopping message (§6A)
    def _not_shopping(self, kind: Optional[str], it: Intent, text: str) -> Response:
        labels = self._store_labels()
        if kind == "GREETING":
            return self._respond(Response("UNSUPPORTED", (
                f"Hi! I can help you find and compare products in this store ({labels}), answer questions "
                "about a product, and place an order once you approve it."), reason_codes=["GREETING"]))
        if kind == "THANKS":
            return self._respond(Response("UNSUPPORTED", "You're welcome! Happy shopping.",
                                          reason_codes=["GREETING"]))
        if kind == "OFF_TOPIC":
            if re.search(r"\b(who|what) are you\b|\byour name\b|\bare you\b", text, re.I):
                msg = f"I'm this store's shopping assistant. I can help you find and buy {labels}."
            else:
                msg = ("That's not something I can help with, sorry. But I'd love to help you find something "
                       f"for your home: {labels}.")
            return self._respond(Response("UNSUPPORTED", msg, reason_codes=["OFF_TOPIC"]))
        if kind == "UNCLEAR":
            return self._respond(Response("UNSUPPORTED", "Sorry, I didn't understand that. I can help you find, "
                                          "compare and buy home and living products.", reason_codes=["UNCLEAR"]))
        page_product = self.current if self.context.get("page") == "product" else None
        if kind == "CRITICISM":                      # B44: take it seriously; never the abusive reply or a goodbye
            if page_product is not None:
                noun = qa.product_noun(page_product)
                msg = (f"Sorry, that's fair. I can only answer from this {noun}'s details, and they don't cover "
                       f"everything. I can tell you about its size, materials, delivery and care, or help you order it.")
            else:
                msg = ("Sorry, that's fair. I can find products in this store, answer questions about them and help "
                       "you order. Tell me what you're looking for and I'll do my best.")
            return self._respond(Response("ANSWER", msg, reason_codes=["FRUSTRATED"]))
        if kind == "ABUSIVE":
            return self._respond(Response("UNSUPPORTED", "Apologies for the inconvenience. Hope you find what "
                                          "you're looking for.", reason_codes=["ABUSIVE"]))
        if kind == "TRICK":
            self.tracer.event("guardrail", "policy_refusal", status="warn", note="request to bypass rules")
            return self._respond(Response("UNSUPPORTED", "Sorry, I can't help with that. I can only help you pick the "
                                          "right product and buy it, with your approval.",
                                          reason_codes=["POLICY_REFUSAL"]))
        if kind == "COMPARE":
            return self._respond(Response("DEFER", "Side-by-side comparison isn't something I can do just yet, "
                                          "sorry! I can tell you the width, seats and price of each one, though. "
                                          "Which one first?", reason_codes=["WORKFLOW_NOT_AVAILABLE"]))
        if kind == "HELP":
            if self.intent is not None and self.intent.product_query and self._no_progress:
                return self._respond(Response("ANSWER", (
                    "Sorry about the trouble. I can find products, answer questions about them and order with your "
                    f"approval. Want to pick up with the {_plural(self.intent.product_query)}?"), reason_codes=["HELP"]))
            if page_product is not None:            # B35 (round 2, O-44): help about the product on screen
                noun = qa.product_noun(page_product)
                return self._respond(Response("ANSWER", (
                    f"For this {noun}, I can tell you its size, materials, delivery time and care, or help you order "
                    "it. I can also find other products for your home."), reason_codes=["HELP"]))
            return self._respond(Response("ANSWER", self._help_text(), reason_codes=["HELP"]))
        if kind == "STORE_INFO":
            return self._respond(Response("ANSWER", self._store_info(text), reason_codes=["STORE_INFO"]))
        if kind == "CATCH_ALL":
            named = self._name_or_brand(text)
            if named is not None:
                return named
        if kind == "HINGLISH" and it.product_query:
            matches, _ = self._find(it.product_query)
            if matches:
                phrase = it.product_query + (f" under {it.max_total_inr}" if it.max_total_inr else "")
                self._pending_confirm = intent_mod.extract_rules(phrase, self.context)
                return self._respond(Response("CLARIFY", f"Are you searching for a {it.product_query}? "
                                              "Only English is supported.", reason_codes=["LANGUAGE_NOT_SUPPORTED"]))
        return self._respond(Response("UNSUPPORTED", "Sorry, I didn't quite get that. I can help you find and "
                                      "buy things for your home.", reason_codes=["CATCH_ALL"]))

    def _store_info(self, text: str) -> str:
        """B35: answers about the store from catalog facts only; honest about what the data doesn't cover."""
        t = text.lower()
        if re.search(r"\bpay|cash on delivery|\bcod\b|\bemi\b", t):
            return ("I don't have information about payment options. In this demo store, orders are mock and no "
                    "payment is taken.")
        if "policy" in t:
            return "I don't have the store's policies (returns, shipping or warranty) in my data, sorry."
        cats = self.catalog.categories() if hasattr(self.catalog, "categories") else []
        if re.search(r"brand", t) and hasattr(self.catalog, "_brand_index"):
            from collections import Counter
            top = Counter(b for b in self.catalog._brand_index().values() if b).most_common(5)
            return (f"We have {len({b for b in self.catalog._brand_index().values() if b}):,} brands. The biggest are "
                    + ", ".join(f"{b} ({n})" for b, n in top) + ".")
        if cats:
            total = sum(c["count"] for c in cats)
            return (f"We have {total:,} products: " + ", ".join(f"{c['count']:,} in {c['label'].lower()}" for c in cats)
                    + ".")
        return f"This store sells {self._store_labels()}."

    @staticmethod
    def _requirement_labels(prior: Optional[Intent], new: Intent, changed: list[str]) -> list[str]:
        """Reason labels for how this message changed the current product's requirements (B10, B19)."""
        if prior is None or "product" in changed:
            return []
        labels = []
        for f in changed:
            if f in new.remove_fields:
                labels.append("REQUIREMENT_REMOVED")
            elif f in intent_mod.CONSTRAINT_FIELDS or f in ("required_compatibility", "preferred_brands"):
                before = getattr(prior, f)
                labels.append("REQUIREMENT_CHANGED" if before not in (None, []) else "REQUIREMENT_ADDED")
        return list(dict.fromkeys(labels))

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
    def _clarify(self, missing: list[str]) -> Response:
        key = tuple(sorted(missing))
        if key == self._last_clarify:
            # Same gap as last turn: don't ask the same question again. Say what's needed and stop.
            needs = " and ".join(_NEED.get(m, m) for m in missing)
            self.tracer.event("agent", "clarify.repeat_suppressed", status="warn", missing_info=missing)
            r = Response("CLARIFY", f"No rush. I still need {needs} before I can search. Tell me whenever you're ready.")
        else:
            self.tracer.event("agent", "clarify", missing_info=missing)
            r = Response("CLARIFY", " ".join(_ASK.get(m, f"Could you tell me the {m}?") for m in missing))
        out = self._respond(r)
        self._last_clarify = key
        return out

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
        matches, related = self._find(query)
        label = None
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
        candidates = [pid for pid in matches if pid not in exclude][:MAX_CANDIDATES]
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

        if not ranked:
            return self._closest(rejected, rej, query, it)
        self.shown = ranked
        invite = self._invite(it)
        msg = self._explain(ranked, rej, len(eligible), it, closing=invite,
                            lead=partial_note.rstrip(":") + "." if partial_note else None)
        return self._respond(Response("RECOMMEND", msg, recommendations=recs, rejected=rej,
                                      reason_codes=[label] if label else []))

    def _invite(self, it: Intent) -> Optional[str]:
        """B18: after a broad search, one light line inviting the shopper to narrow down."""
        self._last_invite = None
        is_sofa = it.category == "sofa" or intent_mod.head_term(it.product_query) in ("sofa", "couch", "settee")
        if is_sofa and (it.seats is None or it.max_width_cm is None):
            self._last_invite = [f for f in ("seats", "max_width_cm") if getattr(it, f) is None]
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
        lines = [lead + show]
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
    def _answer(self, p: ProductView, it: Intent) -> Response:
        self._count_tool()
        with self.tracer.tool("answer_about_product", product_id=p.product_id, question=it.question) as t:
            result = qa.answer_about_product(p, it.question or "", it, history=self._recent())
            t["summary"] = {"method": result.method, "status": result.status, "cited_fields": result.cited_fields,
                            **{k: result.meta[k] for k in ("model", "prompt_version", "tried_first") if k in result.meta}}
        if result.status == "rejected":
            self.tracer.event("guardrail", "qa.answer_rejected", status="warn", product_id=p.product_id,
                              reason=result.meta.get("rejected"))
        if (result.status == "not_in_listing" and self._last_answer and self._last_answer["pid"] == p.product_id
                and self._last_answer["status"] == "not_in_listing"):
            # B36 on a product page (round 2, O-43): a second "don't know" in a row changes approach
            result.answer = (f"Sorry, I don't have that one either. For this {qa.product_noun(p)}, I can tell you "
                             "its size, materials, delivery time and care, or help you order it.")
            self.tracer.event("agent", "stuck_recovery", status="warn", page="product")
        self.current = p
        self._last_answer = {"pid": p.product_id, "fields": list(result.cited_fields), "status": result.status,
                             "question": it.question or ""}
        return self._respond(Response("ANSWER", result.answer, cited_fields=result.cited_fields,
                                      product_id=p.product_id,
                                      reason_codes=["NOT_IN_LISTING"] if result.status == "not_in_listing" else []))

    # ------------------------------------------------------------------ B28 on a product page
    _FIT_Q = re.compile(r"\b(fit|fits|big enough|too (big|large|small|wide|long)|enough (room|space))\b", re.I)
    _MEASURE = re.compile(r"(\d+(?:\.\d+)?)\s*(mm|cm|centimet\w*|m\b|met(?:er|re)s?|ft|feet|foot|in\b|inch\w*)?", re.I)

    def _space_cm(self, text: str) -> list[float]:
        out = []
        for num, unit in self._MEASURE.findall(text):
            v = float(num)
            u = (unit or "").lower()
            if u.startswith(("mm",)) or u.startswith("milli"):
                v /= 10
            elif u in ("m",) or u.startswith("met"):
                v *= 100
            elif u in ("ft", "feet", "foot"):
                v *= 30.48
            elif u in ("in",) or u.startswith("inch"):
                v *= 2.54
            elif not u:
                v = v * 100 if v <= 10 else v           # a bare "3" is metres, a bare "150" is cm
            out.append(v)
        return out

    def _fit(self, text: str, p: ProductView) -> Optional[Response]:
        dims = {f: qa.measurement_mm(p, f) for f in ("Width", "Depth")}
        if self._pending_fit == p.product_id:
            space = self._space_cm(text)
            self._pending_fit = None
            if space:
                return self._fit_result(p, dims, space)
        if not self._FIT_Q.search(text) or self._space_cm(text):
            return None                                # "will it fit a 2 m wall?" is the normal requirement check
        w, d = dims["Width"], dims["Depth"]
        if w is None:
            return self._respond(Response("ANSWER", f"Sorry, I don't have the size of this {qa.product_noun(p)}, "
                                          "so I can't check the fit.", product_id=p.product_id,
                                          reason_codes=["VAGUE_REQUIREMENT"]))
        size = f"{w / 10:.0f} cm wide" + (f" and {d / 10:.0f} cm long" if d else "")
        self._pending_fit = p.product_id
        return self._respond(Response("CLARIFY", f"It's {size}. How much space do you have for it? Tell me and "
                                      "I'll check.", cited_fields=[f for f in ("Width", "Depth") if dims[f]],
                                      product_id=p.product_id, reason_codes=["VAGUE_REQUIREMENT"]))

    def _fit_result(self, p: ProductView, dims: dict, space: list[float]) -> Response:
        w = dims["Width"] / 10
        d = dims["Depth"] / 10 if dims["Depth"] else None
        cited = [f for f in ("Width", "Depth") if dims[f]]
        self.tracer.event("tool", "fit_check", product_id=p.product_id, product_cm=[w, d], space_cm=space)
        if len(space) >= 2 and d:
            a, b = space[0], space[1]
            if (w <= a and d <= b) or (w <= b and d <= a):
                msg = (f"Good news, it fits! It's {w:.0f} × {d:.0f} cm, and your space is {a:.0f} × {b:.0f} cm.")
            else:
                msg = (f"Sorry, it won't fit: it's {w:.0f} × {d:.0f} cm, and your space is {a:.0f} × {b:.0f} cm.")
        else:
            a = space[0]
            if w <= a:
                msg = f"Good news, it fits! It's {w:.0f} cm wide, within your {a:.0f} cm."
            else:
                msg = f"Sorry, it won't fit: it's {w:.0f} cm wide, {w - a:.0f} cm more than your {a:.0f} cm."
        return self._respond(Response("ANSWER", msg, cited_fields=cited, product_id=p.product_id,
                                      reason_codes=["FIT_CHECK"]))

    # ------------------------------------------------------------------ B43: browsing a category
    _CATEGORY_WORDS = [("home_decor", r"home d[eé]cor|\bd[eé]cor\b"), ("kitchen_dining", r"\bkitchen\b|\bdining\b"),
                       ("home_furnishing", r"furnishing|\blinen\b|\bbedding\b"), ("furniture", r"\bfurniture\b")]

    def _browse(self, text: str) -> Optional[Response]:
        low = text.lower()
        if not re.search(r"\b(what|which|show|list|browse)\b", low) or not re.search(
                r"\b(items?|stuff|things|products?|kinds?|types?|do you (have|sell)|you sell|have you got)\b", low):
            return None
        slug = next((sl for sl, pat in self._CATEGORY_WORDS if re.search(pat, low)), None)
        if slug is None or not hasattr(self.catalog, "category_kinds"):
            return None
        kinds = self.catalog.category_kinds(slug)
        if not kinds:
            return None
        label = next(c["label"] for c in self.catalog.categories() if c["slug"] == slug)
        total = next(c["count"] for c in self.catalog.categories() if c["slug"] == slug)
        listed = ", ".join(f"{k.lower()} ({n})" for k, n in kinds[:-1]) + f" and {kinds[-1][0].lower()} ({kinds[-1][1]})"
        self.tracer.event("tool", "category_kinds", category=slug, kinds=kinds)
        return self._respond(Response("ANSWER", f"Plenty! We have {total:,} {label.lower()} products, including "
                                      f"{listed}. Which would you like to see?", reason_codes=["CATEGORY_BROWSE"]))

    # ------------------------------------------------------------------ B21 option A: add a closest option anyway
    def _add_anyway(self, override: dict) -> Response:
        p = self._get(override["pid"])
        if p is None:
            return self._respond(Response("BLOCKED", "Sorry, I couldn't find that product anymore.",
                                          reason_codes=["PRODUCT_NOT_FOUND"]))
        self.tracer.event("policy", "override_accepted", product_id=p.product_id, waived=override["waived"])
        e = policy.evaluate(Intent(intent="BUY_THIS"), p, 1)   # stock and a known price still must pass
        if not e.eligible:
            return self._respond(Response("BLOCKED", f"Sorry, that one doesn't work anymore: {_reasons(e.reason_codes)}.",
                                          reason_codes=e.reason_codes))
        return self.select_product(p.product_id, from_product_page=True, waived=override["waived"])

    # ------------------------------------------------------------------ B41: store policy questions
    def _policy(self, topic: str, text: str, product: Optional[ProductView]) -> Response:
        self._count_tool()
        with self.tracer.tool("answer_store_policy", topic=topic,
                              product_id=product.product_id if product else None) as t:
            a = store_policy.answer(topic, text, product=product, use_llm=intent_mod.llm_available())
            t["summary"] = {"method": a.method, "cited": a.cited,
                            **{k: a.meta[k] for k in ("model", "prompt_version", "fallback") if k in a.meta}}
        return self._respond(Response("ANSWER", a.answer, cited_fields=a.cited,
                                      product_id=product.product_id if product else None,
                                      reason_codes=["STORE_POLICY"]))

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
            self._pending_qty = {"pid": product_id, "qty": limit}
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
    _NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    _QTY_SAY = re.compile(
        r"\b(?:make it|change (?:the )?(?:quantity|qty) to|set (?:the )?(?:quantity|qty) to|(?:i|we) (?:want|need|'?ll take|"
        r"will take)|add|buy|get me|order|i'?d like)\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b"
        r"(?!\s*(?:k\b|000|rs|rupees|inr|seater|seat))|"
        r"^\s*(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:of (?:these|this|them|it)|please|pcs|pieces|units?)\b", re.I)
    _REMOVE_ITEM = re.compile(r"\b(?:remove|delete|take out|drop)\b(.*?)(?:\bfrom (?:my |the )?cart\b|$)", re.I)
    _CART_Q = re.compile(r"\b(?:what'?s|what is|show(?: me)?|view|see) (?:in )?(?:my |the )?cart\b|^\s*(?:my )?cart\??\s*$", re.I)
    _ADD_TO_CART = re.compile(r"\badd (?:it|this|that|this one|that one)?\s*(?:to (?:my |the )?cart|too|as well)\b|"
                              r"\badd to (?:my |the )?cart\b|\balso (?:add|buy|get) (?:this|it)\b", re.I)

    def _cart_chat(self, text: str, page_product: Optional[ProductView]) -> Optional[Response]:
        low = text.lower()
        if self._CART_Q.search(low):
            return self.cart_summary()
        has_cart = self.cart is not None and self.cart.status == "PROPOSED" and self.cart.lines
        m = self._REMOVE_ITEM.search(low)
        if m and has_cart and re.search(r"\bcart\b|^\s*(remove|delete|drop)\b", low):
            words = set(re.findall(r"[a-z]{3,}", m.group(1))) - {"the", "this", "that", "item", "one", "from", "please"}
            hits = [ln for ln in self.cart.lines if words & set(re.findall(r"[a-z]{3,}", ln.title.lower()))]
            if not hits and page_product is not None and self.cart.line(page_product.product_id) and \
                    re.search(r"\b(this|it)\b", m.group(1)):
                hits = [self.cart.line(page_product.product_id)]
            if len(hits) == 1:
                return self.remove_line(hits[0].product_id)
            if len(self.cart.lines) == 1 and not words:
                return self.remove_line(self.cart.lines[0].product_id)
            names = "; ".join(ln.title for ln in self.cart.lines)
            return self._respond(Response("CLARIFY", f"Which one should I remove? Your cart has: {names}.",
                                          cart=self.cart, reason_codes=["WHICH_ITEM"]))
        q = self._QTY_SAY.search(low)
        if q:
            n_raw = (q.group(1) or q.group(2)).lower()
            n = self._NUM.get(n_raw) or int(n_raw)
            if n > 99:
                return None
            if page_product is not None:
                return self.select_product(page_product.product_id, qty=n, from_product_page=True, set_qty=True)
            if has_cart and len(self.cart.lines) == 1:
                return self.set_line_quantity(self.cart.lines[0].product_id, n)
            if has_cart:
                names = "; ".join(ln.title for ln in self.cart.lines)
                return self._respond(Response("CLARIFY", f"Which one should be {n}? Your cart has: {names}.",
                                              cart=self.cart, reason_codes=["WHICH_ITEM"]))
            return None
        if page_product is not None and self._ADD_TO_CART.search(low):
            return self.select_product(page_product.product_id, from_product_page=True)
        return None

    # ------------------------------------------------------------------ R11: holding a conversation
    _CHALLENGE = re.compile(
        r"\b(can'?t|cant|cannot|couldn'?t) you\b|\bwhy (not|can'?t you|won'?t you|didn'?t you)\b|\bare you sure\b|"
        r"^\s*really\b|\bdoesn'?t (seem|look)\b|\bdoes ?n'?t look\b|\bthat'?s (not|wrong)\b|\bwhen did\b.*\bbecome\b|"
        r"\bis (that|it) (really|actually)\b|\byou said\b|\bnot (real|actually)\b", re.I)
    _DOUBT = re.compile(r"\b(doesn'?t (seem|look)|are you sure|really|actually|real)\b", re.I)
    _WHICH_PRODUCT = re.compile(r"\b(which|what) (product|one|item)\b.*\b(talking|mean|asking)\b", re.I)

    def _recent(self, n: int = 6) -> list[str]:
        """The last few turns, for the steps that write replies (R11). The current message is the last one."""
        return [f"{'Shopper' if role == 'user' else 'Assistant'}: {m[:300]}" for role, m in self.history[-n - 1:-1]]

    def _last_reply(self) -> Optional[str]:
        return next((m for role, m in reversed(self.history[:-1]) if role == "assistant"), None)

    def _conversation(self, text: str, target: Optional[ProductView]) -> Optional[Response]:
        """B38 (follow-ups to the last answer) and B39 (challenges to the last reply). None: handle as usual."""
        if self._last_reply() is None:
            return None
        challenge = bool(self._CHALLENGE.search(text))
        unit = qa.unit_asked(text)
        if unit is None and challenge and re.search(r"\bconvert", text, re.I):
            unit = self._last_unit
        la = self._last_answer
        if unit and target is not None and la and la["pid"] == target.product_id:
            r = self._convert(target, unit, la, sorry=challenge)
            if r is not None:
                return r
        if not challenge or len(re.findall(r"[a-z']+", text.lower())) > 14:
            return None
        self._challenges += 1
        self.tracer.event("agent", "challenge", text=text, product_id=target.product_id if target else None,
                          last_status=la["status"] if la else None)
        if target is not None and self._DOUBT.search(text) and not (la and la["status"] == "not_in_listing"):
            # "doesn't seem to be wooden", "are you sure that's real wood?": check the listing and answer the doubt
            r = self._answer(target, Intent(intent="PRODUCT_QUESTION", question=text))
            r.reason_codes = list(dict.fromkeys(r.reason_codes + ["CHALLENGE"]))
            return r
        if target is not None:
            if self._challenges == 1:
                msg = ("Sorry, I can only answer from what's in this product's details, like its size, materials, "
                       "delivery and care. I'm a shopping assistant: I can help you find things and answer questions "
                       "about this product.")
            else:
                msg = ("Sorry, that detail just isn't in this product's information, so I can't tell you more. "
                       "Want to know its size, materials, delivery time or care instead?")
            return self._respond(Response("ANSWER", msg, product_id=target.product_id, reason_codes=["CHALLENGE"]))
        prev = next((m for role, m in reversed(self.history[:-1]) if role == "user"), None)
        msg = ("Fair point, sorry about that! " if self._challenges == 1 else "Sorry again! ") + \
              "I'm a shopping assistant: I can find products, answer questions about them and help you order."
        if prev:
            msg += " Tell me what you're looking for and I'll take another look."
        return self._respond(Response("ANSWER", msg, reason_codes=["CHALLENGE"]))

    def _convert(self, p: ProductView, unit: str, la: dict, sorry: bool) -> Optional[Response]:
        fields = [f for f in la["fields"] if f in qa.MEASURE_FIELDS] or \
                 [f for f in ("Width", "Depth", "Height") if f in (la.get("question") or "")]
        q = (la.get("question") or "").lower()
        parts = []
        for f in fields:
            mm = qa.measurement_mm(p, f)
            if mm is None:
                continue
            word = {"Width": "wide", "Depth": "long" if re.search(r"\blong|length", q) else "deep",
                    "Height": "high", "Length": "long"}[f]
            parts.append(f"{qa.format_length(mm, unit)} {word}")
        if not parts:
            return None
        self._last_unit = unit
        self.tracer.event("tool", "unit_conversion", product_id=p.product_id, fields=fields, unit=unit)
        lead = "Sorry about that! " if sorry else ""
        body = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        r = self._respond(Response("ANSWER", f"{lead}That's {body}.", cited_fields=fields, product_id=p.product_id,
                                   reason_codes=["FOLLOW_UP"] + (["CHALLENGE"] if sorry else [])))
        return r

    def _about_current(self, text: str) -> Optional[Response]:
        """B40: on the listing page, a question about the product just shown or discussed."""
        low = text.lower()
        if self._WHICH_PRODUCT.search(low):
            if self.current is not None:
                return self._respond(Response("ANSWER", f"Yes, the {self.current.title} I just showed you. What would "
                                              "you like to know about it?", product_id=self.current.product_id,
                                              reason_codes=["FROM_SHOWN_RESULTS"]))
            if self.shown:
                names = "; ".join(f"{i}. {p.title}" for i, p in enumerate(self.shown, 1))
                return self._respond(Response("CLARIFY", f"Which one do you mean? I showed: {names}.",
                                              reason_codes=["FROM_SHOWN_RESULTS"]))
            return None
        named = self._named_product(low)                 # O-68: "tell me about the sofa" -> the sofa in the cart
        if isinstance(named, Response):
            return named
        if named is not None:
            self.current = named
            if re.search(r"\b(tell me (more )?about|describe|details|what about|more about)\b", low):
                return self._describe(named)
            r = self._answer(named, Intent(intent="PRODUCT_QUESTION", question=text))
            r.reason_codes = list(dict.fromkeys(r.reason_codes + ["FROM_SHOWN_RESULTS"]))
            return r
        if not self.shown and self.current is None:
            return None
        as_product = intent_mod.extract_rules(text, {"page": "product"}, None)
        refers = re.search(r"\b(it|its|it's|this|that|this one|that one|that product|this product)\b", low)
        question = "?" in text or re.match(r"\s*(is|are|does|do|did|can|could|will|would|what|how|which|when|where|"
                                           r"who|has|have|tell me)\b", low)
        if as_product.intent != "PRODUCT_QUESTION" or not refers or not question or as_product.message_kind:
            return None
        if self.current is not None:
            r = self._answer(self.current, Intent(intent="PRODUCT_QUESTION", question=text))
            r.reason_codes = list(dict.fromkeys(r.reason_codes + ["FROM_SHOWN_RESULTS"]))
            return r
        names = "; ".join(f"{i}. {p.title}" for i, p in enumerate(self.shown, 1))
        return self._respond(Response("CLARIFY", f"Which one do you mean? I showed: {names}.",
                                      reason_codes=["FROM_SHOWN_RESULTS"]))

    _THE_NOUN = re.compile(r"\b(?:the|that|this|my)\s+([a-z][a-z-]{2,})\b")
    _ASKING = re.compile(r"\?|^\s*(tell me|describe|what|how|is|are|does|do|can|will|which)\b|\bmore about\b")

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

    def _named_product(self, low: str):
        """O-68: "tell me about the sofa" names one product the shopper already has in front of them. The cart wins
        (that's the one they chose), then the product being discussed, then the results just shown. If several match,
        ask which one instead of searching again. Returns a product, a CLARIFY response, or None."""
        if not self._ASKING.search(low):
            return None
        nouns = [n.rstrip("s") for n in self._THE_NOUN.findall(low)
                 if n not in ("one", "first", "second", "third", "last", "store", "cart", "price", "same", "other")]
        if not nouns:
            return None
        def matching(ps):
            seen, out = set(), []
            for p in ps:
                if p is not None and p.product_id not in seen and any(
                        n in f"{p.title} {p.category_path or p.category}".lower() for n in nouns):
                    seen.add(p.product_id)
                    out.append(p)
            return out
        in_cart = matching([self._get(ln.product_id) for ln in (self.cart.lines if self.cart else [])])
        if len(in_cart) == 1:
            return in_cart[0]
        pool = in_cart or matching([self.current] if self.current else []) or matching(self.shown or [])
        if len(pool) == 1:
            return pool[0]
        if len(pool) > 1:
            names = "; ".join(f"{i}. {p.title}" for i, p in enumerate(pool, 1))
            return self._respond(Response("CLARIFY", f"Which one do you mean? {names}.",
                                          reason_codes=["FROM_SHOWN_RESULTS"]))
        return None

    def _describe(self, p: ProductView) -> Response:
        """A short, plain summary of one product (O-68), from its own details only."""
        f = qa.listing_fields(p)
        total = (p.list_price_inr or 0) + (p.shipping_inr or 0)
        parts = [f"Here's the {p.title}: ₹{total:,} including delivery, arriving in about {p.delivery_days} days."]
        for field in ("Seating Capacity", "Width", "Primary Material", "Primary Color"):
            if field not in f:
                continue
            seats = re.search(r"\d+", str(f[field])) if field == "Seating Capacity" else None
            parts.append(f"It seats {seats.group()}." if seats else f"It comes in {str(f[field]).lower()}."
                         if field == "Primary Color" else qa._say(p, field, f[field]))
        parts.append("Ask me anything else about it.")
        cited = ["Price", "Delivery time"] + [x for x in ("Seating Capacity", "Width", "Primary Material", "Primary Color")
                                               if x in f]
        return self._respond(Response("ANSWER", " ".join(parts), cited_fields=cited, product_id=p.product_id,
                                      reason_codes=["FROM_SHOWN_RESULTS"]))

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
                self._pending_override = {"pid": product_id, "waived": e.reason_codes}
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
