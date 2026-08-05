"""Build a deterministic AGENTIC-OS runtime topology graph."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors import build_all, check_all
from algo_agents.os.artifacts import read_active_strategy
from algo_agents.os.graphify.models import GraphEdge, GraphNode, SystemGraph
from algo_agents.os.registry import names as job_names
from algo_agents.universe.scanner import watchlist_path

# Daily pipeline order (matches algo_agents.os.jobs.daily).
_DAILY_FLOW = (
    "health",
    "evals",
    "universe-scan",
    "paper",
    "monitor",
    "portfolio",
    "graphify",
)

_STRATEGIES = (
    ("momentum", "Momentum + sentiment baseline"),
    ("agent", "LLM / heuristic agent strategy"),
    ("ml", "ML signal strategy"),
)

_ARTIFACTS = (
    ("watchlist", "runs/daily_watchlist.json", "Daily ranked symbols"),
    ("active_strategy", "runs/active_strategy.json", "Promoted strategy"),
    ("paper_account", "runs/paper_account.json", "Simulated paper book"),
    ("pnl_history", "runs/pnl_history.jsonl", "PnL history log"),
    ("regime_sharpe", "runs/regime_sharpe.json", "Regime Sharpe history"),
)


def build_agentic_os_graph(*, include_live_status: bool = True) -> SystemGraph:
    """Materialize jobs, connectors, strategies, artifacts, and data flows."""
    settings = get_settings()
    # Callers (AgenticOS / tests) must register jobs before building.
    graph = SystemGraph(
        meta={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "include_live_status": include_live_status,
            "runs_dir": str(settings.runs_dir),
        }
    )

    graph.add_node(
        GraphNode(
            id="kernel",
            label="AgenticOS",
            kind="kernel",
            meta={"role": "orchestrator"},
        )
    )

    registered = set(job_names())
    for name in sorted(registered):
        graph.add_node(
            GraphNode(
                id=f"job:{name}",
                label=name,
                kind="job",
                meta={"registered": True},
            )
        )
        graph.add_edge(
            GraphEdge(source="kernel", target=f"job:{name}", relation="registers")
        )

    for left, right in zip(_DAILY_FLOW, _DAILY_FLOW[1:]):
        if left in registered and right in registered:
            graph.add_edge(
                GraphEdge(
                    source=f"job:{left}",
                    target=f"job:{right}",
                    relation="daily_next",
                )
            )

    if "daily" in registered:
        for step in _DAILY_FLOW:
            if step in registered:
                graph.add_edge(
                    GraphEdge(
                        source="job:daily",
                        target=f"job:{step}",
                        relation="invokes",
                    )
                )

    connector_status: dict[str, dict[str, Any]] = {}
    if include_live_status:
        for statuses in check_all().values():
            for status in statuses:
                connector_status[status.name] = {
                    "state": status.state.value,
                    "detail": status.detail,
                    "ok": status.ok,
                }

    for category, connectors in build_all().items():
        for connector in connectors:
            node_id = f"connector:{connector.name}"
            meta: dict[str, Any] = {"category": category}
            if connector.name in connector_status:
                meta.update(connector_status[connector.name])
            graph.add_node(
                GraphNode(
                    id=node_id,
                    label=connector.name,
                    kind="connector",
                    meta=meta,
                )
            )
            if "health" in registered:
                graph.add_edge(
                    GraphEdge(
                        source="job:health",
                        target=node_id,
                        relation="checks",
                    )
                )
            if "paper" in registered and category in {"brokers", "market_data"}:
                graph.add_edge(
                    GraphEdge(
                        source=node_id,
                        target="job:paper",
                        relation="feeds",
                    )
                )
            if "universe-scan" in registered and category == "market_data":
                graph.add_edge(
                    GraphEdge(
                        source=node_id,
                        target="job:universe-scan",
                        relation="feeds",
                    )
                )

    active = read_active_strategy() if include_live_status else None
    active_name = active.get("strategy") if isinstance(active, dict) else None

    for key, label in _STRATEGIES:
        meta = {"router_key": key}
        if active_name == key:
            meta["active"] = True
        graph.add_node(
            GraphNode(
                id=f"strategy:{key}",
                label=label,
                kind="strategy",
                meta=meta,
            )
        )
        if "paper" in registered:
            graph.add_edge(
                GraphEdge(
                    source=f"strategy:{key}",
                    target="job:paper",
                    relation="may_drive",
                )
            )
        if "monitor" in registered:
            graph.add_edge(
                GraphEdge(
                    source="job:monitor",
                    target=f"strategy:{key}",
                    relation="evaluates",
                )
            )

    runs = Path(settings.runs_dir)
    for key, rel_path, label in _ARTIFACTS:
        path = runs / Path(rel_path).name
        # Prefer scanner helper for watchlist path (honors settings).
        if key == "watchlist":
            path = watchlist_path(settings)
        meta: dict[str, Any] = {"path": str(path)}
        if include_live_status:
            meta["exists"] = path.exists()
        graph.add_node(
            GraphNode(
                id=f"artifact:{key}",
                label=label,
                kind="artifact",
                meta=meta,
            )
        )

    _link_artifacts(graph, registered)
    graph.meta["node_count"] = len(graph.nodes)
    graph.meta["edge_count"] = len(graph.edges)
    return graph


def _link_artifacts(graph: SystemGraph, registered: set[str]) -> None:
    links = (
        ("job:universe-scan", "artifact:watchlist", "writes"),
        ("artifact:watchlist", "job:paper", "consumes"),
        ("job:paper", "artifact:paper_account", "writes"),
        ("job:portfolio", "artifact:pnl_history", "writes"),
        ("job:monitor", "artifact:active_strategy", "may_write"),
        ("job:monitor", "artifact:regime_sharpe", "writes"),
        ("artifact:active_strategy", "job:paper", "routes"),
        ("job:graphify", "artifact:watchlist", "reads"),
    )
    for source, target, relation in links:
        src_ok = source.startswith("artifact:") or source.removeprefix("job:") in registered
        tgt_ok = target.startswith("artifact:") or target.removeprefix("job:") in registered
        if src_ok and tgt_ok:
            graph.add_edge(GraphEdge(source=source, target=target, relation=relation))
