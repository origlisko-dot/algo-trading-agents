# Cursor Cloud Environment — secrets checklist

Add these in [Cloud Agents → Secrets](https://cursor.com/dashboard/cloud-agents) (environment-scoped preferred).  
`Settings` already reads process env vars; a committed `.env` is not required in the cloud VM.

## Runtime secrets (API keys)

| Name | Notes |
|------|--------|
| `OPENROUTER_API_KEY` | Recommended LLM path (`LLM_MODEL=openai/gpt-4o-mini`) |
| `OPENAI_API_KEY` | Optional if not using OpenRouter |
| `LANGSMITH_API_KEY` | Optional tracing |
| `POLYGON_API_KEY` | Market data / universe |
| `FINNHUB_API_KEY` | Market data / universe |
| `FMP_API_KEY` | Optional; 403s are non-blocking |
| `NEWSAPI_KEY` | Optional news |
| `ALPACA_API_KEY` | Optional; paper can use simulated broker |
| `ALPACA_SECRET_KEY` | Optional |
| `HF_TOKEN` | Optional for gated HF models |

## Safe non-secret env vars (optional overrides)

| Name | Suggested |
|------|-----------|
| `TRADING_PAPER` | `true` |
| `PAPER_BROKER` | `simulated` |
| `TRADING_UNIVERSE` | `*` |
| `TRADING_UNIVERSE_MAX` | `50` |
| `LLM_MODEL` | `openai/gpt-4o-mini` |
| `LANGSMITH_PROJECT` | `algo-trading-agents` |
| `LANGCHAIN_TRACING_V2` | `true` |
| `EDGAR_USER_AGENT` | `algo-trading-agents you@example.com` |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` |

## Setup steps

1. Open [Environments](https://cursor.com/dashboard/cloud-agents#environments) → create environment for `origlisko-dot/algo-trading-agents`.
2. Paste secrets from this checklist (copy values from your local `.env`; never commit them).
3. Run agent-driven setup (or rely on `.cursor/environment.json` `install`).
4. Save a snapshot when `pip install` + `python scripts/check_connections.py` look healthy.
5. Future agents: pick this environment in the dropdown.
