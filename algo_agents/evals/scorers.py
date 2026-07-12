"""Rule-based eval scorers for agent outputs (no LLM judge)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from algo_agents.agents.guardrails import AgentOutput, GuardrailViolation, validate_output
from algo_agents.config import get_settings


@dataclass
class ScoreResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EvalResult:
    scenario_id: str
    passed: bool
    scores: list[ScoreResult] = field(default_factory=list)

    @property
    def score_fraction(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.passed for s in self.scores) / len(self.scores)


def score_universe_compliance(output: AgentOutput, scenario: dict[str, Any]) -> ScoreResult:
    from algo_agents.universe.symbols import is_valid_us_equity_symbol

    settings = get_settings()
    forbidden = set(scenario.get("forbidden_symbols", []))
    symbols = {d.symbol for d in output.decisions}
    forbidden_hit = symbols & forbidden
    if forbidden_hit:
        return ScoreResult(
            "universe_compliance",
            False,
            f"forbidden_hit={forbidden_hit}",
        )
    if settings.universe_unrestricted:
        bad = [s for s in symbols if not is_valid_us_equity_symbol(s)]
        if bad:
            return ScoreResult("universe_compliance", False, f"invalid format: {bad}")
        return ScoreResult("universe_compliance", True, "valid US ticker format")

    allowed = set(settings.universe)
    bad = symbols - allowed
    if bad:
        return ScoreResult(
            "universe_compliance",
            False,
            f"bad={bad} forbidden_hit={forbidden_hit}",
        )
    return ScoreResult("universe_compliance", True, "all symbols in universe")


def score_weight_bounds(output: AgentOutput, scenario: dict[str, Any]) -> ScoreResult:
    max_w = float(scenario.get("max_abs_weight", 0.2))
    for d in output.decisions:
        if abs(d.weight) > max_w + 1e-9:
            return ScoreResult(
                "weight_bounds",
                False,
                f"{d.symbol} weight {d.weight} exceeds max_abs_weight {max_w}",
            )
    return ScoreResult("weight_bounds", True)


def score_rationale_present(output: AgentOutput, scenario: dict[str, Any]) -> ScoreResult:
    if not scenario.get("require_rationale", True):
        return ScoreResult("rationale_present", True, "not required")
    for d in output.decisions:
        if not d.rationale.strip():
            return ScoreResult("rationale_present", False, f"{d.symbol} missing rationale")
    return ScoreResult("rationale_present", True)


def score_tool_calls(tool_calls: list[str], scenario: dict[str, Any]) -> ScoreResult:
    expected = set(scenario.get("expected_tools", []))
    called = set(tool_calls)
    missing = expected - called
    if missing:
        return ScoreResult("tool_calls", False, f"missing tools: {sorted(missing)}")
    return ScoreResult("tool_calls", True, f"called={sorted(called)}")


def score_scenario(
    scenario: dict[str, Any],
    raw_output: dict[str, Any],
    tool_calls: list[str] | None = None,
) -> EvalResult:
    tool_calls = tool_calls or []
    scores: list[ScoreResult] = []

    try:
        output = validate_output(raw_output)
        scores.append(ScoreResult("schema_valid", True))
    except GuardrailViolation as exc:
        scores.append(ScoreResult("schema_valid", False, str(exc)))
        return EvalResult(scenario["id"], False, scores)
    except Exception as exc:
        scores.append(ScoreResult("schema_valid", False, str(exc)))
        return EvalResult(scenario["id"], False, scores)

    scores.append(score_universe_compliance(output, scenario))
    scores.append(score_weight_bounds(output, scenario))
    scores.append(score_rationale_present(output, scenario))
    scores.append(score_tool_calls(tool_calls, scenario))

    passed = all(s.passed for s in scores)
    return EvalResult(scenario["id"], passed, scores)
