"""Structured logging configured from Settings.log_level."""
from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from algo_agents.config import get_settings

_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_symbol: ContextVar[str | None] = ContextVar("symbol", default=None)
_agent_role: ContextVar[str | None] = ContextVar("agent_role", default=None)

_CONFIGURED = False


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get() or "-"
        record.symbol = _symbol.get() or "-"
        record.agent_role = _agent_role.get() or "-"
        return True


def setup_logging(level: str | None = None) -> None:
    """Configure root logging once. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_level = (level or get_settings().log_level).upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [run=%(run_id)s sym=%(symbol)s role=%(agent_role)s] "
            "%(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(_ContextFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level, logging.INFO))
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def bind_context(
    *,
    run_id: str | None = None,
    symbol: str | None = None,
    agent_role: str | None = None,
) -> dict[str, Any]:
    """Set logging context vars; returns tokens for optional reset."""
    tokens: dict[str, Any] = {}
    if run_id is not None:
        tokens["run_id"] = _run_id.set(run_id)
    if symbol is not None:
        tokens["symbol"] = _symbol.set(symbol)
    if agent_role is not None:
        tokens["agent_role"] = _agent_role.set(agent_role)
    return tokens
