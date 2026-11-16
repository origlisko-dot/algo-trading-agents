"""Tests for LLM provider resolution (OpenRouter / NVIDIA NIM / OpenAI)."""
from __future__ import annotations

import pytest

from algo_agents.config import Settings


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_openai_only_uses_default_base_url(monkeypatch: pytest.MonkeyPatch):
    s = _settings(monkeypatch, OPENAI_API_KEY="sk-test")
    assert s.llm_api_key == "sk-test"
    assert s.effective_llm_base_url is None


def test_openrouter_takes_precedence(monkeypatch: pytest.MonkeyPatch):
    s = _settings(monkeypatch, OPENROUTER_API_KEY="or-test", NVIDIA_API_KEY="nv-test", OPENAI_API_KEY="sk-test")
    assert s.llm_api_key == "or-test"
    assert s.effective_llm_base_url == "https://openrouter.ai/api/v1"


def test_nvidia_nim_base_url(monkeypatch: pytest.MonkeyPatch):
    s = _settings(monkeypatch, NVIDIA_API_KEY="nv-test", OPENAI_API_KEY="sk-test")
    assert s.llm_api_key == "nv-test"
    assert s.effective_llm_base_url == "https://integrate.api.nvidia.com/v1"


def test_explicit_base_url_wins(monkeypatch: pytest.MonkeyPatch):
    s = _settings(monkeypatch, NVIDIA_API_KEY="nv-test", LLM_BASE_URL="http://localhost:8000/v1")
    assert s.effective_llm_base_url == "http://localhost:8000/v1"
