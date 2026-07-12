"""Technical feature engineering on OHLCV bars.

All features at row t use only information available up to and including t.
Shift by one bar before using them as a signal to avoid look-ahead bias.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window).mean()


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Augment an OHLCV frame with a standard technical feature set."""
    if df.empty:
        return df
    out = df.copy()
    out["return_1d"] = out["close"].pct_change()
    out["sma_10"] = out["close"].rolling(10).mean()
    out["sma_50"] = out["close"].rolling(50).mean()
    out["momentum_10"] = out["close"].pct_change(10)
    out["volatility_20"] = out["return_1d"].rolling(20).std()
    out["rsi_14"] = _rsi(out["close"])
    out["atr_14"] = _atr(out)
    vol_mean = out["volume"].rolling(20).mean()
    vol_std = out["volume"].rolling(20).std()
    out["volume_zscore"] = (out["volume"] - vol_mean) / vol_std.replace(0, np.nan)
    out["trend"] = np.sign(out["sma_10"] - out["sma_50"])
    return out
