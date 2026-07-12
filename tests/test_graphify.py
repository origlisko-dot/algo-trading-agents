"""Tests for Graphify system-graph export."""
from __future__ import annotations

from pathlib import Path

from algo_agents.os.graphify import build_agentic_os_graph, export_system_graph
from algo_agents.os.graphify.export import to_mermaid
from algo_agents.os.jobs import register_all_jobs
from algo_agents.os.registry import run_job
from algo_agents.os import RunContext


def test_build_agentic_os_graph_has_core_nodes():
    register_all_jobs()
    graph = build_agentic_os_graph(include_live_status=False)
    ids = {n.id for n in graph.nodes}
    assert "kernel" in ids
    assert "job:daily" in ids
    assert "job:graphify" in ids
    assert "job:universe-scan" in ids
    assert "connector:yfinance" in ids
    assert "strategy:momentum" in ids
    assert "artifact:watchlist" in ids
    assert len(graph.edges) >= 10


def test_export_system_graph_writes_artifacts(tmp_path: Path):
    register_all_jobs()
    graph = build_agentic_os_graph(include_live_status=False)
    paths = export_system_graph(graph, tmp_path / "graphify")
    assert Path(paths["json"]).exists()
    assert Path(paths["mermaid"]).exists()
    assert Path(paths["html"]).exists()
    mermaid = Path(paths["mermaid"]).read_text(encoding="utf-8")
    assert mermaid.startswith("flowchart")
    assert "kernel" in mermaid or "AgenticOS" in mermaid


def test_to_mermaid_escapes_quotes():
    register_all_jobs()
    graph = build_agentic_os_graph(include_live_status=False)
    text = to_mermaid(graph)
    assert "-->" in text


def test_graphify_job(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    register_all_jobs()
    result = run_job("graphify", RunContext.create())
    assert result.ok
    assert result.data["nodes"] > 0
    assert Path(result.data["paths"]["json"]).exists()
    get_settings.cache_clear()
