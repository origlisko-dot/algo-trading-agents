"""Data model for the AGENTIC-OS system graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    id: str
    kind: str  # kernel | job | connector | strategy | artifact
    label: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    src: str
    dst: str
    label: str = ""


@dataclass
class SystemGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def node(self, node_id: str) -> GraphNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def add_node(self, node: GraphNode) -> None:
        if self.node(node.id) is None:
            self.nodes.append(node)

    def add_edge(self, src: str, dst: str, label: str = "") -> None:
        edge = GraphEdge(src=src, dst=dst, label=label)
        if edge not in self.edges:
            self.edges.append(edge)
