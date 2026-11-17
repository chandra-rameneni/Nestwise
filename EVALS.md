# IntentGuard P0: test results and observed failures

**Run:** 2026-11-17, Python 3.13.1, macOS, `python -m pytest -q`
**Result:** **44 passed, 2 skipped, 0 failed.**
**Configuration:** rule-based intent extractor (`INTENTGUARD_LLM=off`, set by `tests/conftest.py`). The 2 skipped tests call Claude and need an `ANTHROPIC_API_KEY`, which wasn't available here.

> What this does and doesn't show: these results come from a synthetic catalog and a deterministic extractor. They show that the policy, approval, checkout and tracing logic behave as specified for the constructed cases. They don't measure Claude's extraction accuracy, real-world task completion or user value. Passing a finite test suite doesn't make the system safe in general.

## Coverage against the master plan's P0 catalog

| Group | Scenarios | Covered by an executed test | Notes |
|---|---|---|---|
| A: Intent (INT-01…08) | 8 | 8 | Tested against the **rules** extractor only. Matching Claude tests exist but were skipped. |
| B: Catalog (PRD-01…10) | 10 | 10 | |
| C: Checkout (BUY-01…08) | 8 | 8 | BUY-04 is tested both within budget (approval still invalidated) and over budget. |
| D: Traces (OBS-01…06) | 6 | 5 | **OBS-05 is not done**: failed eval cases aren't yet linked to their traces automatically. |
| E2E-01…03 | 3 | 3 | Run with the rules extractor. |
| **Total** | **35** | **34** | |

Tests not in the original catalog that were added along the way: changing constraints invalidates an existing approval, a product that was never recommended can't be put in the cart, the sofa width is unknown, the critical trace events appear in order, and "4k" is read as ₹4,000.

## Observed failures (from actually running the code)

| ID | First upstream failure | Customer impact | Fix | Regression test |
|---|---|---|---|---|
| F-001 | `catalog.search` matched keywords against product **descriptions**, so "gaming laptop" matched KM-009, a keyboard described as being "for laptops". | Asking for a product that isn't in the catalog returned a keyboard recommendation instead of "not in catalog" (PRD-03). | Keyword search now matches title and category only. | `test_prd03_unknown_product_not_invented` |
| F-002 | Streamlit chat rendered single newlines as spaces, so the cart summary ran together on one line. | Cosmetic. The cart total was still shown. | Line breaks are now converted for Markdown. | Manual UI check only |

## Failure taxonomy (starting set)

Wrong intent · lost constraint across turns · wrong data join · unsupported compatibility claim · stale approval used · unauthorised action · duplicate order · misleading answer when nothing is eligible · tool error hidden · **keyword over-match (F-001)**.

## Not done yet (honest gaps)

- Claude extraction hasn't been run. The code path (`intent.extract_llm`, structured outputs on `claude-opus-5-5`) is written but untested against the live API. Next step: set a key, run `pytest -m llm`, then extract a sample of ~20 varied requests and hand-label the fields.
- No review of LLM traces yet. The method in the master plan (§8) starts once real model traces exist.
- No LLM-written explanations. Recommendation text is a deterministic template built from catalog fields; that's a deliberate P0 choice.
- OBS-05 (linking a failed eval to its trace), P1 workflows, and real data are all still to do.
