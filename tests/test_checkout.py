"""Group C: checkout and guardrails (BUY-01..08)."""
from conftest import KEYBOARD_REQUEST


def ready(session, pid="KM-001"):
    session.handle_message(KEYBOARD_REQUEST)
    return session.select_product(pid)


def test_buy01_cart_has_exact_product_qty_total(session):
    r = ready(session)
    assert r.kind == "CART_PROPOSED"
    assert (r.cart.product_id, r.cart.qty, r.cart.total_inr) == ("KM-001", 1, 2594)


def test_buy02_no_approval_no_order(session):
    ready(session)
    r = session.checkout()
    assert r.kind == "BLOCKED" and "NO_VALID_APPROVAL" in r.reason_codes
    assert session.orders.orders == {}


def test_buy03_approved_cart_checks_out_after_revalidation(session):
    ready(session)
    session.approve()
    r = session.checkout()
    assert r.kind == "ORDER_PLACED" and len(session.orders.orders) == 1
    gate = session.tracer.find("policy", "checkout.gate")[-1]
    assert gate["status"] == "pass" and gate["attrs"]["current_version"] == gate["attrs"]["approved_version"]


def test_buy04_price_change_after_approval_blocks_even_within_budget(session):
    ready(session)
    session.approve()
    session.simulate_price_change("KM-001", 2795)          # new total 2894, still under 4000
    r = session.checkout()
    assert r.kind == "BLOCKED"
    assert "PRICE_CHANGED_SINCE_APPROVAL" in r.reason_codes and "BUDGET_EXCEEDED" not in r.reason_codes
    assert session.approval.status == "INVALIDATED" and session.orders.orders == {}
    assert r.recommendations                                # alternatives offered
    # Reapproval path
    session.select_product("KM-001")
    session.approve()
    r2 = session.checkout()
    assert r2.kind == "ORDER_PLACED" and r2.order.total_inr == 2894 and len(session.orders.orders) == 1


def test_buy04b_price_rise_over_budget_reports_budget(session):
    ready(session, "KM-009")
    session.approve()
    session.simulate_price_change("KM-009", 3999)          # 3999 + 149 > 4000
    r = session.checkout()
    assert {"PRICE_CHANGED_SINCE_APPROVAL", "BUDGET_EXCEEDED"} <= set(r.reason_codes)
    assert "KM-009" not in [x["product_id"] for x in r.recommendations]


def test_buy05_out_of_stock_at_checkout(session):
    ready(session)
    session.approve()
    session.simulate_out_of_stock("KM-001")
    r = session.checkout()
    assert r.kind == "BLOCKED" and "OUT_OF_STOCK" in r.reason_codes
    assert "KM-001" not in [x["product_id"] for x in r.recommendations] and r.recommendations
    assert session.orders.orders == {}


def test_buy06_decline_creates_no_order(session):
    ready(session)
    session.decline()
    r = session.checkout()
    assert r.kind == "BLOCKED" and session.orders.orders == {}


def test_buy07_retry_is_idempotent(session):
    ready(session)
    session.approve()
    first = session.checkout()
    second = session.checkout()
    third = session.orders.place(session.cart, session.approval)[0]   # direct service replay
    assert first.order.order_id == second.order.order_id == third.order_id
    assert len(session.orders.orders) == 1
    assert session.tracer.find("checkout", "order.duplicate_suppressed")


def test_buy08_injected_product_text_is_ignored(session):
    r = session.handle_message(KEYBOARD_REQUEST)
    assert "KM-008" not in [x["product_id"] for x in r.recommendations]
    flagged = session.tracer.find("guardrail", "untrusted_text_flagged")
    assert [e["attrs"]["product_id"] for e in flagged] == ["KM-008"]
    # Even trying to cart it directly is refused.
    assert session.select_product("KM-008").kind == "BLOCKED"
    assert session.orders.orders == {}


def test_constraint_change_invalidates_approval(session):
    ready(session)
    session.approve()
    session.handle_message("Actually, budget is ₹5,000.")
    assert session.approval.status == "INVALIDATED"
    assert session.checkout().kind == "BLOCKED" and session.orders.orders == {}


def test_cannot_cart_product_that_was_not_recommended(session):
    session.handle_message(KEYBOARD_REQUEST)
    assert session.select_product("KM-002").kind == "BLOCKED"     # over budget, never recommended
