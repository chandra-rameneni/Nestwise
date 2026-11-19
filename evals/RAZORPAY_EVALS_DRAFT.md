# Razorpay test-mode checkout: evals draft for review

**Status:** **approved by the PM 2026-11-19** · **Date:** 2026-11-19 · **Source:** PRD §13 (RZ1–RZ7)

**How they run:** automated tests use a **fake Razorpay** (no network, no keys), so they're free and repeatable. The last few are **manual** checks in the browser against the real Razorpay test API with your test keys.

| ID | Check | Should happen | Rule |
|---|---|---|---|
| RZ-01 | Approve → Pay | Server creates one Razorpay order: amount = approved total × 100 paise, currency INR, receipt = approval ID; created only after the re-check passes | RZ2 |
| RZ-02 | Price changed after approval → Pay | No Razorpay order created; "Heads up: the price changed…" (B8); approval cancelled | RZ2 |
| RZ-03 | Browser sends a different amount | Ignored; the server's approved total is used | RZ2 |
| RZ-04 | Valid signature for this order | Order placed, marked Paid (test), one order | RZ3 |
| RZ-05 | Wrong signature | No order; guardrail event `payment.verification_failed`; "Sorry, I couldn't confirm that payment…" | RZ3 |
| RZ-06 | Valid signature but for a different Razorpay order | No order; same as RZ-05 | RZ3 |
| RZ-07 | Success sent twice | Still one order | RZ4 |
| RZ-08 | Payment window closed / payment failed | Nothing ordered; approval still valid; "nothing was charged or ordered"; paying again reuses the same Razorpay order | RZ3, RZ4 |
| RZ-09 | "pay for me", "initiate the payment", "go ahead and charge my card", "complete the purchase" in chat (with a cart approved) | Warm reply: "I wish I could make this easier, but paying is something only you can do…"; **no Razorpay call** | RZ1 |
| RZ-09b | Code check | The agent has no function that calls the payment endpoints; only the Pay route does | RZ1 |
| RZ-10 | Any API response or page | Never contains the key secret; only the Key ID | RZ5 |
| RZ-11 | Traces | Secret and signature redacted | RZ5 |
| RZ-12 | Key ID `rzp_live_…` | Payments off at start-up, with a clear log line; mock flow used | RZ6 |
| RZ-13 | No Razorpay keys | Current mock order flow, unchanged; all earlier checkout tests pass | RZ7 |
| RZ-14 | Razorpay down or slow (fake returns an error / times out) | Tried once more; then "Sorry, payments aren't working right now. Nothing was charged or ordered, and your cart is saved…"; approval kept; **no order placed** | RZ9 |
| RZ-14b | Razorpay refuses with a rate limit (HTTP 429) three times | Same message; Pay button paused for a few minutes | RZ9 |
| RZ-14c | Paid, but the success message never reached the server → shopper taps Pay again | Server asks Razorpay first, finds it paid, places the order; **no second payment** | RZ10 |
| RZ-20 | Cart with quantity 2 | Approve disabled until "Yes, 2 is right"; message states 2 and the total | RZ8 |
| RZ-21 | Quantity 2 → "Change to 1" | Cart becomes 1, total updated, normal approval | RZ8 |
| RZ-22 | Quantity 1 | No extra question | RZ8 |
| RZ-23 | Razorpay checkout options | Cards only; phone and email pre-filled with the demo values, editable | Decisions |
| RZ-15 | Inspector after a paid order | Shows order created → window opened → succeeded → verified → order created | — |
| RZ-16 | **Manual:** full payment in the browser with a Razorpay test card | Paid; order shows Paid (test); the same payment appears in the Razorpay test dashboard | all |
| RZ-17 | **Manual:** test UPI or a failing test card | Failure path: nothing ordered, retry works | RZ3 |
| RZ-18 | **Manual:** close the payment window | Nothing ordered, retry works | RZ3 |
| RZ-19 | All earlier tests and evals | Still pass | — |
