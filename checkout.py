"""Exact-cart approval and idempotent checkout. Orders are mock, or paid through Razorpay in TEST mode
(payments.py, PRD §13). No real money moves."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from catalog import ProductView


@dataclass
class Cart:
    cart_id: str
    product_id: str
    title: str
    qty: int
    unit_price_inr: int
    shipping_inr: int
    total_inr: int
    data_version: int
    status: str = "PROPOSED"   # PROPOSED | DECLINED | ORDERED | SUPERSEDED
    qty_confirmed: bool = False   # RZ8: a quantity above 1 must be confirmed before approval


@dataclass
class Approval:
    approval_id: str
    cart_id: str
    approved_total_inr: int
    data_version: int
    intent_version: int
    status: str = "APPROVED"   # APPROVED | INVALIDATED | USED
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


def new_cart(p: ProductView, qty: int = 1) -> Cart:
    return Cart(cart_id=f"cart_{uuid.uuid4().hex[:8]}", product_id=p.product_id, title=p.title, qty=qty,
                unit_price_inr=p.list_price_inr, shipping_inr=p.shipping_inr, total_inr=p.total_for(qty),
                data_version=p.version)


def new_approval(cart: Cart, intent_version: int) -> Approval:
    return Approval(approval_id=f"appr_{uuid.uuid4().hex[:8]}", cart_id=cart.cart_id,
                    approved_total_inr=cart.total_inr, data_version=cart.data_version,
                    intent_version=intent_version)


def idempotency_key(cart: Cart, approval: Approval) -> str:
    return hashlib.sha256(f"{cart.cart_id}|{approval.approval_id}|{cart.product_id}|{cart.qty}".encode()).hexdigest()[:24]


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
                          qty=cart.qty, total_inr=cart.total_inr, payment_id=payment_id, paid=payment_id is not None)
        self.orders[key] = order
        return order, True
