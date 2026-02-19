from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

import yaml

from .util import env


@dataclass(frozen=True)
class LLMConfig:
    enabled: bool = True
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_s: float = 60.0
    temperature: float = 0.0
    max_tokens: int = 1200
    max_doc_chars: int = 20000
    max_section_chars: int = 8000
    allowed_models: list[str] | None = None  # optional allow-list


@dataclass(frozen=True)
class EngineConfig:
    llm: LLMConfig


def load_config(path: Path) -> EngineConfig:
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raw = {}

    llm_raw = raw.get("llm") or {}
    if not isinstance(llm_raw, dict):
        llm_raw = {}

    allowed_models = llm_raw.get("allowed_models")
    if allowed_models is not None and not isinstance(allowed_models, list):
        allowed_models = None

    llm = LLMConfig(
        enabled=bool(llm_raw.get("enabled", True)),
        base_url=str(llm_raw.get("base_url") or LLMConfig.base_url),
        model=str(llm_raw.get("model") or LLMConfig.model),
        timeout_s=float(llm_raw.get("timeout_s", LLMConfig.timeout_s)),
        temperature=float(llm_raw.get("temperature", LLMConfig.temperature)),
        max_tokens=int(llm_raw.get("max_tokens", LLMConfig.max_tokens)),
        max_doc_chars=int(llm_raw.get("max_doc_chars", LLMConfig.max_doc_chars)),
        max_section_chars=int(llm_raw.get("max_section_chars", LLMConfig.max_section_chars)),
        allowed_models=[str(x) for x in allowed_models] if allowed_models else None,
    )

    # Prompts and schemas live in policy validators directory (CUSTOM), not in CORE config.
    return EngineConfig(llm=llm)


def resolve_llm_settings(cfg: LLMConfig) -> LLMConfig:
    """Apply env overrides. Priority:
      - LLMOPS_BASE_URL env overrides cfg.base_url
      - LLM_MODEL env overrides cfg.model
      - API key is ONLY from env LLMOPS_API_KEY (checked elsewhere)
    """
    base_url = env("LLMOPS_BASE_URL", cfg.base_url) or cfg.base_url
    model = env("LLM_MODEL", cfg.model) or cfg.model

    # optional allow-list (policy may want to lock models)
    if cfg.allowed_models and model not in cfg.allowed_models:
        raise ValueError(f"Model '{model}' is not allowed by policy (allowed_models).")

    return LLMConfig(
        enabled=cfg.enabled,
        base_url=base_url,
        model=model,
        timeout_s=cfg.timeout_s,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        max_doc_chars=cfg.max_doc_chars,
        max_section_chars=cfg.max_section_chars,
        allowed_models=cfg.allowed_models,
    )


def render_prompt(block: dict[str, str], **vars: str) -> list[dict[str, str]]:
    """Render prompt via string.Template. Returns OpenAI-style messages."""
    system_t = Template(block.get("system", "")).safe_substitute(**vars)
    user_t = Template(block.get("user", "")).safe_substitute(**vars)

    messages = []
    if system_t.strip():
        messages.append({"role": "system", "content": system_t})
    if user_t.strip():
        messages.append({"role": "user", "content": user_t})
    return messages
