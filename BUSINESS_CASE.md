# Nestwise: business case and competitor research

**Status:** v1 · **Date:** 2026-11-18 · **Owner:** project author · **Feeds into:** [`PRD.md`](PRD.md) → code
**Evidence standard:** desk research from public sources (linked at the end). No shopper interviews; none are needed for the Razorpay submission. Figures from vendor-run surveys are marked as such and are directional, not proof.

This is the starting point of the project. It answers **why** we're building Nestwise, **for whom**, and **what other shopping assistants already do**. The PRD turns it into requirements, and the code implements the PRD. The tracker in §6 links them, so we can see what's done.

---

## 1. Summary

- **The problem:** AI shopping assistants are now everywhere (Amazon, Flipkart, Walmart, ChatGPT, Google, Perplexity), but shoppers can't trust what they say. One vendor study found the same shopping question gave **conflicting** facts (price, specs, availability) in 86% of cases. Shoppers blame the store when an AI gets it wrong.
- **The opportunity:** assistants are starting to **buy**, not just recommend (Amazon auto-buy, Google agentic checkout, Razorpay + NPCI UPI payments in ChatGPT and Claude). Once an agent spends money, a wrong fact turns into a wrong order.
- **What Nestwise is:** a shopping assistant embedded in a store. It says only what the product listing supports, checks every requirement in the open, says plainly when the store doesn't sell something, and never orders without approval of the exact cart at the current price.
- **What this project is:** a working sample, built to showcase product thinking and AI engineering for the Razorpay AI Builders application and an AI PM portfolio. It isn't built for Razorpay as a customer, and it isn't a commercial product.

## 2. Business case

### 2.1 The problem

A shopper on a large store is in one of two states:
1. **"I've found something"**, but has questions the page doesn't make easy to answer ("Will it fit my wall?", "Is it waterproof?").
2. **"Help me choose"**: hundreds of products and filters that don't express real needs ("a 3-seater under ₹30,000 that fits a 2 m wall").

AI assistants promise to help with both. In practice, they fail in five ways that cost the store trust and sales:

| # | Pain point | Evidence |
|---|---|---|
| P1 | **Invented or conflicting facts** (prices, specs, availability) | Product.ai, a company that sells AI shopping technology, asked ChatGPT, Claude, Gemini and Perplexity the same 220 shopping questions, 5 times each (about 8,800 answers), through the companies' **developer APIs**, not the consumer chat apps. In 86% of questions the answers **conflicted** on a checkable fact; for comparisons, 97%. Where a price was wrong, the median miss was $300. **Caveats:** a vendor study; "conflict" is not the same as "confirmed wrong"; Google disputed the method. **To revisit** (§7). |
| P2 | **Forgotten requirements**: the budget or size the shopper stated gets dropped a few turns later | We reproduced it ourselves (F-010 in `EVALS.md`). See §2.1.1 for why it happens. |
| P3 | **Dead-end loops**: the assistant asks the same thing again instead of saying "we don't sell that" | Found in our own P0 build ("mobile" twice gave the same generic reply; F-003) |
| P4 | **Acting on stale data**: the price or stock changes between recommendation and checkout | Prices change constantly; the agent-checkout products (Amazon auto-buy, Google, Perplexity) all have to deal with it |
| P5 | **Unclear authority**: did the shopper really approve *this* item at *this* total? | Razorpay's UPI agent payments are built around user-set limits and instant revocation, which shows the industry treats this as a core risk. See §2.1.2 for how approval works in Nestwise. |
| P6 | **Two shoppers, one item**: shopper A adds the last unit to their cart while shopper B, elsewhere, is about to buy it too | Standard e-commerce problem, made worse when an agent acts quickly for many shoppers at once. See §2.1.3. |

#### 2.1.1 Why assistants forget requirements in long chats (P2)

An LLM has no memory between messages. Each turn, the app resends the conversation so far, and the model re-reads it. Things go wrong in three ways:
- **Buried detail:** "under ₹30,000" was said five messages ago. Newer messages pull the model's attention, and it drops the old constraint.
- **Ambiguous updates:** "actually, make it bigger". Bigger than what? Does the budget still apply? The model guesses.
- **Leaking across topics:** a limit from one question gets applied to a different product (our F-010: a wall width from one sofa question applied to the next question).

**Nestwise's fix:** the requirements live in a structured record in code (budget, seats, width…), not just in the chat text. Each message updates that record explicitly, every change is logged, and changing a requirement cancels any earlier approval.

#### 2.1.2 Where the shopper approves (P5)

In Nestwise's chat panel:
1. The agent recommends products. Each card has an **Add to cart** button (or the shopper says "buy this" on a product page).
2. The agent shows the cart: one product, quantity, price, shipping and **exact total**.
3. The shopper clicks **Approve this exact cart**. The approval is tied to that cart, that total and that version of the product data.
4. The shopper clicks **Place mock order**. Code re-checks price and stock first. If anything changed, the approval is cancelled and the shopper has to approve again.

The agent can't click Approve or place an order by itself. Only those buttons do it.

#### 2.1.3 Two shoppers, one item (P6)

**What should happen:**
- Adding to cart **holds** the units for a short time (for example 10 minutes). Other shoppers see only the stock that's left.
- If shopper A holds the last unit, shopper B can't add it to a cart. The agent says it's currently unavailable and offers alternatives.
- If A's hold expires or A removes the item, the unit becomes available again.
- If there are 5 units and A holds 1, B can still buy. We only block when **all** units are held, not whenever someone has it in their cart.
- At order time, code checks the stock again, and the order goes through only if the held unit is still there. One unit can never be sold twice.

**Today's gap:** in the current build, each browser session gets its **own copy** of stock, and placing a mock order doesn't reduce stock. Two shoppers can't see each other's carts or orders. Tracked in §4 and §6.

**The cost to the business:**
- 58% of shoppers blame the retailer or brand when an AI gives wrong product information, and 16% would skip the product (Rithum, 1,046 US/UK shoppers; vendor survey).
- 60% would stop using an AI shopping agent after one mistake (ACI Worldwide / YouGov, UK).
- Yet usage is high: 70% used AI for shopping in the last three months (Rithum). **Shoppers use it but don't trust it.** That gap is the opportunity.

### 2.2 Who it's for

The shopper is the one who chats with the agent. The store is the one who **puts the agent on its website**, like Amazon with Rufus or Flipkart with Flippi. Both are users, in different ways:

| User | Job to be done | What the agent does for them |
|---|---|---|
| **Shopper** (primary; uses the chat) | "Help me find and buy the right thing without wasting time or getting surprised." | Answers questions about a product, helps choose from many, checks every requirement, shows the exact total, orders only after approval |
| **Store / merchant** (deploys the agent) | "Help my shoppers decide and buy, without the assistant giving wrong information under my name." | **Sells:** turns undecided browsers into buyers, like a good shop assistant. **Protects the brand:** shoppers blame the store when its assistant is wrong (58% in the Rithum survey), so answering only from the store's listings matters. **Cuts costly mistakes:** fewer wrong orders, returns and "it didn't fit" complaints. **Shows its work:** the trace shows exactly what the agent said and why, for support and disputes. |
| **Reviewer** (Razorpay AI Builders, hiring managers) | "Show me you can turn a fuzzy problem into a working, tested AI system." | Running code, tests, evals, traces, honest limits |

In this demo, we play the store: the agent is embedded in our sample store.

### 2.3 Why now

- **Assistants are becoming buyers.** Amazon's assistant can auto-buy at a target price. Google's AI Mode can check out on merchant sites. Perplexity has Instant Buy with PayPal.
- **India is testing the payment rails.** Razorpay, NPCI and OpenAI started a private beta of UPI payments inside ChatGPT (Oct 2025). Razorpay and NPCI announced a pilot inside **Claude** for Zomato, Swiggy and Zepto (Feb 2026). Both are **pilots for a small group of invited users**. They happen inside the ChatGPT or Claude chat, not in the Swiggy or Zepto apps, which is why most people haven't seen them. They use **UPI Reserve Pay**: the user sets aside a spending limit for a merchant once, and the agent can then pay within that limit without a UPI PIN each time.
- **Standards are forming:** Google's UCP and AP2, OpenAI and Stripe's Agentic Commerce Protocol. These cover *how* an agent pays. They don't make the agent's product advice correct.

### 2.4 Why an AI agent, and not just better filters

- Filters can't take "fits a 2 m wall with a bit of room" or "something to sit on for my balcony". Language understanding is the job the AI does well.
- **But the AI must not decide what's true or what's allowed.** Prices, sizes, stock, budget checks and approval are deterministic code. That split (AI for understanding and wording, code for facts and permissions) is Nestwise's core design choice, and directly addresses P1, P4 and P5.

### 2.5 How we'd know it works (targets, not results)

| Measure | Target | How measured |
|---|---|---|
| Prices in replies that didn't come from the store | 0 | Code check on every reply (`agent_llm._bad_prices`) and evals |
| Orders placed without approval of the exact current cart | 0 | Checkout gate, tests, evals |
| "Not sold here" requests answered without a loop | 100% | R1/R2 evals |
| Recommendations that break a stated requirement | 0 | Policy checks, evals |
| Live conversations passing, with an independent AI reviewer | 27 of 28 (96%) on 23 Nov | `evals/live_agent_run.py` |

Business measures (conversion, returns, support tickets) can't be measured in a portfolio demo. We list them as what a real pilot would track.

### 2.6 Assumptions and risks

| Assumption / risk | Impact | How we handle it |
|---|---|---|
| The product data is good enough to answer from | Answers are only as good as the listing | We say "The listing doesn't say" and flag impossible values (D10) |
| The data is 2015–16 Flipkart, so prices are old | Not a live store | Labelled historical everywhere; stock and delivery labelled simulated |
| Free AI models can be busy | Slower replies at peak times | Several providers in turn; busy models are retried until the time limit; an honest "try again" if none answers |
| Strict grounding can feel less helpful | "Is it waterproof?" → "doesn't say" even when care text hints at it (F-014) | Accept for now: honest beats helpful-but-wrong |
| Competitors move fast | Features overlap | Compete on trust and verification, not feature count |

## 3. Competitor research: how others build shopping assistants

Status as reported in public sources up to Nov 2026. Where a source was unclear, it says so.

### 3.1 Store-owned assistants (live inside one retailer's site or app)

| Assistant | What it does | How it's built (where known) | Buying and approval | Notes |
|---|---|---|---|---|
| **Amazon: Rufus → Alexa for Shopping** (US, UK, Canada, India…) | Conversational search, comparisons, review summaries, up to a year of price history, price alerts, list-to-cart from a photo of a handwritten list, scheduled tasks (restock, alerts) | Amazon's own shopping-tuned model trained on its catalog, reviews and web data | **Auto-buy** for Prime members when a target price is hit; requests stay active up to six months. Some reports say it can buy outside Amazon (not confirmed). | Reported rename to *Alexa for Shopping* in May 2026. Most mature; sets shopper expectations. |
| **Flipkart: Flippi → SLAP** (India) | Guided discovery for undecided shoppers, product comparisons, nudges | Built on OpenAI models (2023); in Jan 2026 Flipkart planned a standalone app, *Shop Like a Pro* | Recommends; buying goes through the normal app checkout | Same "help me choose" job as our listing-page agent. **SLAP is a separate, agent-first app**: the chat *is* the shop, rather than an assistant added to the existing app. Launch status not confirmed. Google is also testing Flipkart purchases inside Gemini in India. |
| **Myntra: MyFashionGPT** (India) | Natural-language fashion search instead of filters | Microsoft Azure OpenAI | Normal checkout | Shows Indian retailers buy rather than build the model |
| **Walmart: Sparky** (US, expanding) | Review summaries, recommendations, comparisons; photo or handwritten list → cart; recipes → ingredients; text, image, audio, video input | Walmart's own agent stack | Builds carts; planned auto-reorder (not confirmed shipped) | Oct 2026: six new features, Spanish and French |
| **IKEA: AI Assistant (GPT), Billie, Kreativ** | Room-based suggestions from dimensions, style and budget; stock checks; support answers; 3D room planning | ChatGPT GPT Store app (2024); Microsoft-based chatbots in some markets | Generates a link; you buy on IKEA | Closest to our home-and-living store. Uses **room dimensions**, like our "fits 200 cm" check. Current status unclear. |

### 3.2 General AI assistants that shop across stores

| Assistant | What it does | Buying and approval | Notes |
|---|---|---|---|
| **ChatGPT: Shopping Research** | Builds a buyer's guide by asking about needs and budget | **Instant Checkout** (single item, ACP with Stripe) launched 2025 and was later scaled back; ACP is now used for discovery | Even OpenAI stepped back from running checkout itself |
| **Perplexity: Shopping + Instant Buy** | Product research and comparison across merchants | **Instant Buy** with PayPal (US, Nov 2025): confirm with PayPal login or passkey; the retailer stays merchant of record | Explicit user confirmation at purchase |
| **Google: AI Mode / Gemini** | Shopping in search and chat, Universal Cart | **Agentic checkout** on merchant sites with Google Pay; built on **UCP** (whole purchase flow) and **AP2** (agent payment permission) | Co-developed with Shopify, Etsy, Wayfair, Target, Walmart |

### 3.3 Payment rails (not competitors, but where Nestwise would plug in)

| Rail | What it does | Relevance |
|---|---|---|
| **Razorpay + NPCI agentic payments** (India) | UPI payments from inside ChatGPT (Oct 2025 private beta: bigbasket, Vi) and Claude (Feb 2026 pilot, select users: Zomato, Swiggy, Zepto). User-set limits, real-time tracking, instant revoke (UPI Reserve Pay, UPI Circle). | Industry context: in a real build, a payment would sit right after Nestwise's approval step. Today it's a mock order. |
| **OpenAI ACP, Google UCP / AP2** | Standards for agent ↔ merchant checkout and payment permission | We don't implement these; we'd follow one in a real build |

### 3.4 What we learned

**Everyone has these (table stakes):**
1. Natural-language search and recommendations
2. Side-by-side product comparison
3. Review summaries
4. Price history and price alerts
5. A path to buy (from a link up to full agent checkout)

**Where the market is heading:**
- **Agents that act alone:** auto-buy at a price, scheduled restocks, list-to-cart.
- **Multimodal input:** photos, handwritten lists, voice.
- **Standard payment permission:** spending limits, revocable mandates (AP2, UPI Reserve Pay).

**Where public information is thin, so we can't claim a gap, but it's our focus:**
- **Showing the checks.** Public material rarely shows an assistant listing each requirement as pass / fail / unknown.
- **"The listing doesn't say."** The Product.ai study suggests general assistants guess rather than admit missing data.
- **Telling the shopper when the price changed** between approval and checkout, and asking again.
- **A clear "we don't sell that"** that ends the conversation instead of steering to something loosely related.
- **A reviewable trace** of every step, for the merchant.

Store-owned assistants may already do some of these internally. We haven't tested them hands-on, so these are **focus areas, not proven gaps**.

## 4. What this means for Nestwise

| Idea from research | Seen in | Decision | Status |
|---|---|---|---|
| Answer only from the listing, cite the field, admit gaps | (our differentiator; P1 pain) | **Core** | **Built** (`qa.py`) |
| Show requirement checks (pass / fail / unknown) | (our differentiator) | **Core** | **Built** (`policy.py`) |
| Room-fit checks from dimensions | IKEA | **Core** for home and living | **Built**: width, depth, height |
| Clear "we don't sell that", no loop | (our P3 pain) | **Core** | **Built** (R1, R2) |
| Exact-cart approval, recheck before ordering, one order per approval | Perplexity confirm step, AP2, UPI limits | **Core** | **Built** (`checkout.py`, checkout gate) |
| Trace of every step | (merchant need) | **Core** | **Built** (`/inspector`) |
| **Shared stock and cart holds**: two shoppers can't buy the same last unit (P6) | Standard e-commerce | **Core: add next** | **Not built.** Today each session has its own stock copy, and orders don't reduce stock. |
| **Side-by-side comparison** of 2–3 products | Amazon, Flipkart, Walmart, Perplexity | **Add (P1)**: table stakes we're missing; render the same checks per product | Not started |
| Price alerts and buy-at-target-price | Amazon | **P1**, only with a fresh approval at the target price and a spending cap | Not started |
| Spending limit and revocable approval, modelled on UPI Reserve Pay | Razorpay + NPCI, AP2 | **P1**: mirrors how agent payments are being built in India | Not started |
| Order tracking and refunds | Common in support bots (IKEA Billie) | P1 (already in the master plan) | Not started |
| Synonyms ("couch" = "sofa") | Expected by any shopper | **P1**: small fix (F-019) | Not started |
| Review summaries | Amazon, Walmart | **Skip**: the dataset has no review text, and 91% of products have no rating | — |
| Hindi and other Indian languages | Flipkart (planned), Walmart (Spanish, French) | P2: Claude can do it; needs evals per language | Not started |
| Photo or handwritten list → cart | Amazon, Walmart | P2 | Not started |
| Real payment (Razorpay test mode) | Razorpay | P2: replace the mock order | Not started |

## 5. Positioning in one line

> Other assistants compete on **how much they can do**. Nestwise competes on **whether you can trust what it says and buys**: every fact traced to the listing, every requirement checked in the open, and no order without your approval of the exact cart at the current price.

## 6. Tracker: pain point → requirement → code → proof

Update this table when anything changes. It's the reference point for "where are we?".

| Pain point | PRD requirement | Code | Proof | Status |
|---|---|---|---|---|
| P1 wrong facts | R5 grounded answers, R6 product text is data | `agent_llm.py` (tools + price check) | `tests/test_ai_agent.py`, live evals | Built |
| P2 forgotten requirements | The AI reads the whole chat and the screen; requirement changes reset approval | `agent_llm.py`, `agent.py` | live evals (N05, N06) | Built |
| P3 dead-end loops | R1 not sold here, R2 no repeat questions, R3 greeting, R4 one outcome | `agent_llm.py`, `catalog.find_products` | live evals (C02, C04, N15) | Built |
| P4 stale data | Checkout gate rechecks price, stock and data version | `policy.checkout_gate` | `test_px01`, `test_product_page_price_change_*` | Built |
| P5 unclear authority | R7 no unapproved actions; approval tied to cart, total and data version | `checkout.py` | `test_bt01`, idempotency tests | Built (mock order) |
| P6 two shoppers, one item | Shared stock, timed cart holds, stock check and decrement at order | — | — | **Not started** |
| Missing table stakes | Comparison | — | — | **Not started (P1)** |
| Measurement | Live conversations with an independent AI reviewer | `evals/live_agent_run.py` | 27 of 28 (23 Nov) | Built |

## 7. Open questions

1. What comes next: **shared stock and cart holds** (P6, a core gap), **comparison** (the biggest table-stakes gap), or **spending limit / price-alert buy** (closest to how agent payments work in India)?
2. Should the demo show a Razorpay **test-mode** payment instead of the mock order? Adds realism; needs a Razorpay test account.
3. Do we spend time on hands-on competitor testing (e.g. ask Amazon and Flipkart's assistants our eval questions)? It would turn "focus areas" into evidence.
4. **To revisit: the Product.ai study** (P1 evidence). Read the full method, and decide whether to keep it as the headline figure or replace it with stronger evidence.

### Parked thoughts (not decided yet)

- **Response scenarios:** write down how the agent should respond in specific situations (example conversations with the expected reply). Still to decide whether they belong here, in the PRD, or in their own document.
- **Agent-first app (Flipkart SLAP):** an app where the chat *is* the shop, instead of an assistant added to a normal store. Worth considering as a future direction for Nestwise.

## Sources

Accessed 2026-11-18. Secondary sources are trade press or blogs; check the primary source before quoting a figure publicly.

**Pain points and trust**
- Product.ai, the study itself, "We Asked Four AI Engines the Same 220 Shopping Questions…": https://product.ai/research/ai-shopping-divergence-study/
- Tech.co coverage of the study: https://tech.co/news/ai-shopping-assistants-not-ready-holidays
- Hyper.ai coverage, including Google's objection: https://hyper.ai/en/stories/bf5435c33f1291acbcbe3759595a689a
- Rithum survey via FashionUnited, "When AI shares incorrect information, 58 percent of shoppers blame the brand": https://fashionunited.uk/news/retail/when-ai-shares-incorrect-information-58-of-shoppers-blame-the-brand/2026032687108
- Trust gap summary (ACI Worldwide / YouGov, Synchrony): https://www.paz.ai/blog/ai-shopping-trust-gap-one-mistake

**Amazon**
- Amazon, Rufus personalised shopping features: https://aboutamazon.com/news/retail/amazon-rufus-ai-assistant-personalized-shopping-features
- PPC Land, memory, price tracking and auto-buy: https://ppc.land/amazons-rufus-ai-assistant-gains-memory-price-tracking-and-auto-buying/
- PPC Land, a year of price history: https://ppc.land/amazons-rufus-now-shows-a-full-year-of-price-history-to-50m-shoppers/
- GeekWire, Amazon unifies Alexa and Rufus: https://www.geekwire.com/2026/amazon-unifies-alexa-and-rufus-as-ai-rivals-move-into-online-shopping/
- Amazon India, Rufus launch: https://www.aboutamazon.in/news/retail/rufus-ai-shopping-assistant-launch-in-india

**Flipkart and Myntra**
- Inc42, Flippi launch: https://inc42.com/buzz/flipkart-launches-chatgpt-powered-shopping-assistant-flippi
- Apparel Resources, standalone assistant (SLAP): https://apparelresources.com/technology-news/retail-tech/flipkart-roll-standalone-conversational-ai-shopping-assistant/
- YourStory, Gemini shopping with Flipkart: https://yourstory.com/ai-story/gemini-shopping-assistant-flipkart-india
- Business Today, MyFashionGPT: https://www.businesstoday.in/technology/news/story/myntra-collaborates-with-microsoft-to-unveil-ai-powered-online-shopping-with-myfashiongpt-410366-2023-12-21

**Walmart and IKEA**
- Retail Dive, Sparky holiday features: https://retaildive.com/news/walmart-sparky-features-AI-holidays/873718
- Let's Data Science, Sparky visual search and cart generation: https://letsdatascience.com/news/walmart-adds-visual-search-and-cart-generation-to-sparky-bf067eb6
- Synthedia, IKEA GPT assistant: https://synthedia.substack.com/p/ikea-introduces-generative-ai-shopping
- Microsoft, IKEA Bulgaria's Sofia: https://news.microsoft.com/en-cee/2023/12/11/meet-sofia-the-ai-chatbot-assistant-introduced-by-ikea-bulgaria-powered-by-microsoft/

**General assistants and protocols**
- E-commerce Fastlane, ChatGPT Instant Checkout and ACP: https://ecommercefastlane.com/chatgpt-instant-checkout/
- Retail Systems, ACP expansion after Instant Checkout suspension: https://retail-systems.com/rs/OpenAI_expands_ecommerce_search_tool_following_Instant_Checkout_suspension.php
- PayPal newsroom, Instant Buy with Perplexity: https://newsroom.paypal-corp.com/2025-11-PayPal-and-Perplexity-Launch-Instant-Buy
- Google developers, Universal Commerce Protocol: https://developers.google.com/universal-commerce-protocol
- Google blog, agentic commerce tools for retailers: https://blog.google/products/ads-commerce/agentic-commerce-ai-tools-protocol-retailers-platforms
- TechCrunch, Google announces UCP: https://www.techcrunch.com/2026/01/11/google-announces-a-new-protocol-to-facilitate-commerce-using-ai-agents/

**Razorpay**
- Razorpay AI Builders: https://razorpay.com/ai-builders/
- Razorpay newsroom, agentic payments with NPCI and OpenAI: https://razorpay.com/newsroom/razorpay-npci-and-openai-come-together-to-launch-agentic-payments-ushering-in-ai-driven-commerce-at-national-scale/
- Analytics India Magazine, UPI payments on Claude for Zomato, Swiggy, Zepto: https://analyticsindiamag.com/ai-news/razorpay-npci-enable-in-chat-upi-payments-on-claude-for-zomato-swiggy-zepto/
- Razorpay blog, agentic payments for UPI on Claude: https://razorpay.com/blog/agentic-payments-and-npci/
- The Paypers, pilot with select users: https://thepaypers.com/payments/news/razorpay-and-npci-launch-agentic-payments-on-claude
