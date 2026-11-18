# Catalog report: flipkart-home-v1

Built 2026-11-18 by `build_catalog.py` from the Flipkart Products CSV (CC BY-SA 4.0, PromptCloud). Prices are **historical (2015–16)**; stock, delivery and shipping are **simulated**.

- Rows in the four categories: 2,456
- Duplicates dropped (same pid, or same name and price): 413
- **Products in the store: 2,043**

## Products per category

| Category | Products | With price | With brand | Median price ₹ | Out of stock (simulated) |
|---|---|---|---|---|---|
| Home décor | 761 | 100% | 97% | 699 | 73 |
| Kitchen & dining | 639 | 100% | 56% | 299 | 64 |
| Home furnishing | 479 | 100% | 100% | 820 | 52 |
| Furniture | 164 | 100% | 100% | 1,999 | 12 |

## How often the agent can check each attribute

*Parsed* means a clean number in a standard unit. *Ambiguous* means the listing has a value but it couldn't be read safely (for example no unit, or two numbers run together); the agent treats those as unknown.

| Attribute | Furniture | Home furnishing | Home décor | Kitchen & dining | Ambiguous (all) |
|---|---|---|---|---|---|
| seats | 35% | 1% | 0% | 0% | 0 |
| width_cm | 85% | 67% | 80% | 37% | 22 |
| depth_cm | 87% | 10% | 29% | 10% | 0 |
| height_cm | 89% | 13% | 78% | 45% | 2 |
| length_cm | 9% | 65% | 9% | 1% | 1 |
| diameter_cm | 0% | 0% | 3% | 33% | 11 |
| weight_kg | 56% | 43% | 51% | 57% | 11 |
| capacity_l | 0% | 0% | 0% | 19% | 14 |
| material | 94% | 86% | 73% | 79% | 0 |
| color | 99% | 100% | 80% | 39% | 0 |

## Sample of 10 products (2–3 per category, chosen by a fixed rule: lowest pid)

| pid | Name | Brand | Category | Price ₹ (MRP) | Key attributes | Stock / delivery (simulated) |
|---|---|---|---|---|---|---|
| `BDDEH29DNAN4AKYH` | Ethnic Handicrafts Solid Wood Queen Bed | Ethnic Handicrafts | Furniture | 24,999 (39999) | width_cm=165.0, depth_cm=210.0, height_cm=30.0, weight_kg=70.0, material=Solid Wood | 21 / 5 days |
| `BDDEH29EWHWRAPWG` | Ethnic Handicrafts Solid Wood Single Bed | Ethnic Handicrafts | Furniture | 24,999 (36999) | width_cm=99.0, depth_cm=205.0, height_cm=71.0, weight_kg=29.0, material=Solid Wood | 7 / 7 days |
| `BEBE74HTZM8FQPWK` | The Bean House XXXL Bean Bag  Cover (Without Fil | The Bean House | Furniture | 1,199 (3499) | height_cm=55.9, weight_kg=3.3, color=Blue, White | 21 / 7 days |
| `BEBEGAREKEHWEHZS` | ABCD Small Bean Bag  With Foam Filling | ABCD | Furniture | 899 (2299) | width_cm=55.9, depth_cm=55.9, height_cm=83.8, weight_kg=1.0, material=Artificial Leather | 4 / 10 days |
| `ALCEJNYHRXSGBZGC` | JTC Platinum Water Dispenser Cover | JTC Platinum | Home furnishing | 235 (348) | width_cm=28.0, depth_cm=28.0, height_cm=43.0, material=PVC, color=Multicolor | 20 / 3 days |
| `APREGUT8FZF9ZJDF` | Tappu Ki Dukaan Cotton Apron Free Size | Tappu Ki Dukaan | Home furnishing | 799 (799) | material=Cotton, color=Red, type=Chef's | 2 / 6 days |
| `AIRE98PZ7PC54SRA` | Myesquire Black and White Aroma Burner Combo Lem | Myesquire | Home décor | 310 (750) | weight_kg=0.5, color=Black | 10 / 4 days |
| `AIRE98PZBVSXHCBG` | Myesquire White Brown Aroma Burner Combo Lemongr | Myesquire | Home décor | 270 (790) | weight_kg=0.5, color=White | 12 / 2 days |
| `BLBDYGA8SAAWHNVH` | Wipro 5 W LED 6500K Cool Day Light Bulb | Wipro | Kitchen & dining | 265 (375) | weight_kg=0.067, material=Polycarbonate | 21 / 4 days |
| `BLBE2GTCQEHHRMC9` | Soy Impulse LED Bulb | Soy Impulse | Kitchen & dining | 299 (699) | material=Plastic | 20 / 4 days |

## Furniture subcategories

| Subcategory | Products |
|---|---|
| Furniture > Pet Furniture | 76 |
| Furniture > Living Room > Sofas & Sectionals | 53 |
| Furniture > Bedroom Furniture > Mattresses | 8 |
| Furniture > Study & Home Office Furniture > Portable Laptop Tables | 3 |
| Furniture > Storage Furniture > Shoe Racks | 2 |
| Furniture > Kitchen & Dining Furniture > Dining Tables, Chairs & Sets > Dining Sets > Handiana Dining Sets | 2 |
| Furniture > Kids Room Furniture > Kids Tables & Seating > Kids Bean Bags | 2 |
| Furniture > Kids Room Furniture > Kids Storage > Collapsible Wardrobes | 2 |
| Furniture > Bedroom Furniture > Beds | 2 |
| Furniture > Study & Home Office Furniture > Computer Tables | 1 |
| Furniture > Seating Furniture > Outdoor & Cafeteria Chairs > RoyalOak Outdoor & Cafeteria Chairs | 1 |
| Furniture > Seating Furniture | 1 |

## Search: what counts as "we sell this"

A **match** is a product that *is* what the shopper named: the head noun of its name or its own category, so a table lamp is a lamp, not a table. **Related** products only mention the word (a sofa cover, a mobile-stand showpiece). Rule R1: no matches means *"not sold here"*, even if related items exist.

| Shopper says | Matches | Related | First match | Agent outcome |
|---|---|---|---|---|
| sofa | 54 | 10 | Durian Leatherette 2 Seater Sofa | search and recommend |
| 3 seater sofa | 54 | 0 | Durian Leatherette 2 Seater Sofa | search and recommend |
| sofa cover | 7 | 0 | Swastik Velvet Sofa Cover | search and recommend |
| bed sheet | 17 | 5 | ZAIN Polyester 3D Printed Double Bedsheet | search and recommend |
| curtain | 67 | 2 | Skipper Blends Aqua Striped Eyelet Window Cur | search and recommend |
| pressure cooker | 11 | 0 | Ultra 8 L Pressure Cooker | search and recommend |
| table lamp | 6 | 0 | Tucasa LG-295 Table Lamp | search and recommend |
| table | 4 | 195 | @home Annulus Solid Wood Dressing Table | search and recommend |
| bean bag | 2 | 3 | ORKA Leatherette XXXL Teardrop Kid Bean Bag | search and recommend |
| mobile | 0 | 3 | – | **not sold here** |
| mobile stand | 0 | 3 | – | **not sold here** |
| air fryer | 0 | 0 | – | **not sold here** |
| dining table | 0 | 35 | – | **not sold here** |

**Known limits:** "mobile stand" and "dining table" come back as not sold. The data files mobile stands as showpieces, and has dining *sets* but no standalone dining tables. Fixing that would mean synonym lists, which we have deliberately left out for now.
