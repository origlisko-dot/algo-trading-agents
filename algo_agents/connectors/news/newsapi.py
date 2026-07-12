"""NewsAPI.org connector for company headlines."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from algo_agents.config import get_settings
from algo_agents.connectors.base import ConnectorState, ConnectorStatus, NewsConnector

_BASE_URL = "https://newsapi.org/v2/everything"


class NewsAPINews(NewsConnector):
    name = "newsapi"

    def __init__(self) -> None:
        self._key = get_settings().newsapi_key

    def check(self) -> ConnectorStatus:
        if not self._key:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_CREDENTIALS, "set NEWSAPI_KEY"
            )
        return ConnectorStatus(self.name, ConnectorState.READY, "key present")

    def get_news(self, symbol: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if not self._key:
            raise RuntimeError("NEWSAPI_KEY not set")
        resp = requests.get(
            _BASE_URL,
            params={
                "q": symbol,
                "from": f"{start:%Y-%m-%d}",
                "to": f"{end:%Y-%m-%d}",
                "language": "en",
                "sortBy": "publishedAt",
                "apiKey": self._key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return [
            {
                "datetime": a.get("publishedAt"),
                "headline": a.get("title"),
                "summary": a.get("description"),
                "url": a.get("url"),
            }
            for a in resp.json().get("articles", [])
        ]
