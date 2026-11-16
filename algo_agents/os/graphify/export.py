"""Export the AGENTIC-OS system graph to JSON, Mermaid, and HTML artifacts."""
from __future__ import annotations

import html
import json
from dataclasses import asdict
from pathlib import Path

from algo_agents.os.graphify.model import SystemGraph


def _mermaid_id(node_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in node_id)


def _mermaid_label(label: str) -> str:
    return label.replace('"', "'")


def to_mermaid(graph: SystemGraph) -> str:
    lines = ["flowchart TD"]
    for node in graph.nodes:
        lines.append(f'    {_mermaid_id(node.id)}["{_mermaid_label(node.label)}"]')
    for edge in graph.edges:
        if edge.label:
            lines.append(
                f"    {_mermaid_id(edge.src)} -- {_mermaid_label(edge.label)} --> {_mermaid_id(edge.dst)}"
            )
        else:
            lines.append(f"    {_mermaid_id(edge.src)} --> {_mermaid_id(edge.dst)}")
    return "\n".join(lines) + "\n"


def graph_to_dict(graph: SystemGraph) -> dict:
    return {
        "meta": graph.meta,
        "nodes": [asdict(n) for n in graph.nodes],
        "edges": [asdict(e) for e in graph.edges],
    }


def _to_html(graph: SystemGraph, mermaid: str) -> str:
    body = html.escape(mermaid)
    meta = html.escape(json.dumps(graph.meta, indent=2))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AGENTIC-OS system graph</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }}
  pre {{ background: #1e293b; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 12px; }}
  h1 {{ font-size: 1.2rem; }}
  .mermaid {{ background: #f8fafc; border-radius: 8px; padding: 1rem; }}
</style>
</head>
<body>
<h1>AGENTIC-OS system graph</h1>
<p>{len(graph.nodes)} nodes / {len(graph.edges)} edges (deterministic, local export — no LLM).</p>
<pre class="mermaid">
{body}
</pre>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
</script>
<h2>meta</h2>
<pre>{meta}</pre>
</body>
</html>
"""


def export_system_graph(graph: SystemGraph, out_dir: Path | str) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "graph.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(graph_to_dict(graph), f, indent=2)

    mermaid = to_mermaid(graph)
    mermaid_path = out / "graph.mmd"
    mermaid_path.write_text(mermaid, encoding="utf-8")

    html_path = out / "graph.html"
    html_path.write_text(_to_html(graph, mermaid), encoding="utf-8")

    return {"json": str(json_path), "mermaid": str(mermaid_path), "html": str(html_path)}
