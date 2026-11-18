# Phase 3 (warm wording): draft for review

**Status:** draft, waiting for the PM's review · **Date:** 2026-11-19
**Source:** PRD §6A.1 (voice and tone), the example replies in each block, and observations O-6, O-9, O-20, O-27.
**Scope:** only the *words* of replies. No change to what the agent decides, searches or allows.

## 1. Wording rules (added to PRD §6A.1)

1. **No internal codes in shopper text:** no product IDs like `[SOFE9FS5YH6TTNJT]`, no reason codes like `BUDGET_EXCEEDED`, no "mock order MOCK-…" IDs in the sentence. They stay in the trace and the inspector.
2. **No "(s)" plurals:** "16 sofas", "1 sofa", never "option(s)". Correct grammar: "1 seat", "2 seats".
3. **Products appear once:** the reply text gives a short lead-in and a compact list (name and price). Full details (seats, width, delivery, checks) are on the product cards.
4. **One warm opener, then the point:** "Good news", "Sure", "Sorry", "No problem", "Heads up". At most 3 sentences besides the list.
5. **One closing line**, never two.
6. **Don't repeat yourself word for word.** If the same reply would be given twice in a row, the second one is shorter.
7. **Safety words stay exact.** Approval, price and order messages keep the exact total and "nothing is ordered without your approval". Warmth never removes a safety fact.

## 2. Before and after

| Situation | Today | Proposed |
|---|---|---|
| Results (B18) | "I found 16 option(s) that meet every requirement I could verify (showing the top 3 of 16): 1. Durian BID/32625/A/1 Leatherette 1 Seater Sofa [SOFE9FS5YH6TTNJT]: ₹9,209 total (₹8,710 + ₹499 delivery), arrives in 8 days, 1 seats, 56 cm wide. … I left out 38 product(s) that failed or couldn't be verified … (see details)." | "Good news, 16 sofas are under ₹20,000. Here are the 3 best value:" + compact list + cards. "Tell me how many seats you need or how much space you have, and I'll narrow these down." |
| Not sold (B1) | "We don't sell mobile. This store sells home décor, …" | "Sorry, we don't sell mobiles. We're a home and living store: furniture, home furnishing, décor and kitchen & dining." |
| Closest options (B21) | "Sorry, none of the sofa meet all your requirements. These come closest: …" | "Sorry, no 2-seater sofas come in under ₹5,000. These are the closest:" + list with "₹7,220 over your budget". |
| Cart (B7) | "Cart: 1 x Durian … [SOFE9…] Item ₹8,710 + delivery ₹499 = **₹9,209 total** … Do you approve buying exactly this cart for this total? Nothing will be ordered without your approval." | "Great choice! Durian Leatherette 1-Seater Sofa: ₹8,710 + ₹499 delivery = **₹9,209**. Arrives in 8 days. Tap **Approve this exact cart** when you're ready. Nothing is ordered without your approval." |
| Approved | "Approved: ₹9,209 for … I'll check the latest price and stock again before placing the mock order." | "Approved for ₹9,209. I'll double-check the price and stock before placing the order." |
| Order placed | "Mock order MOCK-DD0964B4 placed for …, ₹9,209 total. This is a simulation: no payment was taken and nothing will ship." | "Done! Your order for the Durian sofa (₹9,209) is placed. This is a demo, so no payment was taken and nothing will ship." |
| Price changed (B8) | (current) | "Heads up: the price changed from ₹14,900 to ₹15,400 since you approved, so I haven't ordered anything. If the new total works for you, just approve again." |
| Out of stock (B23) | (reason code text) | "Sorry, this one's out of stock right now. Here are similar ones you can order today:" |
| Declined (B25) | (current) | "No problem, nothing was ordered. If you change your mind, I'm right here and happy to pick up where we left off." |
| AI down (B29) | "I need the AI model to answer that." | "My product brain is taking a quick tea break. Try again in a moment, or have a look at the specs table on this page." |
| Off-topic, second time (O-20) | The same long reply again | "Still can't help with that one, sorry! Ask me about anything for your home." |
| "What are you capable of?" after frustration (O-6) | Cold self-introduction | "Sorry about the trouble. I can find products, answer questions about them and order with your approval. Want to pick up with the sofas under ₹20,000?" |
| Clarify product (B2) | "What product are you looking for?" | "Happy to help! What kind of product do you have in mind, for example a sofa, a bedsheet or a dining set?" *(The PRD example said "dinner set", which the store doesn't sell; changed to "dining set".)* |
| Refunds and tracking (B9) | Long explanation | "Sorry, I can't track orders just yet. I can help you find and buy products, though." |

## 3. Evals

Each eval sends a message and checks the reply's wording. The checks look for forbidden patterns and a few required words, not exact sentences.

| ID | Shopper says | Check |
|---|---|---|
| P3-W01 | "sofas under 20000" | No `[A-Z0-9]{16}` product codes; no "(s)"; no "I left out"; starts warmly ("Good news" or similar); one "Tell me" line |
| P3-W02 | "sofas under 20000" | Contains "sofas" with a number (e.g. "16 sofas"); no "1 seats" |
| P3-W03 | "mobile" | Contains "Sorry"; "mobiles" (plural); no follow-up question |
| P3-W04 | "2 seater sofa under 5000" | No reason codes (`[A-Z]+_[A-Z]+`); contains "over your budget" |
| P3-W05 | "sofas under 20000" → "the first one" | Cart reply: no product code; contains the exact total and "Nothing is ordered without your approval" |
| P3-W06 | (cart) → Approve | Contains "Approved" and the total; no "mock order" wording |
| P3-W07 | (approved cart) → Place order | Contains "Done"; no `MOCK-` ID in the text; says no payment was taken |
| P3-W08 | (cart) → Decline | Contains "nothing was ordered" and an invitation to come back |
| P3-W09 | "write a song" twice | Second reply is shorter than the first |
| P3-W10 | "I need something" | Contains "Happy to help" and "dining set" (not "dinner set") |
| P3-W11 | "where is my order" | Contains "Sorry"; at most 2 sentences |
| P3-W12 | On a product page with the model off: "what is the warranty period?" (not in specs) | If it can't answer: B5 or B29 wording, never "I need the AI model" |
| P3-W13 | (cart) → price changes → Place order | Contains "Heads up", the old and new price, and "haven't ordered" |
| P3-W14 | Out-of-stock product page → "buy this" | Contains "out of stock"; no reason code |
| P3-W15 | Every eval in Phases 1–2 | Still passes (wording changes must not change behaviour) |

## 4. Questions for you

1. **Results order:** "sofas under 20000" lists 1-seaters first, because ranking is cheapest first. For a broad "sofas" search, should it show a **mix of sizes** instead, or keep cheapest first?
2. **Compact list in the text:** keep a short name-and-price list in the reply (useful when you scroll back after changing page, where cards aren't shown again), or cards only?
