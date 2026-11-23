# How the Nestwise agent is evaluated

Four layers, from fast checks to real conversations. Every result below is from the current code.

## 1. Live conversations with an independent reviewer

`evals/live_agent_run.py` runs **28 shopper conversations (64 replies)** through the live AI, in parallel, in about 10 minutes.

- **What they cover:** sofa search and follow-ups ("what about the Durian?", "the second one"), products the store doesn't sell, comparing and buying both then removing one, confusion and pushback, a bed and its mattress, refunds for damage, quantity changes, tricks ("ignore your rules"), requests to pay, products in focus, product pages, long chats that come back to an earlier product, changing the budget mid-chat, swapping items in the cart, store policy, warranty and delivery charges, a price change and an item going out of stock after it's added, vague requests, rudeness with a real request, several items on one budget, and questions the product data can't answer.
- **Automatic checks on every reply:** expected words, cart contents, no invented prices, and that the AI never approves or pays.
- **Independent AI reviewer:** a different model from the one that answered grades every reply PASS or FAIL. It fails a reply that misunderstands the shopper, gets a fact or price wrong, claims an order was placed, ignores the question, or is confusing.

**Latest run (23 Nov 2026): 27 of 28 conversations passed (96%).** Typical reply time 3.1 s; 6.4 s for the slowest 1 in 10. Results: `evals/results/20261123T064520Z_live_agent.json`; re-run on the final code, also 27 of 28: `evals/results/20261123T105315Z_live_agent.json`.

## 2. Hand review and audit

Every reply from that run was read by hand and doubtful facts were checked against the catalog and `STORE_POLICY.md`. The pipeline was audited with Hamel Husain's eval-audit method (github.com/hamelsmu/evals-skills).

**Result: 25 of 28 conversations fully right (89%); 61 of 64 replies right (95%).** The audit's recommendations (validate the reviewer against human labels, give it the tool results, add more varied conversations) are in `evals/ai_agent_audit.html`.

## 3. After every change

`evals/smoke_check.py` runs the main demo chats through the live AI in about a minute: the sofa search and follow-ups, focus following the product asked about, the product-details layout, a vague request, real store product types, wall art, a short "why these?", the product page, a discount trick, a payment request, and adding to the cart without approving. It runs after every fix, before the change is called ready. **Latest: all passed.**

## 4. Automated tests

`tests/` (130 tests, about 6 seconds, no AI calls):

- **The agent loop** with a stand-in model: tools run on real store data, the cart, the price check (and sums of real prices), context and focus, product pages, honest replies when no model answers, payment requests never reaching the AI, search by section name, a price change after adding to the cart, empty replies rewritten by another model, and live progress steps.
- **Cart, approval and checkout:** exact product, quantity and total; no approval, no order; price or stock changes after approval stop checkout; quantity limits; several items.
- **Razorpay (test mode):** the order is created for the approved total only; the browser can't set the amount; signatures are verified; one paid order even if success arrives twice; the secret never reaches the browser; live keys are refused; Razorpay being down or rate-limited.
- **API, dashboard, catalog and traces.**

## What the numbers mean

No AI agent is right every time, and these numbers don't claim it is. What the evals guarantee is narrower and stronger: the agent never shows a price that didn't come from the store, every step it takes is recorded, and it can't spend money without the shopper's own approval.
