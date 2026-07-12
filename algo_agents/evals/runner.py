"""Run agent evals against golden scenarios."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from algo_agents.evals.scorers import EvalResult, score_scenario
from algo_agents.observability.logging import bind_context, get_logger, new_run_id

_log = get_logger(__name__)

_DATASET = Path(__file__).parent / "datasets" / "golden_scenarios.json"


class AgentRunner(Protocol):
    def __call__(
        self, scenario: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]: ...


@dataclass
class EvalRunSummary:
    total: int = 0
    passed: int = 0
    results: list[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _DATASET
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def run_evals(
    runner: AgentRunner,
    scenarios: list[dict[str, Any]] | None = None,
    *,
    run_id: str | None = None,
) -> EvalRunSummary:
    scenarios = scenarios or load_scenarios()
    run_id = run_id or new_run_id()
    bind_context(run_id=run_id, agent_role="eval_runner")
    summary = EvalRunSummary(total=len(scenarios))

    for scenario in scenarios:
        bind_context(symbol=scenario.get("symbol"))
        _log.info("eval scenario %s", scenario["id"])
        raw_output, tool_calls = runner(scenario)
        result = score_scenario(scenario, raw_output, tool_calls)
        summary.results.append(result)
        summary.passed += int(result.passed)
        _log.info(
            "scenario %s %s (%.0f%%)",
            scenario["id"],
            "PASS" if result.passed else "FAIL",
            result.score_fraction * 100,
        )

    return summary


def mock_runner(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Deterministic runner for tests when LLM is unavailable."""
    symbol = scenario["symbol"]
    max_w = float(scenario.get("max_abs_weight", 0.2))
    weight = 0.0 if scenario["id"] == "flat_no_signal" else max_w * 0.5
    tool_calls = list(scenario.get("expected_tools", []))
    return (
        {
            "decisions": [
                {
                    "symbol": symbol,
                    "weight": weight,
                    "rationale": f"mock decision for {scenario['id']}",
                    "confidence": 0.6,
                }
            ]
        },
        tool_calls,
    )
