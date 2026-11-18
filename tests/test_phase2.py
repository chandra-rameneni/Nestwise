"""Phase 2 (BUILD_PLAN.md): the PM-approved evals in evals/phase2_scenarios.json as regression tests, plus the
UI and data checks P2-U01 to P2-U04."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from catalog import STORE_DB_PATH  # noqa: E402

pytestmark = pytest.mark.skipif(not STORE_DB_PATH.exists(), reason="needs data/catalog.sqlite")
SCENARIOS = json.loads((ROOT / "evals" / "phase2_scenarios.json").read_text())["scenarios"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_phase2_scenario(sc):
    import run_evals
    from agent import Session
    from catalog import SqliteCatalog
    s = Session(catalog=SqliteCatalog())
    responses, states = [], []
    for turn in sc["turns"]:
        responses.append(run_evals.run_turn(s, turn, sc.get("page")))
        states.append(run_evals.snapshot(s))
    fails = [f for exp in sc["expect"] for f in run_evals.check(exp, responses[exp["turn"]], responses, states[exp["turn"]])]
    assert not fails, fails


def test_p2_u01_suggestions_all_lead_to_results():
    from agent import Session
    html = (ROOT / "web" / "index.html").read_text()
    chips = json.loads(re.search(r"suggestions:\s*(\[.*?\])", html).group(1))
    assert "Do you sell mobiles?" not in chips
    for chip in chips:
        assert Session().handle_message(chip).kind == "RECOMMEND", chip


def test_p2_u02_suggestions_hide_once_the_chat_starts():
    js = (ROOT / "web" / "agent.js").read_text()
    assert '$("ig-suggest").hidden = true' in js


def test_p2_u03_state_reports_which_extractor_answered():
    from fastapi.testclient import TestClient
    import server
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "sofas", "context": {"page": "listing"}})
    st = c.get("/api/agent/state").json()
    assert st["last_extractor"] == "rules_fallback"           # rules mode in tests: the badge can say so


def test_p2_u04_colour_in_brand_column_is_replaced_by_real_brand():
    from catalog import SqliteCatalog
    c = SqliteCatalog()
    pid = c._con.execute("SELECT pid FROM products WHERE brand = 'Red' AND name LIKE 'Petshop7%' LIMIT 1").fetchone()[0]
    assert c.get(pid).brand == "Petshop7"


# ---- PM observations after Phase 2 (O-24 to O-28)
def test_o24_full_phrase_fails_but_main_product_exists():
    from agent import Session
    r = Session().handle_message("i want shive temple")
    assert r.kind == "RECOMMEND" and "PARTIAL_MATCH" in r.reason_codes and "We don't sell" not in r.message


@pytest.mark.parametrize("msg", ["gaming laptop under 60000", "air fryer", "dinner set", "mobile phones"])
def test_o24_still_not_sold_when_the_main_product_isnt_sold(msg):
    from agent import Session
    assert Session().handle_message(msg).kind == "NOT_AVAILABLE"


def test_o25_hidden_suggestions_are_not_forced_visible_by_css():
    css = (ROOT / "web" / "styles.css").read_text()
    assert ".suggest[hidden] { display: none; }" in css


def test_o27_one_closing_line():
    from agent import Session
    r = Session().handle_message("sofas")
    assert r.message.count("Tell me") == 1


def test_o28_model_reply_with_one_bad_field_is_kept():
    import llm
    from intent import IntentExtraction
    parsed, dropped = llm._validate_lenient(IntentExtraction, {"intent": "PRODUCT_DISCOVERY", "product_query": "sofa",
                                                               "seats": "three"})
    assert parsed is not None and parsed.product_query == "sofa" and dropped == ["seats"]
    assert llm._validate_lenient(IntentExtraction, {"intent": "NOT_A_REAL_INTENT"})[0] is None
