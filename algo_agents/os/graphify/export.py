"""Export AGENTIC-OS system graphs to JSON, Mermaid, and HTML."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from algo_agents.os.graphify.models import SystemGraph


def _escape_mermaid_label(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def to_mermaid(graph: SystemGraph) -> str:
    """Render a flowchart Mermaid diagram from the system graph."""
    lines = ["flowchart LR"]
    for node in graph.nodes:
        label = _escape_mermaid_label(f"{node.label}\\n({node.kind})")
        lines.append(f'  {_mermaid_id(node.id)}["{label}"]')
    for edge in graph.edges:
        rel = _escape_mermaid_label(edge.relation)
        lines.append(
            f"  {_mermaid_id(edge.source)} -->|{rel}| {_mermaid_id(edge.target)}"
        )
    return "\n".join(lines) + "\n"


def _mermaid_id(node_id: str) -> str:
    # Mermaid node ids cannot contain ':'; keep a stable alphanumeric form.
    return "".join(ch if ch.isalnum() else "_" for ch in node_id)


def to_html(graph: SystemGraph, mermaid: str) -> str:
    """Minimal self-contained HTML viewer (Mermaid via CDN)."""
    title = "AGENTIC-OS Graphify"
    safe_mermaid = html.escape(mermaid)
    meta = html.escape(json.dumps(graph.meta, indent=2))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";
    mermaid.initialize({{ startOnLoad: true, theme: "neutral" }});
  </script>
  <style>
    body {{ font-family: Georgia, "Times New Roman", serif; margin: 2rem; background: #f7f4ef; color: #1c1c1c; }}
    h1 {{ font-weight: 600; letter-spacing: 0.02em; }}
    pre.meta {{ background: #ebe6dc; padding: 1rem; overflow: auto; }}
    .mermaid {{ background: #fff; padding: 1.5rem; border: 1px solid #d8d0c4; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>{len(graph.nodes)} nodes · {len(graph.edges)} edges</p>
  <pre class="meta">{meta}</pre>
  <pre class="mermaid">{safe_mermaid}</pre>
</body>
</html>
"""


def export_system_graph(graph: SystemGraph, out_dir: str | Path) -> dict[str, str]:
    """Write graph.json, graph.mmd, and graph.html under ``out_dir``."""
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    json_path = target / "graph.json"
    mermaid_path = target / "graph.mmd"
    html_path = target / "graph.html"

    mermaid = to_mermaid(graph)
    payload: dict[str, Any] = graph.to_dict()

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    mermaid_path.write_text(mermaid, encoding="utf-8")
    html_path.write_text(to_html(graph, mermaid), encoding="utf-8")

    return {
        "json": str(json_path),
        "mermaid": str(mermaid_path),
        "html": str(html_path),
    }
