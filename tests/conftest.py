import os
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
def rules_only(monkeypatch, request):
    """Deterministic tests use the rules extractor unless a test is marked `llm`."""
    if "llm" not in request.keywords:
        monkeypatch.setenv("INTENTGUARD_LLM", "off")


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
