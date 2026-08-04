"""Render / persist the AGENTIC-OS system graph as JSON, Mermaid, and HTML."""
from __future__ import annotations

import json
import re
from pathlib import Path

from algo_agents.os.graphify.model import SystemGraph

# Mermaid node shapes per node kind (open/close bracket pair).
_SHAPES: dict[str, tuple[str, str]] = {
    "kernel": ("{{", "}}"),
    "scheduler": ("([", "])"),
    "job": ("[", "]"),
    "connector": ("[(", ")]"),
    "strategy": ("([", "])"),
    "artifact": ("[/", "/]"),
}


def _safe_id(node_id: str) -> str:
    """Mermaid identifiers cannot contain ':' or '-'; map to a stable safe token."""
    return re.sub(r"[^0-9A-Za-z_]", "_", node_id)


def _escape(label: str) -> str:
    """Escape characters that would break a Mermaid quoted label."""
    return label.replace('"', "#quot;").replace("\n", " ").strip()


def to_mermaid(graph: SystemGraph) -> str:
    """Return a Mermaid `flowchart` representation of the system graph."""
    lines: list[str] = ["flowchart TD"]
    for node in graph.nodes:
        open_b, close_b = _SHAPES.get(node.kind, ("[", "]"))
        lines.append(f'    {_safe_id(node.id)}{open_b}"{_escape(node.label)}"{close_b}')
    for edge in graph.edges:
        label = _escape(edge.label)
        arrow = f'-->|"{label}"|' if label else "-->"
        lines.append(f"    {_safe_id(edge.src)} {arrow} {_safe_id(edge.dst)}")
    return "\n".join(lines) + "\n"


def to_json(graph: SystemGraph) -> str:
    """Return the system graph as pretty JSON."""
    return json.dumps(graph.to_dict(), indent=2)


def to_html(graph: SystemGraph) -> str:
    """Return a self-contained HTML page that renders the graph via Mermaid.js."""
    mermaid = to_mermaid(graph)
    meta = graph.to_dict()["meta"]
    meta_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in meta.items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>AGENTIC-OS system graph</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  table {{ border-collapse: collapse; margin-bottom: 1.5rem; font-size: 0.85rem; }}
  td {{ border: 1px solid #ddd; padding: 2px 8px; }}
  td:first-child {{ color: #666; }}
  .graph {{ border: 1px solid #eee; border-radius: 8px; padding: 1rem; }}
</style>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, securityLevel: "loose" }});
</script>
</head>
<body>
<h1>AGENTIC-OS system graph</h1>
<table>{meta_rows}</table>
<div class="graph"><pre class="mermaid">
{mermaid}
</pre></div>
</body>
</html>
"""


def export_system_graph(graph: SystemGraph, out_dir: str | Path) -> dict[str, str]:
    """Write graph.json / graph.mmd / graph.html into `out_dir`; return their paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "graph.json"
    mermaid_path = out / "graph.mmd"
    html_path = out / "graph.html"

    json_path.write_text(to_json(graph), encoding="utf-8")
    mermaid_path.write_text(to_mermaid(graph), encoding="utf-8")
    html_path.write_text(to_html(graph), encoding="utf-8")

    return {
        "json": str(json_path),
        "mermaid": str(mermaid_path),
        "html": str(html_path),
    }


__all__: list[str] = ["to_mermaid", "to_json", "to_html", "export_system_graph"]
