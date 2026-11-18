"""Phase 3 (BUILD_PLAN.md): the PM-approved wording evals in evals/phase3_scenarios.json.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))

from catalog import STORE_DB_PATH  # noqa: E402

pytestmark = pytest.mark.skipif(not STORE_DB_PATH.exists(), reason="needs data/catalog.sqlite")
SCENARIOS = json.loads((ROOT / "evals" / "phase3_scenarios.json").read_text())["scenarios"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_phase3_scenario(sc):
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


