"""Build the live AGENTIC-OS system graph from the runtime registry."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from algo_agents.config import get_settings
from algo_agents.os.graphify.model import Edge, Node, SystemGraph
from algo_agents.os.registry import names as job_names

# Static strategy roster mirrored from algo_agents.os.routing.strategy_router.
_STRATEGIES: list[tuple[str, str]] = [
    ("momentum", "MomentumSentimentStrategy"),
    ("agent", "AgentStrategy"),
    ("ml", "MLSignalStrategy"),
]

# Which connectors each job leans on for its primary data flow.
_JOB_CONNECTORS: dict[str, list[str]] = {
    "health": ["yfinance", "simulated", "edgar", "hf_sentiment", "memory"],
    "universe-scan": ["yfinance"],
    "paper": ["simulated", "yfinance", "hf_sentiment"],
    "monitor": ["yfinance"],
    "ml-backtest": ["yfinance"],
    "evals": ["hf_sentiment"],
}

# Which strategies a job exercises.
_JOB_STRATEGIES: dict[str, list[str]] = {
    "paper": ["momentum", "agent", "ml"],
    "monitor": ["momentum", "agent", "ml"],
    "ml-backtest": ["ml"],
    "evals": ["agent"],
}

# Artifacts produced (write) or consumed (read) by each job.
_JOB_ARTIFACT_WRITES: dict[str, list[str]] = {
    "universe-scan": ["watchlist"],
    "paper": ["paper_account", "pnl_history"],
    "monitor": ["active_strategy"],
    "portfolio": ["pnl_dashboard"],
    "graphify": ["graphify"],
}
_JOB_ARTIFACT_READS: dict[str, list[str]] = {
    "paper": ["watchlist", "active_strategy"],
    "monitor": ["watchlist"],
    "portfolio": ["pnl_history"],
}

# Sub-jobs composed by the `daily` pipeline.
_DAILY_STEPS: list[str] = [
    "health",
    "evals",
    "universe-scan",
    "paper",
    "monitor",
    "portfolio",
    "graphify",
]

_ARTIFACTS: dict[str, tuple[str, str]] = {
    "watchlist": ("Daily watchlist", "runs/daily_watchlist.json"),
    "active_strategy": ("Active strategy", "runs/active_strategy.json"),
    "pnl_history": ("PnL history", "runs/pnl_history.jsonl"),
    "pnl_dashboard": ("PnL dashboard", "runs/pnl_dashboard.html"),
    "paper_account": ("Paper account", "runs/paper_account.json"),
    "universe_cache": ("US universe cache", "runs/universe_us.json"),
    "graphify": ("System graph", "runs/graphify/"),
}


def _connector_status_map() -> dict[str, str]:
    """Best-effort live connector states; never raises."""
    try:
        from algo_agents.connectors import check_all

        statuses: dict[str, str] = {}
        for group in check_all().values():
            for status in group:
                statuses[status.name] = status.state.value
        return statuses
    except Exception:  # pragma: no cover - defensive: live status is optional
        return {}


def build_agentic_os_graph(include_live_status: bool = False) -> SystemGraph:
    """Materialize the AGENTIC-OS topology (kernel, jobs, connectors, strategies, artifacts)."""
    # Lazy import: algo_agents.os.jobs imports this package (graphify job), so a
    # top-level import here would create a circular import at package init time.
    from algo_agents.os.jobs import register_all_jobs

    register_all_jobs()
    settings = get_settings()

    graph = SystemGraph()
    live = _connector_status_map() if include_live_status else {}

    # --- Core kernel + scheduler ---
    graph.add_node(Node("kernel", "AgenticOS kernel", "kernel", {"module": "algo_agents.os.kernel"}))
    graph.add_node(
        Node(
            "scheduler",
            "Scheduler",
            "scheduler",
            {
                "enabled": settings.agentic_schedule_enabled,
                "tz": settings.agentic_schedule_tz,
                "at": f"{settings.agentic_schedule_hour:02d}:{settings.agentic_schedule_minute:02d}",
            },
        )
    )
    graph.add_edge(Edge("scheduler", "kernel", "triggers daily", "control"))

    # --- Connectors (grouped) ---
    from algo_agents.connectors import build_all

    for category, instances in build_all().items():
        for inst in instances:
            meta: dict[str, Any] = {"category": category}
            if include_live_status and inst.name in live:
                meta["status"] = live[inst.name]
            graph.add_node(Node(f"connector:{inst.name}", inst.name, "connector", meta))

    # --- Strategies ---
    for key, cls_name in _STRATEGIES:
        graph.add_node(Node(f"strategy:{key}", key, "strategy", {"class": cls_name}))

    # --- Artifacts ---
    for key, (label, path) in _ARTIFACTS.items():
        graph.add_node(Node(f"artifact:{key}", label, "artifact", {"path": path}))

    # --- Jobs + their wiring ---
    for name in job_names():
        job_id = f"job:{name}"
        graph.add_node(Node(job_id, name, "job", {"module": "algo_agents.os.jobs"}))
        graph.add_edge(Edge("kernel", job_id, "dispatches", "control"))

        for connector in _JOB_CONNECTORS.get(name, []):
            cid = f"connector:{connector}"
            if cid in graph.node_ids():
                graph.add_edge(Edge(job_id, cid, "uses", "flow"))
        for strategy in _JOB_STRATEGIES.get(name, []):
            graph.add_edge(Edge(job_id, f"strategy:{strategy}", "runs", "flow"))
        for artifact in _JOB_ARTIFACT_WRITES.get(name, []):
            graph.add_edge(Edge(job_id, f"artifact:{artifact}", "writes", "artifact"))
        for artifact in _JOB_ARTIFACT_READS.get(name, []):
            graph.add_edge(Edge(f"artifact:{artifact}", job_id, "feeds", "artifact"))

    # --- daily composite pipeline ---
    for step in _DAILY_STEPS:
        step_id = f"job:{step}"
        if step_id in graph.node_ids():
            graph.add_edge(Edge("job:daily", step_id, "step", "pipeline"))

    # --- strategies consume market/sentiment/memory connectors ---
    for strategy in ("momentum", "agent", "ml"):
        graph.add_edge(Edge(f"strategy:{strategy}", "connector:yfinance", "prices", "flow"))
    graph.add_edge(Edge("strategy:agent", "connector:hf_sentiment", "sentiment", "flow"))
    graph.add_edge(Edge("strategy:agent", "connector:memory", "recall", "flow"))

    graph.meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "live_status": include_live_status,
        "runs_dir": settings.runs_dir,
        "default_strategy": settings.default_strategy,
    }
    return graph
