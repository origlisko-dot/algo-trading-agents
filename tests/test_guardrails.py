"""Tests for agent guardrails."""
from __future__ import annotations

import pytest

from algo_agents.agents.guardrails import (
    AgentOutput,
    GuardrailViolation,
    assert_tool_allowed,
    assert_universe,
    validate_output,
    validate_tool_call,
)


def test_universe_rejects_unknown_symbol(monkeypatch):
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL,MSFT")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(GuardrailViolation, match="outside trading universe"):
        assert_universe(["GME"])
    get_settings.cache_clear()


def test_unrestricted_universe_accepts_any_valid_us_ticker(monkeypatch):
    monkeypatch.setenv("TRADING_UNIVERSE", "ALL US STOCK")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    assert_universe(["AAPL", "GME", "BRK.B"])
    with pytest.raises(GuardrailViolation, match="Invalid US ticker"):
        assert_universe(["NOT_A_TICKER"])
    get_settings.cache_clear()


def test_tool_allowlist_blocks_broker():
    with pytest.raises(GuardrailViolation, match="Forbidden"):
        assert_tool_allowed("submit_order")
    with pytest.raises(GuardrailViolation, match="not in allowlist"):
        assert_tool_allowed("random_tool")
    assert_tool_allowed("get_price_history")


def test_validate_output_schema(monkeypatch):
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL,MSFT,NVDA")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    raw = {
        "decisions": [
            {
                "symbol": "AAPL",
                "weight": 0.1,
                "rationale": "uptrend with positive sentiment",
                "confidence": 0.7,
            }
        ]
    }
    out = validate_output(raw)
    assert isinstance(out, AgentOutput)
    assert out.to_weights() == {"AAPL": 0.1}
    get_settings.cache_clear()


def test_validate_tool_call_symbol(monkeypatch):
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL,MSFT,NVDA")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    validate_tool_call("get_news_headlines", {"symbol": "NVDA"})
    with pytest.raises(GuardrailViolation):
        validate_tool_call("get_news_headlines", {"symbol": "GME"})
    get_settings.cache_clear()
