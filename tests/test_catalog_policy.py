"""Group B: catalog grounding and eligibility (PRD-01..10)."""
import json
from pathlib import Path

from catalog import CATALOG_PATH, Catalog
from intent import Intent
import policy

KB = Intent(intent="PRODUCT_DISCOVERY", category="keyboard_mouse_combo", max_total_inr=4000, max_delivery_days=5,
            required_compatibility=["macOS"], preferred_brands=["Logitech"])


def codes(pid, intent=KB):
    return policy.evaluate(intent, Catalog().get(pid)).reason_codes


def test_prd02_join_by_product_id_has_no_crossover():
    raw = json.loads(Path(CATALOG_PATH).read_text())
    c = Catalog()
    for p in raw["products"]:
        v = c.get(p["product_id"])
        assert v.title == p["title"]
        assert v.list_price_inr == raw["prices"][p["product_id"]]["list_price_inr"]
        assert v.stock == raw["inventory"][p["product_id"]]["stock"]
        assert v.specs == raw["specs"][p["product_id"]]


def test_prd04_over_budget_rejected():
    assert "BUDGET_EXCEEDED" in codes("KM-002")      # 3899 + 199 = 4098 > 4000


def test_prd05_missing_compatibility_is_unverified_not_compliant():
    assert codes("KM-003") == ["COMPAT_UNVERIFIED"]
    assert codes("KM-004") == ["COMPAT_FAILED"]


def test_prd06_out_of_stock_excluded():
    assert codes("KM-005") == ["OUT_OF_STOCK"]


def test_prd07_slow_delivery_rejected():
    assert codes("KM-006") == ["DELIVERY_TOO_SLOW"]


def test_sofa_width_unknown_is_unverified():
    sofa = Intent(intent="PRODUCT_DISCOVERY", category="sofa", seats=3, max_width_cm=200, max_total_inr=30000)
    assert codes("SF-003", sofa) == ["WIDTH_UNVERIFIED"]
    assert codes("SF-002", sofa) == ["WIDTH_EXCEEDED"]
    assert codes("SF-001", sofa) == []
