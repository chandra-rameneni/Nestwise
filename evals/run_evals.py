"""Run evals/scenarios.json against the real catalog and write results that link every failure to its trace.

Usage:
  .venv/bin/python evals/run_evals.py            # uses Claude if ANTHROPIC_API_KEY is set, else rules mode
  INTENTGUARD_LLM=off .venv/bin/python evals/run_evals.py   # force rules mode

Writes evals/results/<timestamp>_<mode>.json and .md, and keeps each scenario's trace in traces/<trace_id>.jsonl.
For each failed check the result names the trace and the first event that went wrong (OBS-05): the
agent.response event of the turn whose outcome didn't match.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intent as intent_mod  # noqa: E402
from agent import Session  # noqa: E402
from catalog import STORE_DB_PATH, SqliteCatalog  # noqa: E402
from tracing import Tracer  # noqa: E402

SCENARIOS = Path(__file__).parent / "scenarios.json"
RESULTS = Path(__file__).parent / "results"


def run_turn(s: Session, turn: dict, default_page: str | None):
    page = turn.get("page", default_page)
    ctx = {"page": "product", "product_id": page} if page else {"page": "listing"}
    if "say" in turn:
        return s.handle_message(turn["say"], ctx)
    act = turn["action"]
    if act == "select":
        return s.select_product(turn["product_id"])
    if act in ("approve", "decline", "checkout"):
        return getattr(s, act)()
    if act == "sim_price":
        s.simulate_price_change(turn["product_id"], turn["price_inr"])
        return None
    raise ValueError(f"unknown action {act}")


def check(exp: dict, r, responses: list) -> list[str]:
    """Returns a list of failed-check descriptions for one expectation."""
    if r is None:
        return ["turn produced no response"]
    fails = []
    totals = [x["total_inr"] for x in r.recommendations]
    ids = [x["product_id"] for x in r.recommendations]
    if "kind" in exp and r.kind != exp["kind"]:
        fails.append(f"kind: expected {exp['kind']}, got {r.kind}")
    for s in exp.get("contains", []):
        if s not in r.message:
            fails.append(f"message should contain {s!r}")
    for s in exp.get("not_contains", []):
        if s in r.message:
            fails.append(f"message should not contain {s!r}")
    if "ids" in exp and set(ids) != set(exp["ids"]):
        fails.append(f"recommended ids: expected {sorted(exp['ids'])}, got {sorted(ids)}")
    if "excludes" in exp and set(ids) & set(exp["excludes"]):
        fails.append(f"should not recommend {exp['excludes']}")
    if "all_totals_at_most" in exp and (not totals or any(t is None or t > exp["all_totals_at_most"] for t in totals)):
        fails.append(f"all recommended totals should be <= {exp['all_totals_at_most']} (got {totals})")
    if "all_totals_below" in exp and (not totals or any(t is None or t >= exp["all_totals_below"] for t in totals)):
        fails.append(f"all recommended totals should be < {exp['all_totals_below']} (got {totals})")
    if "titles_contain" in exp and (not ids or not all(exp["titles_contain"] in x["title"].lower() for x in r.recommendations)):
        fails.append(f"every recommendation should be a {exp['titles_contain']}")
    if "cited" in exp and r.cited_fields != exp["cited"]:
        fails.append(f"cited fields: expected {exp['cited']}, got {r.cited_fields}")
    if "cited_any" in exp and not set(exp["cited_any"]) & set(r.cited_fields):
        fails.append(f"should cite one of {exp['cited_any']}, got {r.cited_fields}")
    if "reason" in exp and exp["reason"] not in r.reason_codes:
        fails.append(f"reason codes should include {exp['reason']}, got {r.reason_codes}")
    if "same_message_as_turn" in exp and r.message != responses[exp["same_message_as_turn"]].message:
        fails.append("message should repeat the earlier answer exactly")
    return fails


def main() -> int:
    if not STORE_DB_PATH.exists():
        print("data/catalog.sqlite not found. Run: .venv/bin/python build_catalog.py")
        return 2
    spec = json.loads(SCENARIOS.read_text())
    mode = "claude" if intent_mod.llm_available() else "rules"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    for sc in spec["scenarios"]:
        s = Session(catalog=SqliteCatalog(), tracer=Tracer())
        responses, error = [], None
        try:
            for turn in sc["turns"]:
                responses.append(run_turn(s, turn, sc.get("page")))
        except Exception as exc:  # a crash is a failure, recorded with the trace
            error = f"{type(exc).__name__}: {exc}"
        failures = []
        if error:
            failures.append({"turn": len(responses), "check": f"crashed: {error}"})
        for exp in sc["expect"]:
            if exp["turn"] < len(responses):
                for f in check(exp, responses[exp["turn"]], responses):
                    failures.append({"turn": exp["turn"], "check": f})
        if "expect_orders" in sc and len(s.orders.orders) != sc["expect_orders"]:
            failures.append({"turn": None, "check": f"orders: expected {sc['expect_orders']}, got {len(s.orders.orders)}"})
        reply_events = [e for e in s.tracer.events if e["name"] == "agent.response"]
        first_bad = None
        if failures:
            t = next((f["turn"] for f in failures if f["turn"] is not None), None)
            idx = sum(1 for r in responses[: (t or 0) + 1] if r is not None) - 1 if t is not None else -1
            if error and s.tracer.events:          # a crash: point at the last thing that happened
                ev = s.tracer.events[-1]
                first_bad = {"seq": ev["seq"], "name": ev["name"], "response_kind": None}
            elif reply_events and 0 <= idx < len(reply_events):
                ev = reply_events[idx]
                first_bad = {"seq": ev["seq"], "name": ev["name"], "response_kind": ev["attrs"].get("response_kind")}
        results.append({"id": sc["id"], "group": sc["group"], "probe": sc.get("probe", False), "passed": not failures,
                        "failures": failures, "trace_id": s.tracer.trace_id, "first_failing_event": first_bad,
                        "replies": [None if r is None else {"kind": r.kind, "message": r.message[:300],
                                                            "cited": r.cited_fields} for r in responses],
                        "notes": sc.get("notes")})

    RESULTS.mkdir(exist_ok=True)
    n = len(results)
    passed = sum(r["passed"] for r in results)
    core = [r for r in results if not r["probe"]]
    probes = [r for r in results if r["probe"]]
    summary = {"run_at": stamp, "mode": mode, "model": intent_mod.MODEL if mode == "claude" else None,
               "scenarios_version": spec["version"], "total": n, "passed": passed,
               "core": f"{sum(r['passed'] for r in core)}/{len(core)}",
               "probes": f"{sum(r['passed'] for r in probes)}/{len(probes)}", "results": results}
    out = RESULTS / f"{stamp}_{mode}"
    out.with_suffix(".json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    lines = [f"# Eval run {stamp} ({mode} mode)", "",
             f"**{passed}/{n} scenarios passed.** Core: {summary['core']} · Probes (phrasings the rules weren't written for): {summary['probes']}.", "",
             "| Scenario | Group | Probe | Result | What failed | Trace (first failing event) |", "|---|---|---|---|---|---|"]
    for r in results:
        what = "; ".join(f"turn {f['turn']}: {f['check']}" for f in r["failures"]) or ""
        tr = f"`{r['trace_id']}`" + (f" #{r['first_failing_event']['seq']}" if r["first_failing_event"] else "")
        lines.append(f"| {r['id']} | {r['group']} | {'yes' if r['probe'] else ''} | {'pass' if r['passed'] else '**FAIL**'} | {what} | {tr if not r['passed'] else ''} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:3]))
    for r in results:
        if not r["passed"]:
            print(f"FAIL {r['id']}: " + "; ".join(f["check"] for f in r["failures"]))
    print(f"wrote {out.with_suffix('.json')} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
