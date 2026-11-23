"""Follow-ups after a search (PM screenshots + Claude's probe, 2026-11-21; O-96 to O-109).

Every chat starts with the demo search, which shows 2 sofas:
  1. HomeTown CIAZ Fabric 3 Seater Sectional  ₹14,900, 9 days, 182 cm wide
  2. Durian BID/32625/A/3 Leatherette 3 Seater Sofa  ₹17,680, 5 days, 168 cm wide
Rules mode (conftest), so no AI quota is used and results repeat.
"""
import re

import pytest

from agent import Session

L = {"page": "listing"}
CIAZ_PAGE = {"page": "product", "product_id": "SOFEB7MHGWTHZFVJ"}
SOFA_ASK = "Find a 3-seater sofa under ₹30,000 that fits 200 cm"
BAD = re.compile(r"don't sell|didn't quite get|didn't understand|not something I can help", re.I)


def after_search(*turns, ctx=L):
    s = Session()
    shown = s.handle_message(SOFA_ASK, L).recommendations
    out = [s.handle_message(t, ctx) for t in turns]
    return s, shown, out


def cart_ids(s):
    return [ln.product_id for ln in s.cart.lines] if s.cart is not None and s.cart.status == "PROPOSED" else []


def ids(r):
    return [x["product_id"] for x in r.recommendations or []]


def ciaz(shown):
    return next(x["product_id"] for x in shown if "CIAZ" in x["title"])


def durian(shown):
    return next(x["product_id"] for x in shown if "Durian" in x["title"])


# ---- 1. regression from O-75: "will I get …" about refunds, invoices, discounts, dates is not a "comes with" question
@pytest.mark.parametrize("q,must", [
    ("will I get a refund if the product is damage?", r"48 hours|damaged|replacement"),
    ("will I get a replacement if it's broken?", r"48 hours|damaged|replacement"),
    ("will I get my money back?", r"refund|return"),
    ("will I get an invoice?", None),
    ("will I get a discount?", None),
    ("will I get it by friday?", r"\bdays?\b"),
])
def test_will_i_get_is_not_always_a_box_question(q, must):
    r = Session().handle_message(q, CIAZ_PAGE)
    assert "only the" not in r.message and "don't mention a" not in r.message, r.message
    assert r.kind in ("ANSWER", "CLARIFY"), f"{r.kind}: {r.message}"
    if must:
        assert re.search(must, r.message, re.I), r.message


def test_refund_if_damaged_on_the_store_page():
    r = Session().handle_message("will I get a refund if the product is damaged?", L)
    assert re.search(r"48 hours|damaged", r.message), r.message


# ---- 2. naming a shown product
@pytest.mark.parametrize("say,which", [
    ("I'll purchase Ciaz", ciaz), ("get me the ciaz", ciaz), ("ciaz please", ciaz),
    ("I'll purchase the durian", durian), ("buy the durian", durian), ("I'll take the hometown one", ciaz),
])
def test_buying_a_shown_product_by_name(say, which):
    s, shown, (r,) = after_search(say)
    assert cart_ids(s) == [which(shown)], f"{r.kind}: {r.message[:150]}"


@pytest.mark.parametrize("say,which", [("the durian", durian), ("durian", durian), ("ciaz", ciaz), ("the ciaz?", ciaz)])
def test_naming_a_shown_product_talks_about_it(say, which):
    s, shown, (r,) = after_search(say)
    assert r.kind == "ANSWER" and r.product_id == which(shown) and not cart_ids(s), f"{r.kind}: {r.message[:150]}"


# ---- 3. both
@pytest.mark.parametrize("say", ["buy both", "add both to cart", "I want both", "I want to buy the products that you have listed"])
def test_both(say):
    s, shown, (r,) = after_search(say)
    assert sorted(cart_ids(s)) == sorted(x["product_id"] for x in shown), f"{r.kind}: {r.message[:150]}"


# ---- 4. more results
@pytest.mark.parametrize("say", ["show more", "show me the others", "any other options?"])
def test_show_more(say):
    s, shown, (r,) = after_search(say)
    assert not BAD.search(r.message), r.message
    new = [i for i in ids(r) if i not in [x["product_id"] for x in shown]]
    assert new or re.search(r"\bonly\b", r.message), f"{r.kind}: {r.message[:200]}"


# ---- 5. the same question about another shown product
def test_what_about_the_other_one_keeps_the_question():
    s, shown, out = after_search("installation part of it?", "Ciaz fabric", "what about durian?")
    assert out[2].product_id == durian(shown) and "install" in out[2].message.lower(), out[2].message


@pytest.mark.parametrize("follow", ["and the durian?", "what about the second one?", "how about the durian"])
def test_width_question_carries_over(follow):
    s, shown, out = after_search("how wide is the ciaz?", follow)
    assert out[1].product_id == durian(shown) and "168" in out[1].message, out[1].message


def test_and_the_first_after_a_question_about_the_second():
    s, shown, out = after_search("how wide is the durian?", "and the first?")
    assert out[1].product_id == ciaz(shown) and "182" in out[1].message, out[1].message


# ---- 6. "What?" says the last answer again, plainly
@pytest.mark.parametrize("say", ["What?", "huh?", "what do you mean?", "I don't understand"])
def test_confusion_restates_the_last_answer(say):
    s, shown, out = after_search("how wide is the ciaz?", say)
    assert not BAD.search(out[1].message) and "182" in out[1].message, out[1].message


# ---- 7. pushback about what was shown
@pytest.mark.parametrize("say", ["But already listed them above", "you just showed me sofas", "you already showed them"])
def test_pushback_lists_what_was_shown(say):
    s, shown, (r,) = after_search(say)
    assert not BAD.search(r.message) and "CIAZ" in r.message and "Durian" in r.message, r.message


# ---- 8. simple comparisons
@pytest.mark.parametrize("say,winner,fact", [
    ("which one is cheaper?", "CIAZ", "14,900"), ("which is wider?", "CIAZ", "181.5"),
    ("which one arrives first?", "Durian", "5 days"), ("which is the narrowest?", "Durian", "168"),
])
def test_simple_comparisons(say, winner, fact):
    s, shown, (r,) = after_search(say)
    assert r.kind == "ANSWER" and winner in r.message.split(".")[0] and fact in r.message, r.message


@pytest.mark.parametrize("say", ["what's the difference between them?", "compare them", "tell me more about both"])
def test_side_by_side(say):
    s, shown, (r,) = after_search(say)
    assert r.kind == "ANSWER" and all(w in r.message for w in ("CIAZ", "Durian", "14,900", "17,680")), r.message


# ---- 9. returns for a named shown product
def test_return_policy_for_a_shown_product():
    s, shown, (r,) = after_search("can I return the ciaz?")
    assert re.search(r"return", r.message, re.I) and "don't have that detail" not in r.message, r.message


# ---- 10. cheaper than a shown product
@pytest.mark.parametrize("say,limit", [("the durian is too expensive", 17680), ("something cheaper than the durian", 17680),
                                       ("the ciaz is too expensive", 14900)])
def test_cheaper_than_a_shown_product(say, limit):
    s, shown, (r,) = after_search(say)
    assert not BAD.search(r.message) and not cart_ids(s), r.message
    totals = [x.get("total_inr") for x in r.recommendations or []]
    assert (totals and all(t < limit for t in totals)) or re.search(r"cheapest|lowest", r.message, re.I), r.message


# ---- 11. narrowing what was shown
def test_only_leather_ones():
    s, shown, (r,) = after_search("show me only leather ones")
    assert not BAD.search(r.message) and r.recommendations, r.message
    assert all("leather" in x["title"].lower() for x in r.recommendations), [x["title"] for x in r.recommendations]


# ---- 12. none of these
@pytest.mark.parametrize("say", ["none of these", "I don't like these", "not these"])
def test_none_of_these_asks_what_to_change(say):
    s, shown, (r,) = after_search(say)
    assert r.kind == "CLARIFY" and re.search(r"budget|size|seats|material|change", r.message, re.I), r.message


# ---- 13. why others were left out
def test_why_others_were_left_out():
    s, shown, (r,) = after_search("why did you leave out others?")
    assert not BAD.search(r.message) and re.search(r"budget|wide|seat|left out", r.message, re.I), r.message


# ---- 14. ok
def test_ok_gets_a_gentle_next_step():
    s, shown, (r,) = after_search("ok")
    assert not BAD.search(r.message) and re.search(r"cart|which|add|like", r.message, re.I), r.message


# ---- FOCUS_DESIGN F1 to F8 (approved 2026-11-21)
def test_f2_a_question_with_no_focus_offers_buttons():
    s, shown, (r,) = after_search("installation?")
    assert r.kind == "CLARIFY" and [c["product_id"] for c in r.choices] == [x["product_id"] for x in shown], r.message


def test_f2_tapping_both_answers_the_waiting_question_for_both():
    s, shown, (r,) = after_search("installation?")
    r = s.choose([x["product_id"] for x in shown])
    assert r.kind == "ANSWER" and "install" in r.message.lower() and len(r.about) == 2, r.message
    assert s.focus == [x["product_id"] for x in shown]


def test_f1_one_in_focus_answers_without_asking():
    s, shown, _ = after_search()
    s.set_focus([durian(shown)])
    r = s.handle_message("how wide is it?", L)
    assert r.kind == "ANSWER" and "168" in r.message and r.about[0]["product_id"] == durian(shown), r.message


def test_f1_two_in_focus_answer_each():
    s, shown, _ = after_search()
    s.set_focus([ciaz(shown), durian(shown)])
    r = s.handle_message("how wide is it?", L)
    assert "181" in r.message or "182" in r.message
    assert "168" in r.message and len(r.about) == 2, r.message


def test_f3_naming_a_product_moves_the_focus():
    s, shown, _ = after_search("how wide is the durian?")
    assert s.focus == [durian(shown)]


def test_f4_a_new_search_clears_the_focus():
    s, shown, _ = after_search()
    s.set_focus([ciaz(shown)])
    s.handle_message("show me beds", L)
    assert s.focus == []


def test_f5_buy_with_focus_adds_exactly_the_focus():
    s, shown, _ = after_search()
    s.set_focus([durian(shown)])
    s.handle_message("add to cart", L)
    assert cart_ids(s) == [durian(shown)]


def test_f6_compare_with_focus():
    s, shown, _ = after_search()
    s.set_focus([ciaz(shown), durian(shown)])
    r = s.handle_message("which one is cheaper?", L)
    assert "CIAZ" in r.message.split(".")[0] and "14,900" in r.message, r.message


def test_f8_focus_only_takes_products_the_shopper_has_seen():
    s, shown, _ = after_search()
    assert s.set_focus(["NOT-A-REAL-ID", ciaz(shown)]) == [ciaz(shown)]
    assert len(s.set_focus([x["product_id"] for x in shown] * 3)) <= 3


def test_product_page_focus_is_that_product():
    s = Session()
    r = s.handle_message("how wide is it?", CIAZ_PAGE)
    assert s.focus == ["SOFEB7MHGWTHZFVJ"] and r.about and r.about[0]["product_id"] == "SOFEB7MHGWTHZFVJ"


def test_bedsheets_question_with_focus_is_still_a_search():
    s, shown, _ = after_search()
    s.set_focus([ciaz(shown)])
    r = s.handle_message("bedsheets?", L)
    assert r.kind == "RECOMMEND" and all("bedsheet" in x["title"].lower() for x in r.recommendations), r.message


def test_basic_mode_is_honest():
    r = Session().handle_message("blorp the flazzle", L)
    assert "basic mode" in r.message or r.kind != "UNSUPPORTED", r.message


@pytest.mark.parametrize("q", ["Do we sell mobiles?", "do you sell mobiles?", "mobiles?", "do you have iphones?"])
def test_store_questions_after_a_search_are_not_about_the_shown_sofas(q):
    s, shown, (r,) = after_search(q)
    assert r.kind == "NOT_AVAILABLE" and not r.choices, f"{r.kind}: {r.message}"


def test_store_question_with_focus_is_not_about_the_focus():
    s, shown, _ = after_search()
    s.set_focus([ciaz(shown)])
    r = s.handle_message("Do we sell mobiles?", L)
    assert r.kind == "NOT_AVAILABLE", r.message
