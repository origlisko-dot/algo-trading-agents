"""Central configuration, loaded once from environment / .env.

All credentials are optional so the project runs (in degraded mode) before
any keys are supplied. Access via `from algo_agents.config import get_settings`.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Global guardrails ----
    trading_paper: bool = True
    paper_broker: str = "simulated"
    paper_starting_cash: float = 100_000.0
    paper_state_path: str = "./runs/paper_account.json"
    # Default: full US universe with a capped daily scan (see TRADING_UNIVERSE_MAX).
    trading_universe: str = "*"
    trading_universe_max: int = 50
    universe_cache_path: str = "./runs/universe_us.json"
    universe_cache_hours: float = 24.0
    runs_dir: str = "./runs"
    default_strategy: str = "auto"
    eval_gate_enabled: bool = True
    monitor_after_paper: bool = True
    auto_promote_strategy: bool = True
    promotion_compare_all: bool = True
    # Monitor universe: prefer daily_watchlist.json, then cap symbol count.
    monitor_max_symbols: int = 10
    # Shadow ladder: prefer shadow PnL over backtest Sharpe once each book has N snaps.
    shadow_min_snapshots: int = 3
    agentic_schedule_enabled: bool = False
    agentic_schedule_hour: int = 21
    agentic_schedule_minute: int = 30
    agentic_schedule_tz: str = "America/New_York"
    agentic_schedule_weekdays: str = "mon-fri"
    agentic_schedule_poll_seconds: int = 60
    log_level: str = "INFO"

    # ---- Alpaca ----
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ---- Interactive Brokers ----
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1

    # ---- Market data ----
    polygon_api_key: str | None = None
    finnhub_api_key: str | None = None
    fmp_api_key: str | None = None

    # ---- News ----
    newsapi_key: str | None = None
    edgar_user_agent: str = "algo-trading-agents you@example.com"

    # ---- Hugging Face ----
    hf_token: str | None = None
    finbert_model: str = "ProsusAI/finbert"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ---- Memory ----
    chroma_persist_dir: str = "./chroma_db"

    # ---- LLM / LangSmith ----
    langsmith_api_key: str | None = None
    langsmith_project: str = "algo-trading-agents"
    langchain_tracing_v2: bool = True
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    nvidia_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str = "openai/gpt-4o-mini"
    # Optional cheaper/faster model for analyst data-summarization calls;
    # falls back to llm_model when unset.
    llm_fast_model: str | None = None

    @property
    def llm_api_key(self) -> str | None:
        """OpenRouter takes precedence, then NVIDIA NIM, then OpenAI."""
        return self.openrouter_api_key or self.nvidia_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str | None:
        if self.llm_base_url:
            return self.llm_base_url
        if self.openrouter_api_key:
            return "https://openrouter.ai/api/v1"
        if self.nvidia_api_key:
            return "https://integrate.api.nvidia.com/v1"
        return None

    @property
    def universe_unrestricted(self) -> bool:
        from algo_agents.universe.symbols import is_unrestricted_universe

        return is_unrestricted_universe(self.trading_universe)

    @property
    def universe(self) -> list[str]:
        """Explicit ticker list. Empty when TRADING_UNIVERSE=* (all US equities allowed)."""
        if self.universe_unrestricted:
            return []
        return [s.strip().upper() for s in self.trading_universe.split(",") if s.strip()]

    @property
    def is_live(self) -> bool:
        return not self.trading_paper


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
