"""PRD B26 (quantity, O-57) and B47 (several products in one cart, O-58), approved by the PM 2026-11-19.
Evals Q-01 to Q-14 and M-01 to M-13. With a fake Razorpay for the payment checks."""
from conftest import agent_adds
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import intent as I
import server
from agent import Session
from tests.test_razorpay import sign, rzp  # noqa: F401  (fixture)

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
    agent_adds(c, BED)
    out = c.post("/api/cart/qty", json={"product_id": BED, "qty": 2}).json()
    ln = out["state"]["cart"]["lines"][0]
    assert ln["qty"] == 2 and ln["total_inr"] == 2 * 24999 and ln["max_qty"] == 5
    js = (ROOT / "web" / "agent.js").read_text()
    assert 'data-qty="${esc(ln.qty + 1)}"' in js and "ln.qty >= ln.max_qty" in js      # "+" disabled at the limit


def test_q03_changed_quantity_cancels_the_approval():
    s = Session()
    s.select_product(BED, from_product_page=True)
    s.approve()
    s.set_line_quantity(BED, 2)
    assert s.approval is None and s.approve().kind == "CLARIFY"           # RZ8 again for the new quantity


# ---------------------------------------------------------------- B47: several products
def cart_with_bed_and_bag():
    s = Session()
    s.select_product(BED, from_product_page=True)
    r = s.select_product(bag_pid(), from_product_page=True)
    return s, r


def test_m01_second_product_is_added_not_replaced():
    s, r = cart_with_bed_and_bag()
    assert [ln.product_id for ln in s.cart.lines] == [BED, bag_pid()]
    assert s.cart.total_inr == 24999 + 1149 + 499 and "2 items" in r.message and "Added" in r.message


def test_m02_same_product_again_raises_its_quantity():
    s = Session()
    s.select_product(BED, from_product_page=True)
    s.select_product(BED, from_product_page=True)
    assert len(s.cart.lines) == 1 and s.cart.line(BED).qty == 2


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


def test_m10_adding_after_approval_cancels_it():
    s = Session()
    s.select_product(BED, from_product_page=True)
    s.approve()
    s.select_product(bag_pid(), from_product_page=True)
    assert s.approval is None


def test_m11_cart_holds_up_to_10_products():
    from catalog import SqliteCatalog
    pids = [r[0] for r in SqliteCatalog()._con.execute(
        "SELECT p.pid FROM products p JOIN prices pr USING(pid) WHERE pr.price_inr IS NOT NULL LIMIT 40")]
    s = Session()
    added = 0
    for pid in pids:
        r = s.select_product(pid, from_product_page=True)
        if r.kind == "CART_PROPOSED":
            added += 1
        if added == 10:
            break
    nxt = next(p for p in pids if s.cart.line(p) is None and s.catalog.get(p).stock > 0)
    r = s.select_product(nxt, from_product_page=True)
    assert len(s.cart.lines) == 10 and "up to 10" in r.message


def test_m12_pay_for_me_still_refused_with_several_items(rzp):  # noqa: F811
    s, _ = cart_with_bed_and_bag()
    r = s.handle_message("pay for me", {"page": "listing"})
    assert "only you can do" in r.message and not rzp.created


