import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import Session  # noqa: E402
from catalog import Catalog  # noqa: E402
from tracing import Tracer  # noqa: E402

KEYBOARD_REQUEST = ("Find a Mac-compatible wireless keyboard and mouse combo within ₹4,000 including delivery, "
                    "arriving in five days; prefer Logitech; ask before buying.")


@pytest.fixture(autouse=True)
def saved_chats_to_tmp(monkeypatch, tmp_path_factory):
    """Tests never write saved chats into the real data/sessions/ folder."""
    if "server" in sys.modules:
        monkeypatch.setattr(sys.modules["server"], "SESSION_DIR", tmp_path_factory.mktemp("sessions"))


@pytest.fixture(autouse=True)
def traces_to_tmp(monkeypatch, tmp_path_factory):
    """PRD §14: tests never write to the real traces/ folder (it feeds the observability dashboard)."""
    import tracing
    monkeypatch.setattr(tracing, "TRACE_DIR", tmp_path_factory.mktemp("traces"))


@pytest.fixture(autouse=True)
def no_real_payment_keys(monkeypatch):
    """Audit finding A (2026-11-20): with real Razorpay test keys in the shell, 17 tests failed, because checkout
    then asks for payment. Tests never use the shell's keys (and never call Razorpay); the payment tests set fakes."""
    for var in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def no_real_models(monkeypatch, request):
    """Tests never call a real AI model; AI-agent tests use a stand-in model (tests/test_ai_agent.py)."""
    if "llm" not in request.keywords:
        monkeypatch.setenv("INTENTGUARD_LLM", "off")


def keyboard_search(session):
    """The requirements the AI's search tool records for KEYBOARD_REQUEST (budget, delivery, Mac, Logitech)."""
    from intent import Intent
    session.intent = Intent(intent="PRODUCT_DISCOVERY", category="keyboard_mouse_combo",
                            product_query="wireless keyboard and mouse combo", max_total_inr=4000, max_delivery_days=5,
                            required_compatibility=["mac"], preferred_brands=["Logitech"])
    session.eligible_ids = [pid for pid in getattr(session.catalog, "_products", {}) if pid.startswith("KM-")]


def agent_adds(client, pid):
    """Over HTTP: what the AI's add_to_cart tool does when the shopper says "buy this" on a product page."""
    import server
    client.get("/api/agent/state")
    server._sessions[client.cookies.get(server.COOKIE)].select_product(pid, from_product_page=True)


@pytest.fixture
def session():
    return Session(catalog=Catalog(), tracer=Tracer(persist=False))


@pytest.fixture(scope="session")
def store_db(tmp_path_factory):
    """A fresh real-store database built from the Flipkart CSV (skipped if the CSV isn't present)."""
    import build_catalog as bc
    if not bc.DEFAULT_CSV.exists():
        pytest.skip("Flipkart CSV not present in data/raw/flipkart/")
    db = tmp_path_factory.mktemp("store") / "catalog.sqlite"
    bc.build(bc.DEFAULT_CSV, db)
    return db


@pytest.fixture
def store(store_db):
    """An agent session on the real store catalog (fresh price/stock overrides each test)."""
    from catalog import SqliteCatalog
    return Session(catalog=SqliteCatalog(store_db), tracer=Tracer(persist=False))


def pytest_configure(config):
    config.addinivalue_line("markers", "llm: calls the real Claude API (skipped without credentials)")
