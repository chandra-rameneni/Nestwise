"""IntentGuard session: page-aware routing, bounded tool use, grounded recommendations and answers,
approval and checkout.

The flow is code-driven (a workflow, not a free-running model loop). The model is used only to
interpret language and to phrase product answers from listing data; every search outcome,
eligibility, approval and checkout decision is deterministic code.

Every turn ends in exactly one outcome (PRD rule R4):
RECOMMEND | ANSWER | CLARIFY | NOT_AVAILABLE | NO_ELIGIBLE | CART_PROPOSED | APPROVED | DECLINED |
ORDER_PLACED | BLOCKED | DEFER | UNSUPPORTED
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import intent as intent_mod
import policy
import qa
from catalog import STORE_DB_PATH, Catalog, ProductView, SqliteCatalog, _head_noun
from checkout import Approval, Cart, MockOrder, MockOrderService, new_approval, new_cart
from intent import Intent
from tracing import Tracer

MAX_TOOL_CALLS_PER_TURN = 40
MAX_CANDIDATES = 200
MAX_RECOMMENDATIONS = 3

_ASK = {
    "product": "What product are you looking for?",
    "budget": "What is the most you want to pay in total, including delivery (in ₹)?",
    "seats": "How many seats do you need?",
    "max_width_cm": "How much wall space is there for it? Please give the maximum width in cm.",
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


def default_catalog():
    """The real store catalog when it has been built, otherwise the synthetic fixture."""
    return SqliteCatalog() if STORE_DB_PATH.exists() else Catalog()


class Session:
    def __init__(self, catalog=None, tracer: Optional[Tracer] = None, orders: Optional[MockOrderService] = None):
        self.catalog = catalog or default_catalog()
        self.tracer = tracer or Tracer()
        self.orders = orders or MockOrderService()
        self.intent: Optional[Intent] = None
        self.eligible_ids: list[str] = []
        self.cart: Optional[Cart] = None
        self.approval: Optional[Approval] = None
        self.history: list[tuple[str, str]] = []
        self.context: dict = {"page": "listing"}
        self._tool_calls = 0
        self._last_clarify: Optional[tuple] = None
        self.tracer.event("session", "session.start", catalog_version=self.catalog.meta.get("version"),
                          llm_configured=intent_mod.llm_available())

    # ------------------------------------------------------------------ helpers
    def _respond(self, r: Response) -> Response:
        if r.kind != "CLARIFY":
            self._last_clarify = None
        self.history.append(("assistant", r.message))
        self.tracer.event("agent", "agent.response", response_kind=r.kind, reason_codes=r.reason_codes,
                          recommended_ids=[x["product_id"] for x in r.recommendations],
                          cart_id=r.cart.cart_id if r.cart else None,
                          order_id=r.order.order_id if r.order else None,
                          cited_fields=r.cited_fields, page=self.context.get("page"),
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

        current: Optional[ProductView] = None
        if self.context.get("page") == "product" and self.context.get("product_id"):
            current = self._get(self.context["product_id"])
            if current is None:
                return self._respond(Response("BLOCKED", "I couldn't find this product in the store.",
                                              reason_codes=["PRODUCT_NOT_FOUND"]))
            self.context["product_title"] = current.title
        else:
            self.context["page"] = "listing"

        new_intent, changed, meta = intent_mod.extract(text, self.intent, self.context)
        self.tracer.event("model" if new_intent.extractor.startswith("llm") else "rules", "intent.extracted",
                          status="ok" if "error" not in meta else "warn", extractor=new_intent.extractor,
                          intent=new_intent.intent, constraints=new_intent.constraint_fields(),
                          question=new_intent.question, wants_similar=new_intent.wants_similar,
                          missing_info=new_intent.missing_info, changed_fields=changed,
                          intent_version=new_intent.version, **meta)

        if new_intent.intent == "REFUND_REQUEST":
            return self._respond(Response("DEFER", (
                "I can see you'd like a refund. Refunds aren't available in this demo yet. A real refund needs "
                "you to sign in so I can find your own order and check the store's return policy. "
                "Nothing has been refunded or changed."), reason_codes=["WORKFLOW_NOT_AVAILABLE"]))
        if new_intent.intent == "ORDER_TRACKING":
            return self._respond(Response("DEFER", (
                "I can see you want to track an order. Order tracking isn't available in this demo yet; it would "
                "need you to sign in so only your own orders are looked up. No order data was accessed."),
                reason_codes=["WORKFLOW_NOT_AVAILABLE"]))
        if new_intent.intent == "UNSUPPORTED" and self._last_clarify:
            # A non-answer ("not sure") to our last question: rule R2, say what's still needed and stop.
            return self._clarify(list(self._last_clarify))
        if new_intent.intent == "UNSUPPORTED":
            return self._respond(Response("UNSUPPORTED", (
                f"I can help you find and compare products in this store ({self._store_labels()}), answer "
                "questions about a product, and place an order once you approve it.")))

        if changed and self.intent is not None:
            self._invalidate_approval(f"constraints changed: {', '.join(changed)}")
            if self.cart and self.cart.status == "PROPOSED":
                self.cart.status = "SUPERSEDED"
        self.intent = new_intent

        if current is not None:
            if new_intent.intent == "PRODUCT_QUESTION":
                return self._answer(current, new_intent)
            if new_intent.intent == "BUY_THIS":
                return self.select_product(current.product_id, from_product_page=True)
            if new_intent.wants_similar:
                return self._similar(current, cheaper=new_intent.wants_cheaper)

        if new_intent.missing_info:
            return self._clarify(new_intent.missing_info)
        return self._search_and_recommend()

    # ------------------------------------------------------------------ clarify (rule R2)
    def _clarify(self, missing: list[str]) -> Response:
        key = tuple(sorted(missing))
        if key == self._last_clarify:
            # Same gap as last turn: don't ask the same question again. Say what's needed and stop.
            needs = " and ".join(_NEED.get(m, m) for m in missing)
            self.tracer.event("agent", "clarify.repeat_suppressed", status="warn", missing_info=missing)
            r = Response("CLARIFY", f"I still need {needs} before I can search. Tell me whenever you're ready.")
        else:
            self.tracer.event("agent", "clarify", missing_info=missing)
            r = Response("CLARIFY", " ".join(_ASK.get(m, f"Could you tell me the {m}?") for m in missing))
        out = self._respond(r)
        self._last_clarify = key
        return out

    # ------------------------------------------------------------------ discovery
    def _find(self, query: str) -> tuple[list[str], list[str]]:
        self._count_tool()
        with self.tracer.tool("search_catalog", query=query, category=self.intent.category) as t:
            matches, related = self.catalog.find_products(query, product_category=self.intent.category)
            t["summary"] = {"matches": len(matches), "related": len(related), "first_ids": matches[:10]}
        return matches, related

    def _search_and_recommend(self, exclude: tuple[str, ...] = (), query: Optional[str] = None,
                              probe: Optional[Intent] = None) -> Response:
        it = probe or self.intent
        query = query if query is not None else (it.product_query or "")
        matches, related = self._find(query)
        if not matches:
            # Rule R1: not sold here. Terminal answer, no follow-up question, same answer every time.
            name = query.strip() or "that"
            return self._respond(Response("NOT_AVAILABLE", f"We don't sell {name}. This store sells "
                                          f"{self._store_labels()}.", reason_codes=["NOT_SOLD_HERE"]))
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
                "reason_codes": e.reason_codes} for p, e in rejected]
        self.tracer.event("agent", "recommendation", eligible_ids=self.eligible_ids, eligible_count=len(eligible),
                          rejected={r["product_id"]: r["reason_codes"] for r in rej})

        if not ranked:
            blockers = sorted({c for r in rej for c in r["reason_codes"]})
            return self._respond(Response("NO_ELIGIBLE", (
                f"I found {len(matches)} {query} but none meets all your requirements, so I'm not recommending any. "
                f"What ruled them out: {', '.join(blockers)}. You could raise the budget, allow a later delivery "
                "or relax another requirement."), rejected=rej, reason_codes=blockers))
        return self._respond(Response("RECOMMEND", self._explain(ranked, rej, len(eligible), it),
                                      recommendations=recs, rejected=rej))

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
                "stock": p.stock, "specs": p.specs, "url": f"/product/{p.product_id}",
                "checks": [c.to_dict() for c in e.checks] if e else []}

    def _explain(self, ranked: list[ProductView], rej: list[dict], n_eligible: int, it: Intent) -> str:
        """Template explanation built only from retrieved fields (no free-form model text)."""
        more = f" (showing the top {len(ranked)} of {n_eligible})" if n_eligible > len(ranked) else ""
        lines = [f"I found {n_eligible} option(s) that meet every requirement I could verify{more}:"]
        prefs = {b.lower() for b in it.preferred_brands}
        for i, p in enumerate(ranked, 1):
            facts = [f"{_inr(p.total_for())} total ({_inr(p.list_price_inr)} + {_inr(p.shipping_inr)} delivery)",
                     f"arrives in {p.delivery_days} days"]
            if "macOS" in it.required_compatibility:
                facts.append("listed as macOS compatible")
            if it.seats:
                facts.append(f"{p.specs.get('seats')} seats")
            if it.max_width_cm:
                facts.append(f"{p.specs.get('width_cm'):g} cm wide")
            if it.max_depth_cm:
                facts.append(f"{p.specs.get('depth_cm'):g} cm deep")
            if it.max_height_cm:
                facts.append(f"{p.specs.get('height_cm'):g} cm tall")
            if prefs and (p.brand or "").lower() in prefs:
                facts.append(f"your preferred brand ({p.brand})")
            lines.append(f"{i}. {p.title} [{p.product_id}]: " + ", ".join(facts) + ".")
        if prefs and not any((p.brand or "").lower() in prefs for p in ranked):
            lines.append(f"None of the eligible options are from {', '.join(it.preferred_brands)}; "
                         "these are the closest matches that meet your hard requirements.")
        if rej:
            lines.append(f"I left out {len(rej)} product(s) that failed or couldn't be verified against your "
                         "requirements (see details).")
        lines.append("Tell me which one you'd like, and I'll show you the exact cart total before anything is bought.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ product Q&A (rules R5, R6)
    def _answer(self, p: ProductView, it: Intent) -> Response:
        self._count_tool()
        with self.tracer.tool("answer_about_product", product_id=p.product_id, question=it.question) as t:
            result = qa.answer_about_product(p, it.question or "", it)
            t["summary"] = {"method": result.method, "status": result.status, "cited_fields": result.cited_fields}
        if result.status == "rejected":
            self.tracer.event("guardrail", "qa.answer_rejected", status="warn", product_id=p.product_id,
                              reason=result.meta.get("rejected"))
        return self._respond(Response("ANSWER", result.answer, cited_fields=result.cited_fields,
                                      product_id=p.product_id,
                                      reason_codes=["NOT_IN_LISTING"] if result.status == "not_in_listing" else []))

    # ------------------------------------------------------------------ cart / approval / checkout
    def select_product(self, product_id: str, qty: int = 1, from_product_page: bool = False) -> Response:
        """Propose a cart. From a recommendation list, only products just checked are allowed; from a product
        page ("buy this") the product itself is checked against the shopper's stated requirements."""
        if not from_product_page:
            self._tool_calls = 0
        self.tracer.event("user", "user.select", product_id=product_id, qty=qty, from_product_page=from_product_page)
        if not from_product_page and (self.intent is None or product_id not in self.eligible_ids):
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id,
                              reason="NOT_IN_ELIGIBLE_RECOMMENDATIONS")
            return self._respond(Response("BLOCKED", "I can only put a product in the cart if it's one of the "
                                          "eligible options I just checked.", reason_codes=["NOT_ELIGIBLE"]))
        if self.intent is None:
            self.intent = Intent(intent="BUY_THIS")
        p = self._get(product_id)
        if p is None:
            return self._respond(Response("BLOCKED", "I couldn't find that product.", reason_codes=["PRODUCT_NOT_FOUND"]))
        e = policy.evaluate(self.intent, p, qty)
        if not e.eligible:
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id, reasons=e.reason_codes)
            if from_product_page:
                return self._blocked_with_alternatives(p, e.reason_codes, f"I can't put {p.title} in the cart: "
                                                       f"it doesn't meet your requirements ({', '.join(e.reason_codes)}).")
            return self._respond(Response("BLOCKED", "That product no longer meets your requirements: "
                                          f"{', '.join(e.reason_codes)}.", reason_codes=e.reason_codes))
        if self.cart and self.cart.status == "PROPOSED":
            self.cart.status = "SUPERSEDED"
        self._invalidate_approval("new cart proposed")
        self.cart = new_cart(p, qty)
        self.approval = None
        self.tracer.event("cart", "cart.created", cart_id=self.cart.cart_id, product_id=p.product_id, qty=qty,
                          unit_price_inr=p.list_price_inr, shipping_inr=p.shipping_inr,
                          total_inr=self.cart.total_inr, data_version=p.version)
        return self._respond(Response("CART_PROPOSED", (
            f"Cart: {qty} x {p.title} [{p.product_id}]\n"
            f"Item {_inr(p.list_price_inr * qty)} + delivery {_inr(p.shipping_inr)} = **{_inr(self.cart.total_inr)} total** "
            f"(historical price; delivery simulated). Delivery in {p.delivery_days} days.\n"
            "Do you approve buying exactly this cart for this total? Nothing will be ordered without your approval."),
            cart=self.cart, product_id=p.product_id))

    def _blocked_with_alternatives(self, p: ProductView, reasons: list[str], lead: str) -> Response:
        alt = self._similar(p, cheaper=False)
        self.history.pop()          # merge the alternatives into a single blocked response
        tail = ("Here is what meets your requirements instead:\n" + alt.message) if alt.kind == "RECOMMEND" \
            else alt.message
        alt.message = lead + "\n\n" + tail
        alt.kind, alt.reason_codes, alt.cart = "BLOCKED", reasons, None
        return self._respond(alt)

    def approve(self) -> Response:
        self.tracer.event("user", "user.approve", cart_id=self.cart.cart_id if self.cart else None)
        if self.cart is None or self.cart.status != "PROPOSED":
            return self._respond(Response("BLOCKED", "There's no cart waiting for approval.",
                                          reason_codes=["NO_ACTIVE_CART"]))
        self.approval = new_approval(self.cart, self.intent.version)
        self.tracer.event("approval", "approval.granted", approval_id=self.approval.approval_id,
                          cart_id=self.cart.cart_id, approved_total_inr=self.approval.approved_total_inr,
                          data_version=self.approval.data_version, intent_version=self.approval.intent_version)
        return self._respond(Response("APPROVED", f"Approved: {_inr(self.approval.approved_total_inr)} for "
                                      f"{self.cart.title}. I'll check the latest price and stock again before "
                                      "placing the mock order.", cart=self.cart))

    def decline(self) -> Response:
        self.tracer.event("user", "user.decline", cart_id=self.cart.cart_id if self.cart else None)
        if self.cart:
            self.cart.status = "DECLINED"
        self._invalidate_approval("customer declined")
        return self._respond(Response("DECLINED", "Okay, I haven't ordered anything. Let me know if you'd like "
                                      "to look at other options.", cart=self.cart))

    def checkout(self) -> Response:
        """Revalidate against current data, then place at most one mock order."""
        self._tool_calls = 0
        if self.cart is None:
            return self._respond(Response("BLOCKED", "There's no cart to check out.", reason_codes=["NO_ACTIVE_CART"]))
        if self.cart.status == "ORDERED" and self.approval and self.approval.status == "USED":
            order, created = self.orders.place(self.cart, self.approval)
            self.tracer.event("checkout", "order.duplicate_suppressed", status="ok", order_id=order.order_id,
                              idempotency_key=order.idempotency_key)
            return self._respond(Response("ORDER_PLACED", f"This order was already placed: {order.order_id}. "
                                          "No second order was created.", cart=self.cart, order=order))

        current = self._get(self.cart.product_id)
        reasons = policy.checkout_gate(intent=self.intent, cart=self.cart, approval=self.approval, current=current)
        self.tracer.event("policy", "checkout.gate", status="block" if reasons else "pass",
                          cart_id=self.cart.cart_id,
                          approval_id=self.approval.approval_id if self.approval else None,
                          approved_total_inr=self.approval.approved_total_inr if self.approval else None,
                          current_total_inr=current.total_for(self.cart.qty) if current else None,
                          approved_version=self.approval.data_version if self.approval else None,
                          current_version=current.version if current else None, reason_codes=reasons)
        if reasons:
            return self._recover(reasons, current)

        order, created = self.orders.place(self.cart, self.approval)
        self.cart.status = "ORDERED"
        self.approval.status = "USED"
        self.tracer.event("checkout", "order.created" if created else "order.duplicate_suppressed",
                          order_id=order.order_id, idempotency_key=order.idempotency_key,
                          total_inr=order.total_inr, simulated=True)
        return self._respond(Response("ORDER_PLACED", (
            f"Mock order {order.order_id} placed for {self.cart.title}, {_inr(order.total_inr)} total. "
            "This is a simulation: no payment was taken and nothing will ship."), cart=self.cart, order=order))

    def _recover(self, reasons: list[str], current: Optional[ProductView]) -> Response:
        if "NO_VALID_APPROVAL" in reasons:
            return self._respond(Response("BLOCKED", "I can't place the order: you haven't approved this exact "
                                          "cart yet.", cart=self.cart, reason_codes=reasons))
        self._invalidate_approval(", ".join(reasons))
        old_total = self.approval.approved_total_inr if self.approval else self.cart.total_inr
        self.cart.status = "SUPERSEDED"
        parts = [f"I stopped the order. Something changed after you approved it ({', '.join(reasons)})."]
        if current is not None and current.total_for(self.cart.qty) != old_total:
            parts.append(f"{current.title} is now {_inr(current.total_for(self.cart.qty))} instead of the "
                         f"{_inr(old_total)} you approved.")
        if current is not None and current.stock < self.cart.qty:
            parts.append(f"{current.title} is now out of stock.")
        parts.append("Your earlier approval no longer applies.")
        if self.intent.product_query or self.intent.category:
            alt = self._search_and_recommend()
        else:                                   # bought straight from a product page: look for similar ones
            alt = self._search_and_recommend(query=_head_noun(current.title) if current else "")
        self.history.pop()
        alt.message = " ".join(parts) + "\n\n" + (
            "Here is what meets your requirements right now:\n" + alt.message if alt.kind == "RECOMMEND"
            else alt.message) + "\n\nPick an option and approve again if you'd like to continue."
        alt.kind = "BLOCKED"
        alt.reason_codes = reasons
        alt.cart = None
        return self._respond(alt)

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
