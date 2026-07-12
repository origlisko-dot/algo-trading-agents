"""Tests for local simulated paper broker."""
from __future__ import annotations

import json

import pytest

from algo_agents.connectors.base import OrderRequest, OrderSide
from algo_agents.connectors.brokers.simulated_broker import SimulatedBroker


@pytest.fixture
def broker(tmp_path, monkeypatch):
    state = tmp_path / "paper.json"
    monkeypatch.setenv("PAPER_STATE_PATH", str(state))
    monkeypatch.setenv("PAPER_STARTING_CASH", "100000")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    b = SimulatedBroker()
    yield b
    get_settings.cache_clear()


def test_simulated_broker_ready(broker):
    assert broker.check().ok


def test_simulated_broker_buy_and_position(broker, monkeypatch):
    monkeypatch.setattr(broker, "_last_price", lambda symbol: 100.0)
    resp = broker.submit_order(
        OrderRequest(symbol="AAPL", qty=10, side=OrderSide.BUY)
    )
    assert resp["status"] == "filled"
    positions = broker.get_positions()
    assert any(p["symbol"] == "AAPL" and p["qty"] == 10 for p in positions)
    acct = broker.get_account()
    assert acct["cash"] == 99000.0
