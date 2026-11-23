"""The AI agent loop (agent_llm.py) with a stand-in model, so tests are repeatable and use no AI quota.
The stand-in returns the tool calls and replies a real model would; the code under test is everything around it:
running the tools on real store data, the cart, the focus, the price check and the honest reply when no model answers."""
import json

import agent_llm
import intent as intent_mod
import llm
from agent import Session

L = {"page": "listing"}
CIAZ, DURIAN = "SOFEB7MHGWTHZFVJ", "SOFE9FS5PGNNQV9N"


def call(name, **args):
    return {"id": f"c{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def fake_model(monkeypatch, script):
    """script: list of assistant messages, returned one per model step."""
    steps = list(script)
    seen = []

    def chat_tools(messages, tools, deadline, avoid=None):
        seen.append([dict(m) for m in messages])
        if not steps:
            return None, {"error": "no model answered"}
        return steps.pop(0), {"provider": "fake", "model": "fake-model"}
    monkeypatch.setattr(intent_mod, "llm_available", lambda: True)
    monkeypatch.setattr(llm, "chat_tools", chat_tools)
    return seen


def test_agent_searches_with_tools_and_writes_its_own_reply(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "content": "I found two: the HomeTown CIAZ Fabric 3 Seater Sectional at ₹14,900 and "
                                         "the Durian BID/32625/A/3 Leatherette 3 Seater Sofa at ₹17,680."}])
    s = Session()
    r = s.handle_message("Find a 3-seater sofa under ₹30,000 that fits 200 cm", L)
    assert r.kind == "RECOMMEND" and r.message.startswith("I found two")
    assert {x["product_id"] for x in r.recommendations} == {CIAZ, DURIAN}
    assert r.steps and r.steps[0].startswith("Searched sofa") and r.model == "fake-model"


def test_agent_puts_products_in_the_cart_but_never_approves(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "tool_calls": [call("add_to_cart", product_ids=[CIAZ, DURIAN])]},
        {"role": "assistant", "content": "Both are in your cart, ₹32,580 in total. Tap Approve when you're ready."}])
    s = Session()
    r = s.handle_message("buy both of the 3 seater sofas under 30000 that fit 200 cm", L)
    assert r.kind == "CART_PROPOSED" and sorted(ln.product_id for ln in s.cart.lines) == sorted([CIAZ, DURIAN])
    assert s.approval is None and not s.orders.orders


def test_invented_price_is_sent_back_then_blocked(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("get_product", product_id=CIAZ)]},
        {"role": "assistant", "content": "It costs ₹9,999."},
        {"role": "assistant", "content": "It costs ₹9,999, honestly."}])
    monkeypatch.setattr(llm, "AGENT_BUDGET_S", 1)          # no retry pauses in the test
    r = Session().handle_message("how much is the ciaz?", L)
    assert "9,999" not in r.message                      # an invented price is never shown


def test_invented_price_corrected_after_the_check(monkeypatch):
    seen = fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("get_product", product_id=CIAZ)]},
        {"role": "assistant", "content": "It costs ₹9,999."},
        {"role": "assistant", "content": "It costs ₹14,900 including delivery."}])
    r = Session().handle_message("how much is the ciaz?", L)
    assert r.message == "It costs ₹14,900 including delivery."
    assert "which no tool returned" in seen[-1][-1]["content"]


def test_the_agent_sees_focus_shown_products_and_the_conversation(monkeypatch):
    seen = fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "content": "Here are two sofas."},
        {"role": "assistant", "content": "The Durian is 168 cm wide."}])
    s = Session()
    s.handle_message("3 seater sofa under 30000 that fits 200 cm", L)
    s.set_focus([DURIAN])
    s.handle_message("how wide is it?", L)
    system, last_user = seen[-1][0]["content"], seen[-1][-1]["content"]
    assert DURIAN in system and "in focus" in system and CIAZ in system
    assert any((m.get("content") or "").endswith("Here are two sofas.") for m in seen[-1]) and last_user == "how wide is it?"


def test_product_page_is_in_the_agents_context(monkeypatch):
    seen = fake_model(monkeypatch, [{"role": "assistant", "content": "It doesn't come with a mattress."}])
    s = Session()
    s.handle_message("will I get a mattress with it?", {"page": "product", "product_id": "BDDEH29DNAN4AKYH"})
    assert "BDDEH29DNAN4AKYH" in seen[0][0]["content"] and s.focus == ["BDDEH29DNAN4AKYH"]


def test_no_model_answers_says_so_and_never_uses_the_old_engine(monkeypatch):
    fake_model(monkeypatch, [])
    monkeypatch.setattr(llm, "AGENT_BUDGET_S", 1)          # no retry pauses in the test
    r = Session().handle_message("do you sell mobiles?", L)
    assert r.message.startswith("Sorry, the AI models are busy") and not r.recommendations


def test_payment_requests_never_reach_the_agent(monkeypatch):
    seen = fake_model(monkeypatch, [{"role": "assistant", "content": "Paid!"}])
    r = Session().handle_message("pay for me now", L)
    assert "only you can do" in r.message and not seen


def test_search_tool_honours_category_colour_and_exclusions():
    s, t = Session(), agent_llm.Turn()
    res = agent_llm._search(s, t, {"category": "kitchen_dining", "max_total_inr": 1000})
    assert res["matched_products"] > 50                  # "something for the kitchen under 1000" isn't 1 item
    res = agent_llm._search(s, t, {"query": "sofa", "exclude_material": "leather", "max_total_inr": 20000})
    assert res["products"] and all("leather" not in p["title"].lower() for p in res["products"])
    res = agent_llm._search(s, t, {"query": "bed"})
    assert all("pet" not in p["title"].lower() for p in res["products"])
    res = agent_llm._search(s, t, {"query": "mobile"})
    assert res["matched_products"] == 0 and res["note"]


def test_a_message_after_the_cart_has_items_and_the_price_changed(monkeypatch):
    seen = fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("add_to_cart", product_ids=[CIAZ])]},
        {"role": "assistant", "content": "Added the CIAZ, ₹14,900."},
        {"role": "assistant", "tool_calls": [call("view_cart")]},
        {"role": "assistant", "content": "Heads up: the CIAZ is now ₹16,000, up from ₹14,900."}])
    s = Session()
    s.handle_message("add the ciaz", L)
    s.simulate_price_change(CIAZ, 16000)
    r = s.handle_message("what's my cart total now?", L)
    assert "16,000" in r.message and "total now" in seen[-1][0]["content"]
    tool_result = json.loads(next(m["content"] for m in seen[-1] if m.get("role") == "tool"))
    assert tool_result["cart"]["total_now_inr"] == 16000 and "changed" in tool_result["cart"]["items"][0]


def test_price_check_accepts_sums_of_real_prices():
    assert agent_llm._bad_prices("Bed ₹24,999 + mattress ₹11,668 = ₹36,667", {24999, 11668}, "") == []
    assert agent_llm._bad_prices("Only ₹9,999!", {24999, 11668}, "") == [9999]


def test_an_empty_reply_gets_one_nudge_not_basic_mode(monkeypatch):
    seen = fake_model(monkeypatch, [{"role": "assistant", "content": ""},
                                    {"role": "assistant", "content": "Here's a bundle under ₹40,000."}])
    r = Session().handle_message("a bed, a mattress and two pillows under 40000 total", L)
    assert r.message == "Here's a bundle under ₹40,000." and r.steps
    assert "write your reply" in seen[-1][-1]["content"]


def test_a_wrong_section_never_turns_into_not_sold_here():
    res = agent_llm._search(Session(), agent_llm.Turn(), {"query": "mattress", "category": "home_furnishing"})
    assert res["matched_products"] > 0 and "another section" in res["note"]


def test_price_check_accepts_whats_left_of_the_budget():
    reply = "Total: ₹35,370, leaving you ₹4,630 of your budget."
    assert agent_llm._bad_prices(reply, {24999, 5571, 2400}, "a bed, a mattress and two pillows under 40000 total") == []


def test_live_steps_are_shown_while_the_agent_works_and_cleared_after(monkeypatch):
    seen_steps = []
    script = [{"role": "assistant", "tool_calls": [call("search_products", query="bed")]},
              {"role": "assistant", "tool_calls": [call("get_product", product_id="BDDEH29DNAN4AKYH")]},
              {"role": "assistant", "content": "Here's the queen bed."}]

    def chat_tools(messages, tools, deadline, avoid=None):
        seen_steps.append(s.progress)
        return script.pop(0), {"provider": "fake", "model": "fake-model"}
    monkeypatch.setattr(intent_mod, "llm_available", lambda: True)
    monkeypatch.setattr(llm, "chat_tools", chat_tools)
    s = Session()
    s.handle_message("I need a bed", L)
    assert seen_steps[0] == "Understanding your request"
    assert seen_steps[1] == "Working out the answer" and "Reading the Ethnic Handicrafts" not in seen_steps[0]
    assert s.progress == ""


def test_an_empty_reply_is_rewritten_by_a_different_model(monkeypatch):
    calls = []
    replies = [({"role": "assistant", "content": ""}, "thinker"), ({"role": "assistant", "content": "Here is a bundle that fits."}, "writer")]

    def chat_tools(messages, tools, deadline, avoid=None):
        calls.append(set(avoid or ()))
        msg, model = replies.pop(0)
        return msg, {"provider": "fake", "model": model}
    monkeypatch.setattr(intent_mod, "llm_available", lambda: True)
    monkeypatch.setattr(llm, "chat_tools", chat_tools)
    r = Session().handle_message("a bed, a mattress and two pillows under 40000 total", L)
    assert r.message == "Here is a bundle that fits." and r.model == "writer" and calls[1] == {"thinker"}


def test_the_agent_sees_what_it_did_in_earlier_turns(monkeypatch):
    seen = fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="cushion cover", max_total_inr=300)]},
        {"role": "assistant", "content": "Here are some cushion covers."},
        {"role": "assistant", "content": "I searched cushion covers up to ₹300."}])
    s = Session()
    s.handle_message("cushion covers under 300", L)
    s.handle_message("why these?", L)
    earlier = next(m["content"] for m in seen[-1] if m.get("role") == "assistant" and "cushion covers." in (m.get("content") or ""))
    assert earlier.startswith("[What I did for this reply: Searched cushion cover")


def test_search_finds_products_by_store_section_name():
    s, t = Session(), agent_llm.Turn()
    for q in ("wall decor", "wall art", "rug"):
        assert agent_llm._search(s, t, {"query": q})["matched_products"] > 0, q
    res = agent_llm._search(s, t, {"query": "mobile"})
    assert res["matched_products"] == 0 and "try other words" in res["note"]


def test_about_tag_only_for_products_used_in_this_reply(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "tool_calls": [call("set_focus", product_ids=[CIAZ])]},
        {"role": "assistant", "content": "The CIAZ is 182 cm wide."},
        {"role": "assistant", "content": "What kind of living room decor would you like?"},
        {"role": "assistant", "tool_calls": [call("set_focus", product_ids=[])]},
        {"role": "assistant", "content": "Here's some wall decor."}])
    s = Session()
    r = s.handle_message("3 seater sofa under 30000 that fits 200 cm, how wide is the ciaz?", L)
    assert [a["product_id"] for a in r.about] == [CIAZ]
    r = s.handle_message("give me home decor ideas for the living room", L)
    assert r.about == [] and s.focus == [CIAZ]             # not used in this reply: no tag
    s.handle_message("wall art", L)
    assert s.focus == []                                   # the AI cleared it when the topic moved on


def test_the_agent_knows_what_the_store_sells(monkeypatch):
    seen = fake_model(monkeypatch, [{"role": "assistant", "content": "Wall decor, lamps or showpieces?"}])
    Session().handle_message("home decor ideas for my living room", L)
    assert "Wall Decor & Clocks" in seen[0][0]["content"] and "Floor Coverings" in seen[0][0]["content"]


def test_a_sofa_search_does_not_pull_in_sofa_beds():
    res = agent_llm._search(Session(), agent_llm.Turn(), {"query": "sofa", "category": "furniture", "seats": 3,
                                                          "max_total_inr": 30000, "max_width_cm": 200})
    assert {p["product_id"] for p in res["products"]} == {CIAZ, DURIAN}


def test_reading_a_product_puts_it_in_focus(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "content": "Here are two sofas."},
        {"role": "assistant", "tool_calls": [call("get_product", product_id=CIAZ)]},
        {"role": "assistant", "content": "The CIAZ: ₹14,900."}])
    s = Session()
    s.handle_message("3 seater sofa under 30000 that fits 200 cm", L)
    s.set_focus([])
    r = s.handle_message("more about the hometown one", L)
    assert s.focus == [CIAZ] and [a["product_id"] for a in r.about] == [CIAZ]


def test_add_to_cart_button_works_on_products_the_agent_showed(monkeypatch):
    fake_model(monkeypatch, [
        {"role": "assistant", "tool_calls": [call("search_products", query="sofa", seats=3, max_total_inr=30000,
                                                  max_width_cm=200)]},
        {"role": "assistant", "content": "Here are two sofas."}])
    s = Session()
    s.handle_message("3 seater sofa under 30000 that fits 200 cm", L)
    r = s.select_product(CIAZ)                             # the card's Add to cart button
    assert r.kind == "CART_PROPOSED" and [ln.product_id for ln in s.cart.lines] == [CIAZ]


def test_used_up_limit_stops_at_once_with_a_clear_message(monkeypatch):
    calls = []

    def chat_tools(messages, tools, deadline, avoid=None):
        calls.append(1)
        return None, {"error": "no model answered", "quota_used_up": True}
    monkeypatch.setattr(intent_mod, "llm_available", lambda: True)
    monkeypatch.setattr(llm, "chat_tools", chat_tools)
    r = Session().handle_message("show me sofas", L)
    assert len(calls) == 1                                  # no waiting and retrying
    assert "usage limit for this demo has been used up" in r.message and "AI_QUOTA" in r.reason_codes


def test_quota_is_detected_when_every_model_says_limit_reached(monkeypatch):
    monkeypatch.setattr(llm, "_chain", lambda: [("nvidia", "u", "k", ["a", "b"])])
    monkeypatch.setattr(llm, "_no_quota", {})
    assert not llm.quota_used_up()
    llm._no_quota.update({"nvidia/a": 10 ** 12, "nvidia/b": 10 ** 12})
    assert llm.quota_used_up()


def test_no_key_says_how_to_fix_it():
    r = Session().handle_message("show me sofas", L)          # tests run with the AI off
    assert "No AI model key is set up" in r.message and "README" in r.message
