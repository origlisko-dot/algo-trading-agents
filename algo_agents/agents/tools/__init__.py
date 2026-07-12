"""Aggregate LangChain tools for the agent layer."""
from __future__ import annotations

from typing import Any

from algo_agents.agents.tools.market import get_market_tools
from algo_agents.agents.tools.memory import get_memory_tools
from algo_agents.agents.tools.news import get_news_tools
from algo_agents.agents.tools.sentiment import get_sentiment_tools


def get_all_tools() -> list[Any]:
    return [
        *get_market_tools(),
        *get_news_tools(),
        *get_sentiment_tools(),
        *get_memory_tools(),
    ]


def tool_by_name(name: str) -> Any | None:
    for t in get_all_tools():
        tname = getattr(t, "name", None) or getattr(t, "__name__", None)
        if tname == name:
            return t
    return None
