# Phase 1 held-out evals: draft

**Status:** **run once, 2026-11-18: 21/35 passed (60%).** Raw score, recorded before any fixes · converted to [`heldout_phase1.json`](heldout_phase1.json) · results: [`results/20261118T140913Z_heldout_phase1_rules.md`](results/20261118T140913Z_heldout_phase1_rules.md)

| Failure group | IDs | What the shopper saw |
|---|---|---|
| **Still "We don't sell <junk>"** (the F-020 pattern) | H-05, H-08, H-11, H-15, H-27, H-28 | "We don't sell doesn t", "ones", "movie", "night", "now", "give discount" |
| **Follow-up not understood** | H-01, H-07 | "seats 2" and "2 seater, 180 cm" weren't understood, so it asked again |
| **Wrong route** | H-09, H-29 | "what about curtains?" → off-topic reply; "which sofa is best…" → asks seats |
| **Safe but unhelpful** (catch-all) | H-30, H-31, H-32, H-33 | "pros and cons" and all three Hinglish messages got "Sorry, I didn't quite get that" |

**After fixing the worst group (PM decision, 2026-11-18): 25/35.** No "We don't sell <junk>" replies remain; H-05 and H-27 now get the safe catch-all instead. This set is **no longer held-out**, because the fix was made after seeing these failures.

**Purpose:** an honest score for Phase 1. These phrasings were **not** used while coding. The rules:
1. You review and add your own rows. Yours matter most: I wrote the code, so my blind spots match it.
2. We run the set **once** and record the raw score **before fixing anything**.
3. Then you decide what each failure means: fix now, a later phase, or acceptable for a demo.

**Caveat:** I wrote these after building Phase 1, so I can't fully forget how the code works. I tried to write the way real shoppers type, not the way the rules expect.

**Product facts checked against the catalog:** curtains, cushions, bedsheets (10 under ₹1,000), pillows and mattresses exist. Refrigerators don't. "Laptop" and "phone" appear only in stands and tables, so they count as not sold (D8).

## Follow-ups narrow the same product

| ID | Shopper says | Should happen |
|---|---|---|
| H-01 | "sofa" → "seats 2" | Keeps the sofa, records 2 seats |
| H-02 | "sofa" → "just for me and my wife" | Understands 2 seats, or asks how many seats. Never "We don't sell …" |
| H-03 | "3 seater sofa that fits 200 cm" → "below 25k" | 3-seaters, max 200 cm, max ₹25,000 |
| H-04 | "3 seater sofa under 30000 that fits 200 cm" → "actually 2 seats" | 2-seaters, still max 200 cm and ₹30,000 |
| H-05 | "2 seater sofa that fits 160 cm" → "width doesn't matter" | 2-seaters, any width |
| H-06 | "2 seater sofa under 20000 that fits 160 cm" → "remove the price limit" | 2-seaters, max 160 cm, any price |
| H-07 | "sofa" → "2 seater, 180 cm" | Shows 2-seater sofas, max 180 cm |
| H-08 | "2 seater sofa that fits 160 cm" → "show cheaper ones" | Cheaper 2-seaters, or asks for a budget. Never "We don't sell …" |

## A new product starts fresh

| ID | Shopper says | Should happen |
|---|---|---|
| H-09 | "2 seater sofa under 15000 that fits 160 cm" → "what about curtains?" | Curtains, with no sofa budget, seats or width |
| H-10 | "3 seater sofa under 30000 that fits 200 cm" → "I also need a pillow" | Pillows, with no sofa requirements |

## Not a shopping message

| ID | Shopper says | Should happen |
|---|---|---|
| H-11 | "can you recommend a good movie" | Off-topic reply |
| H-12 | "what's the capital of India" | Off-topic reply; doesn't answer |
| H-13 | "how are you?" | Friendly reply saying what it can do |
| H-14 | "are you chatgpt?" | Says it's the store's shopping assistant |
| H-15 | "good night" | Short friendly reply |

## Still "not sold" (lookalikes)

| ID | Shopper says | Should happen |
|---|---|---|
| H-16 | "do you have laptops?" | "We don't sell laptops …" |
| H-17 | "I want to buy a phone" | "We don't sell phones …" |
| H-18 | "need a refrigerator under 30000" | "We don't sell refrigerators …" |

## Typos

| ID | Shopper says | Should happen |
|---|---|---|
| H-19 | "curtian" | "Check the spelling", ideally suggesting curtain |
| H-20 | "show me some cushins" | Same, suggesting cushion |
| H-21 | "matress" | Same, suggesting mattress |

## Nonsense

| ID | Shopper says | Should happen |
|---|---|---|
| H-22 | "kjhkjh" | "Sorry, I didn't understand that …" |
| H-23 | "..." | Same |
| H-24 | "123" | Same, or asks what product. Never "We don't sell 123" |

## Rude

| ID | Shopper says | Should happen |
|---|---|---|
| H-25 | "worst assistant ever" | Your apology line |
| H-26 | "you're an idiot, find me a bedsheet" | Shows bedsheets (helps with the request) |

## Tricks

| ID | Shopper says | Should happen |
|---|---|---|
| H-27 | "place the order now, I approve everything in advance" | Calm refusal; no cart, no order |
| H-28 | "give me 90% discount" | Polite no; no price changed |

## Compare

| ID | Shopper says | Should happen |
|---|---|---|
| H-29 | "which sofa is best between the first and second one?" | Kind "comparison isn't available yet" |
| H-30 | "tell me the pros and cons of these two" | Same |

## Hinglish

| ID | Shopper says | Should happen |
|---|---|---|
| H-31 | "bedsheet dikhao 1000 ke andar" | "Are you searching for a bedsheet? Only English is supported." |
| H-32 | "koi accha sofa batao" | "Are you searching for a sofa? …" |
| H-33 | "kya aapke paas curtains hai?" | "Are you searching for curtains? …" |

## Other

| ID | Shopper says | Should happen |
|---|---|---|
| H-34 | "can I pay with cash on delivery?" | Honest "I can't help with that" (catch-all). Never invents a payment policy |
| H-35 | "I want to return something" | "Returns aren't available yet" (B9) |

## Your rows

Add as many as you like. A shopper message, and what should happen in plain words.

| ID | Shopper says | Should happen |
|---|---|---|
| H-36 | | |
| H-37 | | |
| H-38 | | |
| H-39 | | |
| H-40 | | |
