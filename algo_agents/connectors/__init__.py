"""Connector registry: one place to build and health-check every integration."""
from __future__ import annotations

from algo_agents.connectors.base import (
    BaseConnector,
    ConnectorState,
    ConnectorStatus,
)
from algo_agents.connectors.brokers import AlpacaBroker, IBKRBroker, SimulatedBroker
from algo_agents.connectors.market_data import (
    FinnhubData,
    FMPData,
    PolygonData,
    YFinanceData,
)
from algo_agents.connectors.memory import ChromaMemory
from algo_agents.connectors.news import EdgarNews, NewsAPINews
from algo_agents.connectors.sentiment import HFSentiment

_CONNECTOR_CLASSES: dict[str, list[type[BaseConnector]]] = {
    "brokers": [SimulatedBroker, IBKRBroker, AlpacaBroker],
    "market_data": [YFinanceData, PolygonData, FinnhubData, FMPData],
    "news": [NewsAPINews, EdgarNews],
    "sentiment": [HFSentiment],
    "memory": [ChromaMemory],
}


def build_all() -> dict[str, list[BaseConnector]]:
    """Instantiate every connector (construction never performs network I/O)."""
    return {
        category: [cls() for cls in classes]
        for category, classes in _CONNECTOR_CLASSES.items()
    }


def check_all() -> dict[str, list[ConnectorStatus]]:
    """Return the readiness status of every connector, grouped by category."""
    report: dict[str, list[ConnectorStatus]] = {}
    for category, classes in _CONNECTOR_CLASSES.items():
        statuses: list[ConnectorStatus] = []
        for cls in classes:
            try:
                statuses.append(cls().check())
            except Exception as exc:
                statuses.append(
                    ConnectorStatus(
                        getattr(cls, "name", cls.__name__), ConnectorState.ERROR, str(exc)
                    )
                )
        report[category] = statuses
    return report


__all__ = ["build_all", "check_all", "ConnectorStatus", "ConnectorState"]
