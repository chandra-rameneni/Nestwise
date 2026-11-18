"""PRD v2 acceptance tests (PRD.md §9) on the real home-and-living catalog, rules extractor.

Product IDs below are real Flipkart pids; prices are historical, stock and delivery simulated
(deterministic from the pid, see build_catalog.simulated_inventory).
"""
import qa
from catalog import SqliteCatalog
from intent import IntentExtraction

LISTING = {"page": "listing"}
HOMETOWN_3S = "SOFEB7MHGWTHZFVJ"     # HomeTown CIAZ Fabric 3 Seater Sectional, 181.5 cm, ₹14,900, stock 12
DURIAN_BID_3S = "SOFE9FS5PGNNQV9N"   # Durian BID 3 Seater, Width 1680 mm, ₹17,680, stock 11
DURIAN_BERRY_3S = "SOFE8BZMFT7VRBSJ"  # Durian Berry 3 Seater, 190.5 cm, ₹31,590
COMFORT_COUCH = "SOFEGDV3HGY3AB43"   # Comfort Couch 3 Seater, 215.9 cm
ARRA_7S = "SOFEDVYZ29EW7VEP"         # ARRA Solid Wood 7 Seater, listed Width 700 mm (implausible)
OUT_OF_STOCK_1S = "SOFE8BZMZWJYZUWW"  # Durian Berry 1 Seater, simulated stock 0
SOFA_QUERY = "Find a 3-seater sofa under ₹30,000 that fits 200 cm"


def page(pid):
    return {"page": "product", "product_id": pid}


# ------------------------------------------------------------------ R1: not sold here
def test_na01_mobile_not_available_and_no_question(store):
    r = store.handle_message("mobile", LISTING)
    assert r.kind == "NOT_AVAILABLE" and "NOT_SOLD_HERE" in r.reason_codes
    assert "We don't sell mobile" in r.message and "furniture" in r.message
    assert "?" not in r.message and r.recommendations == []


def test_na01b_question_phrasing(store):
    # Found in the Phase 3 browser check (F-011): "Do you sell mobiles?" became "We don't sell do sell mobiles."
    for text in ["Do you sell mobiles?", "Do you have air fryers?", "Is there a mobile?"]:
        r = store.handle_message(text, LISTING)
        assert r.kind == "NOT_AVAILABLE" and "sell do" not in r.message and "sell is" not in r.message, r.message
    assert store.handle_message("Do you sell sofas?", LISTING).kind in ("CLARIFY", "RECOMMEND")


def test_na02_same_answer_twice_no_loop(store):
    first = store.handle_message("mobile", LISTING)
    second = store.handle_message("mobile", LISTING)
    assert first.kind == second.kind == "NOT_AVAILABLE" and first.message == second.message
    assert "What are you shopping for" not in second.message


def test_na03_decided_by_search_not_a_word_list(store):
    assert store.handle_message("air fryer", LISTING).kind == "NOT_AVAILABLE"
    assert store.handle_message("pressure cooker", LISTING).kind == "RECOMMEND"


def test_r3_greeting_is_one_short_reply_not_not_available(store):
    r = store.handle_message("hello", LISTING)
    assert r.kind == "UNSUPPORTED" and "find and compare products" in r.message


# ------------------------------------------------------------------ R2: no repeated questions
def test_cl01_clarification_not_repeated_verbatim(store):
    first = store.handle_message("I need something", LISTING)
    second = store.handle_message("not sure", LISTING)
    assert first.kind == second.kind == "CLARIFY"
    assert first.message != second.message and second.message.startswith("I still need")
    assert store.tracer.find("agent", "clarify.repeat_suppressed")


def test_sofa_without_fit_info_asks_once_then_recommends(store):
    assert store.handle_message("I want to buy a sofa under ₹30,000", LISTING).kind == "CLARIFY"
    r = store.handle_message("3 seats, and it must fit in 200 cm of wall space", LISTING)
    assert r.kind == "RECOMMEND" and store.intent.max_total_inr == 30000


# ------------------------------------------------------------------ Journey B: listing page
def test_ls01_only_products_meeting_every_requirement(store):
    r = store.handle_message(SOFA_QUERY, LISTING)
    assert r.kind == "RECOMMEND"
    assert {x["product_id"] for x in r.recommendations} == {HOMETOWN_3S, DURIAN_BID_3S}
    for rec in r.recommendations:
        assert all(c["status"] == "pass" for c in rec["checks"])
    rejected = {x["product_id"]: x["reason_codes"] for x in r.rejected}
    assert rejected[COMFORT_COUCH] == ["WIDTH_EXCEEDED"]
    assert "BUDGET_EXCEEDED" in rejected[DURIAN_BERRY_3S]
    assert "WIDTH_UNVERIFIED" in rejected["SOFEDVYZQNYZYYFT"]       # ARRA 3 seater, implausible 71 cm width


def test_ls02_budget_change_after_approval_invalidates_and_researches(store):
    store.handle_message(SOFA_QUERY, LISTING)
    store.select_product(HOMETOWN_3S)
    store.approve()
    r = store.handle_message("Actually ₹35,000", LISTING)
    assert store.approval.status == "INVALIDATED"
    assert DURIAN_BERRY_3S in [x["product_id"] for x in r.recommendations] or r.kind == "RECOMMEND"
    assert store.checkout().kind == "BLOCKED" and store.orders.orders == {}


def test_px01_price_change_blocks_then_reapproval_places_one_order(store):
    store.handle_message(SOFA_QUERY, LISTING)
    store.select_product(HOMETOWN_3S)
    store.approve()
    store.simulate_price_change(HOMETOWN_3S, 15400)
    r = store.checkout()
    assert r.kind == "BLOCKED" and "PRICE_CHANGED_SINCE_APPROVAL" in r.reason_codes
    assert store.orders.orders == {}
    store.select_product(HOMETOWN_3S)
    store.approve()
    assert store.checkout().kind == "ORDER_PLACED" and len(store.orders.orders) == 1
    assert store.checkout().kind == "ORDER_PLACED" and len(store.orders.orders) == 1   # retry is idempotent


# ------------------------------------------------------------------ Journey A: product page
def test_pq01_width_answer_cites_the_width_field(store):
    r = store.handle_message("How wide is it?", page(DURIAN_BID_3S))
    assert r.kind == "ANSWER" and "1680 mm" in r.message and r.cited_fields == ["Width"]


def test_pq02_not_in_listing(store, store_db):
    p = SqliteCatalog(store_db).get(DURIAN_BID_3S)
    assert "water" not in (p.description + " ".join(p.raw_specs)).lower()
    r = store.handle_message("Is it waterproof?", page(DURIAN_BID_3S))
    assert r.kind == "ANSWER" and r.message == "The listing doesn't say." and "NOT_IN_LISTING" in r.reason_codes


def test_requirement_question_uses_the_policy_check(store):
    r = store.handle_message("Will it fit a 2 m wall?", page(COMFORT_COUCH))
    assert r.kind == "ANSWER" and r.message.startswith("No on width") and "215.9" in r.message
    r = store.handle_message("Will it fit a 2 m wall?", page(DURIAN_BID_3S))
    assert r.message.startswith("Yes on width")


def test_implausible_listed_width_is_not_relied_on(store):
    r = store.handle_message("Will it fit a 2 m wall?", page(ARRA_7S))
    assert "can't confirm the width" in r.message and "700 mm" in r.message
    r = store.handle_message("How wide is it?", page(ARRA_7S))
    assert "700 mm" in r.message and "doesn't look right" in r.message


def test_pq04_llm_answer_citing_a_missing_field_is_rejected(store_db, monkeypatch):
    p = SqliteCatalog(store_db).get(DURIAN_BID_3S)
    fake = qa.ProductAnswer(answer="It is fully waterproof.", cited_fields=["Waterproof Rating"])
    monkeypatch.setattr(qa, "_ask_llm", lambda prod, q: (fake, {"model": "test-double"}))
    res = qa.answer_about_product(p, "Is it waterproof?", IntentExtraction(intent="PRODUCT_QUESTION"), use_llm=True)
    assert res.status == "rejected" and "waterproof" not in res.answer.lower().replace("listing doesn't say", "")
    assert "Waterproof Rating" in res.meta["rejected"]


def test_pq04b_grounded_llm_answer_is_accepted(store_db, monkeypatch):
    p = SqliteCatalog(store_db).get(DURIAN_BID_3S)
    fake = qa.ProductAnswer(answer="About 168 cm wide.", cited_fields=["Width"])
    monkeypatch.setattr(qa, "_ask_llm", lambda prod, q: (fake, {}))
    res = qa.answer_about_product(p, "how wide", IntentExtraction(intent="PRODUCT_QUESTION"), use_llm=True)
    assert res.status == "ok" and res.method == "llm"


def test_cx01_answers_are_about_the_current_product(store):
    a = store.handle_message("How wide is it?", page(DURIAN_BID_3S))
    b = store.handle_message("How wide is it?", page(COMFORT_COUCH))
    assert "1680 mm" in a.message and "2159 mm" in b.message
    assert a.product_id == DURIAN_BID_3S and b.product_id == COMFORT_COUCH


def test_bt01_buy_this_exact_cart_approval_one_order(store):
    r = store.handle_message("Buy this", page(HOMETOWN_3S))
    assert r.kind == "CART_PROPOSED" and r.cart.product_id == HOMETOWN_3S and r.cart.total_inr == 14900
    assert store.checkout().kind == "BLOCKED"                     # not approved yet
    store.approve()
    assert store.checkout().kind == "ORDER_PLACED" and len(store.orders.orders) == 1


def test_bt02_buy_this_breaking_stated_budget_is_blocked_with_alternatives(store):
    r = store.handle_message("Buy this, my budget is ₹15,000", page(DURIAN_BID_3S))
    assert r.kind == "BLOCKED" and "BUDGET_EXCEEDED" in r.reason_codes and store.cart is None
    assert r.recommendations and all(x["total_inr"] <= 15000 for x in r.recommendations)
    assert DURIAN_BID_3S not in [x["product_id"] for x in r.recommendations]


def test_buy_this_out_of_stock_is_blocked(store):
    r = store.handle_message("Buy this", page(OUT_OF_STOCK_1S))
    assert r.kind == "BLOCKED" and "OUT_OF_STOCK" in r.reason_codes and store.orders.orders == {}


# ------------------------------------------------------------------ regressions from eval run 20261118T015110Z_rules
def test_eval_bt06_product_without_price_never_reaches_a_cart(store):
    r = store.handle_message("Buy this", page("CNSEH3GZGG6VYT54"))     # listing has no price
    assert r.kind == "BLOCKED" and "PRICE_UNKNOWN" in r.reason_codes and store.cart is None


def test_eval_ls06_cheapest_phrasing_searches_sofas(store):
    r = store.handle_message("what's the cheapest 2 seater sofa that fits 1.5 m", LISTING)
    assert r.kind == "RECOMMEND" and all(x["specs"]["seats"] == 2 for x in r.recommendations)


def test_eval_cl03_vague_request_asks_what_product(store):
    r = store.handle_message("something to sit on", LISTING)
    assert r.kind == "CLARIFY" and "What product" in r.message


def test_eval_pq07_generic_word_doesnt_pull_in_other_fields(store):
    r = store.handle_message("Is it microwave safe?", page("BWLEHTBPHRBSDEYF"))
    assert r.cited_fields == ["Microwave Safe"]


def test_cheaper_like_this_same_kind_below_current_price(store):
    r = store.handle_message("Show me cheaper ones like this", page(DURIAN_BERRY_3S))
    assert r.kind == "RECOMMEND" and r.recommendations
    assert all(x["total_inr"] < 31590 and "sofa" in x["title"].lower() for x in r.recommendations)
    assert DURIAN_BERRY_3S not in [x["product_id"] for x in r.recommendations]


def test_product_page_price_change_after_buy_this_recovers(store):
    store.handle_message("Buy this", page(HOMETOWN_3S))
    store.approve()
    store.simulate_price_change(HOMETOWN_3S, 16000)
    r = store.checkout()
    assert r.kind == "BLOCKED" and "no longer applies" in r.message and store.orders.orders == {}
