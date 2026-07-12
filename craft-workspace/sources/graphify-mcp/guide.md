# Graphify Knowledge Graph MCP

Stdio MCP server exposing the `algo_agents` knowledge graph built by Graphify.

## Graph location

`algo_agents/graphify-out/graph.json` (493 nodes, 914 edges as of initial build)

## Tools

Use this source for architecture questions instead of grepping:

- Shortest path between concepts
- Node explanations and neighbor traversal
- Impact analysis (what depends on X)

## Refresh

After code changes under `algo_agents/`:

```bash
graphify update algo_agents
```

For a full rebuild:

```bash
graphify extract algo_agents --code-only
graphify cluster-only algo_agents
```

## Requirements

- Project venv with `pip install -e graphify` and `pip install "graphifyy[mcp]"`
- Local MCP servers enabled in Craft workspace settings
