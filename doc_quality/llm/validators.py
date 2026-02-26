from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..config import EngineConfig, render_prompt, resolve_llm_settings
from ..util import env
from ..validators import ValidatorSpec
from .client import OpenAICompatClient
from .json_mode import llm_json


@dataclass
class LLMRunResult:
    validator: str
    result: dict[str, Any] | None
    error: str | None
    raw_head: str | None


def make_llm_client(
    cfg: EngineConfig,
    *,
    override_base_url: str | None = None,
    override_timeout_s: float | None = None,
) -> tuple[OpenAICompatClient | None, str | None, str | None]:
    """Returns (client, base_model, error).

    API key only from env LLMOPS_API_KEY.

    Overrides are useful for generators or special checks that want a different
    gateway/timeout. Env overrides still have the highest priority.
    """

    api_key = env("LLMOPS_API_KEY")
    if not api_key:
        return None, None, "LLMOPS_API_KEY is not set (LLM is disabled)."

    llm_cfg = resolve_llm_settings(cfg.llm)

    base_url = env("LLMOPS_BASE_URL") or (override_base_url or llm_cfg.base_url)
    timeout_s = float(override_timeout_s) if override_timeout_s is not None else llm_cfg.timeout_s

    client = OpenAICompatClient(base_url=base_url, api_key=api_key, timeout_s=timeout_s)
    return client, llm_cfg.model, None


def run_validator(
    *,
    cfg: EngineConfig,
    client: OpenAICompatClient,
    model: str,
    spec: ValidatorSpec,
    section_text: str,
    doc_text: str,
    section_title: str = "",
    doc_meta_json: str = "{}",
    doc_type: str = "",
    template_id: str = "",
) -> LLMRunResult:
    """Run a policy-defined validator. CORE does not know validator internals."""

    # Per-validator overrides. Env still has the highest priority.
    eff_model = env("LLM_MODEL") or spec.llm.model or model
    if cfg.llm.allowed_models and eff_model not in cfg.llm.allowed_models:
        return LLMRunResult(
            spec.id,
            None,
            f"Model '{eff_model}' is not allowed by policy (allowed_models).",
            None,
        )

    temperature = spec.llm.temperature if spec.llm.temperature is not None else cfg.llm.temperature
    max_tokens = spec.llm.max_tokens if spec.llm.max_tokens is not None else cfg.llm.max_tokens

    block = {"system": spec.system_prompt, "user": spec.user_prompt}
    schema_str = json.dumps(spec.schema, ensure_ascii=False)
    messages = render_prompt(
        block,
        schema=schema_str,
        section_text=section_text,
        doc_text=doc_text,
        section_title=section_title,
        doc_meta=doc_meta_json,
        doc_type=doc_type,
        template_id=template_id,
    )

    obj, raw, err = llm_json(
        client=client,
        model=eff_model,
        messages=messages,
        schema=spec.schema,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=spec.max_retries,
    )

    return LLMRunResult(spec.id, obj, err, (raw or "")[:900])
