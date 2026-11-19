"""PRD B26 (quantity, O-57) and B47 (several products in one cart, O-58), approved by the PM 2026-11-19.
Evals Q-01 to Q-14 and M-01 to M-13. Rules mode, plus a fake Razorpay for the payment checks."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import intent as I
import server
from agent import Session
from tests.test_razorpay import FakeRazorpay, sign, rzp  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
BED, BAG, BIRD = "BDDEH29DNAN4AKYH", "BEAEDH4VFQJ5GDAZ", "BRHEDG33DZHYZGZG"


@pytest.fixture(autouse=True)
def rules_mode(monkeypatch):
    monkeypatch.setattr(I, "llm_available", lambda: False)


def page(pid):
    return {"page": "product", "product_id": pid}


def bag_pid():
    from catalog import SqliteCatalog
    c = SqliteCatalog()
    row = c._con.execute("SELECT pid FROM products WHERE name LIKE 'ABCD XL Bean Bag%' LIMIT 1").fetchone()
    return row[0]


# ---------------------------------------------------------------- B26: quantity
def test_q01_q02_cart_buttons_change_quantity_and_stop_at_the_limit():
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "buy this", "context": page(BED)})
    out = c.post("/api/cart/qty", json={"product_id": BED, "qty": 2}).json()
    ln = out["state"]["cart"]["lines"][0]
    assert ln["qty"] == 2 and ln["total_inr"] == 2 * 24999 and ln["max_qty"] == 5
    js = (ROOT / "web" / "agent.js").read_text()
    assert 'data-qty="${esc(ln.qty + 1)}"' in js and "ln.qty >= ln.max_qty" in js      # "+" disabled at the limit


def test_q03_changed_quantity_cancels_the_approval():
    s = Session()
    s.handle_message("buy this", page(BED))
    s.approve()
    s.set_line_quantity(BED, 2)
    assert s.approval is None and s.approve().kind == "CLARIFY"           # RZ8 again for the new quantity


@pytest.mark.parametrize("msg,qty", [("I want 2 of these", 2), ("add 2 to cart", 2), ("buy two", 2),
                                     ("2 please", 2), ("change the quantity to 3", 3)])
def test_q04_q08_quantity_phrases_on_a_product_page(msg, qty):
    s = Session()
    r = s.handle_message(msg, page(BED))
    assert s.cart is not None and s.cart.line(BED).qty == qty, (msg, r.message)


def test_q09_make_it_2_with_a_cart():
    s = Session()
    s.handle_message("buy this", page(BED))
    r = s.handle_message("make it 2", {"page": "listing"})
    assert s.cart.line(BED).qty == 2 and "Is 2 right?" in r.message


def test_q10_make_it_2_is_never_a_2_rupee_budget():
    s = Session()
    s.handle_message("buy this", page(BED))
    r = s.handle_message("make it 2", page(BED))
    assert "No on price" not in r.message and (s.intent is None or s.intent.max_total_inr != 2)


def test_q11_add_2_to_cart_is_never_a_product_search():
    s = Session()
    r = s.handle_message("add 2 to cart", page(BED))
    assert r.kind == "CART_PROPOSED" and "add cart" not in r.message.lower()


def test_q12_over_the_limit_offers_the_limit():
    s = Session()
    s.handle_message("buy this", page(BED))
    r = s.handle_message("buy 10 of these", page(BED))
    assert "up to 5" in r.message and "Shall I make it 5?" in r.message and s.cart.line(BED).qty == 1
    s.handle_message("yes", page(BED))
    assert s.cart.line(BED).qty == 5


def test_q13_two_of_a_product_through_payment(rzp):  # noqa: F811
    s = Session()
    s.handle_message("I want 2 of these", page(BED))
    s.confirm_quantity()
    assert s.approve().kind == "APPROVED"
    _, opts = s.start_payment()
    assert rzp.created[0]["amount"] == 2 * 24999 * 100
    r = s.confirm_payment(opts["order_id"], "pay_Q", sign(opts["order_id"], "pay_Q"))
    assert r.kind == "ORDER_PLACED" and list(s.orders.orders.values())[0].qty == 2


# ---------------------------------------------------------------- B47: several products
def cart_with_bed_and_bag():
    s = Session()
    s.handle_message("buy this", page(BED))
    r = s.handle_message("buy this", page(bag_pid()))
    return s, r


def test_m01_second_product_is_added_not_replaced():
    s, r = cart_with_bed_and_bag()
    assert [ln.product_id for ln in s.cart.lines] == [BED, bag_pid()]
    assert s.cart.total_inr == 24999 + 1149 + 499 and "2 items" in r.message and "Added" in r.message


def test_m02_same_product_again_raises_its_quantity():
    s = Session()
    s.handle_message("buy this", page(BED))
    s.handle_message("buy this", page(BED))
    assert len(s.cart.lines) == 1 and s.cart.line(BED).qty == 2


def test_m03_remove_a_line():
    s, _ = cart_with_bed_and_bag()
    s.confirm_quantity()
    s.approve()
    r = s.handle_message("remove the bean bag from my cart", {"page": "listing"})
    assert [ln.product_id for ln in s.cart.lines] == [BED] and s.approval is None and "24,999" in r.message


def test_m04_whats_in_my_cart():
    s, _ = cart_with_bed_and_bag()
    r = s.handle_message("what's in my cart?", {"page": "listing"})
    assert "Queen Bed" in r.message and "Bean Bag" in r.message and "26,647" in r.message


def test_m05_one_payment_for_the_grand_total(rzp):  # noqa: F811
    s, _ = cart_with_bed_and_bag()
    s.approve()
    _, opts = s.start_payment()
    assert len(rzp.created) == 1 and rzp.created[0]["amount"] == (24999 + 1149 + 499) * 100
    r = s.confirm_payment(opts["order_id"], "pay_M", sign(opts["order_id"], "pay_M"))
    order = list(s.orders.orders.values())[0]
    assert r.kind == "ORDER_PLACED" and len(order.lines) == 2 and order.paid


def test_m06_one_items_price_change_stops_and_names_it(rzp):  # noqa: F811
    s, _ = cart_with_bed_and_bag()
    s.approve()
    s.simulate_price_change(bag_pid(), 1299)
    kind, r = s.start_payment()
    assert kind == "reply" and r.kind == "BLOCKED" and "bean bag" in r.message.lower() and "1,299" in r.message
    assert "haven't charged" in r.message and not rzp.created and len(s.cart.lines) == 2
    assert s.approve().kind == "APPROVED" and s.approval.approved_total_inr == 24999 + 1299 + 499


def test_m07_one_item_out_of_stock_offers_to_remove_it(rzp):  # noqa: F811
    s, _ = cart_with_bed_and_bag()
    s.approve()
    s.simulate_out_of_stock(bag_pid())
    kind, r = s.start_payment()
    assert r.kind == "BLOCKED" and "out of stock" in r.message and "remove" in r.message.lower() and not rzp.created


def test_m08_a_line_above_one_is_confirmed_before_approval():
    s, _ = cart_with_bed_and_bag()
    s.set_line_quantity(bag_pid(), 2)
    assert s.approve().kind == "CLARIFY"
    s.confirm_quantity()
    assert s.approve().kind == "APPROVED"


def test_m09_no_returns_label_per_line():
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "buy this", "context": page(BED)})
    out = c.post("/api/agent/message", json={"text": "buy this", "context": page(BIRD)}).json()
    lines = {ln["product_id"]: ln["returnable"] for ln in out["state"]["cart"]["lines"]}
    assert lines == {BED: True, BIRD: False}


def test_m10_adding_after_approval_cancels_it():
    s = Session()
    s.handle_message("buy this", page(BED))
    s.approve()
    s.handle_message("buy this", page(bag_pid()))
    assert s.approval is None


def test_m11_cart_holds_up_to_10_products():
    from catalog import SqliteCatalog
    pids = [r[0] for r in SqliteCatalog()._con.execute(
        "SELECT p.pid FROM products p JOIN prices pr USING(pid) WHERE pr.price_inr IS NOT NULL LIMIT 40")]
    s = Session()
    added = 0
    for pid in pids:
        r = s.handle_message("buy this", page(pid))
        if r.kind == "CART_PROPOSED":
            added += 1
        if added == 10:
            break
    nxt = next(p for p in pids if s.cart.line(p) is None and s.catalog.get(p).stock > 0)
    r = s.handle_message("buy this", page(nxt))
    assert len(s.cart.lines) == 10 and "up to 10" in r.message


def test_m12_pay_for_me_still_refused_with_several_items(rzp):  # noqa: F811
    s, _ = cart_with_bed_and_bag()
    r = s.handle_message("pay for me", {"page": "listing"})
    assert "only you can do" in r.message and not rzp.created


def test_m13_requirement_change_keeps_the_cart():
    s = Session()
    s.handle_message("buy this", page(BED))
    s.handle_message("sofas under 20000", {"page": "listing"})
    assert s.cart is not None and s.cart.status == "PROPOSED" and s.cart.line(BED)
