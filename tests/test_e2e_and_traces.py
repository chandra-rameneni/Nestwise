"""Group D (OBS-01..06) and P0 end-to-end scenarios (E2E-01..03), plus P0 deferral of INT-02/03."""
import json

import pytest

from agent import Session
from catalog import Catalog
from conftest import KEYBOARD_REQUEST
from tracing import Tracer


def test_e2e01_discover_compare_buy(session):
    assert session.handle_message(KEYBOARD_REQUEST).kind == "RECOMMEND"
    assert session.select_product("KM-001").kind == "CART_PROPOSED"
    assert session.approve().kind == "APPROVED"
    r = session.checkout()
    assert r.kind == "ORDER_PLACED" and len(session.orders.orders) == 1


def test_e2e02_sofa_clarify_then_recommend(session):
    r = session.handle_message("I want to buy a sofa under ₹30,000")
    assert r.kind == "CLARIFY" and "seats" in r.message and "width" in r.message
    r = session.handle_message("3 seats, and it must fit in 200 cm of wall space")
    assert r.kind == "RECOMMEND"
    assert [x["product_id"] for x in r.recommendations] == ["SF-001"]
    assert session.intent.max_total_inr == 30000               # earlier constraint kept
    rejected = {x["product_id"]: x["reason_codes"] for x in r.rejected}
    assert rejected["SF-003"] == ["WIDTH_UNVERIFIED"] and "BUDGET_EXCEEDED" in rejected["SF-005"]


def test_e2e03_price_change_recovery(session):
    session.handle_message(KEYBOARD_REQUEST)
    session.select_product("KM-001")
    session.approve()
    session.simulate_price_change("KM-001", 3001)
    r = session.checkout()
    assert r.kind == "BLOCKED" and "no longer applies" in r.message
    session.select_product("KM-007")
    session.approve()
    assert session.checkout().kind == "ORDER_PLACED"
    assert len(session.orders.orders) == 1


@pytest.mark.parametrize("msg", ["I want a refund for my sofa.", "Where is my order?"])
def test_int02_int03_safe_deferral_no_actions(session, msg):
    r = session.handle_message(msg)
    assert r.kind == "DEFER" and "WORKFLOW_NOT_AVAILABLE" in r.reason_codes
    assert "refunded" not in r.message.lower().replace("nothing has been refunded", "")
    assert session.tracer.find("tool") == [] and session.orders.orders == {}


def test_obs01_unique_trace_ids():
    a, b = Session(tracer=Tracer(persist=False)), Session(tracer=Tracer(persist=False))
    assert a.tracer.trace_id != b.tracer.trace_id
    assert all(e["trace_id"] == a.tracer.trace_id for e in a.tracer.events)


def test_obs02_tool_events_have_name_args_status_duration_result(session):
    session.handle_message(KEYBOARD_REQUEST)
    tools = session.tracer.find("tool")
    assert tools
    for e in tools:
        assert e["name"] and "args" in e["attrs"] and e["status"] == "ok"
        assert e["duration_ms"] is not None and "result" in e["attrs"]


def test_obs03_blocks_have_reason_codes_and_evidence(session):
    session.handle_message(KEYBOARD_REQUEST)
    session.select_product("KM-001")
    session.approve()
    session.simulate_price_change("KM-001", 2795)
    session.checkout()
    gate = session.tracer.find("policy", "checkout.gate")[-1]
    assert gate["status"] == "block" and "PRICE_CHANGED_SINCE_APPROVAL" in gate["attrs"]["reason_codes"]
    assert gate["attrs"]["approved_total_inr"] == 2594 and gate["attrs"]["current_total_inr"] == 2894
    assert session.tracer.find("approval", "approval.invalidated")


def test_obs04_tool_failure_is_reported_not_hidden(session, monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("catalog timeout")
    monkeypatch.setattr(session.catalog, "search", boom)
    with pytest.raises(TimeoutError):
        session.handle_message(KEYBOARD_REQUEST)
    err = session.tracer.find("tool", "search_catalog")[-1]
    assert err["status"] == "error" and "catalog timeout" in err["attrs"]["error"]
    assert session.orders.orders == {}


def test_obs06_trace_chronological_and_redacted(tmp_path, monkeypatch):
    import tracing
    monkeypatch.setattr(tracing, "TRACE_DIR", tmp_path)
    t = Tracer()
    s = Session(catalog=Catalog(), tracer=t)
    s.handle_message(KEYBOARD_REQUEST)
    t.event("test", "secret_probe", api_key="sk-should-not-appear", card_number="4111")
    lines = [json.loads(x) for x in (tmp_path / f"{t.trace_id}.jsonl").read_text().splitlines()]
    assert [e["seq"] for e in lines] == list(range(1, len(lines) + 1))
    text = (tmp_path / f"{t.trace_id}.jsonl").read_text()
    assert "sk-should-not-appear" not in text and "4111" not in text


def test_critical_event_chain_present(session):
    session.handle_message(KEYBOARD_REQUEST)
    session.select_product("KM-001")
    session.approve()
    session.checkout()
    names = [e["name"] for e in session.tracer.events]
    for required in ["session.start", "user.message", "intent.extracted", "search_catalog", "policy.eligibility",
                     "recommendation", "cart.created", "approval.granted", "checkout.gate", "order.created"]:
        assert required in names, required
    order = [names.index(n) for n in ["intent.extracted", "search_catalog", "cart.created", "approval.granted",
                                      "checkout.gate", "order.created"]]
    assert order == sorted(order)
