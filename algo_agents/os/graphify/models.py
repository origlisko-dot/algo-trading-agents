"""Data model for the AGENTIC-OS runtime system graph."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    id: str
    label: str
    kind: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SystemGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        if any(existing.id == node.id for existing in self.nodes):
            return
        self.nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.relation)
        if any((e.source, e.target, e.relation) == key for e in self.edges):
            return
        self.edges.append(edge)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "meta": self.meta,
        }
