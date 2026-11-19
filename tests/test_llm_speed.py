"""O-29: the model chain never makes the shopper wait long. No real network calls: httpx.post is replaced."""
import httpx
import pytest

import llm
from intent import IntentExtraction


@pytest.fixture
def two_providers(monkeypatch):
    monkeypatch.delenv("INTENTGUARD_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    llm._cooling.clear()
    yield
    llm._cooling.clear()


class _Resp:
    def __init__(self, status, content='{"intent": "PRODUCT_DISCOVERY", "product_query": "sofa"}'):
        self.status_code = status
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_busy_models_are_skipped_on_the_next_message(two_providers, monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(json["model"])
        return _Resp(429) if "gemini" in json["model"] else _Resp(200)

    monkeypatch.setattr(httpx, "post", fake_post)
    first, _ = llm.structured("sys", "sofa", IntentExtraction)
    assert first is not None and calls[:2] == llm.GEMINI_MODELS        # both Gemini models tried once
    calls.clear()
    second, meta = llm.structured("sys", "sofa", IntentExtraction)
    assert second is not None and not any("gemini" in m for m in calls)  # skipped while cooling down
    assert any("skipped (busy recently)" in t for t in meta.get("tried_first", []))


def test_total_wait_is_capped(two_providers, monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(llm.time, "monotonic", lambda: clock["t"])
    timeouts = []

    def slow_post(url, json, headers, timeout):
        timeouts.append(timeout)
        clock["t"] += timeout                  # each call uses its whole timeout, then times out
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "post", slow_post)
    parsed, meta = llm.structured("sys", "sofa", IntentExtraction)
    assert parsed is None
    assert sum(timeouts) <= llm.TOTAL_BUDGET_S                          # never more than the budget in total
    assert any("time budget used up" in t for t in meta["tried"])


def test_a_trickling_model_cannot_exceed_the_hard_deadline(two_providers, monkeypatch):
    import time as real_time
    monkeypatch.setattr(llm, "TOTAL_BUDGET_S", 1.5)

    def trickle(url, json, headers, timeout):
        real_time.sleep(3)                     # slower than the budget, whatever httpx's own timeout says
        return _Resp(200)

    monkeypatch.setattr(httpx, "post", trickle)
    start = real_time.monotonic()
    parsed, meta = llm.structured("sys", "sofa", IntentExtraction)
    assert parsed is None and real_time.monotonic() - start < 2.5


def test_second_gemini_key_is_tried_after_the_first(monkeypatch):
    monkeypatch.delenv("INTENTGUARD_LLM", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "k2")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    llm._cooling.clear()
    keys = []

    def fake_post(url, json, headers, timeout):
        keys.append(headers["Authorization"])
        return _Resp(429) if headers["Authorization"].endswith("k1") else _Resp(200)

    monkeypatch.setattr(httpx, "post", fake_post)
    parsed, meta = llm.structured("sys", "sofa", IntentExtraction)
    assert parsed is not None and meta["provider"] == "gemini2"
    assert keys[0].endswith("k1") and keys[-1].endswith("k2")
    llm._cooling.clear()
