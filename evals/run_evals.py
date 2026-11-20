"""Run evals/scenarios.json against the real catalog and write results that link every failure to its trace.

Usage:
  .venv/bin/python evals/run_evals.py            # uses Claude if ANTHROPIC_API_KEY is set, else rules mode
  .venv/bin/python evals/run_evals.py evals/phase1_scenarios.json   # run another scenario file
  INTENTGUARD_LLM=off .venv/bin/python evals/run_evals.py   # force rules mode

Writes evals/results/<timestamp>_<mode>.json and .md, and keeps each scenario's trace in traces/<trace_id>.jsonl.
For each failed check the result names the trace and the first event that went wrong (OBS-05): the
agent.response event of the turn whose outcome didn't match.
"""
from __future__ import annotations

import json
import os
import re
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

# Round 2 (PRD §6A.1, voice for model answers): words that make an answer sound like a robot.
ROBOT_WORDS = [r"(?i)\b(the )?listing (says|states|mentions|shows)\b", r"(?i)\(simulated\)", r"(?i)\(historical\)",
               r"\b[A-Z]{3,}_[A-Z_]{3,}\b", r"(?i)with mattress:", r"(?i)i'?d rather not guess"]
RESULTS = Path(__file__).parent / "results"


# Free models allow only a few requests a minute. In model mode, INTENTGUARD_EVAL_PACE_S pauses between turns so
# an eval run measures the models, not their rate limits (found 2026-11-19: back-to-back runs fell back to rules).
PACE_S = float(__import__("os").environ.get("INTENTGUARD_EVAL_PACE_S", "0"))


def run_turn(s: Session, turn: dict, default_page: str | None):
    if PACE_S and "say" in turn:
        __import__("time").sleep(PACE_S)
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
    if act == "sim_stock":
        s.simulate_out_of_stock(turn["product_id"])
        return None
    raise ValueError(f"unknown action {act}")


def snapshot(s: Session) -> dict:
    """What the agent remembers after a turn: the product thread, its requirements, and the cart."""
    it = s.intent
    return {"product": (it.product_query or "") if it else "",
            "seats": it.seats if it else None, "max_width_cm": it.max_width_cm if it else None,
            "max_total_inr": it.max_total_inr if it else None,
            "material": getattr(it, "material", None) if it else None,
            "cart": s.cart.status if s.cart else None, "cart_qty": s.cart.qty if s.cart else None}


def check(exp: dict, r, responses: list, state: dict | None = None) -> list[str]:
    """Returns a list of failed-check descriptions for one expectation."""
    if r is None:
        return ["turn produced no response"]
    fails = []
    if "kind_not" in exp and r.kind == exp["kind_not"]:
        fails.append(f"kind should not be {exp['kind_not']}")
    if "reason_not" in exp and exp["reason_not"] in r.reason_codes:
        fails.append(f"reason codes should not include {exp['reason_not']}")
    if "min_recs" in exp and len(r.recommendations) < exp["min_recs"]:
        fails.append(f"should show at least {exp['min_recs']} products, showed {len(r.recommendations)}")
    if "check_passed" in exp and (not r.recommendations or not all(
            any(c["constraint"] == exp["check_passed"] and c["status"] == "pass" for c in rec.get("checks", []))
            for rec in r.recommendations)):
        fails.append(f"every shown product should pass the {exp['check_passed']} check")
    for word in exp.get("titles_include_each", []):
        if not any(word in x["title"].lower() for x in r.recommendations):
            fails.append(f"some shown product should be a {word}")
    if "differs_from_turn" in exp and r.message == responses[exp["differs_from_turn"]].message:
        fails.append(f"reply should differ from turn {exp['differs_from_turn']} (same reply repeated)")
    if state is not None:
        for k, v in exp.get("state", {}).items():
            if state.get(k) != v:
                fails.append(f"remembered {k}: expected {v!r}, got {state.get(k)!r}")
        if "product_contains" in exp and exp["product_contains"] not in state["product"].lower():
            fails.append(f"remembered product should be a {exp['product_contains']!r}, got {state['product']!r}")
        if exp.get("no_cart") and state["cart"] is not None:
            fails.append(f"no cart should exist, got one with status {state['cart']}")
    totals = [x["total_inr"] for x in r.recommendations]
    ids = [x["product_id"] for x in r.recommendations]
    if "kind" in exp and r.kind != exp["kind"]:
        fails.append(f"kind: expected {exp['kind']}, got {r.kind}")
    low = r.message.lower()                # case-insensitive: "Sorry, we don't sell" still counts as "We don't sell"
    for s in exp.get("contains", []):
        if s.lower() not in low:
            fails.append(f"message should contain {s!r}")
    for s in exp.get("not_contains", []):
        if s.lower() in low:
            fails.append(f"message should not contain {s!r}")
    for pat in exp.get("not_regex", []):
        if re.search(pat, r.message):
            fails.append(f"message should not match {pat!r}")
    for pat in exp.get("regex", []):
        if not re.search(pat, r.message):
            fails.append(f"message should match {pat!r}")
    if "shorter_than_turn" in exp and len(r.message) >= len(responses[exp["shorter_than_turn"]].message):
        fails.append(f"reply should be shorter than turn {exp['shorter_than_turn']}")
    if "max_sentences" in exp and len([s for s in re.split(r"(?<=[.!?])\s+", r.message.strip()) if s]) > exp["max_sentences"]:
        fails.append(f"reply should have at most {exp['max_sentences']} sentences")
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
    if exp.get("voice"):
        for pat in ROBOT_WORDS:
            if re.search(pat, r.message):
                fails.append(f"voice: robot wording matched {pat!r}")
    if exp.get("starts_sorry") and not re.match(r"\s*(Sorry|Unfortunately|Fair point, sorry)", r.message):
        fails.append("should start with an apology (Sorry)")
    for pat in exp.get("cited_regex", []):
        if not any(re.search(pat, c) for c in r.cited_fields):
            fails.append(f"should cite a source matching {pat!r}, got {r.cited_fields}")
    for pat in exp.get("not_cited_regex", []):
        if any(re.search(pat, c) for c in r.cited_fields):
            fails.append(f"should not cite a source matching {pat!r}, got {r.cited_fields}")
    if exp.get("rejected_excludes_shown"):
        shown = {x["product_id"] for x in r.recommendations}
        if shown & {x["product_id"] for x in r.rejected}:
            fails.append("'left out' list repeats a product that was shown")
    if "same_message_as_turn" in exp and r.message != responses[exp["same_message_as_turn"]].message:
        fails.append("message should repeat the earlier answer exactly")
    return fails


def main() -> int:
    if not STORE_DB_PATH.exists():
        print("data/catalog.sqlite not found. Run: .venv/bin/python build_catalog.py")
        return 2
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SCENARIOS
    spec = json.loads(path.read_text())
    # Audit finding A (2026-11-20): the scenarios measure the agent, with mock checkout. Real Razorpay keys in the
    # shell changed 4 results, so they are switched off for every run, and the results file says so.
    keys_in_shell = bool(os.environ.get("RAZORPAY_KEY_ID") or os.environ.get("RAZORPAY_KEY_SECRET"))
    os.environ.pop("RAZORPAY_KEY_ID", None)
    os.environ.pop("RAZORPAY_KEY_SECRET", None)
    import llm
    mode = llm.provider() or "rules"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []
    skipped = []
    for sc in spec["scenarios"]:
        run_in = sc.get("mode", "RM")             # R: rules only, M: with a model only, RM: both
        if (mode == "rules" and "R" not in run_in) or (mode != "rules" and "M" not in run_in):
            skipped.append(sc["id"])
            continue
        try:
            s = Session(catalog=SqliteCatalog(), tracer=Tracer(), source="eval")
        except TypeError:          # older code (before PRD §14) has no `source`; used for before/after comparisons
            s = Session(catalog=SqliteCatalog(), tracer=Tracer())
        responses, states, error = [], [], None
        try:
            for turn in sc["turns"]:
                responses.append(run_turn(s, turn, sc.get("page")))
                states.append(snapshot(s))
        except Exception as exc:  # a crash is a failure, recorded with the trace
            error = f"{type(exc).__name__}: {exc}"
        failures = []
        if error:
            failures.append({"turn": len(responses), "check": f"crashed: {error}"})
        for exp in sc["expect"]:
            if exp["turn"] < len(responses):
                for f in check(exp, responses[exp["turn"]], responses, states[exp["turn"]]):
                    failures.append({"turn": exp["turn"], "check": f})
        if "expect_orders" in sc and len(s.orders.orders) != sc["expect_orders"]:
            failures.append({"turn": None, "check": f"orders: expected {sc['expect_orders']}, got {len(s.orders.orders)}"})
        reply_events = [e for e in s.tracer.events if e["name"] == "agent.response"]
        extractors = [e["attrs"].get("extractor", "") for e in s.tracer.events if e["name"] == "intent.extracted"]
        answers = [(e["attrs"].get("result") or {}).get("method") for e in s.tracer.events
                   if e["name"] in ("answer_about_product", "answer_store_policy")]
        # Which AI models answered in this scenario (2026-11-20: free quotas run out mid-run and the chain switches
        # models, so each scenario records its own models instead of one model per run).
        # extractor is "llm:<model>:<prompt>", and a model name can itself contain ":" (e.g. "...:free")
        models = sorted({x[4:].rsplit(":", 1)[0] for x in extractors if x.startswith("llm:") and x.count(":") >= 2}
                        | {(e["attrs"].get("result") or {}).get("model") for e in s.tracer.events
                           if e["name"] in ("answer_about_product", "answer_store_policy")
                           and (e["attrs"].get("result") or {}).get("method") == "llm"} - {None})
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
                        "ai_readings": sum(x.startswith("llm") for x in extractors),
                        "rules_fallbacks": sum(x == "rules_fallback" for x in extractors),
                        "ai_answers": sum(a == "llm" for a in answers), "answers": len(answers),
                        "models": models,
                        "answered_by": ("rules only" if not models else models[0] if len(models) == 1
                                        else "mixed: " + " + ".join(models)),
                        "failures": failures, "trace_id": s.tracer.trace_id, "first_failing_event": first_bad,
                        "replies": [None if r is None else {"kind": r.kind, "message": r.message[:300],
                                                            "cited": r.cited_fields} for r in responses],
                        "notes": sc.get("notes")})

    RESULTS.mkdir(exist_ok=True)
    n = len(results)
    passed = sum(r["passed"] for r in results)
    core = [r for r in results if not r["probe"]]
    probes = [r for r in results if r["probe"]]
    summary = {"run_at": stamp, "mode": mode, "model": llm.model_name(),
               "payment_keys": "off for this run" + (" (set in the shell, ignored)" if keys_in_shell else ""),
               "scenarios_version": spec["version"], "total": n, "passed": passed,
               "core": f"{sum(r['passed'] for r in core)}/{len(core)}",
               "probes": f"{sum(r['passed'] for r in probes)}/{len(probes)}", "skipped_for_mode": skipped,
               "ai_readings": sum(r["ai_readings"] for r in results),
               "rules_fallbacks": sum(r["rules_fallbacks"] for r in results),
               "ai_answers": sum(r["ai_answers"] for r in results), "answers": sum(r["answers"] for r in results),
               "results": results}
    # A run in AI mode only counts if the AI really answered (found 2026-11-19: three "AI" runs were mostly rules
    # because the free daily quotas ran out). Below 80% of readings by the AI, the run is labelled not valid.
    readings = summary["ai_readings"] + summary["rules_fallbacks"]
    summary["ai_share"] = round(summary["ai_readings"] / readings, 2) if readings else None
    summary["valid_ai_run"] = None if mode == "rules" else bool(readings and summary["ai_share"] >= 0.8)
    by_model: dict[str, dict] = {}
    for r in results:
        b = by_model.setdefault(r["answered_by"], {"scenarios": [], "passed": 0})
        b["scenarios"].append(r["id"])
        b["passed"] += r["passed"]
    summary["by_model"] = by_model
    out =RESULTS / f"{stamp}_{mode}" if path == SCENARIOS else RESULTS / f"{stamp}_{path.stem}_{mode}"
    out.with_suffix(".json").write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    lines = [f"# Eval run {stamp} ({mode} mode)", "", f"Payment keys: {summary['payment_keys']} (checkout is mock).", "",
             f"**{passed}/{n} scenarios passed.** Core: {summary['core']} · Probes (phrasings the rules weren't written for): {summary['probes']}."
             + (f" Skipped in {mode} mode: {len(skipped)}." if skipped else "")
             + (f" Who answered: {summary['ai_readings']} messages read by the AI, {summary['rules_fallbacks']} fell "
                f"back to the rules; {summary['ai_answers']} of {summary['answers']} answers written by the AI."
                if mode != "rules" else "")
             + ("" if summary["valid_ai_run"] in (None, True) else
                f"\n\n**NOT A VALID AI-MODE RUN:** only {summary['ai_readings']} of {readings} message readings came "
                "from the AI (needs 80%). Most answers came from the rules, so this measures the rules, not the AI."),
             ""]
    if mode != "rules":
        lines += ["## Score by model", "", "| Answered by | Scenarios | Passed | Score |", "|---|---|---|---|"]
        for name, b in sorted(by_model.items(), key=lambda kv: -len(kv[1]["scenarios"])):
            k = len(b["scenarios"])
            lines.append(f"| {name} | {k} | {b['passed']} | {round(100 * b['passed'] / k)}% |")
        lines += ["", "\"mixed\" means the free quota ran out mid-scenario and another model took over. "
                  "\"rules only\" means no AI answered in that scenario.", ""]
    lines += ["| Scenario | Group | Probe | Answered by | Result | What failed | Trace (first failing event) |",
              "|---|---|---|---|---|---|---|"]
    for r in results:
        what = "; ".join(f"turn {f['turn']}: {f['check']}" for f in r["failures"]) or ""
        tr = f"`{r['trace_id']}`" + (f" #{r['first_failing_event']['seq']}" if r["first_failing_event"] else "")
        lines.append(f"| {r['id']} | {r['group']} | {'yes' if r['probe'] else ''} | {r['answered_by']} | {'pass' if r['passed'] else '**FAIL**'} | {what} | {tr if not r['passed'] else ''} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:5]))
    for r in results:
        if not r["passed"]:
            print(f"FAIL {r['id']}: " + "; ".join(f["check"] for f in r["failures"]))
    print(f"wrote {out.with_suffix('.json')} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
