"""Tests for volatility-adjusted sizing in the risk manager."""
from __future__ import annotations

import pandas as pd
import pytest

from algo_agents.risk.risk_manager import RiskLimits, RiskManager


@pytest.fixture
def rm() -> RiskManager:
    return RiskManager(
        RiskLimits(max_weight_per_symbol=0.2, max_gross_exposure=1.0, vol_target=0.01)
    )


def test_no_vols_behaves_like_before(rm):
    weights = {"AAPL": 0.1, "MSFT": -0.05}
    assert rm.apply(weights) == weights


def test_high_vol_scaled_down(rm):
    out = rm.apply({"AAPL": 0.10}, vols={"AAPL": 0.04})
    assert out["AAPL"] == pytest.approx(0.10 * 0.01 / 0.04)


def test_low_vol_never_levered_up(rm):
    out = rm.apply({"AAPL": 0.10}, vols={"AAPL": 0.005})
    assert out["AAPL"] == pytest.approx(0.10)


def test_missing_or_bad_vol_untouched(rm):
    out = rm.apply({"AAPL": 0.10, "MSFT": 0.10}, vols={"AAPL": None, "MSFT": -1})
    assert out == {"AAPL": 0.10, "MSFT": 0.10}


def test_book_vol_cap_scales_down(rm):
    weights = {"AAPL": 0.10, "MSFT": 0.10}
    vols = {"AAPL": 0.02, "MSFT": 0.02}
    out = rm.apply(weights, vols=vols)
    book_vol = abs(sum(w * vols[s] for s, w in out.items()))
    assert book_vol <= rm.limits.max_portfolio_vol + 1e-12
    assert abs(out["AAPL"] - out["MSFT"]) < 1e-12


def test_correlation_matrix_increases_scaling():
    rm = RiskManager(
        RiskLimits(max_weight_per_symbol=0.2, max_gross_exposure=1.0,
                   vol_target=0.01, max_portfolio_vol=0.001)
    )
    perfect = pd.DataFrame(
        [[1.0, 1.0], [1.0, 1.0]], index=["AAPL", "MSFT"], columns=["AAPL", "MSFT"]
    )
    weights = {"AAPL": 0.10, "MSFT": 0.10}
    vols = {"AAPL": 0.02, "MSFT": 0.02}
    out_corr = rm.apply(weights, vols=vols, corr=perfect)
    out_ind = rm.apply(weights, vols=vols)
    gross_corr = sum(abs(w) for w in out_corr.values())
    gross_ind = sum(abs(w) for w in out_ind.values())
    assert gross_corr < gross_ind


def test_kill_switch_still_wins(rm):
    assert rm.apply({"AAPL": 0.1}, current_drawdown=-0.25, vols={"AAPL": 0.01}) == {}
