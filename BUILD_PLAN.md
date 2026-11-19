# Nestwise build plan: from PRD to code

**Status:** draft for review · **Date:** 2026-11-18
**Based on:** [`PRD.md`](PRD.md) (what the agent should do) and [`EVALS.md`](EVALS.md) (known failures)

The PRD is ahead of the code on purpose. This plan says **in what order** we close the gap, and **why that order**. Nothing is coded until you approve this plan, and each phase ends with your sign-off before the next starts.

## 1. What's not built yet

| Gap | PRD blocks | Failures |
|---|---|---|
| Off-topic, nonsense, typos, rude and unclear messages get "We don't sell …" | B3, B12, B15, B17 | F-020 |
| Follow-ups ("2 seater", "only leather") aren't applied to the current product | B19, R9 | F-023 |
| Requirements leak into unrelated requests | B10, R9 | F-021 |
| Results aren't shown until seats and width are answered | B18 | |
| Several products in one message: the second is dropped | B13 | F-022 |
| Nothing meets every requirement: no closest options shown | B21 | |
| Vague words like "wide" aren't clarified | B28 | |
| Quantity can't be set from chat | B26 | |
| Trick, language and compare requests have no designed reply | B14, B16, B27 | |
| Replies are robotic, not warm | §6A.1, B23, B25, B29 | |
| Moving between pages: what's kept isn't fully defined in code | B30 | |
| Stock isn't shared between shoppers; orders don't reduce it | B11, R10 | |
| Reason labels aren't logged, so off-topic can't be found in traces | §6A.4 | F-020 |

## 2. Why this order

Two questions decide the order: **how often shoppers hit it**, and **what other fixes depend on it**.

Most of the top gaps have the **same root cause**. The step that reads the message (`intent.py`) only knows "product request" or "not supported", so anything it doesn't recognise becomes a product name. That one weakness causes F-020 (off-topic → "We don't sell …"), F-023 ("2 seater" → "We don't sell seater") and F-021 (a budget sticks to "write a song"). Fix how messages are understood first, and the later phases build on solid ground.

## 3. Phases

### Phase 1: Understand every message *(highest impact)* — **signed off by the PM 2026-11-18** (approved evals 36/36; held-out 21/35 raw, 25/35 after fixing the worst group; remaining failures accepted, see EVALS.md)
- **Goal:** every message is sorted into the right kind before anything else happens.
- **Kinds of message:** new product request · refinement of the current product · product question · buy · greeting or thanks · off-topic · nonsense · possible typo · rude · trick · other language · compare · several products · refunds and tracking.
- **The shopping thread (R9):** requirements are kept per product. A refinement adds to them; a new product starts fresh; nothing leaks into unrelated messages.
- **Reason labels:** every reply records its label in the trace (§6A.4).
- **Fixes:** F-020, F-021, F-023. **Blocks:** B3, B10, B12, B14, B15, B16, B17, B19, plus recognising B13 and B27.
- **Also:** removing a requirement ("forget the width"), and basic Hinglish: check the product with the shopper before searching.
- **Files:** `intent.py`, `prompts/intent_v3.txt` (new version; v2 is kept), `agent.py` routing, `tracing.py`.

### Phase 2: Better results *(rescoped 2026-11-18 from the PM's 23 store observations)* — **signed off by the PM 2026-11-19** (evals 40/40; held-out 22/25 raw; PM testing found O-24 to O-29, all fixed)

The free model (D11) now handles most *misreading*. Phase 2 fixes the *decisions*, in two parts.

**2a. Stop getting stuck** (what the PM hit most):
- **Search first (B18):** no required questions; show results with seats, width and price, then invite narrowing. Fixes O-1, O-3, O-7.
- **"Show me the results" (B31):** runs the current search. Fixes O-2, O-5.
- **Replies to the agent's question (B32):** numbers, measurements, "no space", "doesn't matter". R2 covers the whole thread. Fixes O-13, O-15.
- **Failed searches don't change memory (B37).** Fixes O-12, O-21.
- **Help and store questions (B35).** Fixes O-22, O-23.
- **Stuck detection (B36).** Fixes O-4.
- **UI and data:** replace the "Do you sell mobiles?" button (O-8); stop the buttons covering results (O-10); the badge shows when the agent has fallen back to rules; a colour in the brand column counts as "brand unknown" (O-17).

**2b. Better matching:**
- **Brand, material and product-name search (B33)**, plus "only leather" as a requirement. Fixes O-14, O-16, O-18, O-19.
- **Pointing at shown results (B34).** Fixes O-11, O-12.
- **Nothing matches (B21):** closest options. **Several products (B13). Vague words (B28). Quantity (B26).**

- **Files:** `agent.py`, `intent.py`, `prompts/intent_v4.txt`, `policy.py`, `catalog.py`, `build_catalog.py`, `web/index.html`, `web/agent.js`, `web/styles.css`.
- **Testing:** evals run in **rules mode** (free, repeatable, no daily limit). A small sample also runs through the model.

### Phase 3: Warm wording — **signed off by the PM 2026-11-19** (wording evals 14/14; all earlier evals still pass)
- Every reply matches the §6A wording and tone, including out of stock (B23), decline (B25), model down (B29), trick (B14) and compare (B27).
- From store testing: no product codes or "option(s)" in replies, products shown once (O-9); warmer off-topic and "what can you do" replies (O-6, O-20).
- **Files:** `agent.py` (reply templates), `prompts/product_qa_v2.txt`.
- This comes after Phases 1 and 2 because those change which replies exist.

### UI rebuild and speed fixes — **signed off by the PM 2026-11-19**
- New storefront to PRD §5A (hero ask box, photo category tiles, slide-over assistant, waiting steps, photo cards with checks, big Approve button). UI checks UI-01 to UI-08 pass.
- Store named **Nestwise**, navy + blue + yellow accent (D12).
- Fixed along the way: O-30 (parallel requests failed), O-31 (product questions 10–16 s → mostly about 2 s), O-32 ("do you sell X" on product pages), O-33 (Q&A prompt v2: no verdicts beyond the listing).
- Evals after the change: original 39/39, Phase 1 36/36, Phase 2 40/40, Phase 3 14/14, held-out 26/35 and 22/25. Results: `evals/results/20261119T0509*`.

### Phase 4: Pages and shared stock
- **Moving between pages (B30):** requirements apply only to the same product type; "it" on the listing page asks which product.
- **Shared stock (R10, B11):** one stock count for all shoppers, timed holds when adding to cart, and stock reduced at order time.
- **Files:** `server.py`, `catalog.py`, `checkout.py`, `agent.py`.
- This comes last because it changes how sessions share data, which is the riskiest change, and real shoppers hit it least in a demo.

### Not scheduled
- **Running in Claude mode:** blocked until an API key is set. Each phase updates the Claude prompt as well as the rules, so the Claude run can happen any time after a key exists.
- **Trace inspector filter by reason label:** after Phase 1, once labels exist.
- **Side-by-side comparison, Hindi support:** P1/P2 in the PRD.

## 4. How each phase is built

1. **Evals first.** I draft eval scenarios from the PRD blocks' *example messages* and *not this situation* lists, as a plain-words table.
2. **You review and approve the evals.** Check that the messages are realistic, add your own, and confirm the expected outcomes. Only approved evals count. Then run them: they should fail, which proves they test the gap.
3. **Code** until they pass, without breaking the existing 109 tests.
4. **A fresh check:** a few new phrasings written *after* the code, so we're not just passing our own examples (see EVALS.md, "not a held-out score").
5. **Update the PRD statuses** (Not built → Built) and EVALS.md.
6. **You check it** in the browser, then sign off. Commit after sign-off; push only when you say so.

## 5. Decision: how much the rules mode does

**Decided 2026-11-18: option B (rules do the basics).**

**Update 2026-11-18: no paid API key, so the demo runs in rules mode only.** The Claude parts stay designed but are never run live. Two cheap rules are added to Phase 1, layered on top of the catch-all:
1. **Typos:** if a word is close to a product name in the catalog ("sofaa"), reply with B12: *"I couldn't find that item. Check the spelling and try again."*
2. **Rude messages:** a short list of common insults gets B15: *"Apologies for the inconvenience. Hope you find what you're looking for."*
3. **Everything else** the rules don't recognise gets the B17 catch-all: *"Sorry, I didn't quite get that…"*, logged as `CATCH_ALL` for review.

**How much should the rules mode do?** Today there are two ways to read a message: Claude (better, but needs an API key) and a hand-written rules fallback (always available). Typos, other languages and rudeness are hard to catch with rules.

| Option | What it means |
|---|---|
| **A. Rules do everything** | Every block works without Claude. More code, and the rules grow complex and brittle. |
| **B. Rules do the basics** *(chosen)* | Rules handle the common, clear cases (refinements, greetings, off-topic, catch-all). Typos, language and rudeness are done well by Claude; in rules mode they fall to the catch-all reply. |
| **C. Claude only** | Simplest code, but nothing works without a key, and today there is no key. |
