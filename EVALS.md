# Nestwise: test results, evals and observed failures

**Last run:** 2026-11-18, Python 3.13.1, macOS.

| Check | Result | How to reproduce |
|---|---|---|
| Unit, acceptance and API tests | **222 passed, 2 skipped, 0 failed** (after Phase 3) | `.venv/bin/python -m pytest -q` |
| Scenario evals (rules mode), before the iteration | **35/39** (core 29/30, probes 6/9) | `evals/results/20261118T015110Z_rules.md` |
| Scenario evals (rules mode), after the iteration | **39/39** (core 30/30, probes 9/9) | `evals/results/20261118T015248Z_rules.md` |
| Phase 1 evals (36, PM-approved), before the code | **5/36** | `evals/results/20261118T133515Z_phase1_scenarios_rules.md` |
| Phase 1 evals, after the code | **36/36** | `evals/results/20261118T160327Z_phase1_scenarios_rules.md` (rerun after Phase 2) |
| Phase 1 fresh-phrasing check (30 new phrasings, written after the code) | **26/30** first time; the 3 Phase 1 misses fixed, 1 was correct behaviour | See "Phase 1" below |
| **Phase 1 held-out set** (35 phrasings not used while coding), run once | **21/35 (60%)**, raw, before fixes | `evals/results/20261118T140913Z_heldout_phase1_rules.md` |
| Same set after fixing the worst group | 25/35. **No longer held-out**: the fix was made after seeing these failures | `evals/results/20261118T144453Z_heldout_phase1_rules.md` |
| **Phase 2 evals** (40 conversations, PM-approved), before / after the code | **4/40 → 40/40** | `evals/results/20261118T155720Z_phase2_scenarios_rules.md` → `20261118T160325Z_…` |
| **Phase 2 held-out set** (25 phrasings written after the code), run once | **22/25 (88%)**, raw, before fixes | `evals/results/20261118T160701Z_heldout_phase2_rules.md` |
| Gemini sample (9 of the PM's observed conversations) | **9/9** behaved as expected | See "Phase 2" below |
| **Phase 3 wording evals** (14, PM-approved), before / after | **2/14 → 14/14**; every Phase 1–2 eval still passes | `evals/results/` (latest `phase3_scenarios`) |
| Scenario evals with Claude | **Not run.** No `ANTHROPIC_API_KEY` on this machine. | `.venv/bin/python evals/run_evals.py` with a key set |
| Manual browser walkthrough of both journeys | Done 2026-11-18 | README demo script |

> **What this does and doesn't show.** Every result above comes from the **rule-based extractor**. The tests run on the real catalog, plus a synthetic fixture for safety cases. They show that search, the "not sold here" rule, eligibility, approval, checkout, recovery and tracing behave as the PRD specifies **for these constructed cases**. They don't measure Claude's accuracy, real shoppers' success rate, or business value.
>
> The 39/39 is **not a held-out score**: I fixed the code against the four scenarios that failed, so they now pass by construction. The next honest measurement is a fresh set of phrasings, ideally run through Claude. Passing a finite set of tests doesn't make the system safe in general.

## Scenario evals (`evals/`)

- `scenarios.json`: 39 short shopper conversations on the real catalog, each with the outcome the PRD says is correct.
  - 30 **core** scenarios cover the PRD journeys.
  - 9 **probes** use phrasings the rules weren't written for ("what's the cheapest…", "I'll take it", "something to sit on", a product with no price), to look for weaknesses.
- `run_evals.py`: runs each scenario in its own session, with its trace saved to `traces/`. Every failed check names its trace ID and **the first event that went wrong**. That's OBS-05, now done.
- `annotations.csv`: notes from reviewing the failing traces (and two passing ones), with the first failure upstream, a category, severity and status. The annotator was the AI assistant, so these **need a human to confirm them**.

### Iteration 1: what the first run found and what changed

| Scenario | What the shopper saw | First failure upstream (from the trace) | Severity | Fix |
|---|---|---|---|---|
| BT-06 | "Buy this" on a listing with **no price** crashed, instead of giving an answer | The rule check let a product with no price into a cart (it only checked price when a budget was stated) | **High:** breaks "never a cart without an exact total" | A missing price is now always `PRICE_UNKNOWN` (not eligible), so it can't reach a cart |
| LS-06 | "What's the cheapest 2 seater sofa that fits 1.5 m" → "We don't sell that" | "What's the cheapest …" wasn't recognised, so the product was lost | High | Phrasings like "the cheapest / best …" are recognised, and a known product type always reaches the search |
| CL-03 | "Something to sit on" → "We don't sell sit on" | The vague phrase was taken as a product name | Medium | "Something / anything …" now gets the "What product?" question |
| PQ-07 | "Is it microwave safe?" also listed "Freezer Safe" | The spec lookup matched the generic word "safe" in every "… Safe" field | Low | Generic field words no longer match on their own |

Each fix has a regression test (`test_eval_*` in `tests/test_store_agent.py`).

### Phase 1 (2026-11-18): understand every message

- **Evals:** 36, drafted from PRD §6A and **approved by the PM** before any code (`evals/PHASE1_EVALS_DRAFT.md`, `evals/phase1_scenarios.json`).
- **Before / after:** 5/36 → 36/36. The original 39 evals still pass.
- **One eval changed during the work:** P1-T05 used a 160 cm width, but the catalog has no 3-seater that fits 160 cm, so it could never pass. It now uses 200 cm. The behaviour it tests is the same.
- **Fresh-phrasing check:** 30 new phrasings written after the code. 26 were right the first time. Misses:
  - "two seats please" → "We don't sell two"
  - "any width is fine" → "We don't sell fine"
  - "hi there" → "We don't sell hi there"

  These three are now fixed, with regression tests in `tests/test_phase1_evals.py`. The fourth, "dinner set under 2000" → not sold, is correct: the catalog has no dinner sets.
- **Not a held-out score.** As with iteration 1, the fixed misses now pass by construction. Rules mode only recognises the phrasings and word lists it was given; anything else goes to the catch-all, which is safe but not helpful.

### Phase 1 held-out run (2026-11-18)

- **Raw score: 21/35 (60%).** This is the honest Phase 1 number.
- **Worst group fixed** (PM decision): 6 messages still got "We don't sell <junk>" ("width doesn't matter" → "doesn t", "good night" → "night"). Now, if the leftover words include common non-product words, the agent gives the catch-all reply and keeps the shopper's current product thread. Real unsold products ("mobile", "air fryer", "phone", "refrigerator") still get "We don't sell …".
- **Still failing (10), accepted for now:**
  - Follow-ups the rules don't recognise ("seats 2", "2 seater, 180 cm", "width doesn't matter")
  - "what about curtains?" → off-topic reply
  - "which sofa is best…" → asks seats
  - "pros and cons" → catch-all
  - Hinglish beyond the word list (3) → catch-all
  - "place the order now, I approve everything in advance" → catch-all, not the refusal (safe: no cart, no order)
- **The next honest measurement needs a new held-out set**, written by someone who hasn't seen these failures.

### Phase 2 (2026-11-18): from the PM's store observations

- **Evals:** 40 conversations plus 4 UI/data checks, drafted from `OBSERVATIONS.md` and **approved by the PM**. Before / after: 4/40 → 40/40.
- **One eval check changed:** P2-B06 ("only leather") checked that every title says "leather", but some sofas have a solid wood frame with leatherette upholstery, so the name doesn't say leather even though the listing's material fields do. It now checks that every shown sofa passes the material check. Same behaviour.
- **Older evals and tests updated for the new PRD:** sofas no longer ask seats and width first (B18), so P1-T02–T04, CL-02, LS-05 and five tests now expect results. This was planned in the Phase 1 eval note. "Couch" now finds sofas (part of F-019).
- **Held-out set (25, written after the code), run once: 22/25.** Misses:
  - "dining set" → "can you show me what you found" → "We don't sell …" ("found" isn't in the show-results phrases)
  - "do you accept upi?" → off-topic reply instead of "I don't have payment information" (UPI not recognised)
  - "Lal Pet Products" → "We don't sell …" (the word "products" is dropped as filler, so the brand doesn't match)
- **Gemini sample:** 9 of the PM's own observed conversations went through Gemini (with OpenRouter as backup), and all 9 behaved as expected: results first, "200cms", "jerry", the HomeTown "fabric one", store and help questions.

### Phase 3 (2026-11-19): warm wording

- **Evals:** 14 wording checks, approved by the PM. 2/14 → 14/14. They check forbidden patterns (product codes, reason codes, "(s)", "I left out", mock order IDs) and required phrases (a warm opener, "Nothing is ordered without your approval", "Heads up" with old and new price), not exact sentences.
- **Eval checks made stricter:** text checks are now case-insensitive, so "Sorry, we don't sell…" still counts as "We don't sell". That exposed that "How many seats" also matched the new invite line ("Tell me how many seats you need"), so those checks now look for the question itself. Behaviour unchanged.
- **Six tests updated** for the new wording only (e.g. "no longer applies" → "haven't ordered").
- **Not done in Phase 3:** product names still include the dataset's model codes ("Durian BID/32625/A/1 …"). They're part of the real product name, so they stay.

### Round 2 baseline (2026-11-19): before any fixes

Evals approved by the PM: `evals/ROUND2_EVALS_DRAFT.md` → `evals/round2_scenarios.json` (48 scenarios; the 4 UI checks and 2 regression checks run separately). Held-out set written before any fix, with different phrasings and products: `evals/heldout_round2.json` (25). Each scenario is tagged R (rules only), M (model only) or RM.

| Run | Round 2 set | Held-out set | Result files |
|---|---|---|---|
| Rules mode | **6/30** (18 model-only skipped) | **1/15** (10 skipped) | `20261119T062508Z_round2_scenarios_rules`, `20261119T062509Z_heldout_round2_rules` |
| Model mode | 11/43 | 4/24 | `20261119T062522Z_round2_scenarios_gemini`, `20261119T062545Z_heldout_round2_gemini` |

- **The model-mode numbers are not a valid baseline.** Every free model was in its cool-down (today's quotas used up by testing): only 8 of 93 message readings and 6 of 52 answers came from a model; the rest were the rules. The "before" code is commit `420ee71`, so a proper model baseline can be run on it once quotas reset, before comparing.
- **Found by the baseline:** "what's the minimum and maximum order?" on a product page proposed a **cart** (the word "order" read as "buy this"). Nothing is ordered without approval, but it's wrong (O-56).
- **Weak checks found** (approved evals, changes need the PM's OK): R2-X04 passes on any different reply, even a nonsense one; R2-B08 passes trivially when the cart step fails earlier.

### Round 2 after the fixes (2026-11-19)

| Run | Round 2 set | Held-out set | Result files |
|---|---|---|---|
| Rules mode, before | 6/30 | 1/15 | `20261119T062508Z_round2_scenarios_rules`, `20261119T062509Z_heldout_round2_rules` |
| **Rules mode, after** | **30/30** | **14/15** | `20261119T065812Z_round2_scenarios_rules`, `20261119T065813Z_heldout_round2_rules` |
| Model mode, after (partial) | 39/43 | 20/24 | `20261119T064248Z_round2_scenarios_gemini`, `20261119T065225Z_heldout_round2_gemini` |

- **All earlier sets unchanged:** original 39/39, Phase 1 36/36, Phase 2 40/40, Phase 3 14/14, held-out 26/35 and 22/25. 255 tests pass.
- **Eval changes, made to match PRD changes the PM approved:** P2-H06 (cash on delivery is now answered from policy P7, not "I don't have information"), PQ-02 (B5 wording "Sorry, I don't have that detail" instead of "doesn't say").
- **The model-mode numbers are still not valid.** Even with pacing between messages (new `INTENTGUARD_EVAL_PACE_S`), every free model hit its daily limit: in the round 2 run only 9 of 34 message readings and 5 of 29 answers came from a model; the held-out run got none. All four round 2 failures were rules-fallback answers, and the three that were fallback gaps were fixed afterwards (yes/no fields like "With Mattress: No" → "Sorry, the mattress isn't included"; "kid friendly" → Suitable For; policy sentences matched by meaning). **To do when quotas reset:** run the model-mode evals on the old commit (`420ee71`, before) and the new one (after) with pacing.
- **Held-out miss (not tuned to):** H2-V01 "when will it get here?" in rules mode (phrasing the rules don't know; the model should handle it).

### Razorpay test-mode checkout (2026-11-19)

- **Automated, fake Razorpay (no network):** `tests/test_razorpay.py`, 28 tests covering RZ-01 to RZ-23 plus "Place order can't skip payment". All pass. Checked that the tests can fail: with the signature check sabotaged to always say "valid", RZ-05 failed as it should.
- **Live, real Razorpay test API, in the built-in browser:**
  - RZ-01 confirmed: a real test order was created for 2,499,900 paise (₹24,999), tagged with the approval ID; Razorpay's window showed ₹24,999, **cards only**, the demo phone pre-filled, and its "Test Mode" ribbon.
  - RZ-17 (failure path) confirmed: the card payment failed inside Razorpay; nothing was ordered, the cart and approval were kept. Found two bugs and fixed them: the failure message showed twice (Razorpay reports a failure more than once) and carried an "Approved" label.
  - RZ-18 (closed window) confirmed after the fix: one message, Pay re-enabled, no order.
  - Pay button disabled from the click until the outcome (PM request), confirmed.
  - **RZ-16 (a successful payment) confirmed live by the PM in Chrome (2026-11-19):** test card, ₹24,999 paid; the store's trace shows approval granted → Pay clicked → re-check passed → Razorpay order `order_U1ypo3ixLHuzQj` created for 2,499,900 paise → window opened → **signature verified** → order created, paid, test mode. No signature is stored in the trace. (The built-in browser blocks Razorpay's test bank pop-up, so success can't be shown there.)
- 283 tests pass in total.

### Observability dashboard (2026-11-19)

- `tests/test_dashboard.py`: 16 tests (DB-01 to DB-15 plus routes) on planted traces with known counts. Sabotage check: with the store/test label ignored, 8 tests failed as they should.
- Tests no longer write to `traces/` (they used to add thousands of files); store chats are labelled `store`, eval runs `eval`.
- **Manual (DB-16):** real chats in the store, AI mode → the dashboard showed them (13 chats today, AI share 100%, funnel 13 → 9 → 5 → 2 → 1, one challenge in "needs attention"); "Open trace" opened the right chat in the inspector.
- **Found in AI mode during the check:** O-59 (a confident guess, "not waterproof", passed the citation check) and O-60 ("do you sell mobiles?" answered with store info). Neither shows on the dashboard as a failure: it can only count what the agent admits. Both go to the model-mode evals.

### Model-mode before/after attempt (2026-11-19): not valid yet

Same exam (round 2 set and held-out set, model-mode scenarios), paced 7 s between messages, AI on, on the code before round 2 (commit `420ee71`, in a side folder) and today's code.

| Run | Score | Messages read by the AI | Fell back to rules | Answers written by the AI |
|---|---|---|---|---|
| After, round 2 | 43/43 | 11 | 8 | 17 of 29 |
| After, held-out | 21/24 | 0 | 9 | 2 of 16 |
| Before, round 2 | 11/43 | 0 | 41 | 0 of 34 |
| Before, held-out | 4/24 | 0 | 19 | 0 of 18 |

- **Not a valid AI comparison:** every free model (both Gemini keys, three OpenRouter models) returned HTTP 429 (daily limit), so the "before" runs were 100% rules. The old code in rules mode reproduced the original baseline exactly (6/30), confirming the setup is right.
- **Partial signal:** in "after, round 2", 17 of 29 answers were written by the AI and all 43 scenarios passed the voice and grounding checks.
- **Guardrail added:** the runner now labels any AI-mode run with under 80% AI readings as **NOT A VALID AI-MODE RUN**, in the results file and summary.
- **Next:** run both versions first thing after the daily quotas reset, before any other testing. Add O-59 (confident guess) and O-60 ("do you sell X" as store info) as model-mode evals, with the PM's approval.

## Observed failures, all sources

| ID | Source | First failure upstream | Customer impact | Status and regression test |
|---|---|---|---|---|
| F-001 | P0 tests | Keyword search matched product descriptions ("gaming laptop" matched a keyboard "for laptops") | Wrong recommendation | Fixed: `test_prd03_unknown_product_not_invented` |
| F-002 | P0 UI | Streamlit merged line breaks | Cosmetic | Fixed, then superseded (Streamlit retired) |
| F-003 | User report | "mobile" labelled "not a shopping request" | Generic reply, loop | Fixed properly by R1: `test_na01_*`, `test_na02_*` |
| F-004 | Phase 1 | Search ranked sofa covers above sofas | Covers recommended first | Fixed (D8): `test_sofa_matches_are_sofas_and_covers_are_only_related` |
| F-005 | Phase 1 | "mobile" matched mobile-stand showpieces | "Not sold" never fired | Fixed (D8): `test_mobile_is_not_sold_even_though_mobile_stands_mention_it` |
| F-006 | Phase 1 | The product name was stored as a category | Wrong categories | Fixed: `test_product_name_is_not_kept_as_a_category` |
| F-007 | Phase 2 | 21 ARRA sofas list impossible widths (7–85 cm for 2–7 seats) | "A 7-seater fits 2 m" | Fixed (D10): `test_implausible_listed_width_is_not_relied_on` |
| F-008 | Phase 2 | "not sure" read as a product | "We don't sell not sure" | Fixed: `test_cl01_*` |
| F-009 | Phase 2 | A non-answer after a question got the generic reply | Loop shape | Fixed (R2): `test_cl01_*` |
| F-010 | Phase 2 | A fit limit from one question leaked into the next | Wrong kind of answer | Fixed: `test_implausible_listed_width_is_not_relied_on` |
| F-011 | Phase 3 browser | "Do you sell mobiles?" → "We don't sell do sell mobiles" | Garbled answer | Fixed: `test_na01b_question_phrasing` |
| F-012 | Phase 3 browser | The chat panel grew and dragged the page | Hard to use | Fixed (CSS); manual check |
| F-013 | Phase 3 browser | Recommendation buttons lost after changing page | Had to ask again | Fixed; manual check |
| F-014 | Phase 3 browser | "Is it waterproof?" → "doesn't say", though the care instructions say "Do not use wet cloth" | True but less helpful | **Open:** re-test with Claude |
| F-015 | Eval BT-06 | Product with no price allowed into a cart | Crash; safety rule not enforced | Fixed: `test_eval_bt06_*` |
| F-016 | Eval LS-06 | "What's the cheapest …" lost the product | "Not sold" for sofas | Fixed: `test_eval_ls06_*` |
| F-017 | Eval CL-03 | Vague phrase taken as a product | "We don't sell sit on" | Fixed: `test_eval_cl03_*` |
| F-018 | Eval PQ-07 | Generic word matched unrelated fields | Extra field in the answer | Fixed: `test_eval_pq07_*` |
| F-020 | User browser test, 2026-11-18 | Anything the rules parser doesn't recognise is treated as a product name: "write a song", "what is 2×2", "bla bla", "sofaa", "you are useless" all get "We don't sell …". Logged as `NOT_SOLD_HERE`, so they can't be told apart from real "not sold" cases. | Confusing reply; off-topic messages hidden in the logs | **Fixed** (Phase 1): each kind of message has its own reply and label. Evals P1-O*, P1-Y*, P1-N*, P1-A*, P1-X* |
| F-021 | Trace review of F-020 | A ₹30,000 sofa budget from earlier in the session was attached to "write a song" | Requirements leak into unrelated requests | **Fixed** (Phase 1): a new product or an off-topic message no longer inherits or wipes requirements. Evals P1-R01, P1-R02 |
| F-022 | Manual check, 2026-11-18 | "a sofa and a coffee table" asks only about the sofa; the coffee table is dropped without saying so | Part of the request ignored | **Fixed** (Phase 2, B13) |
| F-023 | Manual check, 2026-11-18 | Follow-ups aren't applied to the current product: "sofa" then "2 seater" → "We don't sell seater"; "only leather" → "We don't sell only leather"; answering "2" to the seats question isn't understood | The shopper can't narrow a search step by step | **Fixed** (Phase 1) for seats and budget follow-ups. Evals P1-T01–T07. "Only leather" waits for the material requirement (Phase 2) |
| F-024 | PM store test, 2026-11-18 (O-2) | After a sofa question, "first show me the results" → "We don't sell results": a request about the agent's own output was read as a product name | Shopper can't get results; the store looks broken | **Fixed** (Phase 2, B31) |
| F-019 | Trace review (LS-05) | No synonyms: "couch" won't find products named "sofa" | Not-sold answer for couches once the width is given | **Partly fixed** (Phase 2): couch and settee find sofas. Other synonyms are still out of scope |

## Failure taxonomy (from the failures above)

| Category | Failures |
|---|---|
| Request misunderstood (vague phrase, question phrasing, lost product) | F-003, F-008, F-011, F-016, F-017 |
| Search matched the wrong thing (over-match, accessory, no synonym) | F-001, F-004, F-005, F-019 |
| Bad source data trusted | F-006, F-007 |
| Unsafe action allowed (cart without total) | F-015 |
| Conversation loop or repeat | F-003, F-009 |
| Context leak across turns | F-010 |
| Answer less precise or helpful than possible | F-014, F-018 |
| UI | F-002, F-012, F-013 |

## Coverage against the acceptance tests

- **Master-plan P0 (35 scenarios):** all 35 are covered by executed tests, now that OBS-05 is done. INT tests use the rules extractor; the matching Claude tests are skipped without a key.
- **PRD v2 (14 new tests, NA/CL/PQ/BT/LS/CX/PX):** all are covered on the real catalog (`tests/test_store_agent.py`, `tests/test_api.py`).

## Not done yet

- **Claude hasn't been run.** Intent extraction (`intent.extract_llm`) and product answers (`qa._ask_llm`) are written to the documented SDK patterns. They're tested only with a stand-in model answer (PQ-04), never against the live API.
  - Next step: set `ANTHROPIC_API_KEY`, then run `pytest -m llm` and `evals/run_evals.py`.
  - Then review those traces by hand and write a fresh set of probe phrasings to measure on.
- **No validated LLM judge**, and none is needed yet. All checks are code assertions.
- **The annotations need human confirmation.**
- **P1 is still to do:** refunds, order tracking, price-drop alerts, and the agent driving the listing page.

## Model-mode evals MM-01 to MM-05 (O-59, O-60), 2026-11-19

Approved by the PM. Scenarios: `evals/model_mode_scenarios.json` (AI mode only). Code checks with a fake AI: `tests/test_model_mode_fixes.py`.

- **O-59 fix:** an AI yes/no on a property the cited fields never mention is rejected; the shopper gets "I don't have that detail".
- **O-60 fix:** when the AI calls "do you sell mobiles?" store info, the rules' product search wins.
- **Code tests:** 9 new, all pass; turning either fix off makes 6 fail (sabotage check). Full suite: 333 pass, 2 skipped.
- **Real AI run:** not done yet (free quotas used up today). Runs with tomorrow's before/after comparison.

## PM manual check, 2026-11-19 (evals/MANUAL_CHECK.md)

- **Score:** 10/14 tested (71%), AI on for rows 1 to 9, out of quota after that (O-65).
- **Fails found:** O-61 and O-62 (policy questions broke in a long chat, one shared cause), O-63 (store-wide question on a product page), O-64 (robotic raw listing text).
- **Fixed:** all four. `tests/test_manual_check.py` replays the PM's whole chat as one conversation; 5 tests pass, and undoing the fixes makes 3 fail.
- **Lesson:** our scripted evals start every scenario fresh; real shoppers have long chats. Long-chat replays are now part of the tests.
- Full suite: 338 pass, 2 skipped.

## AI-mode run, 2026-11-20 (quotas reset)

Paced run with AI on: 15 s between messages, 20 s per message to reach a backup model, 60 s cool-down after a limit, payment keys off. Each scenario now records which model answered it (`answered_by` in the results).

| Suite | Score | AI share of message readings | Valid AI run? | Results |
|---|---|---|---|---|
| Model-mode MM-01 to MM-05 | 5/5 | 3 of 3 | Yes | `evals/results/20261120T042958Z_model_mode_scenarios_gemini.md` |
| **Held-out round 2** | **22/24 (92%)** | 9 of 9; 13 of 16 answers by the AI | **Yes** | `evals/results/20261120T043129Z_heldout_round2_gemini.md` |
| Round 2 (written with the code) | 42/43 | 13 of 19 (68%) | No (under 80%) | `evals/results/20261120T044036Z_round2_scenarios_gemini.md` |
| **All 72** | **69/72 (96%)** | | | |

**Score by model (all 72 scenarios):**

| Answered by | Scenarios | Passed |
|---|---|---|
| nvidia/nemotron-3.5-super-vl:free (OpenRouter) | 38 | 37 |
| gemini-3.5-flash (Gemini keys 1 and 2) | 11 | 10 |
| gemini-2.5-flash (Gemini keys 1 and 2) | 1 | 1 |
| Rules only (no AI call needed, or every model busy) | 22 | 21 |
| Ollama cloud (gpt-oss:20b, gemma4:31b) | 0 | n/a: HTTP 402, the account has no credits |

- **Gemini ran out fast:** 122 "limit reached" (429) replies across both keys, so OpenRouter's Nemotron answered most of round 2.
- **Fails:** H2-C03 (gemini-3.5-flash asked a question instead of giving the 12 cm answer: a real miss); R2-N04 and H2-N02 (the reply didn't say "sorry": wording checks, see audit finding E).
- **Not yet done:** the before/after comparison on the old code (Option B).

## Fixes, 2026-11-20

- **Audit finding A fixed:** tests and eval runs no longer depend on whether Razorpay keys are set in the shell. With keys set: 341 tests pass, 2 skipped; rules-mode scores unchanged (39/39, 36/36, 40/40, 14/14, 30/30; held-out 26/35, 22/25, 14/15). Each results file now states "Payment keys: off".
- **O-68 fixed:** "tell me about the sofa" after choosing a sofa now describes the sofa in the cart instead of repeating the search; with two sofas shown and none chosen, it asks which one. 3 new tests.

## Closing the test blind spots, 2026-11-20 (`tests/test_coverage_gaps.py`)

O-71 to O-73 were found by the PM, not by tests, because the tests followed the happy path: one well-documented product (the bed), single questions, and no browser. Four new kinds of tests:

| Kind | What it checks | Result |
|---|---|---|
| Product variety | 6 common questions on 40 products (10 per category): grounded, human wording, never treated as a search | 235/240 first run; the 5 misses were raw "Field: value." replies (O-74), fixed |
| "Did it answer the real question?" | Width has a measurement, delivery has days, installation is addressed, no unsupported waterproof verdict, material is named | Included above |
| Follow-ups | Answering "Which one do you mean?" by name, position or number; ignoring it; room size after "will it fit?"; "no" to a quantity check | 9/9 |
| Browser | Chat and sofa cards look the same after clicking through to a product page (Chrome, rules-mode copy of the store) | Pass; proven to fail with the O-72 fix switched off |

Full suite: **602 passed, 2 skipped**. Eval sets unchanged (39/39, 36/36, 40/40, 14/14, 30/30; held-out 26/35, 22/25, 14/15).

## Shopper question list, 2026-11-21 (`evals/SHOPPER_QUESTIONS.md`, `tests/test_shopper_questions.py`)

Why: the PM found "Will I get the bed with it?" failing, and a wider probe found 21 problems (O-75 to O-95). The old tests asked 6 questions written from what was built; this list asks the way shoppers do.

- **Product pages:** 30 question types × 3 wordings, each on 40 products (3,600 checks).
- **Searches:** 40, including odd wording.
- **Short chats:** 15, testing the cart and changes of mind.
- **Bugs found while reading replies:** 3 extra tests ("pillow covers" are not pillows; "bed" inside "bedsheet"; the swap message for two sofas with the same name).

**Before the fixes:** 74 of 145 tests failed. **After:** all pass. The full suite is 751 passed, 2 skipped (including a browser test that restarts the store mid-chat).

**Sabotage checks:** turning off the "cheaper" fix failed C1; turning off the product-page answers failed the mattress question on 39 of 40 products.

**Eval sets (rules mode):** 39/39, 36/36, 40/40, 14/14, 30/30. Held-out: 27/35 (H-09 newly passes, nothing newly fails), 22/25 and 14/15 (both unchanged).

**Wording changes:**
- PQ-05 and one older eval now expect the new phrasing: "Sorry, it won't fit: it's 215.9 cm wide…" instead of "No on width: the listing gives…".
- C4 was changed with a stated reason. With 3 sofas shown and 1 in the cart, "the other one" is ambiguous, so the agent asks which one instead of guessing.

**Design decision:** some questions are answered by code from the product's details, with or without the AI:
- overview, what's in the box, number of pieces;
- whether something else is included;
- handmade, colour, measurements.

So the AI can no longer claim box contents the details don't list (O-84), and these questions use no AI quota.

**Not covered yet:** these phrasings are written by Claude, not taken from real shoppers. The AI-mode run is still pending, because the free quota is used up.

## Follow-ups after a search, 2026-11-21 (`tests/test_followups.py`)

O-96 to O-109, from the PM's screenshots and a probe of 50 follow-up messages.
- **Tests:** 53, approved before code. 48 failed before the fixes, and all pass after.
- **Full suite:** 804 passed, 2 skipped.
- **Eval sets (rules mode):** unchanged at 39/39, 36/36, 40/40, 14/14 and 30/30. Held-out: 27/35, 22/25 and 14/15.

**Lesson:** a chat test has to continue the conversation (name a shown product, compare, push back, say "What?"). Checking only the first reply isn't enough.

## Conversation focus, 2026-11-21 (FOCUS_DESIGN.md)

**Tests:** 12 for rules F1 to F8 and basic mode, plus a browser test of the "Which one?" buttons, the focus bar, the card checkboxes and the "About" tags.
- **Full suite:** 817 passed, 2 skipped.
- **Eval sets (rules mode):** unchanged at 39/39, 36/36, 40/40, 14/14 and 30/30. Held-out: 27/35, 22/25 and 14/15.
