#!/usr/bin/env bash
# Idempotent bootstrap for Cursor Cloud Agents and fresh clones.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[bootstrap] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -e .

clone_if_missing() {
  local dir="$1"
  local url="$2"
  if [[ -d "$dir/.git" ]]; then
    echo "[bootstrap] $dir already present — skipping clone"
    return 0
  fi
  echo "[bootstrap] Cloning $url -> $dir"
  git clone --depth 1 "$url" "$dir"
}

clone_if_missing "graphify" "https://github.com/Graphify-Labs/graphify.git"
clone_if_missing "craft-agents-oss" "https://github.com/craft-ai-agents/craft-agents-oss.git"

if [[ -d graphify ]]; then
  echo "[bootstrap] Installing Graphify (editable)..."
  python3 -m pip install -e graphify || true
  if command -v graphify >/dev/null 2>&1; then
    echo "[bootstrap] Building codebase knowledge graph..."
    graphify update algo_agents || true
  fi
fi

if [[ -d craft-agents-oss ]] && command -v bun >/dev/null 2>&1; then
  echo "[bootstrap] Installing Craft Agents OSS dependencies..."
  (cd craft-agents-oss && bun install) || true
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[bootstrap] Created .env from .env.example (fill secrets locally as needed)"
fi

echo "[bootstrap] Running health check..."
python3 scripts/run_agentic_os.py job health || true

echo "[bootstrap] Cloud bootstrap complete."
