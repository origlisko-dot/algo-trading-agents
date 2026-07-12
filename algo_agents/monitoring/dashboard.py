"""Static HTML dashboard for 30–90 day paper P&L tracking."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings
from algo_agents.monitoring.pnl_tracker import load_history, summarize
from algo_agents.monitoring.shadow import SHADOW_STRATEGIES, shadow_leaderboard


def _runs_root() -> Path:
    return Path(get_settings().runs_dir)


def _read_latest_monitor_verdict() -> dict[str, Any] | None:
    """Read monitor payload from newest run manifest (avoid importing algo_agents.os)."""
    root = _runs_root()
    if not root.exists():
        return None
    manifests = sorted(root.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for manifest in manifests:
        try:
            with manifest.open(encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        monitor = data.get("monitor")
        if isinstance(monitor, dict):
            return monitor
    return None


def _read_active_strategy() -> dict[str, Any] | None:
    path = _runs_root() / "active_strategy.json"
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _sparkline_svg(equities: list[float], width: int = 640, height: int = 160) -> str:
    if len(equities) < 2:
        return '<p class="muted">Need at least 2 snapshots for a chart.</p>'
    lo, hi = min(equities), max(equities)
    span = (hi - lo) or 1.0
    pts: list[str] = []
    for i, eq in enumerate(equities):
        x = i / (len(equities) - 1) * (width - 16) + 8
        y = height - 8 - ((eq - lo) / span) * (height - 16)
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="equity curve">'
        f'<polyline fill="none" stroke="#3dd6c6" stroke-width="2.5" points="{poly}" />'
        f"</svg>"
    )


def _shadow_leaderboard_html(board: dict[str, Any]) -> str:
    rows: list[str] = []
    for key in (*SHADOW_STRATEGIES, "live"):
        entry = board.get(key) or {}
        snaps = int(entry.get("snapshots") or 0)
        if key != "live" and snaps == 0 and not entry.get("has_book"):
            rows.append(
                "<tr>"
                f"<td>{_esc(key)}</td>"
                f'<td colspan="4" class="muted">no shadow book yet</td>'
                "</tr>"
            )
            continue
        equity = entry.get("latest_equity")
        ret = entry.get("total_return")
        sharpe = entry.get("last_sharpe")
        ret_cls = ""
        if isinstance(ret, (int, float)):
            ret_cls = "pos" if ret >= 0 else "neg"
            ret_s = f"{ret:+.2%}"
        else:
            ret_s = "—"
        equity_s = f"{float(equity):,.2f}" if isinstance(equity, (int, float)) else "—"
        sharpe_s = f"{float(sharpe):.3f}" if isinstance(sharpe, (int, float)) else "—"
        rows.append(
            "<tr>"
            f"<td>{_esc(key)}</td>"
            f"<td>{snaps}</td>"
            f"<td>{equity_s}</td>"
            f'<td class="{ret_cls}">{ret_s}</td>'
            f"<td>{sharpe_s}</td>"
            "</tr>"
        )
    return (
        '<table><thead><tr>'
        "<th>book</th><th>snaps</th><th>equity</th><th>return</th><th>sharpe</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _signal_drift_html(monitor: dict[str, Any] | None) -> str:
    if not monitor:
        return '<p class="muted">No monitor verdict yet — run the monitor job.</p>'
    drift = monitor.get("signal_drift")
    winner = monitor.get("winner") or monitor.get("backtest_winner") or "—"
    regime = monitor.get("regime") or "—"
    gate = monitor.get("zero_llm_gate")
    drift_s = f"{float(drift):.4f}" if isinstance(drift, (int, float)) else "—"
    extra = f'<p class="muted">zero-LLM gate: {_esc(gate)}</p>' if gate else ""
    return (
        f"<p>Latest signal drift: <strong>{_esc(drift_s)}</strong> · "
        f"winner <code>{_esc(winner)}</code> · regime <code>{_esc(regime)}</code></p>"
        f"{extra}"
    )


def build_dashboard_html(*, starting_equity: float | None = None) -> str:
    settings = get_settings()
    start = starting_equity if starting_equity is not None else settings.paper_starting_cash
    history = load_history()
    summary = summarize(starting_equity=start)
    active = _read_active_strategy() or {}
    board = shadow_leaderboard(starting_equity=start)
    monitor = _read_latest_monitor_verdict()
    equities = [float(r["equity"]) for r in history if "equity" in r]
    chart = _sparkline_svg(equities)
    shadow_html = _shadow_leaderboard_html(board)
    drift_html = _signal_drift_html(monitor)

    rows = []
    for row in reversed(history[-90:]):
        rows.append(
            "<tr>"
            f"<td>{_esc(row.get('ts', ''))}</td>"
            f"<td>{_esc(row.get('strategy', ''))}</td>"
            f"<td>{float(row.get('equity', 0)):.2f}</td>"
            f"<td>{float(row.get('cash', 0)):.2f}</td>"
            f"<td>{int(row.get('positions', 0))}</td>"
            f"<td>{float(row.get('unrealized_pl', 0)):+.2f}</td>"
            f"<td><code>{_esc(row.get('run_id', ''))}</code></td>"
            "</tr>"
        )

    strategy_switches = []
    prev = None
    for row in history:
        cur = row.get("strategy")
        if cur and cur != prev:
            strategy_switches.append(f"{row.get('ts', '')}: {_esc(cur)}")
            prev = cur

    switches_html = (
        "<ul>" + "".join(f"<li>{s}</li>" for s in strategy_switches[-20:]) + "</ul>"
        if strategy_switches
        else '<p class="muted">No strategy switches recorded yet.</p>'
    )

    now = datetime.now(timezone.utc).isoformat()
    ret = float(summary.get("total_return", 0) or 0)
    dd = float(summary.get("max_drawdown", 0) or 0)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Paper P&amp;L Dashboard · algo-trading-agents</title>
  <style>
    :root {{
      --bg: #0f1419; --panel: #1a222c; --ink: #e8eef4; --muted: #8b9aab;
      --accent: #3dd6c6; --warm: #f0a05a; --line: #2a3644;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "Segoe UI", system-ui, sans-serif;
      background: radial-gradient(900px 400px at 0% 0%, #1b3a3a 0%, transparent 50%), var(--bg);
      color: var(--ink); line-height: 1.5;
    }}
    main {{ max-width: 980px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
    h1 {{ margin: 0 0 0.25rem; font-size: 1.6rem; }}
    .meta {{ color: var(--muted); margin-bottom: 1.5rem; font-size: 0.9rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; }}
    .card {{
      background: var(--panel); border: 1px solid var(--line);
      border-radius: 12px; padding: 0.9rem 1rem;
    }}
    .card .label {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    .card .value {{ font-size: 1.25rem; font-weight: 700; margin-top: 0.2rem; }}
    .pos {{ color: #6bcf7f; }} .neg {{ color: #f07178; }}
    h2 {{ color: var(--warm); font-size: 1.05rem; margin: 1.75rem 0 0.6rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    th, td {{ text-align: left; padding: 0.4rem 0.45rem; border-bottom: 1px solid var(--line); }}
    th {{ color: var(--muted); }}
    code {{ color: var(--accent); font-size: 0.8rem; }}
    .muted {{ color: var(--muted); }}
    footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.78rem; }}
  </style>
</head>
<body>
<main>
  <h1>Paper P&amp;L Dashboard</h1>
  <p class="meta">Phase-2 ops view · generated {_esc(now)} · source <code>runs/pnl_history.jsonl</code></p>

  <div class="grid">
    <div class="card"><div class="label">Snapshots</div><div class="value">{int(summary.get("snapshots", 0))}</div></div>
    <div class="card"><div class="label">Equity</div><div class="value">{float(summary.get("latest_equity", 0) or 0):,.2f}</div></div>
    <div class="card"><div class="label">Total return</div><div class="value {"pos" if ret >= 0 else "neg"}">{ret:+.2%}</div></div>
    <div class="card"><div class="label">Max drawdown</div><div class="value neg">{dd:.2%}</div></div>
    <div class="card"><div class="label">Active strategy</div><div class="value">{_esc(active.get("strategy") or summary.get("latest_strategy") or "—")}</div></div>
    <div class="card"><div class="label">Unrealized P&amp;L</div><div class="value">{float(summary.get("latest_unrealized_pl", 0) or 0):+.2f}</div></div>
  </div>

  <h2>Equity curve</h2>
  <div class="card">{chart}</div>

  <h2>Shadow leaderboard</h2>
  <div class="card" style="overflow-x:auto">{shadow_html}</div>

  <h2>Signal drift</h2>
  <div class="card">{drift_html}</div>

  <h2>Strategy timeline</h2>
  <div class="card">{switches_html}</div>

  <h2>Recent snapshots (latest 90)</h2>
  <div class="card" style="overflow-x:auto">
    <table>
      <thead><tr><th>ts</th><th>strategy</th><th>equity</th><th>cash</th><th>pos</th><th>uPnL</th><th>run</th></tr></thead>
      <tbody>
        {"".join(rows) if rows else '<tr><td colspan="7" class="muted">No snapshots yet. Run daily/portfolio first.</td></tr>'}
      </tbody>
    </table>
  </div>

  <footer>Composed by algo_agents.monitoring.dashboard · starting equity {_esc(f"{start:,.2f}")}</footer>
</main>
</body>
</html>
"""


def write_dashboard(path: Path | None = None) -> Path:
    out = path or (_runs_root() / "pnl_dashboard.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_dashboard_html(), encoding="utf-8")
    sidecar = out.with_suffix(".json")
    start = get_settings().paper_starting_cash
    sidecar.write_text(
        json.dumps(
            {
                "summary": summarize(),
                "active": _read_active_strategy(),
                "shadow": shadow_leaderboard(starting_equity=start),
                "monitor": _read_latest_monitor_verdict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out
