"""Round 2 evals, section G (UI and the "No returns" label), approved by the PM 2026-11-19."""
from pathlib import Path

from fastapi.testclient import TestClient

import server

ROOT = Path(__file__).resolve().parents[1]
BIRD, BED = "BRHEDG33DZHYZGZG", "BDDEH29DNAN4AKYH"


def test_r2_u01_u03_returnable_flag_on_products():
    c = TestClient(server.app)
    assert c.get(f"/api/products/{BIRD}").json()["returnable"] is False
    assert c.get(f"/api/products/{BED}").json()["returnable"] is True
    assert "No returns" in (ROOT / "web" / "product.html").read_text()


def test_r2_u02_cart_says_no_returns_before_approve():
    c = TestClient(server.app)
    c.post("/api/agent/message", json={"text": "buy this", "context": {"page": "product", "product_id": BIRD}})
    cart = c.get("/api/agent/state").json()["cart"]
    assert cart and cart["returnable"] is False
    js = (ROOT / "web" / "agent.js").read_text()
    assert "No returns on this item" in js and js.index("noreturn") < js.index('data-act="approve"')


def test_r2_u04_no_alarming_status_labels():
    js = (ROOT / "web" / "agent.js").read_text()
    assert "Nothing matches everything" not in js and '"Stopped"' not in js and "reason_codes.join" not in js
