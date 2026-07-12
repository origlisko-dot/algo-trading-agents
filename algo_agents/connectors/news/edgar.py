"""SEC EDGAR connector. No API key, but a descriptive User-Agent is required.

Maps a ticker to its CIK and returns recent filings as news-like items.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from algo_agents.config import get_settings
from algo_agents.connectors.base import ConnectorState, ConnectorStatus, NewsConnector

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"


class EdgarNews(NewsConnector):
    name = "edgar"

    def __init__(self) -> None:
        self._ua = get_settings().edgar_user_agent
        self._ticker_to_cik: dict[str, int] | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self._ua}

    def check(self) -> ConnectorStatus:
        if not self._ua or "@" not in self._ua:
            return ConnectorStatus(
                self.name,
                ConnectorState.MISSING_CREDENTIALS,
                "set EDGAR_USER_AGENT to 'name email' (SEC requires it)",
            )
        try:
            requests.get(_TICKERS_URL, headers=self._headers, timeout=10).raise_for_status()
            return ConnectorStatus(self.name, ConnectorState.READY, "EDGAR reachable")
        except Exception as exc:
            return ConnectorStatus(self.name, ConnectorState.ERROR, str(exc))

    def _load_ticker_map(self) -> dict[str, int]:
        if self._ticker_to_cik is None:
            data = requests.get(_TICKERS_URL, headers=self._headers, timeout=30).json()
            self._ticker_to_cik = {
                row["ticker"].upper(): int(row["cik_str"]) for row in data.values()
            }
        return self._ticker_to_cik

    def get_news(self, symbol: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        cik = self._load_ticker_map().get(symbol.upper())
        if cik is None:
            return []
        data = requests.get(
            _SUBMISSIONS_URL.format(cik=cik), headers=self._headers, timeout=30
        ).json()
        recent = data.get("filings", {}).get("recent", {})
        items: list[dict[str, Any]] = []
        for form, date, accession, doc in zip(
            recent.get("form", []),
            recent.get("filingDate", []),
            recent.get("accessionNumber", []),
            recent.get("primaryDocument", []),
        ):
            filed = datetime.fromisoformat(date)
            if start.date() <= filed.date() <= end.date():
                acc = accession.replace("-", "")
                items.append(
                    {
                        "datetime": date,
                        "headline": f"{symbol.upper()} filed {form}",
                        "summary": f"SEC form {form}",
                        "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}",
                    }
                )
        return items
