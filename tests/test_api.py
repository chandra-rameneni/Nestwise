"""Phase 3: the storefront API (server.py) end to end through HTTP, on a freshly built real catalog."""
import pytest
from fastapi.testclient import TestClient

import server
from catalog import SqliteCatalog

HOMETOWN_3S = "SOFEB7MHGWTHZFVJ"
DURIAN_BID_3S = "SOFE9FS5PGNNQV9N"


@pytest.fixture
def client(store_db, monkeypatch):
    monkeypatch.setattr(server, "STORE_DB_PATH", store_db)
    monkeypatch.setattr(server, "_browse", SqliteCatalog(store_db))
    monkeypatch.setattr(server, "_sessions", {})
    with TestClient(server.app) as c:
        yield c


def say(client, text, pid=None):
    ctx = {"page": "product", "product_id": pid} if pid else {"page": "listing"}
    r = client.post("/api/agent/message", json={"text": text, "context": ctx})
    assert r.status_code == 200, r.text
    return r.json()


def test_pages_served(client):
    for path in ["/", f"/product/{HOMETOWN_3S}", "/inspector", "/static/agent.js", "/static/styles.css"]:
        assert client.get(path).status_code == 200, path


def test_listing_search_and_filters(client):
    r = client.get("/api/products", params={"q": "sofa", "category": "furniture"}).json()
    assert r["total"] >= 50 and all(i["category"] == "furniture" for i in r["items"])
    r = client.get("/api/products", params={"q": "mug", "max_price": 200}).json()
    assert r["items"] and all(i["price_inr"] <= 200 for i in r["items"])
    assert client.get("/api/products", params={"q": "air fryer"}).json()["total"] == 0


def test_product_detail_and_404(client):
    d = client.get(f"/api/products/{DURIAN_BID_3S}").json()
    assert d["specs"]["Width"] == "1680 mm" and d["source_flags"]["stock/delivery/shipping"] == "simulated"
    assert client.get("/api/products/NOPE").status_code == 404


def test_meta_lists_the_four_categories(client):
    m = client.get("/api/meta").json()
    assert {c["slug"] for c in m["categories"]} == {"furniture", "home_furnishing", "home_decor", "kitchen_dining"}
    assert m["source"]["licence"] == "CC BY-SA 4.0, PromptCloud"


def test_na02_over_http_same_terminal_answer(client):
    a, b = say(client, "mobile"), say(client, "mobile")
    assert a["kind"] == b["kind"] == "NOT_AVAILABLE" and a["message"] == b["message"]


def test_listing_journey_to_one_order(client):
    r = say(client, "Find a 3-seater sofa under ₹30,000 that fits 200 cm")
    assert {x["product_id"] for x in r["recommendations"]} == {HOMETOWN_3S, DURIAN_BID_3S}
    assert client.post("/api/agent/select", json={"product_id": HOMETOWN_3S}).json()["kind"] == "CART_PROPOSED"
    assert client.post("/api/agent/approve").json()["kind"] == "APPROVED"
    done = client.post("/api/agent/checkout").json()
    assert done["kind"] == "ORDER_PLACED" and len(done["state"]["orders"]) == 1
    assert client.post("/api/agent/checkout").json()["state"]["orders"] == done["state"]["orders"]


def test_product_journey_with_price_change(client):
    assert say(client, "How wide is it?", DURIAN_BID_3S)["cited_fields"] == ["Width"]
    assert say(client, "Buy this", DURIAN_BID_3S)["kind"] == "CART_PROPOSED"
    client.post("/api/agent/approve")
    sim = client.post("/api/sim/price", json={"product_id": DURIAN_BID_3S, "price_inr": 18500}).json()
    assert sim["product"]["price_inr"] == 18500
    blocked = client.post("/api/agent/checkout").json()
    assert blocked["kind"] == "BLOCKED" and "PRICE_CHANGED_SINCE_APPROVAL" in blocked["reason_codes"]
    assert blocked["state"]["approval"]["status"] == "INVALIDATED" and blocked["state"]["orders"] == []


def test_sessions_are_isolated_per_browser(client, store_db):
    say(client, "Buy this", HOMETOWN_3S)
    client.post("/api/sim/price", json={"product_id": HOMETOWN_3S, "price_inr": 99999})
    with TestClient(server.app) as other:
        assert other.get(f"/api/products/{HOMETOWN_3S}").json()["price_inr"] == 14900
        assert other.get("/api/agent/state").json()["cart"] is None


def test_trace_and_state_endpoints(client):
    say(client, "mobile")
    t = client.get("/api/trace").json()
    names = [e["name"] for e in t["events"]]
    assert "intent.extracted" in names and "search_catalog" in names and "agent.response" in names
    st = client.get("/api/agent/state").json()
    assert st["history"][0] == {"role": "user", "text": "mobile"} and st["mode"] in ("rules", "claude")


def test_bad_input_rejected(client):
    assert client.post("/api/agent/message", json={"text": "   "}).status_code == 400
    assert client.post("/api/agent/message", json={"text": "x" * 1001}).status_code == 400
    assert client.post("/api/agent/bogus").status_code == 404
    assert client.post("/api/sim/price", json={"product_id": "NOPE", "price_inr": 5}).status_code == 400
