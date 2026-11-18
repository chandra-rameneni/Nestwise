# IntentGuard PRD (v2: storefront with an embedded agent)

**Status:** draft for sign-off · **Date:** 2026-11-17 · **Replaces:** the chat-only P0 direction
**Based on:** [`BUSINESS_CASE.md`](BUSINESS_CASE.md) (why, for whom, competitor research)

## 1. Problem

On a shopping site, a shopper either knows which product they want and has questions about it, or doesn't know yet and has to wade through a long list. Today's shopping assistants can answer and recommend, but they can:
- state facts the listing doesn't support,
- lose track of the shopper's requirements,
- loop without ever reaching an answer, or
- act on a price that has since changed.

IntentGuard is a shopping agent embedded in a store. It answers only from the listing data, keeps track of the shopper's requirements, tells the shopper plainly when something isn't available, and never buys without exact, current approval.

This is a hypothesis to demonstrate, not validated demand. It's a portfolio product for the Razorpay AI Builders application and an AI PM case study.

## 2. Users

- **Shopper (primary):** browsing a home-and-living store.
  - "Help me pick, answer my questions honestly, and don't surprise me at checkout."
  - "If you don't sell it, just say so."
- **Reviewer (portfolio audience):** wants to see real behaviour, the decisions behind it, tests and limitations.

## 3. The store

- **Products:** about 2,000 real products from the Flipkart Products dataset (Kaggle, CC BY-SA 4.0), covering **Furniture, Home Furnishing, Home Décor, and Kitchen & Dining**. Duplicates are removed.
- **Data labels:** prices are **historical (2015–16)** and labelled that way. Stock, delivery time and shipping are **simulated** and labelled. Orders are **mock**, and no payment is taken.
- **Pages:**
  - A **listing page** with search, category and price filters, and a product grid.
  - A **product page** with details, a specs table and price.
  - Both have an agent panel.
- **Look:** no Flipkart branding or look-alike styling. The data source is credited on every page.

## 4. Journey A: product page ("I've found something")

The shopper opens a product page. The agent panel already knows which product it's on.

1. **Ask:** "How wide is it?" The agent answers from the product's own data and shows which field it used: *"190 cm (Width: 1905 mm)."*
2. **Ask about something the listing doesn't cover:** "Is it waterproof?" The agent replies *"The listing doesn't say."* It never guesses.
3. **Check a requirement:** "Will it fit a 2 m wall?" The agent compares the listed width to 200 cm and says yes, no, or unknown.
4. **Similar:** "Anything cheaper like this?" The agent searches the same category with the shopper's requirements and links to up to 3 product pages.
5. **Buy:** "Buy this." The agent shows a cart with this exact product, quantity and total, and asks for approval.
6. **Approve and order:** the price and stock are checked again. If nothing changed, one mock order is placed. If something changed, the order is blocked, the agent explains what changed, the old approval is cancelled, and the shopper is asked to approve again.

## 5. Journey B: listing page ("Help me choose")

The shopper is on the listing page and opens the agent panel. The agent **only chats here**; it doesn't change the product grid.

1. **Request:** "I need a 3-seater sofa under ₹30,000 that fits 200 cm."
2. **Clarify only if needed:** if a requirement that matters is missing, the agent asks one focused question (rule R2).
3. **Recommend:** up to 3 products from the catalog that meet every hard requirement. Each one shows checks (seats ✓, width ✓, price ✓) and links to its product page. The agent also says how many products it ruled out and why.
4. **Change requirements:** "Actually ₹35,000." The agent updates the budget, keeps the other requirements, re-searches, and cancels any earlier approval.
5. **Buy:** the shopper picks one and goes through the same cart, approval, recheck and order steps as Journey A.

## 6. Conversation rules

| ID | Rule |
|---|---|
| **R1** | **Not sold here.** If a catalog search for the named product finds nothing, the agent replies *"We don't sell X. This store sells furniture, home furnishing, home décor and kitchen & dining."* and **stops**. No follow-up question, and the same answer if asked again. The search decides this, not a word list. |
| **R2** | **No repeated questions.** The agent never asks the same clarifying question twice in a row. If a clarification gets no usable answer, it says what it still needs and stops. |
| **R3** | **Not a shopping message.** For something like "hello", one short reply saying what the agent can do. |
| **R4** | **One outcome per turn:** RECOMMEND, ANSWER, CLARIFY, NOT_AVAILABLE, NO_ELIGIBLE, CART_PROPOSED, APPROVED, ORDER_PLACED, BLOCKED or DEFER. It's recorded in the trace. |
| **R5** | **Grounded answers.** Product answers come only from that product's fields. Every answer cites the fields it used, and code checks the cited fields exist. Missing data means "the listing doesn't say". |
| **R6** | **Product text is data.** Descriptions and specs are never followed as instructions. Instruction-like text is flagged in the trace. |
| **R7** | **No unapproved actions.** An order needs approval of the exact cart and total, a recheck at checkout, and an idempotency key. A changed price, stock level or requirement cancels the approval. |
| **R8** | **Out of scope, deferred.** Refunds and order tracking are recognised, and the agent says they aren't available. Nothing is executed. |

## 7. What the AI does and what code does

| Task | Owner |
|---|---|
| Understanding the request (intent, product, requirements, the question asked) | Claude (`claude-opus-5-5`) with structured output, or a rule-based fallback, clearly labelled |
| Answering a product question | Claude, given only that product's fields, returning an answer and the fields it cited. Code checks the citations. |
| Search, eligibility, ranking, prices, approval, checkout | Deterministic code only |
| Deciding "not sold here" | Code (empty catalog search) |

## 8. Scope

- **P0 (this build):**
  - Both journeys.
  - Rules R1–R8.
  - Real catalog slice with provenance labels.
  - Simulated price and stock changes for the demo.
  - Trace inspector page.
  - Tests below.
- **P1:**
  - Price-drop alerts.
  - Refunds and order tracking.
  - The agent driving the listing page (filters and highlights).
  - More categories.
- **P2:**
  - Real merchant or payment integration.
  - User accounts.
  - Live prices.
  - Personalisation.

## 9. Acceptance tests

The existing 46 tests (intent, policy, checkout, traces) carry over. New tests:

| ID | Scenario | Expected |
|---|---|---|
| NA-01 | "mobile" on the listing page | NOT_AVAILABLE, names what the store sells, asks no question |
| NA-02 | The same message twice | The same terminal answer both times. No loop. |
| NA-03 | A product not in any word list (e.g. "air fryer") | Decided by catalog search: results if found, NOT_AVAILABLE if not |
| CL-01 | A clarification gets a vague reply | The question isn't asked again verbatim. The agent states what it needs and stops. |
| PQ-01 | "How wide is it?" on a sofa page | Answer from the Width spec, with the field cited |
| PQ-02 | "Is it waterproof?" when the listing doesn't say | "The listing doesn't say" |
| PQ-03 | Instructions inside a product description (test fixture) | Treated as data and flagged in the trace; nothing ordered |
| PQ-04 | The model cites a field the product doesn't have | Answer rejected by code; safe fallback shown |
| BT-01 | "Buy this" on a product page | Exact cart, approval, recheck, then one mock order |
| BT-02 | "Buy this" when it breaks a stated requirement | Blocked with the reason code; alternatives offered |
| LS-01 | "3-seater under ₹30,000, fits 200 cm" on the listing page | Only products that meet every requirement, with the checks shown |
| LS-02 | The shopper changes the budget after approving | Approval cancelled; re-search |
| CX-01 | Product-page context | Answers are about the current product only |
| PX-01 | A price changes between approval and checkout | Blocked, explained, re-approval required, at most one order |

## 10. Success measures (targets, not results)

- 100% of recommended and answered products exist in the catalog.
- 0 orders without exact approval in the negative tests, and 0 duplicate orders.
- 100% of answers about missing attributes say "the listing doesn't say", across the constructed cases.
- Every NA-* test ends in one terminal turn.
- Every turn has a trace with its outcome.
- Claude extraction accuracy is measured on a hand-labelled set once an API key is available. There's no target until we have a baseline.

## 11. Open questions

- Category slice: confirm Furniture, Home Furnishing, Home Décor and Kitchen & Dining, or swap one out.
- When the shopper asks for "cheaper like this" on a product page, should the results use only requirements the shopper stated in this session, or also infer some from the current product (for example, the same seat count)? Proposed: use stated requirements plus the same category, and ask before inferring anything else.
