"""Closing the test blind spots behind O-71, O-72 and O-73 (happy-path bias, 2026-11-20).

1. Product variety: 40 products across all four categories, not just the bed.
2. "Did it answer the real question?": each common question has a check on what the answer must be about.
3. Follow-ups: the shopper answers the assistant's own questions.
4. Browser: the chat looks the same after clicking through to a product page (needs Chrome; skipped without it).
Rules mode, so no AI quota is used and results are repeatable.
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

import qa
from agent import Session
from catalog import SqliteCatalog

ROOT = Path(__file__).resolve().parents[1]
ROBOT = [r"(?i)\b(the )?listing (says|states|mentions|shows)\b", r"(?i)\(simulated\)", r"\b[A-Z]{3,}_[A-Z_]{3,}\b"]
FIELD_DUMP = re.compile(r"^(?:[A-Z][A-Za-z&/ ]{2,30}): ")        # "Bed Size: Queen." reads like a raw spec sheet


def sample_products(per_category: int = 10) -> list[str]:
    con = SqliteCatalog()._con
    out = []
    for cat in ("furniture", "home_decor", "home_furnishing", "kitchen_dining"):
        pids = [r[0] for r in con.execute("SELECT pid FROM products WHERE category=? ORDER BY pid", (cat,))]
        step = max(1, len(pids) // per_category)
        out += pids[::step][:per_category]
    return out


PRODUCTS = sample_products()


def ask(pid: str, q: str):
    return Session().handle_message(q, {"page": "product", "product_id": pid})


def fields(pid: str) -> dict:
    return qa.listing_fields(SqliteCatalog().get(pid))


# ---------------------------------------------------------------- 1 + 2: many products, the real question answered
def _about(q: str, pid: str, msg: str) -> str | None:
    """Returns what's wrong if the reply doesn't address the question asked, else None."""
    f, low = fields(pid), msg.lower()
    dont_know = "don't have that detail" in low
    if q == "How wide is it?":
        if "Width" in f and not re.search(r"\d\s*(cm|mm|m)\b", low):
            return "has a Width field but no measurement in the reply"
    elif q == "When will it arrive?":
        if "day" not in low:
            return "no delivery time"
    elif q == "How much is it?":
        if "₹" not in msg:
            return "no price"
    elif q == "Does it come with installation?":
        if "install" not in low:
            return "doesn't say whether installation is included"
    elif q == "Is it waterproof?":
        said = " ".join(str(v) for v in f.values()).lower()
        if "waterproof" not in said and re.search(r"\b(is|it's|isn't|not)\s+(\w+\s+)?waterproof", low):
            return "gives a waterproof verdict the details don't support"
    elif q == "What is it made of?":
        mat = f.get("Material") or f.get("Primary Material")
        if mat and str(mat).lower().split(",")[0].strip() not in low and not dont_know:
            return f"has Material '{mat}' but the reply doesn't say it"
    return None


QUESTIONS = ["How wide is it?", "When will it arrive?", "How much is it?", "Does it come with installation?",
             "Is it waterproof?", "What is it made of?"]


@pytest.mark.parametrize("pid", PRODUCTS)
@pytest.mark.parametrize("q", QUESTIONS)
def test_variety_answers_are_grounded_human_and_on_topic(pid, q):
    r = ask(pid, q)
    problems = []
    if r.kind != "ANSWER":
        problems.append(f"kind {r.kind}")
    if r.recommendations or "don't sell" in r.message.lower():
        problems.append("treated as a search")
    f = fields(pid)
    bad_cites = [c for c in r.cited_fields if c not in f and not re.match(r"^P\d+\b", c)]
    if bad_cites:
        problems.append(f"cites fields the product doesn't have: {bad_cites}")
    problems += [f"robot wording {p}" for p in ROBOT if re.search(p, r.message)]
    if FIELD_DUMP.match(r.message):
        problems.append("reads like a raw spec sheet")
    off = _about(q, pid, r.message)
    if off:
        problems.append(off)
    assert not problems, f"{q!r} on {f.get('Name', pid)[:50]}: {problems} | reply: {r.message[:160]}"


# ---------------------------------------------------------------- 3: follow-ups to the assistant's own questions
SOFA_ASK = "Find a 3-seater sofa under ₹30,000 that fits 200 cm"
L = {"page": "listing"}


def shown_sofas():
    s = Session()
    return s, s.handle_message(SOFA_ASK, L).recommendations


@pytest.mark.parametrize("question,answer,which", [
    ("tell me about the sofa", "the cheaper one", 0),
    ("tell me about the sofa", "the Durian", 1),
    ("is the sofa leather?", "the second one", 1),
    ("does it come with installation?", "the HomeTown one", 0),
    ("how wide is it?", "2", 1),
])
def test_followup_answering_which_one(question, answer, which):
    s, shown = shown_sofas()
    r = s.handle_message(question, L)
    assert r.kind == "CLARIFY" and "Which one" in r.message, r.message
    r = s.handle_message(answer, L)
    assert r.kind == "ANSWER" and r.product_id == shown[which]["product_id"] and s.cart is None, r.message


def test_followup_ignoring_which_one_and_asking_something_new():
    s, _ = shown_sofas()
    s.handle_message("tell me about the sofa", L)
    r = s.handle_message("show me beds", L)
    assert r.kind == "RECOMMEND" and all("bed" in x["title"].lower() for x in r.recommendations)


def test_followup_room_size_after_fit_question():
    bed = {"page": "product", "product_id": "BDDEH29DNAN4AKYH"}
    s = Session()
    r = s.handle_message("Will this fit in my room?", bed)
    assert r.kind == "CLARIFY"
    r = s.handle_message("about 180 cm wide", bed)
    assert r.kind == "ANSWER" and "165" in r.message, r.message


def test_followup_no_to_quantity_check():
    bed = {"page": "product", "product_id": "BDDEH29DNAN4AKYH"}
    s = Session()
    s.handle_message("I want 2 of these", bed)
    r = s.handle_message("no, make it 1", bed)
    assert s.cart.line("BDDEH29DNAN4AKYH").qty == 1, r.message


def test_followup_no_to_make_it_the_limit():
    bed = {"page": "product", "product_id": "BDDEH29DNAN4AKYH"}
    s = Session()
    s.handle_message("buy this", bed)
    s.handle_message("buy 10 of these", bed)
    r = s.handle_message("no", bed)
    assert s.cart.line("BDDEH29DNAN4AKYH").qty == 1, r.message


# ---------------------------------------------------------------- 4: browser: the chat survives a page change
def _free_port() -> int:
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        return sk.getsockname()[1]


@pytest.fixture(scope="module")
def live_store(tmp_path_factory):
    pytest.importorskip("playwright")
    if not Path("/Applications/Google Chrome.app").exists() and not shutil.which("google-chrome"):
        pytest.skip("Chrome not installed")
    port, tmp = _free_port(), tmp_path_factory.mktemp("live")
    env = dict(os.environ, INTENTGUARD_LLM="off", INTENTGUARD_TRACE_DIR=str(tmp),
               INTENTGUARD_CANDIDATES_FILE=str(tmp / "c.jsonl"), RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "server:app", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=10)


def test_browser_chat_looks_the_same_after_opening_a_product(live_store):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 1400, "height": 900})
        page.goto(live_store + "/", wait_until="networkidle")
        page.click("#ig-fab")
        for text in (SOFA_ASK, "do you sell mobiles?"):
            n = page.locator("#ig-msgs .msg.bot").count()
            page.fill("#ig-input", text)
            page.press("#ig-input", "Enter")
            page.wait_for_function("n => document.querySelectorAll('#ig-msgs .msg.bot').length > n", arg=n)
        before = (page.locator("#ig-msgs .msg").count(), page.locator("#ig-msgs .rec").count())
        assert before[1] >= 2
        page.locator("#ig-msgs .rec a.name").first.click()
        page.wait_for_load_state("networkidle")
        if not page.locator("#ig-input").is_visible():
            page.click("#ig-fab")
        page.wait_for_function("n => document.querySelectorAll('#ig-msgs .msg').length >= n", arg=before[0])
        after = (page.locator("#ig-msgs .msg").count(), page.locator("#ig-msgs .rec").count())
        b.close()
    assert after == before, f"messages/cards before {before}, after {after}"
