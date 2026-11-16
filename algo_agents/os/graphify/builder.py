"""Build the live AGENTIC-OS system graph (jobs, connectors, strategies, artifacts)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from algo_agents.os.artifacts import read_active_strategy
from algo_agents.os.graphify.model import GraphEdge, GraphNode, SystemGraph
from algo_agents.os.registry import names as registry_names

_JOBS = [
    "health",
    "evals",
    "universe-scan",
    "paper",
    "monitor",
    "portfolio",
    "ml-backtest",
    "graphify",
    "daily",
]

_CONNECTORS = [
    ("yfinance", "market_data", "yfinance bars"),
    ("polygon", "market_data", "Polygon bars"),
    ("finnhub", "market_data", "Finnhub bars + universe"),
    ("fmp", "market_data", "FMP fundamentals"),
    ("newsapi", "news", "NewsAPI headlines"),
    ("edgar", "news", "SEC EDGAR filings"),
    ("finbert", "sentiment", "FinBERT sentiment"),
    ("chroma", "memory", "Chroma vector memory"),
    ("simulated-broker", "broker", "Simulated paper broker"),
    ("alpaca", "broker", "Alpaca broker"),
    ("ibkr", "broker", "Interactive Brokers"),
]

_STRATEGIES = [
    ("momentum", "MomentumSentimentStrategy"),
    ("agent", "AgentStrategy (LLM/heuristic)"),
    ("ml", "MLSignalStrategy"),
]

_ARTIFACTS = [
    ("watchlist", "runs/daily_watchlist.json"),
    ("paper-account", "runs/paper_account.json"),
    ("pnl-history", "runs/pnl_history.jsonl"),
    ("dashboard", "runs/pnl_dashboard.html"),
    ("active-strategy", "runs/active_strategy.json"),
    ("regime-sharpe", "runs/regime_sharpe.json"),
    ("eval-learning", "runs/eval_learning.json"),
    ("shadow-books", "runs/shadow/{strategy}/account.json"),
    ("scheduler-state", "runs/scheduler_state.json"),
    ("graphify-graph", "runs/graphify/"),
]


def _registered_jobs() -> list[str]:
    known = registry_names()
    if known:
        return known
    try:
        from algo_agents.os.jobs import register_all_jobs

        register_all_jobs()
    except Exception:
        pass
    return registry_names() or list(_JOBS)


def build_agentic_os_graph(*, include_live_status: bool = False) -> SystemGraph:
    graph = SystemGraph()
    graph.add_node(GraphNode(id="kernel", kind="kernel", label="AgenticOS kernel"))

    jobs = _registered_jobs()
    for job in jobs:
        graph.add_node(GraphNode(id=f"job:{job}", kind="job", label=f"job {job}"))
        graph.add_edge("kernel", f"job:{job}", "dispatch")

    for conn_id, group, label in _CONNECTORS:
        graph.add_node(
            GraphNode(id=f"connector:{conn_id}", kind="connector", label=label, meta={"group": group})
        )

    for strat_id, label in _STRATEGIES:
        graph.add_node(GraphNode(id=f"strategy:{strat_id}", kind="strategy", label=label))

    for art_id, path in _ARTIFACTS:
        node = GraphNode(id=f"artifact:{art_id}", kind="artifact", label=path)
        if include_live_status:
            node.meta["exists"] = _artifact_exists(art_id)
        graph.add_node(node)

    _wire_data_flows(graph)
    graph.meta.update(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "jobs": jobs,
            "include_live_status": include_live_status,
        }
    )
    if include_live_status:
        graph.meta["live"] = _live_status()
    return graph


def _wire_data_flows(graph: SystemGraph) -> None:
    # Market data feeds the compute jobs.
    for conn in ("yfinance", "polygon", "finnhub", "fmp"):
        for job in ("universe-scan", "paper", "monitor", "ml-backtest"):
            graph.add_edge(f"connector:{conn}", f"job:{job}", "bars")

    # News / sentiment / memory feed the agent brain.
    graph.add_edge("connector:newsapi", "strategy:agent", "headlines")
    graph.add_edge("connector:edgar", "strategy:agent", "filings")
    graph.add_edge("connector:finbert", "strategy:agent", "sentiment")
    graph.add_edge("connector:chroma", "strategy:agent", "recall")
    graph.add_edge("connector:finbert", "strategy:momentum", "sentiment")

    # Strategies are evaluated by monitor and executed by paper.
    for strat in ("momentum", "agent", "ml"):
        graph.add_edge(f"strategy:{strat}", "job:monitor", "shadow backtest")
        graph.add_edge(f"strategy:{strat}", "job:paper", "weights")
    graph.add_edge("connector:simulated-broker", "job:paper", "fills")
    graph.add_edge("connector:alpaca", "job:paper", "fills")
    graph.add_edge("connector:ibkr", "job:paper", "fills")

    # Artifact flows along the daily pipeline.
    graph.add_edge("job:universe-scan", "artifact:watchlist", "writes")
    graph.add_edge("artifact:watchlist", "job:paper", "consumes")
    graph.add_edge("job:paper", "artifact:paper-account", "writes")
    graph.add_edge("job:paper", "artifact:pnl-history", "appends")
    graph.add_edge("artifact:pnl-history", "job:portfolio", "reads")
    graph.add_edge("job:portfolio", "artifact:dashboard", "writes")
    graph.add_edge("job:monitor", "artifact:active-strategy", "promotes")
    graph.add_edge("job:monitor", "artifact:regime-sharpe", "appends")
    graph.add_edge("artifact:active-strategy", "job:paper", "routing")
    graph.add_edge("job:evals", "artifact:eval-learning", "writes")
    graph.add_edge("artifact:eval-learning", "job:paper", "guards")
    graph.add_edge("job:graphify", "artifact:graphify-graph", "writes")


def _artifact_exists(art_id: str) -> bool:
    from algo_agents.config import get_settings
    from algo_agents.os.artifacts import runs_root

    try:
        root = runs_root()
    except Exception:
        return False
    mapping = {
        "watchlist": "daily_watchlist.json",
        "paper-account": "paper_account.json",
        "pnl-history": "pnl_history.jsonl",
        "dashboard": "pnl_dashboard.html",
        "active-strategy": "active_strategy.json",
        "regime-sharpe": "regime_sharpe.json",
        "eval-learning": "eval_learning.json",
        "scheduler-state": "scheduler_state.json",
    }
    if art_id in mapping:
        return (root / mapping[art_id]).exists()
    if art_id == "shadow-books":
        return (root / "shadow").exists()
    if art_id == "graphify-graph":
        return (root / "graphify").exists()
    return False


def _live_status() -> dict[str, Any]:
    status: dict[str, Any] = {}
    try:
        active = read_active_strategy()
        if active:
            status["active_strategy"] = active.get("strategy")
            status["active_reason"] = active.get("reason")
    except Exception:
        pass
    try:
        from algo_agents.config import get_settings

        settings = get_settings()
        status["paper"] = settings.trading_paper
        status["paper_broker"] = settings.paper_broker
        status["default_strategy"] = settings.default_strategy
    except Exception:
        pass
    return status
