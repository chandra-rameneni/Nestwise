"""Phase 1: the real catalog built from the Flipkart CSV (build_catalog.py + catalog.SqliteCatalog).

Builds a fresh database in a temp folder, so the test doesn't depend on a previously built file.
Skipped when the raw CSV isn't present (it is not committed to git; see data/DATA_PROFILE.md).
"""
import hashlib
import sqlite3

import pytest

import build_catalog as bc
from catalog import SqliteCatalog

pytestmark = pytest.mark.skipif(not bc.DEFAULT_CSV.exists(), reason="Flipkart CSV not present in data/raw/flipkart/")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    db = tmp_path_factory.mktemp("store") / "catalog.sqlite"
    stats = bc.build(bc.DEFAULT_CSV, db)
    return db, stats


@pytest.fixture
def cat(built):
    return SqliteCatalog(built[0])


# ------------------------------------------------------------------ build
def test_slice_size_and_dedupe(built):
    _, stats = built
    assert stats["rows_in_scope"] == 2456
    assert stats["duplicates_dropped"] == 413
    assert stats["products"] == 2043


def test_only_the_four_categories(cat):
    assert {c["slug"] for c in cat.categories()} == {"furniture", "home_furnishing", "home_decor", "kitchen_dining"}


def test_provenance_recorded(built):
    con = sqlite3.connect(built[0])
    meta = dict(con.execute("SELECT key, value FROM meta"))
    assert meta["licence"] == "CC BY-SA 4.0, PromptCloud"
    assert meta["csv_sha256"] == hashlib.sha256(bc.DEFAULT_CSV.read_bytes()).hexdigest()
    assert {r[0] for r in con.execute("SELECT DISTINCT source FROM inventory")} == {"simulated"}
    assert all(s.startswith("historical") for (s,) in con.execute("SELECT DISTINCT source FROM prices"))


@pytest.mark.parametrize("raw,expected", [
    ("1905 mm", 190.5), ("190 cm", 190.0), ("75 inch / 190 cm", 190.0), ("6 inch", 15.2), ("2 m", 200.0),
    ("190", None), ("45 cm55 cm", None), ("NA cm", None),
])
def test_length_parsing_is_strict(raw, expected):
    assert bc.length_cm(raw) == expected


def test_other_unit_parsing():
    assert bc.weight_kg("500 g") == 0.5 and bc.weight_kg("40 kg") == 40 and bc.weight_kg("40") is None
    assert bc.capacity_l("750 ml") == 0.75 and bc.capacity_l("3 L") == 3 and bc.capacity_l("3 L L") is None
    assert bc.seats("3 Seater") == 3 and bc.seats("Three") is None


def test_product_name_is_not_kept_as_a_category():
    cats, leaf = bc.split_tree(["Furniture", "Living Room Furniture", "Sofas & Sectionals",
                                "Comfort Couch Engineered Wood 3 Seater Sofa (Fin.."],
                               "Comfort Couch Engineered Wood 3 Seater Sofa (Finish Color - Brown)")
    assert leaf == "Sofas & Sectionals" and cats[-1] == "Sofas & Sectionals"


def test_simulated_inventory_is_deterministic():
    assert bc.simulated_inventory("SBEEH3QGU7MFYJFY", "furniture", 22646) == \
        bc.simulated_inventory("SBEEH3QGU7MFYJFY", "furniture", 22646)


# ------------------------------------------------------------------ search (rule R1 depends on this)
def test_sofa_matches_are_sofas_and_covers_are_only_related(cat):
    matches, related = cat.find_products("sofa")
    assert len(matches) >= 50
    assert not any("cover" in cat.get(p).title.lower() for p in matches)
    assert any("cover" in cat.get(p).title.lower() for p in related)


def test_mobile_is_not_sold_even_though_mobile_stands_mention_it(cat):
    matches, related = cat.find_products("mobile")
    assert matches == [] and related              # only showpieces that mention "mobile"


def test_air_fryer_not_in_catalog(cat):
    assert cat.find_products("air fryer") == ([], [])


@pytest.mark.parametrize("query", ["bed sheet", "bedsheet", "curtain", "pressure cooker", "mug", "table lamp"])
def test_common_home_products_are_found(cat, query):
    matches, _ = cat.find_products(query)
    assert matches, query


def test_table_lamp_is_not_a_table(cat):
    matches, _ = cat.find_products("table")
    assert not any(cat.get(p).title.lower().endswith("lamp") for p in matches)


# ------------------------------------------------------------------ product view
def test_product_view_has_attributes_raw_specs_and_flags(cat):
    sofa = next(cat.get(p) for p in cat.find_products("3 seater sofa")[0] if cat.get(p).specs.get("seats") == 3)
    assert isinstance(sofa.specs["seats"], int) and sofa.specs.get("width_cm")
    assert "Seating Capacity" in sofa.raw_specs
    assert sofa.source_flags["stock/delivery/shipping"] == "simulated"
    assert sofa.total_for() == sofa.list_price_inr + sofa.shipping_inr


def test_missing_price_means_unknown_total(cat, built):
    con = sqlite3.connect(built[0])
    row = con.execute("SELECT pid FROM prices WHERE price_inr IS NULL LIMIT 1").fetchone()
    assert row, "dataset has 4 products without a price"
    assert cat.get(row[0]).total_for() is None


def test_simulated_price_change_bumps_version_and_never_touches_the_file(cat, built):
    pid = cat.find_products("sofa")[0][0]
    before_bytes = built[0].read_bytes()
    v1 = cat.get(pid).version
    cat.set_price(pid, 12345)
    p = cat.get(pid)
    assert p.list_price_inr == 12345 and p.version == v1 + 1
    assert "changed by demo simulation" in p.source_flags["price"]
    assert built[0].read_bytes() == before_bytes
