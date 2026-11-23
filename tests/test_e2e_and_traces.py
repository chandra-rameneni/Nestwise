"""Group D (OBS-01..06) and P0 end-to-end scenarios (E2E-01..03), plus P0 deferral of INT-02/03."""
import json


from agent import Session
from catalog import Catalog
from conftest import keyboard_search
from tracing import Tracer


def test_obs01_unique_trace_ids():
    a, b = Session(tracer=Tracer(persist=False)), Session(tracer=Tracer(persist=False))
    assert a.tracer.trace_id != b.tracer.trace_id
    assert all(e["trace_id"] == a.tracer.trace_id for e in a.tracer.events)


def test_obs03_blocks_have_reason_codes_and_evidence(session):
    keyboard_search(session)
    session.select_product("KM-001")
    session.approve()
    session.simulate_price_change("KM-001", 2795)
    session.checkout()
    gate = session.tracer.find("policy", "checkout.gate")[-1]
    assert gate["status"] == "block" and "PRICE_CHANGED_SINCE_APPROVAL" in gate["attrs"]["reason_codes"]
    assert gate["attrs"]["approved_total_inr"] == 2594 and gate["attrs"]["current_total_inr"] == 2894
    assert session.tracer.find("approval", "approval.invalidated")


def test_obs06_trace_chronological_and_redacted(tmp_path, monkeypatch):
    import tracing
    monkeypatch.setattr(tracing, "TRACE_DIR", tmp_path)
    t = Tracer()
    s = Session(catalog=Catalog(), tracer=t)
    keyboard_search(s)
    t.event("test", "secret_probe", api_key="sk-should-not-appear", card_number="4111")
    lines = [json.loads(x) for x in (tmp_path / f"{t.trace_id}.jsonl").read_text().splitlines()]
    assert [e["seq"] for e in lines] == list(range(1, len(lines) + 1))
    text = (tmp_path / f"{t.trace_id}.jsonl").read_text()
    assert "sk-should-not-appear" not in text and "4111" not in text


