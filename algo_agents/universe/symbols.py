"""US equity universe resolution and symbol validation."""
from __future__ import annotations

import json
import random
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import requests

from algo_agents.observability.logging import get_logger

if TYPE_CHECKING:
    from algo_agents.config import Settings

_log = get_logger(__name__)

UNIVERSE_ALL_TOKENS: frozenset[str] = frozenset(
    {
        "*",
        "ALL",
        "US",
        "ALL_US",
        "ALL US",
        "ALL US STOCK",
        "ALL US STOCKS",
        "ALL OF US STOCK",
        "ALL OF US STOCKS",
    }
)

_US_TICKER = re.compile(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$")

_DEFAULT_SEED = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "JPM",
    "V",
    "UNH",
]

_FINNHUB_URL = "https://finnhub.io/api/v1"
_POLYGON_URL = "https://api.polygon.io"
# Cache full US lists; daily scan samples TRADING_UNIVERSE_MAX from this.
_CACHE_VERSION = 3
_UNIVERSE_FETCH_MAX = 15_000


def is_unrestricted_universe(trading_universe: str) -> bool:
    return trading_universe.strip().upper() in UNIVERSE_ALL_TOKENS


def is_valid_us_equity_symbol(symbol: str) -> bool:
    """Basic US ticker format check (not a full securities master)."""
    return bool(_US_TICKER.match(symbol.strip().upper()))


def is_scan_friendly_symbol(symbol: str) -> bool:
    """Drop common OTC/pink-sheet patterns that lack usable yfinance bars."""
    sym = symbol.strip().upper()
    if not is_valid_us_equity_symbol(sym):
        return False
    # 5-letter tickers ending in F are often OTC/foreign pinks (e.g. JUTGF).
    if len(sym) == 5 and sym.endswith("F"):
        return False
    return True


def symbol_allowed(symbol: str, settings: Settings) -> bool:
    sym = symbol.strip().upper()
    if is_unrestricted_universe(settings.trading_universe):
        return is_valid_us_equity_symbol(sym)
    return sym in set(settings.universe)


def scan_seed_for_date(day: date | None = None) -> int:
    """Deterministic RNG seed from UTC calendar day (YYYYMMDD)."""
    d = day or datetime.now(timezone.utc).date()
    return int(d.strftime("%Y%m%d"))


def sample_scan_symbols(
    symbols: Sequence[str],
    cap: int,
    *,
    seed: int | None = None,
) -> list[str]:
    """Stratified sample for daily scan — avoids alphabetical A/AA/AAA bias.

    Buckets by first letter, shuffles within each bucket with a date seed,
    then round-robins so the scan covers the alphabet when the full list is large.
    """
    unique = list(dict.fromkeys(s.strip().upper() for s in symbols if str(s).strip()))
    if cap <= 0:
        return []
    if len(unique) <= cap:
        return unique

    rng = random.Random(seed if seed is not None else scan_seed_for_date())
    buckets: dict[str, list[str]] = {}
    for sym in unique:
        buckets.setdefault(sym[0], []).append(sym)
    for key in buckets:
        rng.shuffle(buckets[key])

    keys = sorted(buckets.keys())
    picked: list[str] = []
    depth = 0
    while len(picked) < cap:
        progressed = False
        for key in keys:
            bucket = buckets[key]
            if depth < len(bucket):
                picked.append(bucket[depth])
                progressed = True
                if len(picked) >= cap:
                    break
        if not progressed:
            break
        depth += 1
    return picked


def _load_cache(path: Path, max_age_hours: float) -> list[str] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            payload: dict[str, Any] = json.load(f)
        # v1 caches truncated alphabetically to TRADING_UNIVERSE_MAX — force refresh.
        if int(payload.get("version", 1)) < _CACHE_VERSION:
            return None
        age_h = (time.time() - float(payload.get("ts", 0))) / 3600.0
        if age_h > max_age_hours:
            return None
        symbols = payload.get("symbols")
        if isinstance(symbols, list) and symbols:
            return [str(s).upper() for s in symbols]
    except Exception as exc:
        _log.warning("universe cache read failed (%s)", exc)
    return None


def _save_cache(path: Path, symbols: list[str], source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "ts": time.time(),
                "source": source,
                "version": _CACHE_VERSION,
                "symbols": symbols,
            },
            f,
            indent=2,
        )


def _symbols_from_alpaca(max_symbols: int = _UNIVERSE_FETCH_MAX) -> list[str]:
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import AssetClass, AssetStatus
        from alpaca.trading.requests import GetAssetsRequest

        from algo_agents.config import get_settings

        s = get_settings()
        if not (s.alpaca_api_key and s.alpaca_secret_key):
            return []
        client = TradingClient(s.alpaca_api_key, s.alpaca_secret_key, paper=s.trading_paper)
        assets = client.get_all_assets(
            GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
        )
        symbols = sorted(
            a.symbol
            for a in assets
            if getattr(a, "tradable", False) and is_scan_friendly_symbol(a.symbol)
        )
        if len(symbols) > max_symbols:
            symbols = sample_scan_symbols(symbols, max_symbols, seed=scan_seed_for_date())
            symbols = sorted(symbols)
        _log.info("loaded %d tradable US symbols from Alpaca", len(symbols))
        return symbols
    except Exception as exc:
        _log.warning("Alpaca universe load failed (%s)", exc)
        return []


def _symbols_from_finnhub(api_key: str, max_symbols: int = _UNIVERSE_FETCH_MAX) -> list[str]:
    resp = requests.get(
        f"{_FINNHUB_URL}/stock/symbol",
        params={"exchange": "US", "token": api_key},
        timeout=60,
    )
    resp.raise_for_status()
    rows = resp.json()
    symbols: list[str] = []
    for row in rows:
        sym = str(row.get("symbol", "")).upper()
        if not is_valid_us_equity_symbol(sym):
            continue
        if not is_scan_friendly_symbol(sym):
            continue
        if row.get("type") not in (None, "Common Stock", "EQS"):
            continue
        symbols.append(sym)
    symbols = sorted(set(symbols))
    if len(symbols) > max_symbols:
        symbols = sample_scan_symbols(symbols, max_symbols, seed=scan_seed_for_date())
        symbols = sorted(symbols)
    _log.info("loaded %d US symbols from Finnhub", len(symbols))
    return symbols


def _symbols_from_polygon(api_key: str, max_symbols: int = _UNIVERSE_FETCH_MAX) -> list[str]:
    symbols: set[str] = set()
    url = f"{_POLYGON_URL}/v3/reference/tickers"
    params: dict[str, Any] = {
        "market": "stocks",
        "active": "true",
        "limit": 1000,
        "apiKey": api_key,
    }
    pages = 0
    # Page broadly so we do not stop after the alphabetical first N tickers.
    while url and len(symbols) < max_symbols and pages < 50:
        resp = requests.get(url, params=params if pages == 0 else None, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        for row in body.get("results", []):
            sym = str(row.get("ticker", "")).upper()
            if is_scan_friendly_symbol(sym):
                symbols.add(sym)
        url = body.get("next_url")
        if url and "apiKey=" not in url:
            url = f"{url}&apiKey={api_key}"
        params = {}
        pages += 1
    out = sorted(symbols)
    if len(out) > max_symbols:
        out = sample_scan_symbols(out, max_symbols, seed=scan_seed_for_date())
        out = sorted(out)
    _log.info("loaded %d US symbols from Polygon", len(out))
    return out


def _load_unrestricted_symbols(settings: Settings) -> list[str]:
    cap = settings.trading_universe_max
    cache_path = Path(settings.universe_cache_path)
    cached = _load_cache(cache_path, settings.universe_cache_hours)
    if cached:
        cached = [s for s in cached if is_scan_friendly_symbol(s)]
        sampled = sample_scan_symbols(cached, cap)
        _log.info(
            "using cached universe (%d symbols), sampled %d for daily scan",
            len(cached),
            len(sampled),
        )
        return sampled

    for loader_name, loader in (
        ("alpaca", lambda: _symbols_from_alpaca()),
        ("finnhub", lambda: _symbols_from_finnhub(settings.finnhub_api_key or "")),
        ("polygon", lambda: _symbols_from_polygon(settings.polygon_api_key or "")),
    ):
        try:
            if loader_name == "finnhub" and not settings.finnhub_api_key:
                continue
            if loader_name == "polygon" and not settings.polygon_api_key:
                continue
            symbols = loader()
            if symbols:
                _save_cache(cache_path, symbols, loader_name)
                return sample_scan_symbols(symbols, cap)
        except Exception as exc:
            _log.warning("%s universe load failed (%s)", loader_name, exc)

    _log.warning(
        "Unrestricted universe but no symbol source available — using %d seed symbols.",
        min(cap, len(_DEFAULT_SEED)),
    )
    return sample_scan_symbols(_DEFAULT_SEED, cap)


def resolve_trading_symbols(settings: Settings) -> list[str]:
    """Symbols to scan in daily loops when universe is unrestricted or explicit."""
    if not is_unrestricted_universe(settings.trading_universe):
        return settings.universe
    return _load_unrestricted_symbols(settings)
