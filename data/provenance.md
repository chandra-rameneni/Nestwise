# Data provenance

**Catalog in use:** `data/catalog.json`, version `synthetic-v1`, hand-written on 2026-11-17.

## Why it's synthetic

The plan's first choice was the Kaggle *Flipkart Products* dataset (`PromptCloudHQ/flipkart-products`). It was **not downloaded or inspected**: this machine has no Kaggle credentials (`~/.kaggle` is missing), and the deadline didn't leave time to sort out access, licensing and data cleaning. A small synthetic catalog was used instead, as the plan's fallback allows.

## What is real and what isn't

| Field | Status |
|---|---|
| Brand names (Logitech, HP, Dell, Zebronics, Portronics) | Real brands, used **only** to test brand-preference logic. |
| Model names, product IDs, descriptions | Invented. Every model name contains "Demo". |
| Prices, shipping, stock, delivery days | Invented **and** simulated. They change during the demo (price-change and out-of-stock buttons). |
| Specs (`macos_compatible`, seats, width) | Invented. `null` means unknown, and unknown never counts as meeting a requirement. |
| Orders | Mock only (`MOCK-…` IDs). No payment, no merchant, no shipping. |

The catalog is built to test edge cases. Each product exercises one rule, for example: over budget (KM-002), compatibility unknown (KM-003), not compatible (KM-004), out of stock (KM-005), too slow (KM-006), a prompt injection in the description (KM-008), and a sofa width that's unknown (SF-003).

## Swapping in real data later

Keep the same four sections (`products`, `specs`, `prices`, `inventory`), joined by `product_id`. For each source attribute, record the source dataset, its version and its licence. Historical dataset prices must stay labelled as historical, never presented as live.
