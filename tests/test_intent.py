"""Group A: intent and routing (INT-01..08), rules extractor + merge logic. LLM tests at the bottom."""
import os

import pytest

from conftest import KEYBOARD_REQUEST
from intent import extract, extract_rules, merge


def test_int01_sofa_discovery():
    x = extract_rules("Find a three-seater sofa under ₹30,000.")
    assert x.intent == "PRODUCT_DISCOVERY"
    assert x.category == "sofa" and x.seats == 3 and x.max_total_inr == 30000


def test_int02_refund_recognised():
    assert extract_rules("I want a refund for my sofa.").intent == "REFUND_REQUEST"


def test_int03_tracking_recognised():
    assert extract_rules("Where is my order?").intent == "ORDER_TRACKING"


def test_int04_vague_request_asks_instead_of_inventing_budget():
    x = extract_rules("I need something affordable.")
    assert x.max_total_inr is None
    assert "product" in x.missing_info and "budget" in x.missing_info


def test_int05_brand_is_soft_preference():
    x = extract_rules("Keyboard and mouse combo, prefer Logitech; other brands okay.")
    assert x.preferred_brands == ["Logitech"]


def test_int06_budget_including_delivery():
    x = extract_rules("Keyboard and mouse combo, not more than ₹4,000 including delivery")
    assert x.max_total_inr == 4000


def test_int07_budget_update_keeps_other_constraints():
    first, _, _ = extract(KEYBOARD_REQUEST, None)
    updated, changed, _ = extract("Actually, budget is ₹5,000.", first)
    assert updated.max_total_inr == 5000
    assert changed == ["max_total_inr"]
    assert updated.version == first.version + 1
    assert updated.required_compatibility == ["macOS"]
    assert updated.max_delivery_days == 5 and updated.preferred_brands == ["Logitech"]
    assert updated.category == "keyboard_mouse_combo"


def test_int08_sofa_without_fit_info_searches_first():
    # PRD B18 (Phase 2): seats and width are no longer required before a search.
    x, _, _ = extract("I want to buy a sofa", None)
    assert "seats" not in x.missing_info and "max_width_cm" not in x.missing_info


def test_keyboard_request_fields():
    x = extract_rules(KEYBOARD_REQUEST)
    assert (x.category, x.max_total_inr, x.max_delivery_days) == ("keyboard_mouse_combo", 4000, 5)
    assert x.required_compatibility == ["macOS"] and x.preferred_brands == ["Logitech"]


def test_single_word_product_is_a_search_not_unsupported():
    # Observed in manual UI testing (F-003): "mobile" got the generic "What are you shopping for?" reply.
    x = extract_rules("mobile")
    assert x.intent == "PRODUCT_DISCOVERY" and x.product_query == "mobile"


def test_single_word_unknown_product_says_not_in_catalog(session):
    r = session.handle_message("mobile")
    assert r.kind == "NOT_AVAILABLE" and "mobile" in r.message and r.recommendations == []


def test_4k_shorthand():
    assert extract_rules("keyboard and mouse under 4k").max_total_inr == 4000


# ------------------------------------------------------------------ real model (opt-in)
needs_key = pytest.mark.skipif(not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
                               reason="no Anthropic credentials; LLM extraction not exercised")


@pytest.mark.llm
@needs_key
def test_llm_extracts_keyboard_request():
    x, _, meta = extract(KEYBOARD_REQUEST, None)
    assert x.extractor.startswith("llm:"), meta
    assert x.category == "keyboard_mouse_combo" and x.max_total_inr == 4000 and x.max_delivery_days == 5
    assert "macOS" in x.required_compatibility


@pytest.mark.llm
@needs_key
def test_llm_routes_refund_and_tracking():
    assert extract("I want a refund for my sofa.", None)[0].intent == "REFUND_REQUEST"
    assert extract("Where is my order?", None)[0].intent == "ORDER_TRACKING"
