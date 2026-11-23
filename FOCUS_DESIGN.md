# Nestwise: conversation and focus design (draft for PM review, 2026-11-21)

**Goal:** the shopper always sees which product the assistant is talking about, picks products with a tap instead of typing names, and can work with several products at once. The assistant never has to guess "which one".

## 1. The one idea: a shared "focus"

The **focus** is the product or products the conversation is about right now. The screen and the agent share the same focus, so there are no hidden guesses.

- You set the focus by tapping a product: on a card, a "Which one?" button, or by opening a product page.
- The focus is always visible in a bar above the message box.
- Every question applies to what's in focus.

## 2. What you see

```
┌ Shopping assistant ─────────────────── AI on ─┐
│  …chat…                                        │
│  ┌──────────────────────────────┐              │
│  │ ☑ HomeTown CIAZ Sectional     │ ₹14,900     │  ← tap to select
│  │   ✓ 3 seats ✓ 182 cm  [Add to cart]          │
│  └──────────────────────────────┘              │
│  ┌──────────────────────────────┐              │
│  │ ☐ Durian Leatherette Sofa     │ ₹17,680     │
│  └──────────────────────────────┘              │
│                                                │
│  Talking about: [CIAZ ×]   + add another       │  ← focus bar
│  [ Ask about the CIAZ…                 ] Send  │
└────────────────────────────────────────────────┘
```

1. **Select on every result card.** A checkbox, up to 3 products. A selected card gets a coloured border.
2. **Focus bar** above the input:
   - "Talking about: CIAZ" or "Comparing: CIAZ · Durian";
   - an × on each to remove it;
   - the input hint changes to "Ask about the CIAZ…".
3. **Empty focus** shows: "Select a product above, or tell me what you're looking for."
4. **"Which one?" becomes buttons:** [CIAZ] [Durian] [Both]. One tap answers it, so you never type a name again.
5. **Every answer about a product carries a small tag**, like "About: CIAZ", so scrolling back always shows which product each answer was for.
6. **Product page:** the focus starts as that product. You can add others from "+ add another", which lists recently shown products.
7. **The cart stays separate.** Selecting is not buying. "Add to cart" and "Approve" work as today.

## 3. Behaviour rules

| # | Rule |
|---|---|
| F1 | A question about a product applies to the focus. With 1 in focus, it gets one answer. With 2 or 3, it gets one answer per product, side by side, and never "which one?". |
| F2 | No focus, and the question needs a product? Show the product buttons (F4). Tapping one sets the focus and answers the question. |
| F3 | Naming a shown product in text ("the durian") moves the focus to it, and the bar updates, so you can see the agent understood. |
| F4 | A new search shows new results and clears the focus. The bar empties, so it's visible, not a surprise. |
| F5 | "Buy this" or "add to cart" with products in focus adds exactly those. Approval of the exact cart is still required. |
| F6 | "Compare", or any question with 2+ in focus, gets one table: price, delivery, size, seats, material. |
| F7 | The focus survives page changes and restarts (saved like the chat), and "New chat" clears it. |
| F8 | The agent never acts on a product that isn't in focus or named. Every reply says which product it's about. |

## 4. How the agent works (behind the screen)

- **One conversation state** replaces today's ten separate memory slots:
  - the products shown;
  - the focus;
  - the cart;
  - the requirements;
  - the last question.
  The screen and the agent read and write the same state.
- **The AI understands; code checks and acts.** The AI gets the message, the focus, the shown products and the last few turns. It returns one action: search, ask about the focus, buy, compare, show more, change a requirement, store policy, or small talk.
  - Code checks every product the AI names is shown or in focus, then runs the action. Facts, prices, policy and the cart stay in code, as today.
- **When the AI isn't available ("basic mode"):**
  - Taps and buttons work fully, because they need no understanding.
  - Simple typed questions still work.
  - Anything unclear gets an honest reply: "I'm in basic mode right now. Tap a product or use the buttons, or try again in a minute." No more confident wrong guesses.

## 5. Keeping the AI on (needs your OK)

The free online AI runs out of quota, which is why you mostly see "Rules (AI busy)". The fix is a **free AI model running on your Mac**, through Ollama on your own machine:
- no account, no credits, no quota;
- it's added to the existing chain, after the online models;
- it needs a one-time download of about 2 GB (Llama 3.2 3B) to 5 GB (Qwen 2.5 7B, smarter, slower).

I'd test which one is fast enough before anything else is built on it.

## 6. How we'll know it works

- **Whole-conversation tests, not single replies.** Each test is a script of taps and messages:
  - search → select 2 → "installation?" → both answers;
  - "what about the durian" moves the focus;
  - restart the store → the focus is still there;
  - …about 30 scripts.
- **Browser tests** for the focus bar, the card checkboxes and the "which one" buttons.
- **Your manual check** using the same scripts, before any commit.

## 7. Build order (fits the remaining weekly usage)

| Step | What | Rough size |
|---|---|---|
| 1 | You approve this design, then I update the PRD | small |
| 2 | Conversation state + focus (backend), with conversation tests | medium |
| 3 | Card checkboxes, focus bar, "which one" buttons, "About:" tags (frontend), with browser tests | medium |
| 4 | Honest basic mode | small |
| 5 | Local AI model (after your OK to download) | small to medium |

Steps 1 to 4 should fit before your Sunday 4:30 pm reset. Step 5 can follow.

**Not in this round:** saved wishlists, comparing more than 3, and voice.
