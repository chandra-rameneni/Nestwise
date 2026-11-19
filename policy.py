"""Deterministic eligibility and checkout policy. No model output can override these checks."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from catalog import ProductView
from intent import Intent

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"


@dataclass
class Check:
    constraint: str
    required: object
    observed: object
    status: str          # pass | fail | unknown
    reason_code: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Eligibility:
    product_id: str
    eligible: bool
    total_inr: int
    checks: list[Check]

    @property
    def reason_codes(self) -> list[str]:
        return [c.reason_code for c in self.checks if c.status != PASS and c.reason_code]


def evaluate(intent: Intent, p: ProductView, qty: int = 1) -> Eligibility:
    """Check every hard constraint. Unknown counts as not eligible (unknown != compliant)."""
    checks: list[Check] = []
    total = p.total_for(qty)

    checks.append(Check("in_stock", f">= {qty}", p.stock,
                        PASS if p.stock >= qty else FAIL, None if p.stock >= qty else "OUT_OF_STOCK"))

    if total is None:
        # No listed price: the exact total can't be shown for approval, so it can never be bought (eval BT-06).
        checks.append(Check("listed price", "a price", None, UNKNOWN, "PRICE_UNKNOWN"))
    elif intent.max_total_inr is not None:
        if total is None:
            checks.append(Check("max_total_inr (incl. shipping)", intent.max_total_inr, None, UNKNOWN, "PRICE_UNKNOWN"))
        else:
            ok = total <= intent.max_total_inr
            checks.append(Check("max_total_inr (incl. shipping)", intent.max_total_inr, total,
                                PASS if ok else FAIL, None if ok else "BUDGET_EXCEEDED"))

    if intent.max_delivery_days is not None:
        ok = p.delivery_days <= intent.max_delivery_days
        checks.append(Check("max_delivery_days", intent.max_delivery_days, p.delivery_days,
                            PASS if ok else FAIL, None if ok else "DELIVERY_TOO_SLOW"))

    if "macOS" in intent.required_compatibility:
        v = p.specs.get("macos_compatible")
        if v is True:
            checks.append(Check("macOS compatible", True, True, PASS))
        elif v is False:
            checks.append(Check("macOS compatible", True, False, FAIL, "COMPAT_FAILED"))
        else:
            checks.append(Check("macOS compatible", True, None, UNKNOWN, "COMPAT_UNVERIFIED"))

    if intent.seats is not None:
        v = p.specs.get("seats")
        if v is None:
            checks.append(Check("seats", intent.seats, None, UNKNOWN, "SEATS_UNVERIFIED"))
        else:
            ok = v == intent.seats
            checks.append(Check("seats", intent.seats, v, PASS if ok else FAIL, None if ok else "SEATS_MISMATCH"))

    material = getattr(intent, "material", None)
    if material:
        # "only leather" (B33): leather also matches leatherette; checked against the name and material specs.
        words = {"leather": r"leather", "wood": r"wood", "solid wood": r"solid\s*wood"}.get(material, re.escape(material))
        specs = getattr(p, "raw_specs", {}) or {}
        mat_specs = " ".join(str(v) for k, v in specs.items() if re.search(r"material|upholstery|fabric", k, re.I))
        if re.search(words, f"{p.title} {mat_specs}", re.I):
            checks.append(Check("material", material, "listed", PASS))
        elif mat_specs:
            checks.append(Check("material", material, mat_specs[:60], FAIL, "MATERIAL_MISMATCH"))
        else:
            checks.append(Check("material", material, None, UNKNOWN, "MATERIAL_UNVERIFIED"))

    notes = getattr(p, "data_notes", {}) or {}
    for limit_field, attr, label in (("max_width_cm", "width_cm", "WIDTH"), ("max_depth_cm", "depth_cm", "DEPTH"),
                                     ("max_height_cm", "height_cm", "HEIGHT")):
        limit = getattr(intent, limit_field, None)
        if limit is None:
            continue
        v = p.specs.get(attr)
        if v is None:
            # Missing, or listed but physically implausible (data_notes): either way not verified.
            checks.append(Check(limit_field, limit, notes.get(attr), UNKNOWN, f"{label}_UNVERIFIED"))
        else:
            ok = v <= limit
            checks.append(Check(limit_field, limit, v, PASS if ok else FAIL, None if ok else f"{label}_EXCEEDED"))

    eligible = all(c.status == PASS for c in checks)
    return Eligibility(p.product_id, eligible, total, checks)


def rank(intent: Intent, products: list[ProductView]) -> list[ProductView]:
    """Deterministic baseline ranking: preferred brand first (soft), then lowest total, then fastest."""
    prefs = {b.lower() for b in intent.preferred_brands}
    return sorted(products, key=lambda p: ((p.brand or "").lower() not in prefs,
                                           p.total_for() if p.total_for() is not None else float("inf"),
                                           p.delivery_days, p.product_id))


def checkout_gate(*, intent: Intent, cart, approval, current=None, currents: dict | None = None) -> list[str]:
    """Trusted pre-checkout check, for every line of the cart (B47). Returns blocking reason codes; empty = allowed.
    `currents` maps product_id -> the product as it is now; `current` is the one-product form kept for older code."""
    reasons: list[str] = []
    if approval is None or approval.status != "APPROVED":
        return ["NO_VALID_APPROVAL"]
    if approval.cart_id != cart.cart_id:
        reasons.append("APPROVAL_CART_MISMATCH")
    if currents is None:
        currents = {cart.lines[0].product_id: current}
    for ln in cart.lines:
        cur = currents.get(ln.product_id)
        if cur is None:
            reasons.append("PRODUCT_NOT_FOUND")
            continue
        if cur.version != approval.line_versions.get(ln.product_id, approval.data_version):
            reasons.append("APPROVAL_STALE_DATA_CHANGED")
        if cur.total_for(ln.qty) != approval.line_totals.get(ln.product_id, approval.approved_total_inr):
            reasons.append("PRICE_CHANGED_SINCE_APPROVAL")
        # each line is checked against the requirements it was added with (a search's budget applies to the items
        # picked from that search, not to a bean bag added later from its own page)
        checks_against = ln.checked_with if ln.checked_with is not None else Intent(intent="BUY_THIS")
        reasons.extend(evaluate(checks_against, cur, ln.qty).reason_codes)
    if cart.total_inr != approval.approved_total_inr:
        reasons.append("CART_CHANGED_SINCE_APPROVAL")
    return list(dict.fromkeys(reasons))
