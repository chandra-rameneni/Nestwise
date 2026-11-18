# Decisions, gaps and timeline

## 2026-11-17: direction changed to a storefront with an embedded agent (v2)

The user described the intended product. It's a shopping site with a listing page and product pages, and the agent sits on both: on a product page it answers questions and handles "buy this"; on the listing page it helps the shopper choose. The P0 chat-only app didn't match this. The user also hit a dead-end loop: "mobile" got the same generic reply twice. See `PRD.md`.

| # | Decision | Why | State |
|---|---|---|---|
| D1 | **Real data:** a curated home-and-living slice of the Flipkart dataset (Furniture, Home Furnishing, Home Décor, Kitchen & Dining; about 2,000 unique products) | A coherent store with the richest specs. Furniture averages 22 spec fields per product. | Decided |
| D2 | **Web storefront:** FastAPI plus plain HTML/JS. Streamlit is retired once the new site has everything it had. | It has to look and work like a real shop with page-to-page navigation | Decided |
| D3 | **Listing-page agent is chat-only.** It doesn't change the grid. | Keeps P0 simple. Driving the page is P1. | Decided |
| D4 | **Not sold here:** say so, list what the store sells, and stop (rule R1). The decision comes from an empty catalog search, not a word list. | Fixes the loop the user reported | Decided |
| D5 | **Synthetic catalog kept only as a test fixture** for safety cases the real data lacks (prompt injection, Mac compatibility) | Keeps those tests without mixing fake products into the store | Decided |
| D6 | **Product Q&A is grounded and cited:** the answer comes from that product's fields only, and code checks the citations | Prevents invented facts | Decided |
| D7 | **No deadline.** Build in phases, and the user signs off each phase. | "Follow the correct path" | Decided |
| D8 | **"We sell this" means the product IS that thing.** The head noun of its name or its own category must match; products that only mention the word (sofa covers, mobile-stand showpieces) count as related. No matches means not sold, even if related items exist. | Found in Phase 1: "mobile" matched mobile-stand showpieces, and "sofa" ranked covers above sofas | Built in Phase 1; awaiting user review |
| D10 | **Physically implausible listed values count as unknown.** A sofa width under 45 cm per seat is flagged at build time. The agent quotes what the listing says but doesn't rely on it for fit checks. | 21 ARRA sofas list 7–85 cm widths for 2 to 7 seats (F-007) | Built in Phase 2; awaiting user review |
| D11 | **No paid API. Free models:** Gemini first (added 2026-11-18), then OpenRouter free models. The model understands messages and answers product questions; the rules take over when no model answers (rate limits, invalid replies). The key lives in the user's shell profile, never in the repo. | The user won't pay for an API key (2026-11-18); rules mode alone misread too many messages (OBSERVATIONS.md) | Built 2026-11-18 (`llm.py`). 2026-11-19: an 8-second hard deadline per message and a 5-minute cool-down for busy models (O-29) |
| D9 | PRD open questions accepted as proposed: the four categories, and "cheaper like this" uses stated requirements plus the same category | User sign-off of the PRD | Decided |

## 2026-11-17: deadline removed

The user dropped the Nov 17 deadline: *"the most important thing is we need to follow the correct path."*

## What's still missing

| # | Item | Status | Blocked on |
|---|---|---|---|
| G1 | Real dataset downloaded and inspected | **Done.** See `data/DATA_PROFILE.md`. | — |
| G2 | Normalised real catalog (SQLite) with provenance for each field | **Built 2026-11-17:** 2,043 products. See `data/CATALOG_REPORT.md`. | User review of the report |
| G3 | Claude extraction and product Q&A run against the live API | Code for extraction written; Q&A not yet | User sets `ANTHROPIC_API_KEY` |
| G4 | `PRD.md` | **Drafted.** Awaiting sign-off. | User review |
| G5 | `PROJECT_BRIEF.md` | **Done** | — |
| G5b | Business case and competitor research | **Done 2026-11-18:** `BUSINESS_CASE.md` (desk research, no hands-on competitor tests) | — |
| G6 | `evals/scenarios.json`, `evals/annotations.csv` | **Done 2026-11-18** (rules mode): 39 scenarios, 35/39 before and 39/39 after iteration 1. Claude run still needed. | G3 for the Claude run |
| G7 | OBS-05: link each failed eval case to its trace | **Done 2026-11-18** (`evals/run_evals.py`) | — |
| G8 | Acceptance tests signed off by the user | In the PRD | User review |
| G9 | Fix for one-word product requests | Interim fix done (F-003); the proper fix is R1 in Phase 2 | — |
| G10 | Storefront UI (listing page, product page, inspector) | **Built 2026-11-18** (`server.py`, `web/`). Both journeys clicked through in the browser. The Streamlit `app.py` is retired. | User click-through |

## Order of work

0. PRD, brief and decisions. **User signs off.**
1. Real catalog. **User checks the catalog report.**
2. Agent changes, test-first: R1–R8, product Q&A, "buy this". User sets the API key.
3. API and storefront. **User clicks through both journeys.**
4. Evals with real Claude traces, docs, then commit and push (asking first).

## Earlier decisions (from the master plan, §10)

These still stand: one agent with an internal policy engine, deterministic hard constraints and approval, traces from the start, and honest labelling of what's real versus simulated.
