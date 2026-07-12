"""Persistent vector memory for the agent (Chroma).

Stores trade rationales, reflections and outcomes so future decisions can
retrieve the most relevant past experiences (recency/relevancy ranking is
applied downstream, FinMem-style).
"""
from __future__ import annotations

import uuid
from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors.base import ConnectorState, ConnectorStatus, MemoryStore

try:
    import chromadb

    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False

_COLLECTION = "trade_memory"

_CHROMA_META_TYPES = (str, int, float, bool)


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma rejects None and nested objects in metadata."""
    clean: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, _CHROMA_META_TYPES):
            clean[str(key)] = value
        else:
            clean[str(key)] = str(value)
    return clean


class ChromaMemory(MemoryStore):
    name = "memory"

    def __init__(self) -> None:
        self._dir = get_settings().chroma_persist_dir
        self._collection: Any = None

    def _collection_or_none(self) -> Any:
        if not _CHROMA_AVAILABLE:
            return None
        if self._collection is None:
            client = chromadb.PersistentClient(path=self._dir)
            self._collection = client.get_or_create_collection(_COLLECTION)
        return self._collection

    def check(self) -> ConnectorStatus:
        if not _CHROMA_AVAILABLE:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_DEPENDENCY, "pip install chromadb"
            )
        try:
            count = self._collection_or_none().count()
            return ConnectorStatus(
                self.name, ConnectorState.READY, f"{count} memories at {self._dir}"
            )
        except Exception as exc:
            return ConnectorStatus(self.name, ConnectorState.ERROR, str(exc))

    def add(self, text: str, metadata: dict[str, Any]) -> None:
        collection = self._require_collection()
        collection.add(
            documents=[text],
            metadatas=[_sanitize_metadata(metadata)],
            ids=[str(uuid.uuid4())],
        )

    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        collection = self._require_collection()
        res = collection.query(query_texts=[text], n_results=k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [
            {"text": d, "metadata": m, "distance": dist}
            for d, m, dist in zip(docs, metas, dists)
        ]

    def _require_collection(self) -> Any:
        collection = self._collection_or_none()
        if collection is None:
            raise RuntimeError("chromadb not installed")
        return collection
