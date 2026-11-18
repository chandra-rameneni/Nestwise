"""Build data/catalog.sqlite from the Flipkart Products CSV (home-and-living slice).

Usage:  .venv/bin/python build_catalog.py [path/to/flipkart_com-ecommerce_sample.csv]

What is real and what is simulated is recorded per table and per field:
  - products, specs, attributes, prices: from the CSV (prices are a 2015-16 crawl: HISTORICAL)
  - inventory (stock, delivery_days, shipping_inr): SIMULATED, derived deterministically from pid
Ambiguous values (no unit, two numbers run together) are kept raw and their numeric value left NULL,
which the policy engine treats as unknown.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_CSV = ROOT / "data" / "raw" / "flipkart" / "flipkart_com-ecommerce_sample.csv"
DB_PATH = ROOT / "data" / "catalog.sqlite"
REPORT_PATH = ROOT / "data" / "CATALOG_REPORT.md"

CATEGORIES = {  # top-level category in the CSV -> (slug, shopper-facing label)
    "Furniture": ("furniture", "Furniture"),
    "Home Furnishing": ("home_furnishing", "Home furnishing"),
    "Home Decor & Festive Needs": ("home_decor", "Home décor"),
    "Kitchen & Dining": ("kitchen_dining", "Kitchen & dining"),
}
SOURCE = {
    "dataset": "Flipkart Products (Kaggle PromptCloudHQ/flipkart-products v1)",
    "licence": "CC BY-SA 4.0, PromptCloud",
    "price_note": "Historical prices from a Dec 2015 - Jun 2016 crawl. Not live.",
    "simulated": "stock, delivery_days, shipping_inr are simulated (deterministic from pid).",
}

_SPEC = re.compile(r'"key"=>"((?:[^"\\]|\\.)*)", "value"=>"((?:[^"\\]|\\.)*)"')
_NUM = r"(\d+(?:\.\d+)?)"


# --------------------------------------------------------------------------- parsing helpers
def parse_specs(text: str) -> list[tuple[str, str]]:
    return [(k.strip(), v.strip()) for k, v in _SPEC.findall(text or "")]


def _single_number(raw: str) -> bool:
    return len(re.findall(r"\d+(?:\.\d+)?", raw)) == 1


def length_cm(raw: str) -> float | None:
    """'1905 mm' -> 190.5; '75 inch / 190 cm' -> 190; '6 inch' -> 15.24. Ambiguous -> None."""
    raw = raw.strip()
    m = re.fullmatch(rf"{_NUM}\s*inch\s*/\s*{_NUM}\s*cm", raw, re.I)
    if m:
        return float(m.group(2))
    if not _single_number(raw):
        return None
    m = re.fullmatch(rf"{_NUM}\s*(mm|cm|m|inch|inches|in|ft|feet)\.?", raw, re.I)
    if not m:
        return None
    v, u = float(m.group(1)), m.group(2).lower()
    return round(v * {"mm": 0.1, "cm": 1, "m": 100, "inch": 2.54, "inches": 2.54, "in": 2.54,
                      "ft": 30.48, "feet": 30.48}[u], 1)


def weight_kg(raw: str) -> float | None:
    if not _single_number(raw):
        return None
    m = re.fullmatch(rf"{_NUM}\s*(g|gm|gms|kg)\.?", raw.strip(), re.I)
    if not m:
        return None
    v, u = float(m.group(1)), m.group(2).lower()
    return round(v / 1000 if u.startswith("g") else v, 3)


def capacity_l(raw: str) -> float | None:
    if not _single_number(raw):
        return None
    m = re.fullmatch(rf"{_NUM}\s*(ml|l|litre|liter|litres|liters)\.?", raw.strip(), re.I)
    if not m:
        return None
    v, u = float(m.group(1)), m.group(2).lower()
    return round(v / 1000 if u == "ml" else v, 3)


def seats(raw: str) -> int | None:
    m = re.fullmatch(r"(\d+)\s*Seater", raw.strip(), re.I)
    return int(m.group(1)) if m else None


NUMERIC_ATTRS = {  # spec key -> (attribute name, parser, unit)
    "Width": ("width_cm", length_cm, "cm"),
    "Depth": ("depth_cm", length_cm, "cm"),
    "Height": ("height_cm", length_cm, "cm"),
    "Length": ("length_cm", length_cm, "cm"),
    "Diameter": ("diameter_cm", length_cm, "cm"),
    "Weight": ("weight_kg", weight_kg, "kg"),
    "Capacity": ("capacity_l", capacity_l, "L"),
    "Seating Capacity": ("seats", seats, "seats"),
}
TEXT_ATTRS = {  # attribute name -> spec keys in priority order
    "material": ["Primary Material", "Material", "Outer Material"],
    "color": ["Primary Color", "Color", "Upholstery Color", "Finish Color"],
    "type": ["Type"],
}


def simulated_inventory(pid: str, category_slug: str, price: int | None) -> tuple[int, int, int]:
    h = int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16)
    stock = 0 if h % 10 == 0 else (h // 10) % 25 + 1           # about 10% out of stock
    if category_slug == "furniture":
        delivery = 5 + (h // 7) % 6                               # 5-10 days
        shipping = 0 if (price or 0) >= 10000 else 499
    else:
        delivery = 2 + (h // 7) % 5                               # 2-6 days
        shipping = 0 if (price or 0) >= 499 else 49
    return stock, delivery, shipping


def split_tree(tree: list[str], name: str) -> tuple[list[str], str]:
    """Return (category segments, leaf category). The CSV often ends the tree with the product name
    itself ("... >> Sofas & Sectionals >> Comfort Couch ... (Fin.."), which is not a category."""
    last, nm = tree[-1].lower().rstrip(". ").strip(), name.lower()
    if len(tree) > 1 and (nm.startswith(last[:12]) or last.startswith(nm[:12])):
        tree = tree[:-1]
    return tree, tree[-1]


MIN_CM_PER_SEAT = 45   # a seat narrower than this isn't physically plausible


def implausible(con, pid: str) -> list[tuple[str, str]]:
    """Values the listing states that can't be true. They're kept raw but treated as unknown.
    Example from the data: 'ARRA Solid Wood 7 Seater Sofa', Width 700 mm (10 cm per seat)."""
    name = con.execute("SELECT name FROM products WHERE pid = ?", (pid,)).fetchone()[0]
    if not re.search(r"\b(sofa|sectional|couch|settee)\b", name, re.I) or re.search(r"\bcover\b", name, re.I):
        return []   # the per-seat rule only makes sense for seating made of seats side by side
    vals = dict(con.execute("SELECT name, value_num FROM attributes WHERE pid = ? AND value_num IS NOT NULL", (pid,)))
    out = []
    seats_n, width = vals.get("seats"), vals.get("width_cm")
    if seats_n and width is not None and width < MIN_CM_PER_SEAT * seats_n:
        out.append(("width_cm", f"implausible: {width:g} cm for {int(seats_n)} seats"))
    return out


def _int(v: str) -> int | None:
    return int(v) if v and v.strip().isdigit() else None


# --------------------------------------------------------------------------- build
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE products (
  pid TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT, brand_source TEXT,
  category TEXT NOT NULL, category_label TEXT NOT NULL, category_path TEXT NOT NULL, leaf_category TEXT NOT NULL,
  description TEXT, url TEXT, image_url TEXT, crawled_at TEXT, csv_row INTEGER);
CREATE TABLE prices (pid TEXT PRIMARY KEY, price_inr INTEGER, mrp_inr INTEGER, source TEXT NOT NULL);
CREATE TABLE inventory (pid TEXT PRIMARY KEY, stock INTEGER, delivery_days INTEGER, shipping_inr INTEGER,
  source TEXT NOT NULL DEFAULT 'simulated');
CREATE TABLE specs (pid TEXT, key TEXT, value TEXT);
CREATE TABLE attributes (pid TEXT, name TEXT, value_num REAL, value_text TEXT, unit TEXT, source_key TEXT, raw TEXT,
  quality TEXT NOT NULL DEFAULT 'ok');
CREATE INDEX specs_pid ON specs(pid);
CREATE INDEX attrs_pid ON attributes(pid);
CREATE INDEX attrs_name ON attributes(name, value_num);
CREATE INDEX products_cat ON products(category);
CREATE VIRTUAL TABLE products_fts USING fts5(pid UNINDEXED, name, brand, category_path, type,
  tokenize = 'porter unicode61');
"""


def build(csv_path: Path = DEFAULT_CSV, db_path: Path = DB_PATH) -> dict:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    stats: Counter = Counter()
    seen_pid, seen_key = set(), set()
    for i, r in enumerate(rows, start=2):  # csv line numbers (header is line 1)
        tree = [p.strip() for p in json.loads(r["product_category_tree"])[0].split(">>")]
        if tree[0] not in CATEGORIES:
            continue
        stats["rows_in_scope"] += 1
        pid, name, price = r["pid"].strip(), r["product_name"].strip(), _int(r["discounted_price"])
        key = (name.lower(), price)
        if pid in seen_pid or key in seen_key:
            stats["duplicates_dropped"] += 1
            continue
        seen_pid.add(pid); seen_key.add(key)
        slug, label = CATEGORIES[tree[0]]
        spec_pairs = parse_specs(r["product_specifications"])
        spec_map = {}
        for k, v in spec_pairs:
            spec_map.setdefault(k, v)
        brand, brand_src = r["brand"].strip() or None, "brand column"
        if not brand and spec_map.get("Brand"):
            brand, brand_src = spec_map["Brand"], "specifications"
        if not brand:
            brand_src = None
        try:
            image = (json.loads(r["image"]) or [None])[0]
        except (json.JSONDecodeError, TypeError):
            image = None
        cats, leaf = split_tree(tree, name)
        con.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, name, brand, brand_src, slug, label, " > ".join(cats), leaf,
                     re.sub(r"\s+", " ", r["description"]).strip(), r["product_url"], image,
                     r["crawl_timestamp"][:10], i))
        con.execute("INSERT INTO prices VALUES (?,?,?,?)",
                    (pid, price, _int(r["retail_price"]), "historical: Flipkart crawl 2015-16"))
        con.execute("INSERT INTO inventory (pid, stock, delivery_days, shipping_inr) VALUES (?,?,?,?)",
                    (pid, *simulated_inventory(pid, slug, price)))
        con.executemany("INSERT INTO specs VALUES (?,?,?)", [(pid, k, v) for k, v in spec_pairs])
        for k, (attr, parse, unit) in NUMERIC_ATTRS.items():
            if k in spec_map:
                val = parse(spec_map[k])
                con.execute("INSERT INTO attributes VALUES (?,?,?,?,?,?,?,?)", (pid, attr, val, None, unit, k, spec_map[k], "ok" if val is not None else "ambiguous"))
                stats[f"{attr}:{'parsed' if val is not None else 'ambiguous'}"] += 1
        for attr, keys in TEXT_ATTRS.items():
            for k in keys:
                v = spec_map.get(k)
                if v and v.upper() != "NA":
                    con.execute("INSERT INTO attributes VALUES (?,?,?,?,?,?,?,?)", (pid, attr, None, v, None, k, v, "ok"))
                    break
        con.execute("INSERT INTO products_fts VALUES (?,?,?,?,?)",
                    (pid, name, brand or "", " ".join(cats), spec_map.get("Type", "")))
        for attr, note in implausible(con, pid):
            con.execute("UPDATE attributes SET value_num = NULL, quality = ? WHERE pid = ? AND name = ?", (note, pid, attr))
            stats["implausible_values"] += 1
        stats["products"] += 1
        stats[f"cat:{slug}"] += 1
        if price is None:
            stats["price_missing"] += 1
        if not brand:
            stats["brand_missing"] += 1
    meta = dict(SOURCE, built=date.today().isoformat(), csv=str(csv_path.name),
                csv_sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                categories=json.dumps({v[0]: v[1] for v in CATEGORIES.values()}), version="flipkart-home-v1")
    con.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return dict(stats)


# --------------------------------------------------------------------------- report
def write_report(db_path: Path = DB_PATH, out: Path = REPORT_PATH, stats: dict | None = None) -> str:
    con = sqlite3.connect(db_path)
    q = lambda s, *a: con.execute(s, a).fetchall()
    total = q("SELECT COUNT(*) FROM products")[0][0]
    lines = [f"# Catalog report: {q('SELECT value FROM meta WHERE key=?', 'version')[0][0]}", "",
             f"Built {date.today().isoformat()} by `build_catalog.py` from the Flipkart Products CSV "
             "(CC BY-SA 4.0, PromptCloud). Prices are **historical (2015–16)**; stock, delivery and shipping "
             "are **simulated**.", ""]
    if stats:
        lines += [f"- Rows in the four categories: {stats.get('rows_in_scope', 0):,}",
                  f"- Duplicates dropped (same pid, or same name and price): {stats.get('duplicates_dropped', 0):,}",
                  f"- **Products in the store: {total:,}**", ""]
    lines += ["## Products per category", "", "| Category | Products | With price | With brand | Median price ₹ | Out of stock (simulated) |",
              "|---|---|---|---|---|---|"]
    for slug, label, n in q("SELECT category, category_label, COUNT(*) FROM products GROUP BY 1,2 ORDER BY 3 DESC"):
        wp = q("SELECT COUNT(*) FROM products p JOIN prices USING(pid) WHERE category=? AND price_inr IS NOT NULL", slug)[0][0]
        wb = q("SELECT COUNT(*) FROM products WHERE category=? AND brand IS NOT NULL", slug)[0][0]
        ps = [r[0] for r in q("SELECT price_inr FROM products JOIN prices USING(pid) WHERE category=? AND price_inr IS NOT NULL ORDER BY 1", slug)]
        oos = q("SELECT COUNT(*) FROM products JOIN inventory USING(pid) WHERE category=? AND stock=0", slug)[0][0]
        lines.append(f"| {label} | {n:,} | {wp/n:.0%} | {wb/n:.0%} | {ps[len(ps)//2]:,} | {oos:,} |")
    lines += ["", "## How often the agent can check each attribute", "",
              "*Parsed* means a clean number in a standard unit. *Ambiguous* means the listing has a value but "
              "it couldn't be read safely (for example no unit, or two numbers run together); the agent treats "
              "those as unknown.", "",
              "| Attribute | Furniture | Home furnishing | Home décor | Kitchen & dining | Ambiguous (all) |", "|---|---|---|---|---|---|"]
    cats = [r[0] for r in q("SELECT DISTINCT category FROM products")]
    order = ["furniture", "home_furnishing", "home_decor", "kitchen_dining"]
    for attr in ["seats", "width_cm", "depth_cm", "height_cm", "length_cm", "diameter_cm", "weight_kg", "capacity_l",
                 "material", "color"]:
        cells = []
        for c in order:
            if c not in cats:
                cells.append("–"); continue
            n = q("SELECT COUNT(*) FROM products WHERE category=?", c)[0][0]
            k = q("SELECT COUNT(DISTINCT a.pid) FROM attributes a JOIN products p USING(pid) WHERE p.category=? "
                  "AND a.name=? AND (a.value_num IS NOT NULL OR a.value_text IS NOT NULL)", c, attr)[0][0]
            cells.append(f"{k/n:.0%}")
        amb = q("SELECT COUNT(*) FROM attributes WHERE name=? AND value_num IS NULL AND value_text IS NULL", attr)[0][0]
        lines.append(f"| {attr} | " + " | ".join(cells) + f" | {amb} |")
    lines += ["", "## Sample of 10 products (2–3 per category, chosen by a fixed rule: lowest pid)", "",
              "| pid | Name | Brand | Category | Price ₹ (MRP) | Key attributes | Stock / delivery (simulated) |",
              "|---|---|---|---|---|---|---|"]
    for c, k in zip(order, [4, 2, 2, 2]):
        for pid, name, brand, label, price, mrp, stock, dd in q(
                "SELECT pid, name, brand, category_label, price_inr, mrp_inr, stock, delivery_days FROM products "
                "JOIN prices USING(pid) JOIN inventory USING(pid) WHERE category=? ORDER BY pid LIMIT ?", c, k):
            attrs = q("SELECT name, value_num, value_text FROM attributes WHERE pid=? AND (value_num IS NOT NULL OR value_text IS NOT NULL)", pid)
            a = ", ".join(f"{n}={(v if v is not None else t)}" for n, v, t in attrs[:5]) or "none parsed"
            lines.append(f"| `{pid}` | {name[:48]} | {brand or '*missing*'} | {label} | {price:,} ({mrp or '–'}) | {a} | {stock} / {dd} days |")
    lines += ["", "## Furniture subcategories", "", "| Subcategory | Products |", "|---|---|"]
    for path, n in q("SELECT category_path, COUNT(*) FROM products WHERE category='furniture' GROUP BY 1 ORDER BY 2 DESC LIMIT 12"):
        lines.append(f"| {path} | {n} |")
    con.close()
    lines += search_section(db_path)
    text = "\n".join(lines) + "\n"
    out.write_text(text)
    return text


SAMPLE_QUERIES = ["sofa", "3 seater sofa", "sofa cover", "bed sheet", "curtain", "pressure cooker", "table lamp",
                  "table", "bean bag", "mobile", "mobile stand", "air fryer", "dining table"]


def search_section(db_path: Path) -> list[str]:
    """How the agent will decide 'we sell this' vs 'not sold here' (rule R1), run live on the built DB."""
    from catalog import SqliteCatalog
    cat = SqliteCatalog(db_path)
    out = ["", "## Search: what counts as \"we sell this\"", "",
           "A **match** is a product that *is* what the shopper named: the head noun of its name or its own "
           "category, so a table lamp is a lamp, not a table. **Related** products only mention the word "
           "(a sofa cover, a mobile-stand showpiece). Rule R1: no matches means *\"not sold here\"*, even if "
           "related items exist.", "",
           "| Shopper says | Matches | Related | First match | Agent outcome |", "|---|---|---|---|---|"]
    for q in SAMPLE_QUERIES:
        m, r = cat.find_products(q)
        first = cat.get(m[0]).title[:45] if m else "–"
        out.append(f"| {q} | {len(m)} | {len(r)} | {first} | {'search and recommend' if m else '**not sold here**'} |")
    out += ["", "**Known limits:** \"mobile stand\" and \"dining table\" come back as not sold. The data files "
            "mobile stands as showpieces, and has dining *sets* but no standalone dining tables. Fixing that "
            "would mean synonym lists, which we have deliberately left out for now."]
    return out


if __name__ == "__main__":
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    s = build(csv_path)
    print(json.dumps(s, indent=1, sort_keys=True))
    write_report(stats=s)
    print(f"wrote {DB_PATH} and {REPORT_PATH}")
