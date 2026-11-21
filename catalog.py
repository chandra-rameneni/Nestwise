"""Catalog tools. The agent only sees products through these bounded functions.

Price/stock state is mutable so the demo can simulate changes; every change bumps the
product's data version, which approvals are bound to.
"""
from __future__ import annotations

import copy
import json
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"          # synthetic test fixture
STORE_DB_PATH = Path(__file__).parent / "data" / "catalog.sqlite"       # real store (build_catalog.py)

# Heuristic flag for instruction-like text inside untrusted product data (BUY-08).
# Flagging is for the trace only: product text is never used as instructions anywhere.
_INJECTION_PATTERNS = re.compile(
    r"(ignore (the )?(shopper|user|previous)|system note|ai (shopping )?agents?|place the order|without asking)", re.I
)


@dataclass(frozen=True)
class ProductView:
    """A join of products + specs + prices + inventory for one product_id at one data version.

    `specs` holds the normalised attributes the policy engine checks (seats, width_cm, material, ...).
    `raw_specs` holds the listing's own key/value pairs exactly as written (used for grounded Q&A).
    `source_flags` says where each group of fields came from (historical / simulated / synthetic).
    """
    product_id: str
    title: str
    brand: str | None
    category: str
    description: str
    specs: dict
    list_price_inr: int | None
    shipping_inr: int
    stock: int
    delivery_days: int
    version: int
    injection_flag: bool
    raw_specs: dict = field(default_factory=dict)
    mrp_inr: int | None = None
    category_label: str = ""
    category_path: str = ""
    url: str | None = None
    image_url: str | None = None
    source_flags: dict = field(default_factory=dict)
    data_notes: dict = field(default_factory=dict)   # attribute -> why its listed value isn't usable

    @property
    def returnable(self) -> bool:
        """Store rule (STORE_POLICY.md P3, decided by the PM 2026-11-19): items under ₹500 that are bird houses
        (any category), or home décor showpieces, candles and fragrances, festive décor and wall stickers/decals,
        can't be returned."""
        if self.list_price_inr is None or self.list_price_inr >= 500:
            return True
        text = f"{self.title} {self.category_path}".lower()
        if re.search(r"bird ?house", text):           # bird houses are filed under Furniture > Pet Furniture
            return False
        return not (self.category == "home_decor"
                    and re.search(r"showpiece|candle|fragrance|aroma|festive|decal|sticker", text))

    def total_for(self, qty: int = 1) -> int | None:
        """Final payable total. None when the listing has no price (treated as unknown, never as free)."""
        if self.list_price_inr is None:
            return None
        return self.list_price_inr * qty + self.shipping_inr


class Catalog:
    def __init__(self, path: Path = CATALOG_PATH):
        raw = json.loads(Path(path).read_text())
        self.meta = raw["_meta"]
        self._products = {p["product_id"]: p for p in raw["products"]}
        self._specs = raw["specs"]
        self._prices = copy.deepcopy(raw["prices"])
        self._inventory = copy.deepcopy(raw["inventory"])
        self._versions = {pid: 1 for pid in self._products}

    # --- tools -----------------------------------------------------------------
    def search(self, category: str | None = None, keywords: list[str] | None = None) -> list[str]:
        """Return product IDs matching a category and/or all keywords in the title/category.

        Descriptions are deliberately not searched: "gaming laptop" used to match a keyboard whose
        description says "for laptops" (observed failure F-001, see EVALS.md).
        """
        out = []
        for pid, p in self._products.items():
            if category and p["category"] != category:
                continue
            if keywords:
                text = f"{p['title']} {p['category']}".lower()
                if not all(k.lower() in text for k in keywords):
                    continue
            out.append(pid)
        return out

    def category_labels(self) -> list[str]:
        return ["keyboard-and-mouse combos", "sofas"]

    def find_products(self, query: str, product_category: str | None = None) -> tuple[list[str], list[str]]:
        """Fixture version of SqliteCatalog.find_products: by fixture category, else by the head noun in titles."""
        if product_category:
            return self.search(product_category), []
        terms = query_terms(query)
        if not terms:
            return [], []
        return self.search(keywords=[terms[-1]]), []

    def get(self, product_id: str) -> ProductView | None:
        p = self._products.get(product_id)
        if p is None:
            return None
        price, inv = self._prices[product_id], self._inventory[product_id]
        return ProductView(
            product_id=product_id, title=p["title"], brand=p["brand"], category=p["category"],
            description=p["description"], specs=dict(self._specs.get(product_id, {})),
            list_price_inr=price["list_price_inr"], shipping_inr=price["shipping_inr"],
            stock=inv["stock"], delivery_days=inv["delivery_days"],
            version=self._versions[product_id],
            injection_flag=bool(_INJECTION_PATTERNS.search(p["description"])),
        )

    # --- simulation hooks (demo only) ------------------------------------------
    def set_price(self, product_id: str, list_price_inr: int) -> None:
        self._prices[product_id]["list_price_inr"] = int(list_price_inr)
        self._versions[product_id] += 1

    def set_stock(self, product_id: str, stock: int) -> None:
        self._inventory[product_id]["stock"] = int(stock)
        self._versions[product_id] += 1


# ============================================================================ real store catalog
_STOPWORDS = {"a", "an", "the", "for", "me", "my", "i", "need", "want", "find", "show", "buy", "get", "some",
              "any", "under", "below", "within", "with", "and", "or", "of", "in", "to", "please", "looking",
              "something", "good", "cheap", "best", "new", "rs", "inr", "is", "it", "that", "this", "on", "at"}


# Leaf categories made of these words hold things *for* a product, not the product itself.
_ACCESSORY_WORDS = {"cover", "covers", "stand", "stands", "holder", "holders", "case", "cases", "accessories",
                    "showpiece", "showpieces", "tassel", "tassels", "clip", "clips", "hook", "hooks", "rod", "rods",
                    "protector", "protectors", "mat", "mats", "organizer", "organizers"}


def _word_matches(term: str, word: str) -> bool:
    """Prefix match with simple plural handling: sofa~sofas, bed~bedsheets, cooker~cookers."""
    return word.startswith(term) or term.rstrip("s") == word.rstrip("s")


def _same_word(a: str, b: str) -> bool:
    """Equal ignoring a plural ending: sofa/sofas, bedsheet/bedsheets, box/boxes."""
    norm = lambda w: re.sub(r"(es|s)$", "", w) if len(w) > 3 else w
    return a == b or norm(a) == norm(b)


def _head_noun(text: str, is_category: bool = False) -> str:
    """The noun that says what a thing is: the last word of its first part.
    'Comfort Couch 3 Seater Sofa (Finish Color - Brown)' -> sofa; 'Unique Design Mobile Stand Showpiece'
    -> showpiece; categories also split on '&' and ',': 'Sofas & Sectionals' -> sofas, 'Table Lamps' -> lamps.
    Product names are not split on '&' because brands contain it ('Bed & Bath ... Bedsheet')."""
    seps = r"\(| & |,| - | with | for " if is_category else r"\(| - | with | for "
    first = re.split(seps, text or "", maxsplit=1)[0]
    words = re.findall(r"[a-z]+", first.lower())
    return words[-1] if words else ""


def query_terms(query: str) -> list[str]:
    """Words worth searching for. Numbers and filler words are dropped."""
    return [t for t in re.findall(r"[a-z]+", (query or "").lower()) if t not in _STOPWORDS and len(t) > 1]


class SqliteCatalog:
    """Read-only view of data/catalog.sqlite plus in-memory demo overrides for price and stock.

    Same tool interface as the fixture `Catalog` (search, get, set_price, set_stock), plus
    `search_text` and `categories` for the storefront. The database file is never modified.
    """

    def __init__(self, path: Path = STORE_DB_PATH):
        if not Path(path).exists():
            raise FileNotFoundError(f"{path} not found. Run: .venv/bin/python build_catalog.py")
        self._path = path
        self._local = threading.local()
        self.meta = dict(self._con.execute("SELECT key, value FROM meta").fetchall())
        self._price_override: dict[str, int] = {}
        self._stock_override: dict[str, int] = {}
        self._versions: dict[str, int] = {}

    def __getstate__(self):
        """Saved chats (server restarts) keep the demo overrides, never the open database connections."""
        state = dict(self.__dict__)
        state.pop("_local", None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._local = threading.local()

    @property
    def _con(self) -> sqlite3.Connection:
        """One read-only connection per thread. The web server answers several requests at once, and one shared
        connection used from several threads at the same time fails ("bad parameter or other API misuse")."""
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True, check_same_thread=False)
            self._local.con = con
        return con

    # --- storefront helpers -------------------------------------------------------
    def categories(self) -> list[dict]:
        rows = self._con.execute("SELECT category, category_label, COUNT(*) FROM products GROUP BY 1, 2 "
                                 "ORDER BY 3 DESC").fetchall()
        return [{"slug": s, "label": l, "count": n} for s, l, n in rows]

    def category_kinds(self, slug: str, n: int = 6) -> list[tuple[str, int]]:
        """B43: the main kinds of product in a category with counts, from the second level of the category path
        ("Home Decor > Showpieces > ..." -> "Showpieces"). Near-duplicates are merged."""
        counts: dict[str, int] = {}
        for (path,) in self._con.execute("SELECT category_path FROM products WHERE category = ?", (slug,)):
            parts = [x.strip() for x in (path or "").split(">")]
            if len(parts) < 2:
                continue
            kind = {"Showpiece": "Showpieces", "Living Room Furniture": "Living Room",
                    "Living Room Furnishing": "Living"}.get(parts[1], parts[1])
            counts[kind] = counts.get(kind, 0) + 1
        return sorted(counts.items(), key=lambda kv: -kv[1])[:n]

    def category_labels(self) -> list[str]:
        return [c["label"] for c in self.categories()]

    def search_text(self, query: str = "", category: str | None = None, min_price: int | None = None,
                    max_price: int | None = None, limit: int = 24, offset: int = 0) -> tuple[list[str], int]:
        """Full-text search over name, brand, category path and type. Returns (product ids, total matches).

        All query words must match (prefix match, English stemming), so "air fryer" needs both words.
        An empty query lists everything in the filters.
        """
        terms = query_terms(query)
        where, args = [], []
        if terms:
            where.append("p.pid IN (SELECT pid FROM products_fts WHERE products_fts MATCH ?)")
            args.append(" AND ".join(f'"{t}"*' for t in terms))
        if category:
            where.append("p.category = ?"); args.append(category)
        if min_price is not None:
            where.append("pr.price_inr >= ?"); args.append(min_price)
        if max_price is not None:
            where.append("pr.price_inr <= ?"); args.append(max_price)
        sql_where = ("WHERE " + " AND ".join(where)) if where else ""
        base = f"FROM products p JOIN prices pr USING(pid) {sql_where}"
        total = self._con.execute(f"SELECT COUNT(*) {base}", args).fetchone()[0]
        if terms:
            # Column weights (pid, name, brand, category_path, type): what a product IS (its category and
            # type) outranks words that only appear in its name, so "sofa" ranks sofas above sofa covers.
            order = ("ORDER BY (SELECT bm25(products_fts, 0.0, 1.0, 0.5, 4.0, 4.0) FROM products_fts "
                     "WHERE products_fts.pid = p.pid AND products_fts MATCH ?), p.pid")
            ids = [r[0] for r in self._con.execute(f"SELECT p.pid {base} {order} LIMIT ? OFFSET ?",
                                                    args + [args[0], limit, offset])]
        else:
            ids = [r[0] for r in self._con.execute(f"SELECT p.pid {base} ORDER BY p.category, p.pid LIMIT ? OFFSET ?",
                                                    args + [limit, offset])]
        return ids, total

    def find_products(self, query: str, category: str | None = None, limit: int = 500,
                      product_category: str | None = None) -> tuple[list[str], list[str]]:
        """Split search results into (matches, related).

        A *match* is a product that IS what the shopper named: every query word appears in the product's
        own leaf category or name, and the leaf category isn't an accessory/showpiece category (unless the
        shopper asked for that accessory). Everything else the full-text search found is *related*:
        "sofa" -> sofas are matches, sofa covers are related; "mobile" -> mobile-stand showpieces are
        related only, so the store does not sell mobiles (rule R1).
        """
        terms = query_terms(query)
        if not terms:
            return [], []
        ids, _ = self.search_text(query, category=category, limit=limit)
        if len(terms) > 1:  # "bed sheet" is spelled "Bedsheet" in the data
            joined, _ = self.search_text("".join(terms), category=category, limit=limit)
            ids += [i for i in joined if i not in ids]
        if not ids:
            return [], []
        marks = ",".join("?" * len(ids))
        info = {pid: (path, leaf, name) for pid, path, leaf, name in self._con.execute(
            f"SELECT pid, category_path, leaf_category, name FROM products WHERE pid IN ({marks})", ids)}
        heads = {terms[-1], "".join(terms)}                 # what the shopper wants the product to BE
        modifiers = terms[:-1]
        asked_accessory = bool(set(terms) & _ACCESSORY_WORDS)
        matches, related = [], []
        for pid in ids:
            path, leaf, name = info[pid]
            product_heads = {_head_noun(name), _head_noun(leaf, is_category=True)}
            is_it = any(_same_word(h, ph) for h in heads for ph in product_heads if ph)
            words = re.findall(r"[a-z]+", f"{leaf} {name}".lower())
            has_mods = all(any(_word_matches(m, w) for w in words) for m in modifiers) or \
                any(_same_word("".join(terms), ph) for ph in product_heads if ph)
            accessory = bool(set(re.findall(r"[a-z]+", leaf.lower())) & _ACCESSORY_WORDS) and not asked_accessory
            (matches if is_it and has_mods and not accessory else related).append(pid)
        return matches, related

    # --- brands (O-17) and brand / product-name search (B33) -----------------------------
    _COLOURS = {"red", "black", "blue", "white", "green", "brown", "yellow", "pink", "purple", "grey", "gray",
                "orange", "maroon", "beige", "gold", "golden", "silver", "multicolor", "multicolour", "cream", "navy",
                "light", "dark", "glossy", "matte", "violet", "multi", "&", "and", "sky", "off"}

    def _is_colour(self, brand: str | None) -> bool:
        words = re.findall(r"[a-z&]+", (brand or "").lower())
        return bool(words) and all(w in self._COLOURS for w in words)

    def _brand_index(self) -> dict[str, str]:
        """pid -> cleaned brand. A colour in the brand column ("Red") means the dataset put the colour there:
        take the brand from the start of the product name if it begins with a known brand, else unknown."""
        if getattr(self, "_brands_by_pid", None) is None:
            rows = self._con.execute("SELECT pid, name, brand FROM products").fetchall()
            known = sorted({b for _, _, b in rows if b and not self._is_colour(b)}, key=len, reverse=True)
            out = {}
            for pid, name, brand in rows:
                if brand and not self._is_colour(brand):
                    out[pid] = brand
                    continue
                low = (name or "").lower()
                out[pid] = next((k for k in known if low.startswith(k.lower() + " ")), None)
            self._brands_by_pid = out
        return self._brands_by_pid

    @staticmethod
    def _norm_brand(s: str) -> str:
        s = re.sub(r"'s\b|\s+s$", "", (s or "").lower().strip())
        return re.sub(r"[^a-z0-9]", "", s)

    def brand_products(self, query: str) -> list[str]:
        """Products whose (cleaned) brand is what the shopper typed: 'jerry', "Jerry's", 'petshop7'."""
        q = self._norm_brand(query)
        if len(q) < 3:
            return []
        return [pid for pid, b in self._brand_index().items() if b and self._norm_brand(b) == q]

    def name_products(self, query: str, min_terms: int = 3) -> list[str]:
        """Products whose name contains every word of a longer query (a name copied from the page)."""
        terms = query_terms(query)
        if len(terms) < min_terms:
            return []
        ids, _ = self.search_text(query, limit=60)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        names = dict(self._con.execute(f"SELECT pid, name FROM products WHERE pid IN ({marks})", ids).fetchall())
        return [pid for pid in ids if all(any(_word_matches(t, w) for w in re.findall(r"[a-z0-9]+", names[pid].lower()))
                                          for t in terms)]

    def material_products(self, material: str, limit: int = 60) -> list[str]:
        ids, _ = self.search_text(material, limit=limit)
        return ids

    def vocabulary(self) -> tuple[set[str], set[str]]:
        """(every word in product names and categories, the product-type words). Used to spot typos (B12):
        'sofaa' isn't a word in the store but is close to the product type 'sofa'."""
        if getattr(self, "_vocab", None) is None:
            every, types = set(), set()
            for name, leaf, path in self._con.execute("SELECT name, leaf_category, category_path FROM products"):
                every |= set(re.findall(r"[a-z]+", f"{name} {leaf} {path}".lower()))
                types |= {w for w in (_head_noun(name), *re.findall(r"[a-z]+", leaf.lower())) if len(w) > 3}
            self._vocab = (every, types)
        return self._vocab

    # --- agent tools (same interface as Catalog) --------------------------------------
    def search(self, category: str | None = None, keywords: list[str] | None = None, limit: int = 200) -> list[str]:
        ids, _ = self.search_text(" ".join(keywords or []), category=category, limit=limit)
        return ids

    def get(self, product_id: str) -> ProductView | None:
        row = self._con.execute(
            "SELECT p.pid, p.name, p.brand, p.category, p.category_label, p.category_path, p.description, p.url, "
            "p.image_url, pr.price_inr, pr.mrp_inr, i.stock, i.delivery_days, i.shipping_inr "
            "FROM products p JOIN prices pr USING(pid) JOIN inventory i USING(pid) WHERE p.pid = ?",
            (product_id,)).fetchone()
        if row is None:
            return None
        (pid, name, brand, cat, label, path, desc, url, img, price, mrp, stock, dd, ship) = row
        attrs, notes = {}, {}
        for n, num, text, quality, raw_v in self._con.execute(
                "SELECT name, value_num, value_text, quality, raw FROM attributes WHERE pid = ?", (pid,)):
            attrs[n] = (int(num) if n == "seats" and num is not None else num) if text is None else text
            if quality != "ok":
                notes[n] = f"listing says '{raw_v}' ({quality})"
        raw = {}
        for k, v in self._con.execute("SELECT key, value FROM specs WHERE pid = ?", (pid,)):
            raw.setdefault(k, v)
        price = self._price_override.get(pid, price)
        return ProductView(
            product_id=pid, title=name, brand=self._brand_index().get(pid, brand), category=cat, description=desc or "", specs=attrs,
            list_price_inr=price, shipping_inr=ship, stock=self._stock_override.get(pid, stock), delivery_days=dd,
            version=self._versions.get(pid, 1), injection_flag=bool(_INJECTION_PATTERNS.search(desc or "")),
            raw_specs=raw, mrp_inr=mrp, category_label=label, category_path=path, url=url, image_url=img,
            source_flags={"name/brand/specs/description": "Flipkart dataset (2015-16 crawl)",
                          "price": "historical (2015-16)" + (", changed by demo simulation" if pid in self._price_override else ""),
                          "stock/delivery/shipping": "simulated"},
            data_notes=notes)

    # --- simulation hooks (demo only; never written to disk) -----------------------------
    def set_price(self, product_id: str, list_price_inr: int) -> None:
        self._price_override[product_id] = int(list_price_inr)
        self._versions[product_id] = self._versions.get(product_id, 1) + 1

    def set_stock(self, product_id: str, stock: int) -> None:
        self._stock_override[product_id] = int(stock)
        self._versions[product_id] = self._versions.get(product_id, 1) + 1
