# Nestwise store policies (demo)

**Status:** **approved by the PM 2026-11-19** · **Date:** 2026-11-19 · **Used by:** PRD block B41
**These are demo policies for a demo store.** They are not Flipkart's or any real retailer's policies. Orders in this demo are not real: no payment is taken and nothing ships.

The assistant answers store questions **only** from this page and names the section it used (for example "From: Damaged in delivery"). If a question isn't covered here, it says so; it never makes a policy up. Each section has a short ID the code checks, like a listing field.

**How to review:** for each section, check it's what you want the store to promise. Values marked ⚙ are choices I made from what Indian home stores typically offer; change any of them.

---

### P1. Damaged in delivery
If your order arrives damaged, tell us within **⚙ 48 hours** of delivery, with a photo of the damage and the packaging. We'll send a free replacement, or give a full refund if a replacement isn't available. You don't pay for the return pickup.

### P2. Installation
Some products (mostly furniture) come with free installation; the product page says so. Installation is done by the brand's service partner, usually within **⚙ 72 business hours** of delivery. If the installer damages the product or your home during installation, tell us within **⚙ 48 hours** and we'll arrange a repair or replacement of the product at no cost. Damage to your home is handled by the brand's service partner.

**Installation must be done by the brand's service partner.** If you install the product yourself, or someone else does, **the warranty becomes void**, and damage caused during that installation isn't covered.

### P3. Returns
- Home décor, home furnishing and kitchen & dining: return within **⚙ 10 days** of delivery if unused and in the original packaging.
- Furniture: returns only if it's damaged, defective or not what you ordered (wrong item, colour or size), reported within **⚙ 10 days** of delivery. Change-of-mind returns aren't accepted for furniture, because of its size and assembly.
- Not returnable: products that have been assembled and used, customised items, and bedsheets or pillow covers taken out of their sealed packaging.
- **No-return products:** some small, low-value items can't be returned at all (for example bird houses and small showpieces). Their product page says **"No returns"**. These are items **under ₹500** that are bird houses, or home décor showpieces, candles and fragrances, festive décor, and wall stickers and decals.
  - **The only exception:** if a no-return product arrives broken, send a photo as proof within **⚙ 48 hours** of delivery. A person reviews it, and if it's valid we send **a replacement. No refund is given** for these items.

### P4. Refunds
Once a return is picked up and checked, the refund goes back to the original payment method within **⚙ 5–7 business days**. Delivery charges are refunded if the return is because of our mistake or damage, and not otherwise.

### P5. Cancellations
You can cancel free of charge any time **before the order is shipped**. After it ships, cancel by refusing the delivery or by starting a return (P3).

### P6. Order limits
Minimum order: 1. Maximum per product: what's in stock, up to **⚙ 5** of the same product per order. For larger quantities, contact us (P10).

### P7. Payment
This is a demo store: no real payment is taken. *(When Razorpay test-mode checkout is added, this section will list the test payment methods: cards, UPI, net banking and wallets.)* Cash on delivery: **⚙ not offered.**

### P8. Warranty
Warranty is given by the brand, not by the store, and the product page shows it where the listing has it. The warranty is void if the product wasn't installed by the brand's service partner (P2). To claim, contact the brand's service centre with your order details; we'll help if the brand doesn't respond within **⚙ 7 days**. If a listing shows conflicting warranty details, the assistant says it's unclear rather than picking one.

### P9. Delivery
We deliver across India. The delivery time and charge are shown on each product (simulated in this demo). Large furniture may take longer to remote areas.

### P10. Contacting us
For anything not covered here, contact our support team. *(Demo: there's no real support team yet. A hand-off from the assistant to a person is planned, see PRD B42.)*

---

**How the assistant uses this page:** only for questions about these store rules (PRD B41). Questions about a product's own details are answered from its listing; requests about an actual order (a refund, a return) go through the order checks in PRD B45, which apply these rules to the customer's own order.
