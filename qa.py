"""Product listing fields the AI agent may read and cite (get_product), and short product names for messages.
Product text is data, never instructions."""
from __future__ import annotations

import re

from catalog import ProductView


def listing_fields(p: ProductView) -> dict:
    """Everything the agent may cite, keyed by the name a shopper would see on the product page."""
    out = {"Name": p.title, "Brand": p.brand, "Category": p.category_path or p.category,
           # The page labels prices as historical and stock/delivery as simulated; the values here are plain so
           # answers don't repeat "(simulated)" in every sentence (round 2, O-40).
           "Price": None if p.list_price_inr is None else f"₹{p.list_price_inr:,}",
           "Delivery charge": "free" if not p.shipping_inr else f"₹{p.shipping_inr:,}",
           "Delivery time": f"{p.delivery_days} days", "Stock": f"{p.stock} in stock", "Description": p.description,
           "Photos": "1" if p.image_url else None}
    out.update(p.raw_specs or {k: v for k, v in p.specs.items()})
    return {k: v for k, v in out.items() if v not in (None, "", "NA")}


def product_noun(p: ProductView) -> str:
    """'Ethnic Handicrafts Solid Wood Queen Bed' -> 'bed'; used in warm replies ("this bed")."""
    words = re.findall(r"[A-Za-z]+", p.title or "")
    last = words[-1].lower() if words else ""
    return last if last and len(last) > 2 and last not in {"set", "pack", "combo", "piece"} else "product"


def product_noun_title(title: str) -> str:
    """A short name for a product in replies: 'Ethnic Handicrafts Solid Wood Queen Bed' -> 'queen bed',
    'ABCD XL Bean Bag With Foam Filling' -> 'bean bag' (the part after "with"/"for" is a feature, not the product)."""
    head = re.split(r"\s+(?:with|for|-|\(|\|)\s*", title or "", maxsplit=1, flags=re.I)[0]
    words = [w for w in re.findall(r"[A-Za-z]+", head) if len(w) > 1]
    if not words:
        return "item"
    return " ".join(words[-2:]).lower() if len(words) >= 2 else words[-1].lower()


