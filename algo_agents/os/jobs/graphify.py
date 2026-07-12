"""Graphify job: export AGENTIC-OS runtime system graph."""
from __future__ import annotations

from pathlib import Path

from algo_agents.os.context import JobResult, RunContext
from algo_agents.os.graphify import build_agentic_os_graph, export_system_graph


def run_graphify(ctx: RunContext) -> JobResult:
    out_dir = Path(ctx.settings.runs_dir) / "graphify"
    graph = build_agentic_os_graph(include_live_status=True)
    paths = export_system_graph(graph, out_dir)
    return JobResult(
        name="graphify",
        ok=True,
        detail=f"{len(graph.nodes)} nodes / {len(graph.edges)} edges -> {paths['html']}",
        data={
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "paths": paths,
            "meta": graph.meta,
        },
    )
