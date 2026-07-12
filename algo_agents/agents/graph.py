"""LangGraph multi-agent debate graph for per-symbol weight proposals."""
from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from algo_agents.agents.guardrails import AgentOutput, validate_output
from algo_agents.agents.prompts import (
    DEBATE_MODERATOR,
    FUNDAMENTAL_ANALYST,
    SENTIMENT_ANALYST,
    TECHNICAL_ANALYST,
)
from algo_agents.agents.tools import get_all_tools, tool_by_name
from algo_agents.config import get_settings
from algo_agents.observability.logging import bind_context, get_logger

_log = get_logger(__name__)

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langgraph.graph import END, START, StateGraph

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


class AgentState(TypedDict, total=False):
    symbol: str
    features_summary: str
    analyst_opinions: dict[str, str]
    final_weight: float
    rationale: str
    confidence: float
    tool_calls: list[str]
    raw_output: dict[str, Any]


def _invoke_tool(name: str, **kwargs: Any) -> str:
    fn = tool_by_name(name)
    if fn is None:
        return f"Tool {name} not found"
    if hasattr(fn, "invoke"):
        return str(fn.invoke(kwargs))
    return str(fn(**kwargs))


def _weight_from_features(features_summary: str) -> float:
    """Derive a conservative weight from lagged feature summary (no network)."""
    if not features_summary or features_summary == "no features":
        return 0.0
    weight = 0.0
    lower = features_summary.lower()
    if "momentum_10=" in lower:
        try:
            raw = lower.split("momentum_10=", 1)[1].split(",", 1)[0].strip()
            momentum = float(raw)
            if momentum > 0.03:
                weight = 0.08
            elif momentum < -0.03:
                weight = -0.05
        except ValueError:
            pass
    elif "momentum" in lower or "trend=1" in lower:
        weight = 0.08
    if "rsi_14=" in lower:
        try:
            raw = lower.split("rsi_14=", 1)[1].split(",", 1)[0].strip()
            rsi = float(raw)
            if rsi > 70:
                weight = max(-0.05, weight - 0.03)
            elif rsi < 30:
                weight = min(0.12, weight + 0.03)
        except ValueError:
            pass
    return max(-0.15, min(0.15, weight))


def _heuristic_offline(symbol: str, features_summary: str = "") -> AgentState:
    """Fast deterministic path using feature summary only (backtests/tests)."""
    tool_calls = ["get_price_history", "get_news_headlines", "score_sentiment"]
    weight = _weight_from_features(features_summary)
    rationale = (
        f"Offline heuristic for {symbol} from features ({features_summary or 'none'})"
    )
    opinions = {
        "technical": features_summary[:300] or "offline",
        "fundamental": "offline — skipped news fetch",
        "sentiment": "offline — skipped sentiment fetch",
    }
    raw = {
        "decisions": [
            {
                "symbol": symbol,
                "weight": weight,
                "rationale": rationale,
                "confidence": 0.4,
            }
        ]
    }
    return AgentState(
        symbol=symbol,
        features_summary=features_summary,
        analyst_opinions=opinions,
        final_weight=weight,
        rationale=rationale,
        confidence=0.4,
        tool_calls=tool_calls,
        raw_output=raw,
    )


def _safe_invoke_tool(name: str, tool_calls: list[str], **kwargs: Any) -> str:
    """Invoke a tool and degrade gracefully when connectors are unavailable."""
    try:
        result = _invoke_tool(name, **kwargs)
        if name not in tool_calls:
            tool_calls.append(name)
        return result
    except Exception as exc:
        _log.warning("tool %s failed (%s), using stub", name, exc)
        if name not in tool_calls:
            tool_calls.append(name)
        symbol = str(kwargs.get("symbol", ""))
        if name == "get_price_history":
            return f"{symbol} price data unavailable (degraded)"
        if name == "get_news_headlines":
            return f"{symbol} headlines unavailable (degraded)"
        if name == "score_sentiment":
            return f"{symbol} sentiment neutral avg=+0.000 (degraded)"
        return f"{name} unavailable (degraded)"


def _heuristic_analyze(symbol: str, features_summary: str = "") -> AgentState:
    """Deterministic fallback when LLM/LangGraph unavailable."""
    tool_calls: list[str] = []
    opinions: dict[str, str] = {}

    price_txt = _safe_invoke_tool(
        "get_price_history", tool_calls, symbol=symbol, days=60
    )
    opinions["technical"] = price_txt[:300]

    news_txt = _safe_invoke_tool(
        "get_news_headlines", tool_calls, symbol=symbol, days=7
    )
    opinions["fundamental"] = news_txt[:300]

    if "unavailable" in news_txt.lower():
        sent_txt = f"{symbol} sentiment skipped (news unavailable)"
        if "score_sentiment" not in tool_calls:
            tool_calls.append("score_sentiment")
    else:
        sent_txt = _safe_invoke_tool(
            "score_sentiment", tool_calls, symbol=symbol, headlines=news_txt
        )
    opinions["sentiment"] = sent_txt[:300]

    weight = _weight_from_features(features_summary)
    if weight == 0.0:
        if "uptrend" in features_summary.lower() or "momentum" in price_txt.lower():
            weight = 0.08
        if "positive" in sent_txt.lower() or "avg=+" in sent_txt:
            weight = min(0.15, weight + 0.05)
        if "negative" in sent_txt.lower() or "avg=-" in sent_txt:
            weight = max(-0.10, weight - 0.05)

    rationale = (
        f"Heuristic synthesis for {symbol}: technical={opinions['technical'][:80]}; "
        f"sentiment={opinions['sentiment'][:80]}"
    )
    raw = {
        "decisions": [
            {
                "symbol": symbol,
                "weight": weight,
                "rationale": rationale,
                "confidence": 0.5,
            }
        ]
    }
    return AgentState(
        symbol=symbol,
        features_summary=features_summary,
        analyst_opinions=opinions,
        final_weight=weight,
        rationale=rationale,
        confidence=0.5,
        tool_calls=tool_calls,
        raw_output=raw,
    )


def _build_llm():
    settings = get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env")
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "temperature": 0,
    }
    if settings.effective_llm_base_url:
        kwargs["base_url"] = settings.effective_llm_base_url
    return ChatOpenAI(**kwargs)


def _parse_moderator_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object in moderator response: {text[:200]}")
    return json.loads(match.group())


def _llm_analyze(symbol: str, features_summary: str = "") -> AgentState:
    llm = _build_llm()
    tools = get_all_tools()
    tool_calls: list[str] = []
    opinions: dict[str, str] = {}

    for role, prompt_tpl in [
        ("fundamental", FUNDAMENTAL_ANALYST),
        ("technical", TECHNICAL_ANALYST),
        ("sentiment", SENTIMENT_ANALYST),
    ]:
        bind_context(agent_role=role)
        prompt = prompt_tpl.format(symbol=symbol)
        if role == "fundamental":
            news = _invoke_tool("get_news_headlines", symbol=symbol)
            tool_calls.append("get_news_headlines")
            prompt += f"\n\nNews context:\n{news}"
        elif role == "technical":
            prices = _invoke_tool("get_price_history", symbol=symbol)
            tool_calls.append("get_price_history")
            prompt += f"\n\nPrice context:\n{prices}\nFeatures: {features_summary}"
        else:
            headlines = _invoke_tool("get_news_headlines", symbol=symbol)
            if "get_news_headlines" not in tool_calls:
                tool_calls.append("get_news_headlines")
            sent = _invoke_tool("score_sentiment", symbol=symbol, headlines=headlines)
            tool_calls.append("score_sentiment")
            prompt += f"\n\nSentiment context:\n{sent}"

        if _LANGGRAPH_AVAILABLE:
            resp = llm.invoke([SystemMessage(content=prompt)])
            opinions[role] = str(resp.content)
        else:
            opinions[role] = prompt[:200]

    opinions_text = "\n".join(f"{k}: {v}" for k, v in opinions.items())
    mod_prompt = DEBATE_MODERATOR.format(symbol=symbol, opinions=opinions_text)
    resp = llm.invoke([HumanMessage(content=mod_prompt)])
    parsed = _parse_moderator_json(str(resp.content))
    weight = float(parsed.get("weight", 0.0))
    rationale = str(parsed.get("rationale", ""))
    confidence = float(parsed.get("confidence", 0.5))
    raw = {
        "decisions": [
            {
                "symbol": symbol,
                "weight": weight,
                "rationale": rationale,
                "confidence": confidence,
            }
        ]
    }
    validate_output(raw)
    return AgentState(
        symbol=symbol,
        features_summary=features_summary,
        analyst_opinions=opinions,
        final_weight=weight,
        rationale=rationale,
        confidence=confidence,
        tool_calls=tool_calls,
        raw_output=raw,
    )


def _build_graph():
    if not _LANGGRAPH_AVAILABLE:
        return None

    def fundamental_node(state: AgentState) -> AgentState:
        symbol = state["symbol"]
        calls = list(state.get("tool_calls", []))
        news = _safe_invoke_tool("get_news_headlines", calls, symbol=symbol)
        opinions = dict(state.get("analyst_opinions", {}))
        opinions["fundamental"] = news[:400]
        return {"analyst_opinions": opinions, "tool_calls": calls}

    def technical_node(state: AgentState) -> AgentState:
        symbol = state["symbol"]
        calls = list(state.get("tool_calls", []))
        prices = _safe_invoke_tool("get_price_history", calls, symbol=symbol)
        opinions = dict(state.get("analyst_opinions", {}))
        opinions["technical"] = prices[:400]
        return {"analyst_opinions": opinions, "tool_calls": calls}

    def sentiment_node(state: AgentState) -> AgentState:
        symbol = state["symbol"]
        calls = list(state.get("tool_calls", []))
        headlines = _safe_invoke_tool("get_news_headlines", calls, symbol=symbol)
        if "unavailable" in headlines.lower():
            sent = f"{symbol} sentiment skipped (news unavailable)"
            if "score_sentiment" not in calls:
                calls.append("score_sentiment")
        else:
            sent = _safe_invoke_tool("score_sentiment", calls, symbol=symbol, headlines=headlines)
        opinions = dict(state.get("analyst_opinions", {}))
        opinions["sentiment"] = sent[:400]
        return {"analyst_opinions": opinions, "tool_calls": calls}

    def moderator_node(state: AgentState) -> AgentState:
        symbol = state["symbol"]
        opinions = state.get("analyst_opinions", {})
        opinions_text = "\n".join(f"{k}: {v}" for k, v in opinions.items())
        try:
            llm = _build_llm()
            mod_prompt = DEBATE_MODERATOR.format(symbol=symbol, opinions=opinions_text)
            resp = llm.invoke([HumanMessage(content=mod_prompt)])
            parsed = _parse_moderator_json(str(resp.content))
            weight = float(parsed.get("weight", 0.0))
            rationale = str(parsed.get("rationale", ""))
            confidence = float(parsed.get("confidence", 0.5))
        except Exception as exc:
            _log.warning("moderator LLM failed (%s), using heuristic weight", exc)
            weight, rationale, confidence = 0.05, f"fallback: {opinions_text[:120]}", 0.3

        raw = {
            "decisions": [
                {
                    "symbol": symbol,
                    "weight": weight,
                    "rationale": rationale,
                    "confidence": confidence,
                }
            ]
        }
        try:
            validate_output(raw)
        except Exception as exc:
            _log.warning("output validation failed (%s), flattening to zero", exc)
            weight, rationale, confidence = 0.0, str(exc), 0.0
            raw["decisions"][0].update({"weight": 0.0, "rationale": rationale, "confidence": 0.0})

        return {
            "final_weight": weight,
            "rationale": rationale,
            "confidence": confidence,
            "raw_output": raw,
        }

    graph = StateGraph(AgentState)
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("technical", technical_node)
    graph.add_node("sentiment", sentiment_node)
    graph.add_node("moderator", moderator_node)
    graph.add_edge(START, "fundamental")
    graph.add_edge("fundamental", "technical")
    graph.add_edge("technical", "sentiment")
    graph.add_edge("sentiment", "moderator")
    graph.add_edge("moderator", END)
    return graph.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_graph()
    return _GRAPH


def analyze_symbol(
    symbol: str,
    features_summary: str = "",
    *,
    use_llm: bool | None = None,
    offline: bool = False,
) -> AgentState:
    """Run the analyst/debate pipeline for one symbol."""
    bind_context(symbol=symbol.upper(), agent_role="graph")
    settings = get_settings()
    llm_requested = use_llm if use_llm is not None else bool(settings.llm_api_key)

    if offline or (
        not llm_requested
        and features_summary
        and features_summary != "no features"
    ):
        return _heuristic_offline(symbol.upper(), features_summary)

    if llm_requested and _LANGGRAPH_AVAILABLE and settings.llm_api_key:
        graph = get_graph()
        if graph is not None:
            return graph.invoke(
                {
                    "symbol": symbol.upper(),
                    "features_summary": features_summary,
                    "tool_calls": [],
                    "analyst_opinions": {},
                }
            )

    if llm_requested and settings.llm_api_key:
        try:
            return _llm_analyze(symbol.upper(), features_summary)
        except Exception as exc:
            _log.warning("LLM analyze failed (%s), falling back to heuristic", exc)

    return _heuristic_analyze(symbol.upper(), features_summary)


def run_single_symbol_eval(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Eval runner entry point: analyze one scenario and return output + tool calls."""
    symbol = scenario["symbol"]
    state = analyze_symbol(symbol, use_llm=False)
    raw = state.get("raw_output") or {
        "decisions": [
            {
                "symbol": symbol,
                "weight": state.get("final_weight", 0.0),
                "rationale": state.get("rationale", ""),
                "confidence": state.get("confidence", 0.5),
            }
        ]
    }
    return raw, list(state.get("tool_calls", []))


def state_to_agent_output(state: AgentState) -> AgentOutput:
    raw = state.get("raw_output")
    if raw:
        return validate_output(raw)
    return validate_output(
        {
            "decisions": [
                {
                    "symbol": state["symbol"],
                    "weight": state.get("final_weight", 0.0),
                    "rationale": state.get("rationale", "no rationale"),
                    "confidence": state.get("confidence", 0.5),
                }
            ]
        }
    )
