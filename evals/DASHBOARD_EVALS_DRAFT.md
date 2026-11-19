# Observability dashboard: evals draft for review

**Status:** **approved by the PM 2026-11-19** · **Date:** 2026-11-19 · **Source:** PRD §14
Automated tests build a small set of **known** traces (for example 3 store chats and 1 eval run, with known replies, timings and orders) and check that every number on the dashboard matches what we planted. Plus a manual check in the browser.

| ID | Check | Should happen |
|---|---|---|
| DB-01 | A chat in the store | Its trace records source `store`; an eval run records `eval`; tests write no trace files |
| DB-02 | Default view with planted traces | Counts only store chats; the eval run appears only with "include eval runs" on |
| DB-03 | Period switch (today / 7 days / all) | Counts change to match the planted timestamps |
| DB-04 | AI share | Planted: 6 replies understood by the AI, 2 by the rules (1 quota, 1 timeout) → 75% AI, reasons listed |
| DB-05 | Reply time | Planted durations → correct typical (median) and slowest-1-in-10 values |
| DB-06 | "Don't know" rate | Planted: 2 of 5 product answers were "don't know" → 40% |
| DB-07 | Where it struggles | Each count matches the planted challenges, frustration, catch-alls, off-topic, stuck recoveries |
| DB-08 | Top unanswered questions | "is it waterproof?" asked 3 times in different chats → one row, count 3 |
| DB-09 | Safety | Planted tricks, "pay for me" refusals, a failed payment verification and cancelled approvals → each counted |
| DB-10 | Funnel | Planted: 3 chats, 2 searched, 2 carts, 1 approved, 1 payment opened, 1 paid → those numbers, with paid amount |
| DB-11 | Needs attention | Lists the planted failures, newest first, each with a working link to its trace in the inspector |
| DB-12 | Add to eval candidates | Appends one line (message, page, reply, trace id) to `evals/candidates.jsonl`; nothing else changes |
| DB-13 | Secrets | Dashboard data never contains the Razorpay secret, a signature or an API key, even if planted in a trace |
| DB-14 | Empty state | No store chats yet → friendly "No chats yet" message, no errors |
| DB-15 | Speed | 3,000 planted traces → loads in under 2 seconds |
| DB-16 | **Manual:** two real chats in the store (one with a "don't know" and one paid order), then open the dashboard | Both appear; the failure is in "Needs attention"; its link opens the right trace; the paid order is in the funnel |
| DB-17 | All earlier tests and evals | Still pass |
