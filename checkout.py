"""Exact-cart approval and idempotent checkout. Orders are mock, or paid through Razorpay in TEST mode
(payments.py, PRD §13). No real money moves."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from catalog import ProductView


MAX_LINES = 10          # B47: a cart holds up to 10 different products (demo simplicity)
MAX_QTY_PER_LINE = 5    # store policy P6


@dataclass
class CartLine:
    """One product in the cart (PRD B47). `checked_with` is the requirement set this product was checked against
    when added (a search's budget, size...), so the re-check before payment uses the same rules for this line."""
    product_id: str
    title: str
    qty: int
    unit_price_inr: int
    shipping_inr: int
    data_version: int
    qty_confirmed: bool = False      # RZ8: a quantity above 1 must be confirmed before approval
    returnable: bool = True
    checked_with: object = None      # intent.Intent or None (bought straight from a product page)

    @property
    def total_inr(self) -> int:
        return self.unit_price_inr * self.qty + self.shipping_inr


@dataclass
class Cart:
    cart_id: str
    lines: list
    status: str = "PROPOSED"   # PROPOSED | DECLINED | ORDERED | SUPERSEDED

    # Single-product views, kept so older code and tests read a one-line cart exactly as before.
    @property
    def product_id(self) -> str:
        return self.lines[0].product_id

    @property
    def title(self) -> str:
        names = [ln.title for ln in self.lines]
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + " and " + names[-1]

    @property
    def qty(self) -> int:
        return self.lines[0].qty if len(self.lines) == 1 else sum(ln.qty for ln in self.lines)

    @property
    def unit_price_inr(self) -> int:
        return self.lines[0].unit_price_inr

    @property
    def shipping_inr(self) -> int:
        return sum(ln.shipping_inr for ln in self.lines)

    @property
    def data_version(self) -> int:
        return self.lines[0].data_version

    @property
    def total_inr(self) -> int:
        return sum(ln.total_inr for ln in self.lines)

    @property
    def qty_confirmed(self) -> bool:
        return all(ln.qty == 1 or ln.qty_confirmed for ln in self.lines)

    def line(self, product_id: str):
        return next((ln for ln in self.lines if ln.product_id == product_id), None)


@dataclass
class Approval:
    approval_id: str
    cart_id: str
    approved_total_inr: int
    data_version: int
    intent_version: int
    status: str = "APPROVED"   # APPROVED | INVALIDATED | USED
    line_versions: dict = field(default_factory=dict)   # product_id -> data version approved (B47)
    line_totals: dict = field(default_factory=dict)     # product_id -> line total approved
    invalidated_reason: str | None = None


@dataclass
class MockOrder:
    order_id: str
    idempotency_key: str
    cart_id: str
    approval_id: str
    product_id: str
    qty: int
    total_inr: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    simulated: bool = True
    payment_id: str | None = None      # Razorpay test-mode payment ID when paid (PRD §13)
    paid: bool = False
    lines: list = field(default_factory=list)   # [(product_id, title, qty, line_total)] (B47)


def new_line(p: ProductView, qty: int = 1, checked_with=None) -> CartLine:
    return CartLine(product_id=p.product_id, title=p.title, qty=qty, unit_price_inr=p.list_price_inr,
                    shipping_inr=p.shipping_inr, data_version=p.version,
                    returnable=getattr(p, "returnable", True), checked_with=checked_with)


def new_cart(p: ProductView, qty: int = 1, checked_with=None) -> Cart:
    return Cart(cart_id=f"cart_{uuid.uuid4().hex[:8]}", lines=[new_line(p, qty, checked_with)])


def new_approval(cart: Cart, intent_version: int) -> Approval:
    return Approval(approval_id=f"appr_{uuid.uuid4().hex[:8]}", cart_id=cart.cart_id,
                    approved_total_inr=cart.total_inr, data_version=cart.data_version,
                    intent_version=intent_version,
                    line_versions={ln.product_id: ln.data_version for ln in cart.lines},
                    line_totals={ln.product_id: ln.total_inr for ln in cart.lines})


def idempotency_key(cart: Cart, approval: Approval) -> str:
    lines = ";".join(f"{ln.product_id}x{ln.qty}" for ln in cart.lines)
    return hashlib.sha256(f"{cart.cart_id}|{approval.approval_id}|{lines}".encode()).hexdigest()[:24]


class MockOrderService:
    """Creates at most one mock order per idempotency key. Must only be called after policy.checkout_gate passes."""

    def __init__(self):
        self.orders: dict[str, MockOrder] = {}

    def place(self, cart: Cart, approval: Approval, payment_id: str | None = None) -> tuple[MockOrder, bool]:
        """Returns (order, created). created=False means an identical earlier request was replayed."""
        key = idempotency_key(cart, approval)
        if key in self.orders:
            return self.orders[key], False
        order = MockOrder(order_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}", idempotency_key=key,
                          cart_id=cart.cart_id, approval_id=approval.approval_id, product_id=cart.product_id,
                          qty=cart.qty, total_inr=cart.total_inr, payment_id=payment_id, paid=payment_id is not None,
                          lines=[(ln.product_id, ln.title, ln.qty, ln.total_inr) for ln in cart.lines])
        self.orders[key] = order
        return order, True
