"""Launch the Graphify MCP stdio server for algo_agents/graphify-out/graph.json."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    graph = root / "algo_agents" / "graphify-out" / "graph.json"
    if not graph.exists():
        print(
            f"Graph not found: {graph}\n"
            "Run: graphify extract algo_agents --code-only && graphify cluster-only algo_agents",
            file=sys.stderr,
        )
        raise SystemExit(1)
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "graphify.serve", str(graph)])
    )


if __name__ == "__main__":
    main()
