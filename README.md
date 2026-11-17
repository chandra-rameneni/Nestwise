# IntentGuard (P0)

A constraint-aware shopping agent. You describe what you need in plain language, and it searches a catalog, rejects anything that breaks your hard requirements, explains the options using only catalog data, and asks you to approve the exact cart and total. Right before ordering it checks the price and stock again, and it places **at most one mock order**. If the price or stock changes after you approve, it stops, says what changed, offers alternatives and asks you to approve again. Every step is recorded in a trace that you can inspect in the app.

> **Demo scope:** the catalog is synthetic (see `data/provenance.md`) and prices, stock and orders are simulated. No payment is ever taken. Refund and order-tracking requests are recognised but politely deferred, because those workflows are P1.

## Run it

```bash
cd intentguard
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py          # http://localhost:8501
.venv/bin/python -m pytest -q           # 44 passed, 2 skipped (LLM tests need a key)
```

To use Claude for intent extraction, set `ANTHROPIC_API_KEY` in your shell before starting the app or tests. Never put it in a file in this repo. Without a key the app uses a rule-based extractor and says so in the sidebar and in every trace event (`extractor: rules_fallback`). To force the fallback, set `INTENTGUARD_LLM=off`.

## Demo script (about 2 minutes)

1. Type: *Find a Mac-compatible wireless keyboard and mouse combo within ₹4,000 including delivery, arriving in five days; prefer Logitech; ask before buying.* You get 3 eligible options. Open "Excluded products" to see why the other 6 were rejected (over budget, compatibility unverified or failed, out of stock, too slow, and a product with a prompt injection in its description).
2. **Select** the first option, then **Approve this exact cart** (₹2,594).
3. In the sidebar, **Change price**, then **Place mock order**. The order is blocked with `PRICE_CHANGED_SINCE_APPROVAL`, the approval is invalidated and alternatives are shown.
4. Select again, approve again, and place the order: you get one `MOCK-…` order. **Retry checkout** returns the same order rather than creating a second one.
5. Open **Agent Inspector** to see the real event chain: intent, tool calls, per-product policy checks, cart, approval, checkout gate and order.

Also try *I want to buy a sofa under ₹30,000* (it asks clarifying questions), *Where is my order?* (deferred), and *Find me a gaming laptop* (says it's not in the catalog and invents nothing).

## How it's built

| Concern | Owner |
|---|---|
| Understanding the request (intent and constraints) | Claude `claude-opus-5-5` with structured output into a Pydantic schema (`prompts/intent_v1.txt`), **or** the rules fallback |
| Catalog search and product joins | Code (`catalog.py`): bounded tools only, no SQL access for the model |
| Hard constraints, ranking, checkout gate | Deterministic code (`policy.py`). Unknown is treated as not eligible. |
| Approval and idempotent mock order | `checkout.py`. Each approval is tied to the cart, the total, the product's data version and the constraint version. |
| Flow control | `agent.py`, a code-driven workflow with a cap on tool calls per turn |
| Traces | `tracing.py`: JSONL in `traces/`, with secret-like keys redacted |

Product descriptions are never sent to the model as instructions, and instruction-like text in them is flagged in the trace.

See `EVALS.md` for the test results, the observed failures and what isn't done yet.
