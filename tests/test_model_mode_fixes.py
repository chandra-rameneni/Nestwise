"""O-59 and O-60, model-mode evals MM-01 to MM-05 (approved by the PM 2026-11-19, evals/MODEL_MODE_EVALS_DRAFT.md).
The AI's known bad replies are replayed with fakes, so the code checks are tested without any network."""
import pytest

import intent as I
import qa
from agent import Session
from catalog import SqliteCatalog
from intent import IntentExtraction

BED = "BDDEH29DNAN4AKYH"
LISTING = {"page": "listing"}


def bag():
    c = SqliteCatalog()
    return c.get(c._con.execute("SELECT pid FROM products WHERE name LIKE 'ABCD XL Bean Bag%' LIMIT 1").fetchone()[0])


# ---------------------------------------------------------------- O-59: no yes/no the listing doesn't state
@pytest.mark.parametrize("pid_fn,q,bad", [
    (lambda: SqliteCatalog().get(BED), "is it waterproof?",
     "Sorry, this bed is not waterproof. The care instructions advise cleaning spills right away."),   # MM-01
    (bag, "is it fireproof?", "No, it isn't fireproof."),                                              # MM-02
    (lambda: SqliteCatalog().get(BED), "is it waterproof?", "Yes, it's fully waterproof."),
])
def test_mm01_mm02_guessed_verdict_is_rejected(monkeypatch, pid_fn, q, bad):
    p = pid_fn()
    cited = [f for f in ("Care Instructions", "Description") if f in qa.listing_fields(p)][:1]
    monkeypatch.setattr(qa, "_ask_llm", lambda *a: (qa.ProductAnswer(answer=bad, cited_fields=cited), {}))
    res = qa.answer_about_product(p, q, IntentExtraction(intent="PRODUCT_QUESTION"), use_llm=True)
    word = q.split()[-1].rstrip("?")
    assert res.status == "rejected" and word in res.meta["rejected"]
    assert "don't have that detail" in res.answer


def test_mm01_verdict_the_listing_does_state_is_kept(monkeypatch):
    p = SqliteCatalog().get(BED)
    monkeypatch.setattr(qa, "listing_fields", lambda prod: {"Material": "Waterproof coated sheesham wood"})
    fake = qa.ProductAnswer(answer="Yes, it's waterproof: the wood is coated.", cited_fields=["Material"])
    monkeypatch.setattr(qa, "_ask_llm", lambda *a: (fake, {}))
    res = qa.answer_about_product(p, "is it waterproof?", IntentExtraction(intent="PRODUCT_QUESTION"), use_llm=True)
    assert res.status == "ok" and res.method == "llm"


def test_mm01_related_fact_without_verdict_is_kept(monkeypatch):
    p = SqliteCatalog().get(BED)
    f = [x for x in ("Care Instructions", "Description") if x in qa.listing_fields(p)][0]
    fake = qa.ProductAnswer(answer="I don't have that detail, but the care tip is to wipe spills right away.",
                            cited_fields=[f])
    monkeypatch.setattr(qa, "_ask_llm", lambda *a: (fake, {}))
    res = qa.answer_about_product(p, "is it waterproof?", IntentExtraction(intent="PRODUCT_QUESTION"), use_llm=True)
    assert res.status == "ok"


# ---------------------------------------------------------------- O-60: "do you sell X" is a search
@pytest.fixture
def model_says_store_info(monkeypatch):
    monkeypatch.setattr(I, "llm_available", lambda: True)
    monkeypatch.setattr(I, "extract_llm", lambda text, prior, context=None: (
        IntentExtraction(intent="UNSUPPORTED", message_kind="STORE_INFO"), {"model": "fake-model"}))


@pytest.mark.parametrize("q,noun", [("do you sell mobiles?", "mobiles"), ("do you have laptops?", "laptops")])
def test_mm03_mm04_named_product_is_a_search_not_store_info(model_says_store_info, q, noun):
    r = Session().handle_message(q, LISTING)
    assert f"don't sell {noun}" in r.message.lower() and "2,0" not in r.message, r.message


def test_mm05_real_product_still_shown(model_says_store_info):
    r = Session().handle_message("do you sell sofas?", LISTING)
    assert r.recommendations and all("sofa" in x["title"].lower() for x in r.recommendations), r.message


def test_store_question_stays_store_info(model_says_store_info):
    r = Session().handle_message("how many products do you sell?", LISTING)
    assert "STORE_INFO" in r.reason_codes
