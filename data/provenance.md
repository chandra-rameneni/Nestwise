# Data provenance

**Catalog in use:** `data/catalog.json`, version `synthetic-v1`, hand-written on 2026-11-17.

## Why it's synthetic

When P0 was built, the Kaggle *Flipkart Products* dataset (`PromptCloudHQ/flipkart-products`) hadn't been downloaded, so a small synthetic catalog was used instead, as the plan's fallback allows.

**Update 2026-11-17:** the Flipkart dataset has now been downloaded (no login needed) and profiled; see `DATA_PROFILE.md`. It isn't wired into the app yet. That depends on decision D1 in `DECISIONS.md`.

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
