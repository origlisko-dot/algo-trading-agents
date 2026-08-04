"""Graph data model for the AGENTIC-OS runtime system map."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Node:
    """A single entity in the AGENTIC-OS topology (kernel, job, connector, ...)."""

    id: str
    label: str
    kind: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Edge:
    """A directed relationship / data flow between two nodes."""

    src: str
    dst: str
    label: str = ""
    kind: str = "flow"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SystemGraph:
    """The full AGENTIC-OS topology as inspectable nodes + edges."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: Node) -> Node:
        if not any(existing.id == node.id for existing in self.nodes):
            self.nodes.append(node)
        return node

    def add_edge(self, edge: Edge) -> Edge:
        self.edges.append(edge)
        return edge

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }
