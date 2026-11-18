"""Phase 1 (BUILD_PLAN.md): the PM-approved evals in evals/phase1_scenarios.json run as regression tests,
plus the misses found by the fresh-phrasing check after the code was written."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from catalog import STORE_DB_PATH  # noqa: E402

pytestmark = pytest.mark.skipif(not STORE_DB_PATH.exists(), reason="needs data/catalog.sqlite")
SCENARIOS = json.loads((ROOT / "evals" / "phase1_scenarios.json").read_text())["scenarios"]


@pytest.fixture(autouse=True)
def rules_mode(monkeypatch):
    monkeypatch.setenv("INTENTGUARD_LLM", "off")


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_phase1_scenario(sc):
    import run_evals
    from agent import Session
    from catalog import SqliteCatalog
    s = Session(catalog=SqliteCatalog())
    responses, states = [], []
    for turn in sc["turns"]:
        responses.append(run_evals.run_turn(s, turn, sc.get("page")))
        states.append(run_evals.snapshot(s))
    fails = [f for exp in sc["expect"] for f in run_evals.check(exp, responses[exp["turn"]], responses, states[exp["turn"]])]
    if "expect_orders" in sc:
        assert len(s.orders.orders) == sc["expect_orders"]
    assert not fails, fails


def _run(*msgs):
    from agent import Session
    s = Session()
    r = None
    for m in msgs:
        r = s.handle_message(m)
    return s, r


def test_fresh_number_word_is_not_a_product():
    s, r = _run("sofa", "two seats please")
    assert r.kind == "RECOMMEND" and s.intent.product_query == "sofa" and s.intent.seats == 2   # B18


def test_fresh_any_width_is_fine_removes_the_width():
    s, r = _run("2 seater sofa that fits 160 cm", "any width is fine")
    assert r.kind == "RECOMMEND" and "REQUIREMENT_REMOVED" in r.reason_codes
    assert s.intent.seats == 2 and s.intent.max_width_cm is None


def test_fresh_hi_there_is_a_greeting():
    _, r = _run("hi there")
    assert r.kind == "UNSUPPORTED" and r.reason_codes == ["GREETING"]


# ---- held-out fix (2026-11-18): leftover non-product words never get "We don't sell …"
@pytest.mark.parametrize("msgs", [("good night",), ("give me 90% discount",),
                                  ("2 seater sofa that fits 160 cm", "width doesn't matter")])
def test_heldout_non_product_words_get_catch_all_not_not_sold(msgs):
    _, r = _run(*msgs)
    assert "We don't sell" not in r.message and r.reason_codes == ["CATCH_ALL"]


def test_heldout_catch_all_keeps_the_current_product_thread():
    s, _ = _run("2 seater sofa that fits 160 cm", "show cheaper ones")
    assert s.intent.product_query == "sofa" and s.intent.seats == 2 and s.intent.max_width_cm == 160


@pytest.mark.parametrize("product", ["mobile", "air fryer", "I want to buy a phone", "need a refrigerator under 30000"])
def test_real_unsold_products_still_get_not_sold(product):
    _, r = _run(product)
    assert r.kind == "NOT_AVAILABLE" and r.reason_codes == ["NOT_SOLD_HERE"]
