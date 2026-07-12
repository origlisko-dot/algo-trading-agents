"""Tests for eval scorers."""
from __future__ import annotations

from algo_agents.evals.runner import load_scenarios, mock_runner, run_evals
from algo_agents.evals.scorers import score_scenario


def test_mock_runner_passes_all_scenarios():
    summary = run_evals(mock_runner)
    assert summary.passed == summary.total
    assert summary.total >= 5


def test_score_scenario_weight_bounds_fail():
    scenario = next(s for s in load_scenarios() if s["id"] == "tsla_high_vol")
    raw = {
        "decisions": [
            {
                "symbol": scenario["symbol"],
                "weight": 0.18,
                "rationale": "too aggressive for high-vol name",
                "confidence": 0.5,
            }
        ]
    }
    result = score_scenario(scenario, raw, tool_calls=scenario.get("expected_tools", []))
    assert not result.passed
    assert any(s.name == "weight_bounds" and not s.passed for s in result.scores)


def test_score_scenario_missing_tools():
    scenario = next(s for s in load_scenarios() if s["expected_tools"])
    raw = {
        "decisions": [
            {
                "symbol": scenario["symbol"],
                "weight": 0.05,
                "rationale": "ok",
                "confidence": 0.5,
            }
        ]
    }
    result = score_scenario(scenario, raw, tool_calls=[])
    assert not result.passed
    assert any(s.name == "tool_calls" and not s.passed for s in result.scores)
