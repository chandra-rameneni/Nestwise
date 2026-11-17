"""IntentGuard session: intent routing, bounded tool use, grounded recommendations, approval and checkout.

The flow is code-driven (a workflow, not a free-running model loop). The model is used only to
interpret language; every eligibility, approval and checkout decision is deterministic code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import intent as intent_mod
import policy
from catalog import Catalog, ProductView
from checkout import Approval, Cart, MockOrder, MockOrderService, new_approval, new_cart
from intent import Intent
from tracing import Tracer

MAX_TOOL_CALLS_PER_TURN = 40
MAX_RECOMMENDATIONS = 3

_ASK = {
    "product": "What product are you looking for?",
    "budget": "What is the most you want to pay in total, including delivery (in ₹)?",
    "seats": "How many seats do you need?",
    "max_width_cm": "How much wall space is there for it? Please give the maximum width in cm.",
}


@dataclass
class Response:
    kind: str                     # CLARIFY | RECOMMEND | NO_ELIGIBLE | NOT_IN_CATALOG | DEFER | UNSUPPORTED
                                  # | CART_PROPOSED | APPROVED | DECLINED | ORDER_PLACED | BLOCKED | ERROR
    message: str
    recommendations: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    cart: Optional[Cart] = None
    order: Optional[MockOrder] = None
    reason_codes: list[str] = field(default_factory=list)


def _inr(n: int) -> str:
    return f"₹{n:,}"


class Session:
    def __init__(self, catalog: Optional[Catalog] = None, tracer: Optional[Tracer] = None,
                 orders: Optional[MockOrderService] = None):
        self.catalog = catalog or Catalog()
        self.tracer = tracer or Tracer()
        self.orders = orders or MockOrderService()
        self.intent: Optional[Intent] = None
        self.eligible_ids: list[str] = []
        self.cart: Optional[Cart] = None
        self.approval: Optional[Approval] = None
        self.history: list[tuple[str, str]] = []
        self._tool_calls = 0
        self.tracer.event("session", "session.start", catalog_version=self.catalog.meta["version"],
                          llm_configured=intent_mod.llm_available())

    # ------------------------------------------------------------------ helpers
    def _respond(self, r: Response) -> Response:
        self.history.append(("assistant", r.message))
        self.tracer.event("agent", "agent.response", response_kind=r.kind, reason_codes=r.reason_codes,
                          recommended_ids=[x["product_id"] for x in r.recommendations],
                          cart_id=r.cart.cart_id if r.cart else None,
                          order_id=r.order.order_id if r.order else None)
        return r

    def _get(self, pid: str) -> Optional[ProductView]:
        self._tool_calls += 1
        if self._tool_calls > MAX_TOOL_CALLS_PER_TURN:
            raise RuntimeError("tool-call limit reached for this turn")
        with self.tracer.tool("get_product", product_id=pid) as t:
            p = self.catalog.get(pid)
            t["summary"] = None if p is None else {"version": p.version, "price": p.list_price_inr,
                                                   "shipping": p.shipping_inr, "stock": p.stock}
        if p is not None and p.injection_flag:
            self.tracer.event("guardrail", "untrusted_text_flagged", status="warn", product_id=pid,
                              note="Instruction-like text in product description; treated as data, not instructions.")
        return p

    def _invalidate_approval(self, reason: str) -> None:
        if self.approval and self.approval.status == "APPROVED":
            self.approval.status = "INVALIDATED"
            self.approval.invalidated_reason = reason
            self.tracer.event("approval", "approval.invalidated", status="warn",
                              approval_id=self.approval.approval_id, reason=reason)

    # ------------------------------------------------------------------ user message
    def handle_message(self, text: str) -> Response:
        self._tool_calls = 0
        self.history.append(("user", text))
        self.tracer.event("user", "user.message", text=text)

        new_intent, changed, meta = intent_mod.extract(text, self.intent)
        self.tracer.event("model" if new_intent.extractor.startswith("llm") else "rules", "intent.extracted",
                          status="ok" if "error" not in meta else "warn", extractor=new_intent.extractor,
                          intent=new_intent.intent, constraints=new_intent.constraint_fields(),
                          missing_info=new_intent.missing_info, changed_fields=changed,
                          intent_version=new_intent.version, **meta)

        if new_intent.intent == "REFUND_REQUEST":
            return self._respond(Response("DEFER", (
                "I can see you'd like a refund. Refunds aren't available in this demo yet. A real refund needs "
                "you to sign in so I can find your own order and check the merchant's return policy. "
                "Nothing has been refunded or changed."), reason_codes=["WORKFLOW_NOT_AVAILABLE_P0"]))
        if new_intent.intent == "ORDER_TRACKING":
            return self._respond(Response("DEFER", (
                "I can see you want to track an order. Order tracking isn't available in this demo yet; it would "
                "need you to sign in so only your own orders are looked up. No order data was accessed."),
                reason_codes=["WORKFLOW_NOT_AVAILABLE_P0"]))
        if new_intent.intent == "UNSUPPORTED":
            return self._respond(Response("UNSUPPORTED",
                                          "I can help you find, compare and buy products from this demo catalog. "
                                          "What are you shopping for?"))

        if changed and self.intent is not None:
            self._invalidate_approval(f"constraints changed: {', '.join(changed)}")
            if self.cart and self.cart.status == "PROPOSED":
                self.cart.status = "SUPERSEDED"
        self.intent = new_intent

        if new_intent.missing_info:
            questions = [_ASK.get(m, f"Could you tell me the {m}?") for m in new_intent.missing_info]
            self.tracer.event("agent", "clarify", missing_info=new_intent.missing_info)
            return self._respond(Response("CLARIFY", " ".join(questions)))

        return self._search_and_recommend()

    # ------------------------------------------------------------------ discovery
    def _search_and_recommend(self, exclude: tuple[str, ...] = ()) -> Response:
        it = self.intent
        keywords = None if it.category else (it.product_query or "").split()[-1:]
        with self.tracer.tool("search_catalog", category=it.category, keywords=keywords) as t:
            ids = self.catalog.search(it.category, keywords)
            t["summary"] = {"count": len(ids), "product_ids": ids}
        if not ids:
            return self._respond(Response("NOT_IN_CATALOG", (
                f"I couldn't find any {it.product_query or it.category} in this demo catalog, so I won't "
                "suggest anything. The catalog currently covers keyboard-and-mouse combos and sofas."),
                reason_codes=["NO_CATALOG_MATCH"]))

        eligible, rejected = [], []
        for pid in ids:
            if pid in exclude:
                continue
            p = self._get(pid)
            if p is None:
                continue
            e = policy.evaluate(it, p)
            self.tracer.event("policy", "policy.eligibility", status="pass" if e.eligible else "fail",
                              product_id=pid, total_inr=e.total_inr, eligible=e.eligible,
                              checks=[c.to_dict() for c in e.checks])
            (eligible if e.eligible else rejected).append((p, e))

        ranked = policy.rank(it, [p for p, _ in eligible])[:MAX_RECOMMENDATIONS]
        self.eligible_ids = [p.product_id for p in ranked]
        recs = [self._rec_dict(p) for p in ranked]
        rej = [{"product_id": p.product_id, "title": p.title, "total_inr": e.total_inr,
                "reason_codes": e.reason_codes} for p, e in rejected]
        self.tracer.event("agent", "recommendation", eligible_ids=self.eligible_ids,
                          rejected={r["product_id"]: r["reason_codes"] for r in rej})

        if not ranked:
            blockers = sorted({c for r in rej for c in r["reason_codes"]})
            return self._respond(Response("NO_ELIGIBLE", (
                "None of the matching products meet all your requirements, so I'm not recommending any. "
                f"What blocked them: {', '.join(blockers)}. You could raise the budget, allow a later delivery "
                "or relax another requirement."), rejected=rej, reason_codes=blockers))

        return self._respond(Response("RECOMMEND", self._explain(ranked, rej), recommendations=recs, rejected=rej))

    def _rec_dict(self, p: ProductView) -> dict:
        return {"product_id": p.product_id, "title": p.title, "brand": p.brand, "list_price_inr": p.list_price_inr,
                "shipping_inr": p.shipping_inr, "total_inr": p.total_for(), "delivery_days": p.delivery_days,
                "stock": p.stock, "specs": p.specs}

    def _explain(self, ranked: list[ProductView], rej: list[dict]) -> str:
        """Template explanation built only from retrieved fields (no free-form model text)."""
        it = self.intent
        lines = [f"I found {len(ranked)} option(s) that meet every requirement I could verify:"]
        prefs = {b.lower() for b in it.preferred_brands}
        for i, p in enumerate(ranked, 1):
            facts = [f"{_inr(p.total_for())} total ({_inr(p.list_price_inr)} + {_inr(p.shipping_inr)} delivery)",
                     f"arrives in {p.delivery_days} days"]
            if "macOS" in it.required_compatibility:
                facts.append("listed as macOS compatible")
            if it.seats:
                facts.append(f"{p.specs.get('seats')} seats")
            if it.max_width_cm:
                facts.append(f"{p.specs.get('width_cm')} cm wide")
            if prefs and p.brand.lower() in prefs:
                facts.append(f"your preferred brand ({p.brand})")
            lines.append(f"{i}. {p.title} [{p.product_id}]: " + ", ".join(facts) + ".")
        if prefs and not any(p.brand.lower() in prefs for p in ranked):
            lines.append(f"None of the eligible options are from {', '.join(it.preferred_brands)}; "
                         "these are the closest matches that meet your hard requirements.")
        if rej:
            lines.append(f"I left out {len(rej)} product(s) that failed or couldn't be verified against your "
                         "requirements (see details).")
        lines.append("Tell me which one you'd like, and I'll show you the exact cart total before anything is bought.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ cart / approval / checkout
    def select_product(self, product_id: str, qty: int = 1) -> Response:
        self._tool_calls = 0
        self.tracer.event("user", "user.select", product_id=product_id, qty=qty)
        if self.intent is None or product_id not in self.eligible_ids:
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id,
                              reason="NOT_IN_ELIGIBLE_RECOMMENDATIONS")
            return self._respond(Response("BLOCKED", "I can only put a product in the cart if it's one of the "
                                          "eligible options I just checked.", reason_codes=["NOT_ELIGIBLE"]))
        p = self._get(product_id)
        e = policy.evaluate(self.intent, p, qty)
        if not e.eligible:
            self.tracer.event("policy", "cart.denied", status="block", product_id=product_id, reasons=e.reason_codes)
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
            f"(simulated prices). Delivery in {p.delivery_days} days.\n"
            "Do you approve buying exactly this cart for this total? Nothing will be ordered without your approval."),
            cart=self.cart))

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
        # Replay of an already-completed checkout: return the same order (idempotent).
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
        alt = self._search_and_recommend()
        # _search_and_recommend already logged its own response; merge it into one recovery message.
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
