# IntentGuard Home

A home-and-living web store built on **real product data** (the Flipkart Products dataset), with an AI shopping assistant on every page:

- **Listing page:** tell the assistant what you need ("a 3-seater sofa under ₹30,000 that fits 200 cm"). It recommends only products that meet every requirement it can check, shows the checks, and lists what it ruled out and why.
- **Product page:** ask about the product ("how wide is it?", "is it waterproof?"). It answers only from that listing, cites the field it used, and says "The listing doesn't say" when the listing doesn't cover something. Say "buy this" to order.
- **Not sold here:** ask for something the store doesn't carry ("mobile") and you get a plain answer, the same every time, with no loop.
- **Safe ordering:** nothing is ordered without approval of the exact cart and total. Price and stock are checked again just before the order. If anything changed, the order is stopped, explained, and you approve again. At most one mock order is ever created per approval.
- **Agent inspector:** every step the assistant took, as recorded events, at `/inspector`.

> **What's real:** product names, brands, specs, descriptions and photos are from the dataset (CC BY-SA 4.0, PromptCloud). **Prices are historical (2015–16).** Stock, delivery time and shipping are **simulated**. Orders are **mock**, and no payment is ever taken.

## Run it

```bash
cd intentguard
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -I -c "import kagglehub; kagglehub.dataset_download('PromptCloudHQ/flipkart-products', output_dir='data/raw/flipkart')"
.venv/bin/python build_catalog.py          # writes data/catalog.sqlite and data/CATALOG_REPORT.md
.venv/bin/uvicorn server:app --port 8000   # open http://localhost:8000
.venv/bin/python -m pytest -q              # 109 passed, 2 skipped (those 2 need an API key)
```

**Claude:** set `ANTHROPIC_API_KEY` in your shell before starting the server. Without it the assistant runs in **rules mode**: a rule-based parser understands requests, and product answers are read straight from the listing fields. The panel shows which mode is on. Never put the key in a file in this repo.

## Demo script (about 3 minutes)

1. **Listing page.** Click *Do you sell mobiles?* twice: you get the same plain "We don't sell mobiles" answer both times.
2. Click *Find a 3-seater sofa under ₹30,000 that fits 200 cm*. You get 2 real sofas with their checks, and 52 ruled out (open *Ruled out*: over budget, too wide, or a width the listing gets impossibly wrong).
3. **Add to cart**, then **Approve this exact cart**. Open *Demo: simulate a change*, click **Change price**, then **Place mock order**. It's stopped, explained, and the approval is cancelled. Add it again, approve, and place the order: you get one `MOCK-…` order. **Retry checkout** doesn't create a second one.
4. **Product page.** Open a sofa and ask *How wide is it?* (cites Width), *Is it waterproof?* ("The listing doesn't say"), and *Will it fit a 2 m wall?* (answered by the rule check). Then try *Show me cheaper ones like this* and *Buy this*.
5. Open **Agent inspector** to see the full event chain.

## How it's built

| Concern | Where | Owner |
|---|---|---|
| Real catalog (2,043 products), unit parsing, implausible values flagged | `build_catalog.py` → `data/catalog.sqlite` | Code |
| Search; "is this product" versus "only mentions it" (rule R1) | `catalog.py` (`find_products`) | Code |
| Understanding the request (intent, product, limits, page context) | `intent.py`, `prompts/intent_v2.txt` | Claude `claude-opus-5-5` (structured output), or the rules fallback |
| Answers about one product, with checked citations | `qa.py`, `prompts/product_qa_v1.txt` | Rule check, then Claude, then spec lookup |
| Eligibility, ranking, checkout gate | `policy.py` | Deterministic code |
| Approval and idempotent mock order | `checkout.py` | Deterministic code |
| Conversation flow and rules R1–R4 | `agent.py` | Code-driven workflow |
| Web API and pages | `server.py`, `web/` | FastAPI and plain HTML/JS |
| Traces | `tracing.py` | JSONL in `traces/` plus the inspector |

More detail:
- `PRD.md`: journeys, rules and acceptance tests.
- `DECISIONS.md`: decisions and gaps.
- `EVALS.md`: results and every failure found.
- `evals/`: scenario set, runner (`run_evals.py`), results and trace annotations.
- `data/DATA_PROFILE.md` and `data/CATALOG_REPORT.md`: the data.
