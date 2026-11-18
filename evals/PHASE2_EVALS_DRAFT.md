# Phase 2 evals: draft for review

**Status:** draft, waiting for the PM's review · **Date:** 2026-11-18
**Source:** the PM's store observations (`OBSERVATIONS.md`, O-1 to O-23) and PRD blocks B13, B18, B21, B26, B28, B31–B37.
**Runs in rules mode** (free and repeatable). A small sample also runs through the free model.

**Catalog facts checked:** 55 sofas (17 at ₹20,000 or less; 18 leather or leatherette, 12 fabric); 7 Jerry's products; 30 "solid wood" products; 807 brands.

**How to review:** for each row, check that a real shopper would say it and that "Should happen" is right. Add your own at the end.

## 2a. Stop getting stuck

### Search first (B18): fixes O-1, O-7

| ID | Shopper says | Should happen |
|---|---|---|
| P2-S01 | "sofas under 20000" | Shows sofas under ₹20,000 straight away, each with seats, width and price, then one line inviting narrowing. **No questions first** |
| P2-S02 | "sofas" | Shows sofas straight away (up to 3), then invites narrowing |
| P2-S03 | "show me bedsheets" | Shows bedsheets (unchanged) |
| P2-S04 | "something to sit on" | Still asks what product (B2). Search first only applies once a product is named |

### "Show me the results" (B31): fixes O-2, O-3, O-5

| ID | Shopper says | Should happen |
|---|---|---|
| P2-R01 | "sofa" → "first show me the results" | Shows sofas. Never "We don't sell results" |
| P2-R02 | "sofas under 20000" → "share the results for the query I asked" | Shows sofas under ₹20,000 |
| P2-R03 | "3 seater sofa" → "just show me what you have" | Shows 3-seater sofas |
| P2-R04 | "show me the results" (nothing searched yet) | Asks what product. Never "We don't sell results" |

### Replies to the agent's own question (B32): fixes O-13, O-15

The agent no longer asks seats or width first (B18), so these start from a case where it still asks something, or the shopper volunteers the reply.

| ID | Shopper says | Should happen |
|---|---|---|
| P2-Q01 | "3 seater sofa" → "200cms" | 3-seaters up to 200 cm |
| P2-Q02 | "3 seater sofa" → "2 metres" | 3-seaters up to 200 cm |
| P2-Q03 | "3 seater sofa" → "200 centimeters" | 3-seaters up to 200 cm |
| P2-Q04 | "3 seater sofa that fits 200 cm" → "no space limit" | 3-seaters, any width. Never "We don't sell space" |
| P2-Q05 | "I need something" → "not sure" → "not sure" | The question isn't asked a third time; says what's needed and stops (R2) |

### Failed searches don't change memory (B37): fixes O-12, O-21

| ID | Shopper says | Should happen |
|---|---|---|
| P2-M01 | "3 seater sofa under 30000 that fits 200 cm" → "mobile" | "We don't sell mobiles", and the sofa, 3 seats, ₹30,000 and 200 cm are **still remembered** |
| P2-M02 | "dumber" → "you can find anything" | The second reply doesn't repeat "We don't sell dumber" |

### Help and store questions (B35): fixes O-22, O-23

| ID | Shopper says | Should happen |
|---|---|---|
| P2-H01 | "what can you help me with?" | Says what it can do, with 2–3 examples. Never "That's not something I can help with" |
| P2-H02 | "what can you do" | Same |
| P2-H03 | "help" | Same |
| P2-H04 | "how many products are listed here?" | "We have 2,043 products: …", with counts per category |
| P2-H05 | "what categories do you have?" | Lists the 4 categories with counts |
| P2-H06 | "can I pay with cash on delivery?" | Honest "I don't have information about payment". Never invents a policy |
| P2-H07 | "write a song" *(lookalike)* | Still the off-topic reply |

### Stuck detection (B36): fixes O-4

| ID | Shopper says | Should happen |
|---|---|---|
| P2-K01 | "I need something" → "hmm" → "whatever" | By the third reply, changes approach: examples or popular products, not the same question again |
| P2-K02 | "sofa" → "are you not capable of understanding? just show me" | A brief apology, then sofas |

### UI and data

| ID | Check | Should happen |
|---|---|---|
| P2-U01 | Suggestion buttons | No "Do you sell mobiles?"; every suggestion leads to results |
| P2-U02 | Suggestion buttons after the first message | Don't cover the results (hidden after the chat starts, or placed below) |
| P2-U03 | Badge when no model answers | Shows that the rules took over, not "AI mode" |
| P2-U04 | Petshop7 bed whose brand column says "Red" | Brand shown as Petshop7 (from the name), not "RED" |

## 2b. Better matching

### Brand, material and product name (B33): fixes O-14, O-16, O-18, O-19

| ID | Shopper says | Should happen |
|---|---|---|
| P2-B01 | "jerry" | Shows Jerry's products |
| P2-B02 | "Jerry's" | Same |
| P2-B03 | "petshop7" | Shows Petshop7 products |
| P2-B04 | "solid wood" | Shows solid wood products, and may ask which kind |
| P2-B05 | "Handiana Solid Wood Dining Set" | Shows that product |
| P2-B06 | "3 seater sofa" → "only leather" | 3-seater leather or leatherette sofas only |
| P2-B07 | "mobile" *(lookalike)* | Still "We don't sell mobiles" |

### Pointing at shown results (B34): fixes O-11, O-12

| ID | Shopper says | Should happen |
|---|---|---|
| P2-P01 | "Find a 3-seater sofa under ₹30,000 that fits 200 cm" → "I want the fabric one. When can it be delivered?" | Answers about the HomeTown CIAZ Fabric sofa: arrives in 9 days |
| P2-P02 | (same first message) → "the first one" | Picks the first sofa shown (offers the cart) |
| P2-P03 | (same first message) → "when can the hometown ciaz be delivered?" | Answers about the HomeTown CIAZ, keeping the ₹30,000 and 200 cm |
| P2-P04 | (same first message) → "the blue one" (neither is blue) | Says which ones were shown and asks which one |

### Nothing matches, several products, vague words, quantity

| ID | Shopper says | Should happen |
|---|---|---|
| P2-N01 | "2 seater sofa under 5000" | Says none match, then shows the closest options with how much over budget each is (B21) |
| P2-N02 | "bedsheets and curtains" | Results for both, in two groups (B13) |
| P2-N03 | "a sofa and a coffee table" | Sofas, plus "we don't sell coffee tables" (B13) |
| P2-N04 | "is the hometown sofa wide?" | Asks how much space the shopper has (B28) |
| P2-N05 | On a product page: "buy 2 of these" | Cart with quantity 2 and the total for 2 (B26) |

## Your rows

| ID | Shopper says | Should happen |
|---|---|---|
| P2-X01 | | |
| P2-X02 | | |

## Summary

| | Count |
|---|---|
| 2a evals | 28 |
| 2b evals | 16 |
| Total | 44 |
