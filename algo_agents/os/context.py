"""Shared runtime context for AGENTIC-OS jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from algo_agents.config import Settings, get_settings
from algo_agents.observability.logging import new_run_id


@dataclass
class RunContext:
    run_id: str
    mock: bool = False
    skip_eval: bool = False
    strategy: str | None = None
    symbols: list[str] | None = None
    top_n: int = 5
    ml_days: int = 730
    settings: Settings = field(default_factory=get_settings)

    @classmethod
    def create(
        cls,
        *,
        mock: bool = False,
        skip_eval: bool = False,
        strategy: str | None = None,
        symbols: list[str] | None = None,
        top_n: int = 5,
        ml_days: int = 730,
    ) -> RunContext:
        return cls(
            run_id=new_run_id(),
            mock=mock,
            skip_eval=skip_eval,
            strategy=strategy,
            symbols=symbols,
            top_n=top_n,
            ml_days=ml_days,
        )


@dataclass
class JobResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, Any] = field(default_factory=dict)
