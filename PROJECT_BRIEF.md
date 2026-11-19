# Nestwise: project brief

**What:** a home-and-living web store built on real product data (the Flipkart Products dataset). It has an AI shopping agent on the listing page, which helps the shopper choose, and on every product page, where it answers questions and handles "buy this".

**Why:**
1. Evidence for the Razorpay AI Builders application: a working AI app with real tool use, guardrails, traces and tests.
2. An AI PM case study on LinkedIn: problem, decisions, trade-offs, evaluation, and limits stated honestly.

**What makes it different:**
- Answers come only from listing data and cite their source. When the data is missing, the agent says "the listing doesn't say".
- A product the store doesn't sell gets a clear "not available" and the conversation stops. No loops.
- Rules the AI can't override decide eligibility and checkout.
- Approval covers the exact cart and total, and a change in price or stock cancels it.
- Every decision is visible in a trace.

**Not claimed:** real demand, live prices, real payments, production readiness. Prices are historical (2015–16); stock and delivery are simulated; orders are mock.

**Stack:** Python, FastAPI, SQLite, plain HTML/JS, Claude (`claude-opus-5-5`, structured outputs) and pytest.

**Documents:**
- `PRD.md`: journeys, rules, acceptance tests.
- `DECISIONS.md`: decisions and gaps.
- `data/DATA_PROFILE.md`: what's in the data.
- `EVALS.md`: test results and observed failures.
- `../IntentGuard_MASTER_PLAN.md`: the original plan.

**Status (2026-11-17):** the P0 chat prototype works on synthetic data (46 tests pass). The v2 storefront PRD is awaiting the user's sign-off. The build happens in phases, each followed by a user checkpoint.
