# IntentGuard: test results, evals and observed failures

**Last run:** 2026-11-18, Python 3.13.1, macOS.

| Check | Result | How to reproduce |
|---|---|---|
| Unit, acceptance and API tests | **109 passed, 2 skipped, 0 failed** | `.venv/bin/python -m pytest -q` |
| Scenario evals (rules mode), before the iteration | **35/39** (core 29/30, probes 6/9) | `evals/results/20261118T015110Z_rules.md` |
| Scenario evals (rules mode), after the iteration | **39/39** (core 30/30, probes 9/9) | `evals/results/20261118T015248Z_rules.md` |
| Scenario evals with Claude | **Not run.** No `ANTHROPIC_API_KEY` on this machine. | `.venv/bin/python evals/run_evals.py` with a key set |
| Manual browser walkthrough of both journeys | Done 2026-11-18 | README demo script |

> **What this does and doesn't show.** Every result above comes from the **rule-based extractor**. The tests run on the real catalog, plus a synthetic fixture for safety cases. They show that search, the "not sold here" rule, eligibility, approval, checkout, recovery and tracing behave as the PRD specifies **for these constructed cases**. They don't measure Claude's accuracy, real shoppers' success rate, or business value.
>
> The 39/39 is **not a held-out score**: I fixed the code against the four scenarios that failed, so they now pass by construction. The next honest measurement is a fresh set of phrasings, ideally run through Claude. Passing a finite set of tests doesn't make the system safe in general.

## Scenario evals (`evals/`)

- `scenarios.json`: 39 short shopper conversations on the real catalog, each with the outcome the PRD says is correct.
  - 30 **core** scenarios cover the PRD journeys.
  - 9 **probes** use phrasings the rules weren't written for ("what's the cheapest…", "I'll take it", "something to sit on", a product with no price), to look for weaknesses.
- `run_evals.py`: runs each scenario in its own session, with its trace saved to `traces/`. Every failed check names its trace ID and **the first event that went wrong**. That's OBS-05, now done.
- `annotations.csv`: notes from reviewing the failing traces (and two passing ones), with the first failure upstream, a category, severity and status. The annotator was the AI assistant, so these **need a human to confirm them**.

### Iteration 1: what the first run found and what changed

| Scenario | What the shopper saw | First failure upstream (from the trace) | Severity | Fix |
|---|---|---|---|---|
| BT-06 | "Buy this" on a listing with **no price** crashed, instead of giving an answer | The rule check let a product with no price into a cart (it only checked price when a budget was stated) | **High:** breaks "never a cart without an exact total" | A missing price is now always `PRICE_UNKNOWN` (not eligible), so it can't reach a cart |
| LS-06 | "What's the cheapest 2 seater sofa that fits 1.5 m" → "We don't sell that" | "What's the cheapest …" wasn't recognised, so the product was lost | High | Phrasings like "the cheapest / best …" are recognised, and a known product type always reaches the search |
| CL-03 | "Something to sit on" → "We don't sell sit on" | The vague phrase was taken as a product name | Medium | "Something / anything …" now gets the "What product?" question |
| PQ-07 | "Is it microwave safe?" also listed "Freezer Safe" | The spec lookup matched the generic word "safe" in every "… Safe" field | Low | Generic field words no longer match on their own |

Each fix has a regression test (`test_eval_*` in `tests/test_store_agent.py`).

## Observed failures, all sources

| ID | Source | First failure upstream | Customer impact | Status and regression test |
|---|---|---|---|---|
| F-001 | P0 tests | Keyword search matched product descriptions ("gaming laptop" matched a keyboard "for laptops") | Wrong recommendation | Fixed: `test_prd03_unknown_product_not_invented` |
| F-002 | P0 UI | Streamlit merged line breaks | Cosmetic | Fixed, then superseded (Streamlit retired) |
| F-003 | User report | "mobile" labelled "not a shopping request" | Generic reply, loop | Fixed properly by R1: `test_na01_*`, `test_na02_*` |
| F-004 | Phase 1 | Search ranked sofa covers above sofas | Covers recommended first | Fixed (D8): `test_sofa_matches_are_sofas_and_covers_are_only_related` |
| F-005 | Phase 1 | "mobile" matched mobile-stand showpieces | "Not sold" never fired | Fixed (D8): `test_mobile_is_not_sold_even_though_mobile_stands_mention_it` |
| F-006 | Phase 1 | The product name was stored as a category | Wrong categories | Fixed: `test_product_name_is_not_kept_as_a_category` |
| F-007 | Phase 2 | 21 ARRA sofas list impossible widths (7–85 cm for 2–7 seats) | "A 7-seater fits 2 m" | Fixed (D10): `test_implausible_listed_width_is_not_relied_on` |
| F-008 | Phase 2 | "not sure" read as a product | "We don't sell not sure" | Fixed: `test_cl01_*` |
| F-009 | Phase 2 | A non-answer after a question got the generic reply | Loop shape | Fixed (R2): `test_cl01_*` |
| F-010 | Phase 2 | A fit limit from one question leaked into the next | Wrong kind of answer | Fixed: `test_implausible_listed_width_is_not_relied_on` |
| F-011 | Phase 3 browser | "Do you sell mobiles?" → "We don't sell do sell mobiles" | Garbled answer | Fixed: `test_na01b_question_phrasing` |
| F-012 | Phase 3 browser | The chat panel grew and dragged the page | Hard to use | Fixed (CSS); manual check |
| F-013 | Phase 3 browser | Recommendation buttons lost after changing page | Had to ask again | Fixed; manual check |
| F-014 | Phase 3 browser | "Is it waterproof?" → "doesn't say", though the care instructions say "Do not use wet cloth" | True but less helpful | **Open:** re-test with Claude |
| F-015 | Eval BT-06 | Product with no price allowed into a cart | Crash; safety rule not enforced | Fixed: `test_eval_bt06_*` |
| F-016 | Eval LS-06 | "What's the cheapest …" lost the product | "Not sold" for sofas | Fixed: `test_eval_ls06_*` |
| F-017 | Eval CL-03 | Vague phrase taken as a product | "We don't sell sit on" | Fixed: `test_eval_cl03_*` |
| F-018 | Eval PQ-07 | Generic word matched unrelated fields | Extra field in the answer | Fixed: `test_eval_pq07_*` |
| F-020 | User browser test, 2026-11-18 | Anything the rules parser doesn't recognise is treated as a product name: "write a song", "what is 2×2", "bla bla", "sofaa", "you are useless" all get "We don't sell …". Logged as `NOT_SOLD_HERE`, so they can't be told apart from real "not sold" cases. | Confusing reply; off-topic messages hidden in the logs | **Open:** PRD §6A blocks B3, B12, B15, B17 |
| F-021 | Trace review of F-020 | A ₹30,000 sofa budget from earlier in the session was attached to "write a song" | Requirements leak into unrelated requests | **Open:** PRD R9, block B10 |
| F-022 | Manual check, 2026-11-18 | "a sofa and a coffee table" asks only about the sofa; the coffee table is dropped without saying so | Part of the request ignored | **Open:** PRD block B13 |
| F-023 | Manual check, 2026-11-18 | Follow-ups aren't applied to the current product: "sofa" then "2 seater" → "We don't sell seater"; "only leather" → "We don't sell only leather"; answering "2" to the seats question isn't understood | The shopper can't narrow a search step by step | **Open:** PRD R9, block B19 |
| F-019 | Trace review (LS-05) | No synonyms: "couch" won't find products named "sofa" | Not-sold answer for couches once the width is given | **Open:** synonyms are deliberately out of scope (CATALOG_REPORT known limits) |

## Failure taxonomy (from the failures above)

| Category | Failures |
|---|---|
| Request misunderstood (vague phrase, question phrasing, lost product) | F-003, F-008, F-011, F-016, F-017 |
| Search matched the wrong thing (over-match, accessory, no synonym) | F-001, F-004, F-005, F-019 |
| Bad source data trusted | F-006, F-007 |
| Unsafe action allowed (cart without total) | F-015 |
| Conversation loop or repeat | F-003, F-009 |
| Context leak across turns | F-010 |
| Answer less precise or helpful than possible | F-014, F-018 |
| UI | F-002, F-012, F-013 |

## Coverage against the acceptance tests

- **Master-plan P0 (35 scenarios):** all 35 are covered by executed tests, now that OBS-05 is done. INT tests use the rules extractor; the matching Claude tests are skipped without a key.
- **PRD v2 (14 new tests, NA/CL/PQ/BT/LS/CX/PX):** all are covered on the real catalog (`tests/test_store_agent.py`, `tests/test_api.py`).

## Not done yet

- **Claude hasn't been run.** Intent extraction (`intent.extract_llm`) and product answers (`qa._ask_llm`) are written to the documented SDK patterns. They're tested only with a stand-in model answer (PQ-04), never against the live API.
  - Next step: set `ANTHROPIC_API_KEY`, then run `pytest -m llm` and `evals/run_evals.py`.
  - Then review those traces by hand and write a fresh set of probe phrasings to measure on.
- **No validated LLM judge**, and none is needed yet. All checks are code assertions.
- **The annotations need human confirmation.**
- **P1 is still to do:** refunds, order tracking, price-drop alerts, and the agent driving the listing page.
