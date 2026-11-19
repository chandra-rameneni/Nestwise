"""Razorpay payments in TEST mode (PRD §13, approved by the PM 2026-11-19).

Who does what (rule RZ1): the agent never calls anything here. Only the server's Pay routes do, and only after the
shopper's own click. The amount always comes from the approved cart (RZ2). An order is placed only after the
signature check passes (RZ3). Test keys only (RZ6); without keys the store keeps its mock orders (RZ7).

Keys come from the environment only: RAZORPAY_KEY_ID (sent to the browser; it's semi-public) and
RAZORPAY_KEY_SECRET (server only; never logged, never returned). Docs checked 2026-11-19: Orders API
POST /v1/orders (amount in paise), signature = HMAC-SHA256(order_id + "|" + payment_id, secret),
payments for an order: GET /v1/orders/{id}/payments.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

import httpx

API = "https://api.razorpay.com/v1"
TIMEOUT_S = 10
PAUSE_AFTER_FAILURES = 3         # RZ9: consecutive failures before the Pay button pauses
PAUSE_S = float(os.environ.get("INTENTGUARD_PAY_PAUSE_S", "180"))
_state = {"failures": 0, "paused_until": 0.0}


class PaymentUnavailable(Exception):
    """Razorpay is down, slow, or refusing requests (5xx, 429, timeout, network). Nothing was charged."""


def key_id() -> Optional[str]:
    return os.environ.get("RAZORPAY_KEY_ID") or None


def _secret() -> Optional[str]:
    return os.environ.get("RAZORPAY_KEY_SECRET") or None


def mode() -> str:
    """'razorpay_test', 'mock' (no keys), or 'refused_live' (a live key: payments stay off, RZ6)."""
    k, s = key_id(), _secret()
    if not k or not s:
        return "mock"
    if not k.startswith("rzp_test_"):
        return "refused_live"
    return "razorpay_test"


def enabled() -> bool:
    return mode() == "razorpay_test"


def paused() -> bool:
    return _state["paused_until"] > time.monotonic()


def _ok() -> None:
    _state["failures"] = 0


def _fail() -> None:
    _state["failures"] += 1
    if _state["failures"] >= PAUSE_AFTER_FAILURES:
        _state["paused_until"] = time.monotonic() + PAUSE_S
        _state["failures"] = 0


def _request(method: str, path: str, json: Optional[dict] = None) -> dict:
    try:
        r = httpx.request(method, f"{API}{path}", json=json, auth=(key_id(), _secret()), timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise PaymentUnavailable(type(exc).__name__) from None
    if r.status_code == 429 or r.status_code >= 500:
        raise PaymentUnavailable(f"HTTP {r.status_code}")
    if r.status_code >= 400:
        # A 4xx other than 429 is our mistake or a bad key; treat it as unavailable but say why in the trace.
        raise PaymentUnavailable(f"HTTP {r.status_code}: {r.text[:120]}")
    return r.json()


def create_order(amount_inr: int, receipt: str, notes: dict) -> dict:
    """RZ2 + RZ9: create a Razorpay order for the approved amount; one retry after a short wait."""
    if paused():
        raise PaymentUnavailable("paused after repeated failures")
    body = {"amount": int(amount_inr) * 100, "currency": "INR", "receipt": receipt[:40], "notes": notes}
    for attempt in (1, 2):
        try:
            out = _request("POST", "/orders", body)
            _ok()
            return out
        except PaymentUnavailable:
            if attempt == 2:
                _fail()
                raise
            time.sleep(1)
    raise PaymentUnavailable("unreachable")


def paid_payment(order_id: str) -> Optional[str]:
    """RZ10: has this Razorpay order already been paid? Returns the payment ID if so. Raises if Razorpay is down."""
    out = _request("GET", f"/orders/{order_id}/payments")
    for p in out.get("items", []):
        if p.get("status") in ("captured", "authorized") and p.get("order_id", order_id) == order_id:
            return p.get("id")
    return None


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """RZ3: the signature must be HMAC-SHA256(order_id|payment_id) with our secret. order_id is OUR stored one."""
    secret = _secret()
    if not secret or not (order_id and payment_id and signature):
        return False
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def checkout_options(order: dict, title: str) -> dict:
    """What the browser needs to open Razorpay Checkout. Contains the Key ID, never the secret (RZ5).
    Cards only, and phone/email pre-filled with fake demo values the shopper can edit (PM decisions)."""
    return {
        "key": key_id(), "order_id": order["id"], "amount": order["amount"], "currency": order.get("currency", "INR"),
        "name": "Nestwise (test mode)", "description": title[:250],
        "prefill": {"name": os.environ.get("INTENTGUARD_DEMO_NAME", "Demo Shopper"),
                    "email": os.environ.get("INTENTGUARD_DEMO_EMAIL", "demo.shopper@example.com"),
                    "contact": os.environ.get("INTENTGUARD_DEMO_CONTACT", "+919000090000")},
        "config": {"display": {"blocks": {"cards_only": {"name": "Pay by card", "instruments": [{"method": "card"}]}},
                               "sequence": ["block.cards_only"], "preferences": {"show_default_blocks": False}}},
        "theme": {"color": "#2a6fe8"},
    }
