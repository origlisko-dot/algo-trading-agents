"""Universe scanner job (ideation I1): rank symbols -> daily_watchlist.json."""
from __future__ import annotations

from algo_agents.os.context import JobResult, RunContext
from algo_agents.os.jobs._data import fetch_features
from algo_agents.universe.scanner import rank_universe, write_watchlist
from algo_agents.universe.symbols import resolve_trading_symbols, sample_scan_symbols


def run_universe_scan(ctx: RunContext) -> JobResult:
    settings = ctx.settings
    candidates = ctx.symbols or resolve_trading_symbols(settings)
    if not candidates:
        return JobResult(name="universe-scan", ok=False, detail="no candidate symbols")

    # Cap feature fetch for speed; sample (not alphabetical slice) within the scanned set.
    scan_cap = min(len(candidates), max(settings.trading_universe_max, ctx.top_n))
    if ctx.symbols:
        # Explicit CLI symbols keep caller order.
        to_scan = candidates[:scan_cap]
    elif len(candidates) > scan_cap:
        to_scan = sample_scan_symbols(candidates, scan_cap)
    else:
        to_scan = list(candidates)
    features = fetch_features(to_scan)
    if not features:
        return JobResult(
            name="universe-scan",
            ok=False,
            detail=f"no feature data for {len(to_scan)} candidates",
            data={"candidates": to_scan},
        )

    top_n = max(1, ctx.top_n)
    ranked = rank_universe(features, top_n=top_n)
    path = write_watchlist(ranked, scanned=len(features), source="universe_scan")
    symbols = [r["symbol"] for r in ranked]
    return JobResult(
        name="universe-scan",
        ok=True,
        detail=f"ranked {len(features)} -> top {len(symbols)}: {', '.join(symbols[:5])}"
        + ("…" if len(symbols) > 5 else ""),
        data={
            "path": str(path),
            "symbols": symbols,
            "scanned": len(features),
            "ranked": ranked,
        },
    )
