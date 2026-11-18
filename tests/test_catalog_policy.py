"""Group B: catalog grounding and eligibility (PRD-01..10)."""
import json
from pathlib import Path

from catalog import CATALOG_PATH, Catalog
from conftest import KEYBOARD_REQUEST
from intent import Intent
import policy

KB = Intent(intent="PRODUCT_DISCOVERY", category="keyboard_mouse_combo", max_total_inr=4000, max_delivery_days=5,
            required_compatibility=["macOS"], preferred_brands=["Logitech"])


def codes(pid, intent=KB):
    return policy.evaluate(intent, Catalog().get(pid)).reason_codes


def test_prd01_search_tool_called_and_traced(session):
    session.handle_message(KEYBOARD_REQUEST)
    calls = session.tracer.find("tool", "search_catalog")
    assert len(calls) == 1 and calls[0]["attrs"]["result"]["matches"] == 9


def test_prd02_join_by_product_id_has_no_crossover():
    raw = json.loads(Path(CATALOG_PATH).read_text())
    c = Catalog()
    for p in raw["products"]:
        v = c.get(p["product_id"])
        assert v.title == p["title"]
        assert v.list_price_inr == raw["prices"][p["product_id"]]["list_price_inr"]
        assert v.stock == raw["inventory"][p["product_id"]]["stock"]
        assert v.specs == raw["specs"][p["product_id"]]


def test_prd03_unknown_product_not_invented(session):
    r = session.handle_message("Find me a gaming laptop under ₹80,000")
    assert r.kind == "NOT_AVAILABLE" and r.recommendations == [] and "?" not in r.message


def test_prd04_over_budget_rejected():
    assert "BUDGET_EXCEEDED" in codes("KM-002")      # 3899 + 199 = 4098 > 4000


def test_prd05_missing_compatibility_is_unverified_not_compliant():
    assert codes("KM-003") == ["COMPAT_UNVERIFIED"]
    assert codes("KM-004") == ["COMPAT_FAILED"]


def test_prd06_out_of_stock_excluded():
    assert codes("KM-005") == ["OUT_OF_STOCK"]


def test_prd07_slow_delivery_rejected():
    assert codes("KM-006") == ["DELIVERY_TOO_SLOW"]


def test_prd08_multiple_eligible_compared_and_ranked(session):
    r = session.handle_message(KEYBOARD_REQUEST)
    assert r.kind == "RECOMMEND"
    assert [x["product_id"] for x in r.recommendations] == ["KM-001", "KM-009", "KM-007"]  # Logitech first, then price
    assert "₹2,594 total" in r.message and "arrives in 3 days" in r.message


def test_prd09_preferred_brand_absent_offers_alternatives(session):
    r = session.handle_message("Mac keyboard and mouse combo under ₹4,000, prefer Apple")
    assert r.kind == "RECOMMEND" and r.recommendations
    assert "None of the eligible options are from Apple" in r.message


def test_prd10_no_eligible_explains_blockers(session):
    r = session.handle_message("Mac keyboard and mouse combo under ₹1,000 delivered in 2 days")
    assert r.kind == "NO_ELIGIBLE" and "BUDGET_EXCEEDED" in r.reason_codes
    # PRD B21 (Phase 2): the closest options are shown, but none can go in a cart.
    assert session.eligible_ids == [] and all(x["product_id"] for x in r.recommendations)


def test_all_recommended_ids_exist_in_catalog(session):
    r = session.handle_message(KEYBOARD_REQUEST)
    c = Catalog()
    assert all(c.get(x["product_id"]) is not None for x in r.recommendations)


def test_sofa_width_unknown_is_unverified():
    sofa = Intent(intent="PRODUCT_DISCOVERY", category="sofa", seats=3, max_width_cm=200, max_total_inr=30000)
    assert codes("SF-003", sofa) == ["WIDTH_UNVERIFIED"]
    assert codes("SF-002", sofa) == ["WIDTH_EXCEEDED"]
    assert codes("SF-001", sofa) == []
