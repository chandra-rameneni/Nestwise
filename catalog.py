"""Catalog tools. The agent only sees products through these bounded functions.

Price/stock state is mutable so the demo can simulate changes; every change bumps the
product's data version, which approvals are bound to.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"

# Heuristic flag for instruction-like text inside untrusted product data (BUY-08).
# Flagging is for the trace only: product text is never used as instructions anywhere.
_INJECTION_PATTERNS = re.compile(
    r"(ignore (the )?(shopper|user|previous)|system note|ai (shopping )?agents?|place the order|without asking)", re.I
)


@dataclass(frozen=True)
class ProductView:
    """A join of products + specs + prices + inventory for one product_id at one data version."""
    product_id: str
    title: str
    brand: str
    category: str
    description: str
    specs: dict
    list_price_inr: int
    shipping_inr: int
    stock: int
    delivery_days: int
    version: int
    injection_flag: bool

    def total_for(self, qty: int = 1) -> int:
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
