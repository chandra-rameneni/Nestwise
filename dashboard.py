"""Observability dashboard (PRD §14, approved by the PM 2026-11-19): counts across all chats, from the traces.

Every number comes from trace events; every "needs attention" row links to its trace. Only chats whose trace says
source 'store' count by default (eval runs on request; tests and old unlabelled traces never). No secrets: traces
are redacted when written, and this module only reads a fixed set of fields.
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import tracing

STRUGGLE = {"NOT_IN_LISTING": "Don't know", "CHALLENGE": "Challenged a reply", "FRUSTRATED": "Frustrated",
            "CATCH_ALL": "Didn't understand", "UNCLEAR": "Didn't understand", "OFF_TOPIC": "Off-topic",
            "STUCK_RECOVERY": "Stuck, changed approach"}
SAFETY = {"policy_refusal": "Tricks refused", "payment_request_refused": "“Pay for me” refused",
          "payment.verification_failed": "Payments not verified", "untrusted_text_flagged": "Product text flagged",
          "qa.answer_rejected": "AI answers rejected (bad citation)"}
_cache: dict = {}
CACHE_S = 60


def _ts(e: dict) -> datetime:
    return datetime.fromisoformat(e["ts"])


def load(trace_dir: Optional[Path] = None, include_eval: bool = False, since: Optional[datetime] = None,
         use_cache: bool = True) -> list[list[dict]]:
    """Every trace (as a list of events) from the chosen sources, newest first."""
    trace_dir = Path(trace_dir or tracing.TRACE_DIR)
    key = (str(trace_dir), include_eval, since.isoformat() if since else None)
    hit = _cache.get(key)
    if use_cache and hit and hit[0] > time.monotonic():
        return hit[1]
    sources = {"store", "eval"} if include_eval else {"store"}
    out = []
    for f in trace_dir.glob("*.jsonl"):
        if since is not None and datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < since:
            continue
        try:
            with f.open() as fh:
                first = json.loads(fh.readline() or "{}")
                if (first.get("attrs") or {}).get("source") not in sources:
                    continue
                events = [first] + [json.loads(line) for line in fh if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        if since is not None and _ts(events[0]) < since:
            continue
        out.append(events)
    out.sort(key=lambda ev: ev[0]["ts"], reverse=True)
    _cache[key] = (time.monotonic() + CACHE_S, out)
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def _pct(a: int, b: int) -> Optional[float]:
    return round(100 * a / b, 1) if b else None


def _percentile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    v = sorted(values)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))])


def _fallback_reason(attrs: dict) -> str:
    tried = " ".join(attrs.get("tried") or attrs.get("tried_first") or [])
    if "429" in tried or "busy recently" in tried:
        return "free quota / busy"
    if "Timeout" in tried or "time budget" in tried:
        return "too slow"
    if "schema" in tried or "not JSON" in tried:
        return "bad AI reply"
    return "other"


def summary(trace_dir: Optional[Path] = None, period: str = "7d", include_eval: bool = False,
            use_cache: bool = True) -> dict:
    since = {"today": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
             "7d": datetime.now(timezone.utc) - timedelta(days=7), "all": None}.get(period)
    traces = load(trace_dir, include_eval, since, use_cache)
    chats = [t for t in traces if any(e["name"] == "user.message" for e in t)]
    msgs = ai = fast = fallback = 0
    reasons = Counter()
    times: list[float] = []
    qa_total = dont_know = 0
    struggle, safety = Counter(), Counter()
    unanswered: Counter = Counter()
    unanswered_example: dict = {}
    cancelled = Counter()
    funnel = Counter()
    paid_orders = paid_amount = orders = 0
    attention = []
    for t in chats:
        sid = t[0]["trace_id"]
        names = {e["name"] for e in t}
        last_user, last_user_ts, last_page = None, None, None
        for e in t:
            n, a = e["name"], e.get("attrs") or {}
            if n == "user.message":
                msgs += 1
                last_user, last_user_ts, last_page = a.get("text", ""), _ts(e), a.get("page")
            elif n == "intent.extracted":
                ex = a.get("extractor", "")
                if ex.startswith("llm"):
                    ai += 1
                elif ex in ("fast_path:product_question", "rules_policy_route"):
                    fast += 1
                elif "fallback" in a:                    # the AI was configured but didn't answer
                    fallback += 1
                    reasons[_fallback_reason(a)] += 1
            elif n in ("answer_about_product",):
                qa_total += 1
            elif n == "agent.response":
                if last_user_ts is not None:
                    times.append((_ts(e) - last_user_ts).total_seconds() * 1000)
                    last_user_ts = None
                codes = a.get("reason_codes") or []
                hit = [STRUGGLE[c] for c in codes if c in STRUGGLE]
                for label in dict.fromkeys(hit):
                    struggle[label] += 1
                if "NOT_IN_LISTING" in codes:
                    dont_know += 1
                if hit and last_user:
                    if any(c in codes for c in ("NOT_IN_LISTING", "CATCH_ALL", "UNCLEAR")):
                        k = _norm(last_user)
                        unanswered[k] += 1
                        unanswered_example.setdefault(k, last_user)
                    attention.append({"ts": e["ts"], "trace_id": sid, "page": last_page, "said": last_user[:200],
                                      "reply": (a.get("message") or "")[:240], "why": hit[0]})
            elif n == "stuck_recovery":
                struggle[STRUGGLE["STUCK_RECOVERY"]] += 1
            elif n in SAFETY:
                safety[SAFETY[n]] += 1
            elif n == "approval.invalidated":
                r = str(a.get("reason", ""))
                kind = ("price or stock changed" if re.search(r"PRICE|STOCK|STALE|CHANGED_SINCE", r) else
                        "quantity or items changed" if re.search(r"quantity|item|new cart", r) else
                        "requirements changed" if "constraint" in r else "other")
                cancelled[kind] += 1
            elif n == "order.created":
                orders += 1
                if a.get("paid"):
                    paid_orders += 1
                    paid_amount += a.get("total_inr") or 0
        funnel["chats"] += 1
        if names & {"recommendation", "search_catalog"}:
            funnel["searched"] += 1
        if names & {"cart.created", "cart.item_added"}:
            funnel["added to cart"] += 1
        if "approval.granted" in names:
            funnel["approved"] += 1
        if "payment.window_opened" in names:
            funnel["payment opened"] += 1
        if "order.created" in names:
            funnel["ordered"] += 1
    attention.sort(key=lambda r: r["ts"], reverse=True)
    understood = ai + fallback
    return {
        "period": period, "include_eval": include_eval, "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline": {"chats": len(chats), "messages": msgs,
                     "ai_share_pct": _pct(ai, understood), "ai_replies": ai, "rules_fallbacks": fallback,
                     "shortcuts_by_design": fast, "fallback_reasons": dict(reasons),
                     "reply_ms_typical": _percentile(times, 0.5), "reply_ms_slowest_10pct": _percentile(times, 0.9),
                     "dont_know_pct": _pct(dont_know, qa_total), "dont_know": dont_know, "product_answers": qa_total,
                     "orders": orders, "paid_orders": paid_orders, "paid_amount_inr": paid_amount},
        "struggles": dict(struggle.most_common()),
        "top_unanswered": [{"question": unanswered_example[k], "count": c} for k, c in unanswered.most_common(10)],
        "safety": {**{v: safety.get(v, 0) for v in SAFETY.values()},
                   **{f"Approvals cancelled: {k}": v for k, v in cancelled.items()}},
        # A strict funnel: each step needs the one before. "Searched" isn't a step (shoppers can buy straight from
        # a product page), so it's reported beside the funnel instead.
        "funnel": [{"step": s, "count": funnel.get(s, 0)} for s in
                   ("chats", "added to cart", "approved", "payment opened", "ordered")],
        "searched_chats": funnel.get("searched", 0),
        "needs_attention": attention[:25],
    }


# INTENTGUARD_CANDIDATES_FILE keeps a rehearsal store's clicks out of the real file (demo/record_walkthrough.py).
CANDIDATES = Path(os.environ.get("INTENTGUARD_CANDIDATES_FILE") or Path(__file__).parent / "evals" / "candidates.jsonl")


def add_candidate(item: dict, path: Path = CANDIDATES) -> dict:
    """The loop (PRD §14): save a real failure for the PM to review and turn into an eval. Nothing else changes."""
    row = {"added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           **{k: str(item.get(k, ""))[:300] for k in ("trace_id", "page", "said", "reply", "why")}}
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def trace(trace_id: str, trace_dir: Optional[Path] = None) -> Optional[list[dict]]:
    if not re.fullmatch(r"tr_[0-9a-f]{12}", trace_id or ""):
        return None
    f = Path(trace_dir or tracing.TRACE_DIR) / f"{trace_id}.jsonl"
    if not f.exists():
        return None
    return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
