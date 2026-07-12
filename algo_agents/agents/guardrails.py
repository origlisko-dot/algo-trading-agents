"""Software guardrails for the agent layer (not prompt-only)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from algo_agents.config import get_settings
from algo_agents.universe.symbols import is_valid_us_equity_symbol, symbol_allowed

# Read-only tools analysts may invoke. Broker/order tools are never exposed.
ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "get_price_history",
        "get_news_headlines",
        "score_sentiment",
        "recall_past_trades",
        "store_reflection",
    }
)

FORBIDDEN_TOOLS: frozenset[str] = frozenset(
    {
        "submit_order",
        "place_order",
        "buy",
        "sell",
    }
)

MAX_WEIGHT = 0.20
MIN_WEIGHT = -0.20


class SymbolDecision(BaseModel):
    symbol: str
    weight: float = Field(ge=MIN_WEIGHT, le=MAX_WEIGHT)
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()


class AgentOutput(BaseModel):
    decisions: list[SymbolDecision]

    def to_weights(self) -> dict[str, float]:
        return {d.symbol: d.weight for d in self.decisions}

    def to_rationale(self) -> dict[str, str]:
        return {d.symbol: d.rationale for d in self.decisions}


class GuardrailViolation(Exception):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def assert_universe(symbols: list[str]) -> None:
    settings = get_settings()
    if settings.universe_unrestricted:
        bad = [s for s in symbols if not is_valid_us_equity_symbol(s)]
        if bad:
            raise GuardrailViolation(
                f"Invalid US ticker format: {bad}",
                field="universe",
            )
        return
    allowed = set(settings.universe)
    bad = [s for s in symbols if s.upper() not in allowed]
    if bad:
        raise GuardrailViolation(
            f"Symbols outside trading universe: {bad}. Allowed: {sorted(allowed)}",
            field="universe",
        )


def assert_tool_allowed(tool_name: str) -> None:
    name = tool_name.strip()
    if name in FORBIDDEN_TOOLS:
        raise GuardrailViolation(f"Forbidden tool: {name}", field="tool")
    if name not in ALLOWED_TOOLS:
        raise GuardrailViolation(
            f"Tool '{name}' not in allowlist. Allowed: {sorted(ALLOWED_TOOLS)}",
            field="tool",
        )


def assert_paper_only() -> None:
    settings = get_settings()
    if settings.is_live:
        raise GuardrailViolation(
            "Agent layer blocked in live mode. Set TRADING_PAPER=true.",
            field="paper",
        )


def validate_output(raw: dict[str, Any]) -> AgentOutput:
    """Validate and normalize agent output against schema + universe."""
    assert_paper_only()
    output = AgentOutput.model_validate(raw)
    assert_universe([d.symbol for d in output.decisions])
    return output


def validate_tool_call(tool_name: str, args: dict[str, Any] | None = None) -> None:
    assert_paper_only()
    assert_tool_allowed(tool_name)
    args = args or {}
    symbol = args.get("symbol")
    if symbol:
        assert_universe([str(symbol)])
