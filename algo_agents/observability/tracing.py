"""LangSmith tracing bootstrap. No-op when credentials are absent."""
from __future__ import annotations

import os

from algo_agents.config import get_settings
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)
_INITIALIZED = False


def tracing_enabled() -> bool:
    settings = get_settings()
    return bool(settings.langsmith_api_key and settings.langchain_tracing_v2)


def init_tracing() -> bool:
    """Configure LangSmith env vars from Settings. Returns True if active."""
    global _INITIALIZED
    if _INITIALIZED:
        return tracing_enabled()

    settings = get_settings()
    if not settings.langsmith_api_key:
        _log.info("LangSmith tracing disabled (LANGSMITH_API_KEY not set)")
        _INITIALIZED = True
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    if settings.llm_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.llm_api_key)

    _log.info("LangSmith tracing enabled for project '%s'", settings.langsmith_project)
    _INITIALIZED = True
    return settings.langchain_tracing_v2
