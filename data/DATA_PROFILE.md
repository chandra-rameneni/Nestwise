# Flipkart Products dataset: what's actually in it

**Profiled:** 2026-11-17, from the downloaded file (not from the Kaggle description).

| Item | Value |
|---|---|
| Source | Kaggle `PromptCloudHQ/flipkart-products`, version 1, by PromptCloud |
| Licence | **CC BY-SA 4.0**: attribution required, and anything derived from it (our normalised catalog) must use the same licence |
| Downloaded | 2026-11-17 with `kagglehub` 1.0.3, no login needed. Archive 5.5 MB. |
| File | `data/raw/flipkart/flipkart_com-ecommerce_sample.csv`, 38,114,963 bytes, SHA-256 `56f8f699c9e847356666c2eab3c3ab1244340f6a98ad08e39ea2199ebe993ad1` (not committed to git) |
| Rows | 20,000 (2 duplicate `pid`s; many repeated product names) |
| Crawled | 2015-12-01 to 2016-06-28. **Prices are about 10 years old and historical, not live.** |

## Columns and how complete they are

| Column | Empty or "not available" | Notes |
|---|---|---|
| uniq_id, pid, product_name, product_url, product_category_tree, image, description | 0% | `pid` is the Flipkart product ID |
| retail_price, discounted_price | 0.4% | Whole rupees, parse cleanly |
| brand | **29.3%** | Brand-preference logic can't be applied to these |
| product_rating, overall_rating | **90.8%** | Effectively unusable |
| product_specifications | 0.1% | Ruby-hash text (`"key"=>"…", "value"=>"…"`) that needs a parser |
| is_FK_Advantage_product | 0% | true for 785 rows |
| Stock, delivery time, shipping cost | **Not in the data** | Must be simulated and labelled as simulated |

## Category coverage

Top-level categories: Clothing 6,198 · Jewellery 3,531 · Footwear 1,227 · Mobiles & Accessories 1,099 · Automotive 1,012 · Home Decor 929 · Beauty 710 · Home Furnishing 700 · Kitchen & Dining 647 · Computers 578 · Watches 530 · …

## Fit with the master plan's demo journeys

| Journey | Supported by real data? | Evidence |
|---|---|---|
| **Mac-compatible wireless keyboard + mouse combo** (core demo) | **No** | No keyboard-and-mouse combos. About 5 standalone keyboards (wired or tablet) and a few wireless mice. Where an OS is listed it's Windows only (for example "OS Supported: Windows 7/8/8.1/10"). |
| **Mobile phones** | **No** | "Mobiles & Accessories" contains only tablet and mobile **accessories** (cases, holders, cables). No handsets. |
| **Sofa with seats and room fit** (E2E-02) | **Yes, best fit** | 71 sofa rows (47 unique names). 60 have **Seating Capacity**, 66 have **Width** (in mm), 64 have Depth. Some rows are sofa covers, which need filtering out. |
| General search, compare and buy | Partly | Plenty of products, but mostly clothing and jewellery. Specs vary a lot by category. |

## Conclusions

1. The real data can support a **sofa-led** demo with verifiable seat and width constraints. Missing widths are a real-world case for "unknown is not eligible".
2. The **keyboard demo can't use this data**. Keeping it means either a labelled synthetic subset or a different dataset.
3. Phone searches will correctly come back as "not in catalog" even after the data is loaded.
4. Every price must be shown as a historical 2015–16 price. Stock, delivery and shipping stay simulated.
