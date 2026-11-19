"""PRD §13: Razorpay test-mode checkout, evals RZ-01 to RZ-23 (approved by the PM 2026-11-19).
Razorpay is faked: no network, no real keys. The fake key and secret below are test doubles, not credentials."""
import hashlib
import hmac
import inspect
import json

import httpx
import pytest
from fastapi.testclient import TestClient

import agent as agent_mod
import payments
import server
from agent import Session

BED = "BDDEH29DNAN4AKYH"          # ₹24,999, free delivery, 21 in stock
FAKE_ID, FAKE_SECRET = "rzp_test_FAKEFAKEFAKE12", "fake_secret_for_tests_only"


def sign(order_id, payment_id, secret=FAKE_SECRET):
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


class FakeRazorpay:
    def __init__(self):
        self.created, self.fail_create, self.payments, self.status = [], 0, {}, None

    def request(self, method, url, json=None, auth=None, timeout=None):
        assert auth == (FAKE_ID, FAKE_SECRET)
        if self.status:
            return httpx.Response(self.status, json={"error": {}}, request=httpx.Request(method, url))
        if self.fail_create and method == "POST":
            self.fail_create -= 1
            raise httpx.ConnectTimeout("down")
        if method == "POST" and url.endswith("/orders"):
            order = {"id": f"order_FAKE{len(self.created) + 1}", "amount": json["amount"], "currency": json["currency"],
                     "receipt": json["receipt"]}
            self.created.append(order)
            return httpx.Response(200, json=order, request=httpx.Request(method, url))
        if method == "GET" and "/payments" in url:
            oid = url.split("/orders/")[1].split("/")[0]
            return httpx.Response(200, json={"items": self.payments.get(oid, [])}, request=httpx.Request(method, url))
        raise AssertionError(f"unexpected call {method} {url}")


@pytest.fixture
def rzp(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", FAKE_ID)
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", FAKE_SECRET)
    monkeypatch.setattr(payments.time, "sleep", lambda s: None)
    payments._state.update(failures=0, paused_until=0.0)
    fake = FakeRazorpay()
    monkeypatch.setattr(httpx, "request", fake.request)
    yield fake
    payments._state.update(failures=0, paused_until=0.0)


def approved_session(qty=1):
    s = Session()
    if qty > 1:                      # B47: adding the same product again adds to it, so start with the quantity
        s.select_product(BED, qty=qty, from_product_page=True)
        s.confirm_quantity()
    else:
        s.handle_message("buy this", {"page": "product", "product_id": BED})
    assert s.approve().kind == "APPROVED"
    return s


def test_rz01_order_created_for_the_approved_total_after_the_recheck(rzp):
    s = approved_session()
    kind, opts = s.start_payment()
    assert kind == "checkout" and len(rzp.created) == 1
    o = rzp.created[0]
    assert o["amount"] == 24999 * 100 and o["currency"] == "INR" and o["receipt"] == s.approval.approval_id
    assert opts["key"] == FAKE_ID and opts["order_id"] == o["id"] and opts["amount"] == 2499900
    names = [e["name"] for e in s.tracer.events]
    assert names.index("checkout.gate") < names.index("payment.order_created")


def test_rz02_price_changed_after_approval_creates_no_order(rzp):
    s = approved_session()
    s.simulate_price_change(BED, 26000)
    kind, r = s.start_payment()
    assert kind == "reply" and r.kind == "BLOCKED" and "haven't ordered" in r.message and not rzp.created


def test_rz03_browser_cannot_set_the_amount(rzp):
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "buy this", "context": {"page": "product", "product_id": BED}})
    c.post("/api/agent/approve")
    out = c.post("/api/pay/start", json={"amount": 100}).json()
    assert out["checkout"]["amount"] == 2499900 and rzp.created[0]["amount"] == 2499900


def test_rz04_valid_signature_places_one_paid_order(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    r = s.confirm_payment(opts["order_id"], "pay_FAKE1", sign(opts["order_id"], "pay_FAKE1"))
    assert r.kind == "ORDER_PLACED" and "test mode" in r.message
    orders = list(s.orders.orders.values())
    assert len(orders) == 1 and orders[0].paid and orders[0].payment_id == "pay_FAKE1"


def test_rz05_wrong_signature_places_nothing(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    r = s.confirm_payment(opts["order_id"], "pay_FAKE1", "0" * 64)
    assert r.kind == "BLOCKED" and "couldn't confirm" in r.message and not s.orders.orders
    assert s.tracer.find(name="payment.verification_failed")


def test_rz06_signature_for_another_order_places_nothing(rzp):
    s = approved_session()
    s.start_payment()
    r = s.confirm_payment("order_SOMEONE_ELSE", "pay_X", sign("order_SOMEONE_ELSE", "pay_X"))
    assert r.kind == "BLOCKED" and not s.orders.orders


def test_rz07_success_twice_is_still_one_order(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    sig = sign(opts["order_id"], "pay_FAKE1")
    s.confirm_payment(opts["order_id"], "pay_FAKE1", sig)
    r = s.confirm_payment(opts["order_id"], "pay_FAKE1", sig)
    assert len(s.orders.orders) == 1 and "didn't create a second" in r.message


def test_rz08_closed_or_failed_payment_orders_nothing_and_reuses_the_order(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    r = s.payment_not_completed(failed=False)
    assert "nothing was charged or ordered" in r.message and not s.orders.orders
    r = s.payment_not_completed(failed=True, reason="card_declined")
    assert "didn't go through" in r.message and s.approval.status == "APPROVED"
    _, again = s.start_payment()
    assert again["order_id"] == opts["order_id"] and len(rzp.created) == 1


@pytest.mark.parametrize("msg", ["pay for me", "initiate the payment", "go ahead and charge my card",
                                 "complete the purchase", "just pay", "place the order for me"])
def test_rz09_chat_cannot_start_a_payment(rzp, msg):
    s = approved_session()
    r = s.handle_message(msg, {"page": "product", "product_id": BED})
    assert "only you can do" in r.message and "Pay button" in r.message
    assert not rzp.created and not s.orders.orders


def test_rz09b_the_agent_has_no_path_to_the_payment_api():
    src = inspect.getsource(agent_mod.Session.handle_message)
    assert "start_payment" not in src and "create_order" not in src and "confirm_payment" not in src
    called_from = [n for n, f in inspect.getmembers(agent_mod.Session, inspect.isfunction)
                   if "payments.create_order" in inspect.getsource(f)]
    assert called_from == ["start_payment"]          # reached only through the /api/pay/start route


def test_rz10_secret_never_reaches_the_browser(rzp):
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "buy this", "context": {"page": "product", "product_id": BED}})
    c.post("/api/agent/approve")
    texts = [c.post("/api/pay/start").text, c.get("/api/agent/state").text, c.get("/api/meta").text,
             c.get("/").text, c.get("/static/agent.js").text, c.get("/api/trace").text]
    assert not any(FAKE_SECRET in t for t in texts)


def test_rz11_traces_redact_signatures(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    sig = sign(opts["order_id"], "pay_FAKE1")
    s.confirm_payment(opts["order_id"], "pay_FAKE1", sig)
    s.tracer.event("payment", "probe", razorpay_signature=sig)
    assert sig not in json.dumps(s.tracer.events)


def test_rz12_live_key_is_refused(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_SOMETHING")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "x")
    assert payments.mode() == "refused_live" and not payments.enabled()


def test_rz13_without_keys_the_mock_flow_is_unchanged(monkeypatch):
    monkeypatch.delenv("RAZORPAY_KEY_ID", raising=False)
    monkeypatch.delenv("RAZORPAY_KEY_SECRET", raising=False)
    s = approved_session()
    kind, r = s.start_payment()
    assert kind == "reply" and r.kind == "ORDER_PLACED" and "no payment was taken" in r.message


def test_rz14_razorpay_down_retries_once_then_says_so(rzp):
    s = approved_session()
    rzp.fail_create = 2
    kind, r = s.start_payment()
    assert kind == "reply" and "payments aren't working right now" in r.message and "cart is saved" in r.message
    assert not s.orders.orders and s.approval.status == "APPROVED" and rzp.fail_create == 0


def test_rz14b_rate_limits_pause_the_pay_button(rzp):
    s = approved_session()
    rzp.status = 429
    for _ in range(3):
        kind, r = s.start_payment()
        assert "payments aren't working" in r.message
    assert payments.paused()
    c = TestClient(server.app)
    assert c.get("/api/agent/state").json()["payments_paused"] is True


def test_rz14c_paid_but_unconfirmed_is_found_without_a_second_payment(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    rzp.payments[opts["order_id"]] = [{"id": "pay_LOST", "status": "captured", "order_id": opts["order_id"]}]
    kind, r = s.start_payment()                     # the shopper taps Pay again
    assert kind == "reply" and r.kind == "ORDER_PLACED" and len(rzp.created) == 1
    assert list(s.orders.orders.values())[0].payment_id == "pay_LOST"


def test_rz15_trace_shows_the_payment_chain(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    s.confirm_payment(opts["order_id"], "pay_FAKE1", sign(opts["order_id"], "pay_FAKE1"))
    names = [e["name"] for e in s.tracer.events]
    chain = ["payment.order_created", "payment.window_opened", "payment.verified", "order.created"]
    assert [n for n in names if n in chain] == chain


def test_rz20_quantity_above_one_needs_confirmation(rzp):
    s = Session()
    r = s.select_product(BED, qty=2, from_product_page=True)
    assert "**2**" in r.message and "Is 2 right?" in r.message
    r = s.approve()
    assert r.kind == "CLARIFY" and s.approval is None
    s.confirm_quantity()
    assert s.approve().kind == "APPROVED" and s.approval.approved_total_inr == 2 * 24999


def test_rz21_change_to_one(rzp):
    s = Session()
    s.select_product(BED, qty=2, from_product_page=True)
    r = s.set_quantity_one()
    assert s.cart.qty == 1 and s.cart.total_inr == 24999 and s.approve().kind == "APPROVED"


def test_rz22_quantity_one_asks_nothing_extra(rzp):
    s = Session()
    r = s.handle_message("buy this", {"page": "product", "product_id": BED})
    assert "Is 1 right" not in r.message and s.approve().kind == "APPROVED"


def test_rz23_cards_only_and_prefilled_demo_details(rzp):
    s = approved_session()
    _, opts = s.start_payment()
    d = opts["config"]["display"]
    assert d["sequence"] == ["block.cards_only"] and d["preferences"]["show_default_blocks"] is False
    assert d["blocks"]["cards_only"]["instruments"] == [{"method": "card"}]
    assert opts["prefill"]["email"].endswith("@example.com") and opts["prefill"]["contact"]


def test_checkout_route_cannot_skip_payment_when_razorpay_is_on(rzp):
    s = approved_session()
    r = s.checkout()
    assert r.kind == "BLOCKED" and "Tap **Pay**" in r.message and not s.orders.orders
