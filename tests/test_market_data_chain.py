"""Tests for the resilient market-data chain (failover + cache) and Stooq."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from algo_agents.connectors.base import MarketDataConnector
from algo_agents.connectors.market_data.resilient import (
    ResilientMarketData,
    build_market_data_chain,
)
from algo_agents.connectors.market_data.stooq_data import StooqData

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END = datetime(2024, 3, 1, tzinfo=timezone.utc)


def _bars(symbol: str = "AAPL") -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=3, freq="1D", tz="UTC")
    return pd.DataFrame(
        {"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100},
        index=idx,
    ).rename_axis("timestamp")


class _OkSource(MarketDataConnector):
    name = "ok"

    def __init__(self) -> None:
        self.calls = 0

    def check(self):
        from algo_agents.connectors.base import ConnectorState, ConnectorStatus

        return ConnectorStatus(self.name, ConnectorState.READY, "")

    def get_bars(self, symbol, start, end, timeframe="1Day"):
        self.calls += 1
        return _bars(symbol)


class _FailingSource(MarketDataConnector):
    name = "failing"

    def check(self):
        from algo_agents.connectors.base import ConnectorState, ConnectorStatus

        return ConnectorStatus(self.name, ConnectorState.ERROR, "down")

    def get_bars(self, symbol, start, end, timeframe="1Day"):
        raise RuntimeError("boom")


class _EmptySource(MarketDataConnector):
    name = "empty"

    def check(self):
        from algo_agents.connectors.base import ConnectorState, ConnectorStatus

        return ConnectorStatus(self.name, ConnectorState.READY, "")

    def get_bars(self, symbol, start, end, timeframe="1Day"):
        return pd.DataFrame()


def test_failover_skips_failing_source():
    ok = _OkSource()
    chain = ResilientMarketData([_FailingSource(), ok])
    df = chain.get_bars("AAPL", START, END)
    assert not df.empty
    assert chain.last_source == "ok"
    assert ok.calls == 1


def test_failover_skips_empty_source():
    ok = _OkSource()
    chain = ResilientMarketData([_EmptySource(), ok])
    df = chain.get_bars("AAPL", START, END)
    assert not df.empty
    assert chain.last_source == "ok"


def test_all_sources_fail_returns_empty():
    chain = ResilientMarketData([_FailingSource(), _EmptySource()])
    df = chain.get_bars("AAPL", START, END)
    assert df.empty
    assert chain.last_source is None


def test_cache_hit_avoids_refetch(tmp_path):
    ok = _OkSource()
    chain = ResilientMarketData([ok], cache_dir=tmp_path)
    df1 = chain.get_bars("AAPL", START, END)
    df2 = chain.get_bars("AAPL", START, END)
    assert not df1.empty and not df2.empty
    assert ok.calls == 1
    assert chain.last_source == "cache"
    pd.testing.assert_frame_equal(df1, df2, check_freq=False)


def test_check_ready_when_any_source_ready():
    chain = ResilientMarketData([_FailingSource(), _OkSource()])
    status = chain.check()
    assert status.ok
    assert "failing=ERROR" in status.detail


def test_build_chain_defaults():
    chain = build_market_data_chain(cache=False)
    names = [s.name for s in chain.sources]
    assert names[:2] == ["yfinance", "stooq"]


def test_build_chain_adds_keyed_sources(monkeypatch):
    from algo_agents.config import Settings

    cfg = Settings(_env_file=None, finnhub_api_key="k", polygon_api_key="k")
    chain = build_market_data_chain(cfg, cache=False)
    names = [s.name for s in chain.sources]
    assert names == ["yfinance", "stooq", "finnhub", "polygon"]


_STOOQ_CSV = "Date,Open,High,Low,Close,Volume\n2024-01-02,1.0,2.0,0.5,1.5,100\n2024-01-03,1.5,2.5,1.0,2.0,120\n"


def test_stooq_parses_csv(monkeypatch):
    class _Resp:
        text = _STOOQ_CSV

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "algo_agents.connectors.market_data.stooq_data.requests.get",
        lambda *a, **kw: _Resp(),
    )
    df = StooqData().get_bars("AAPL", START, END)
    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None
    assert df.index.is_monotonic_increasing


def test_stooq_no_data_returns_empty(monkeypatch):
    class _Resp:
        text = "No data"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "algo_agents.connectors.market_data.stooq_data.requests.get",
        lambda *a, **kw: _Resp(),
    )
    df = StooqData().get_bars("AAPL", START, END)
    assert df.empty


def test_stooq_intraday_unsupported():
    assert StooqData().get_bars("AAPL", START, END, timeframe="1Hour").empty
