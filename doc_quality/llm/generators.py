from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..config import EngineConfig, render_prompt
from ..util import env
from ..generators import GeneratorSpec
from .client import OpenAICompatClient
from .json_mode import llm_json


@dataclass
class LLMGenerateResult:
    generator: str
    result: dict[str, Any] | None
    error: str | None
    raw_head: str | None


def _effective_model(cfg: EngineConfig, base_model: str, spec: GeneratorSpec) -> tuple[str, str | None]:
    eff = env("LLM_MODEL") or spec.llm.model or base_model
    if cfg.llm.allowed_models and eff not in cfg.llm.allowed_models:
        return eff, f"Model '{eff}' is not allowed by policy (allowed_models)."
    return eff, None


def run_generator(
    *,
    cfg: EngineConfig,
    client: OpenAICompatClient,
    base_model: str,
    spec: GeneratorSpec,
    doc_text: str,
    doc_meta_json: str = "{}",
    doc_type: str = "",
    template_id: str = "",
    bundle_json: str = "{}",
    options_json: str = "{}",
    feature_summary: str = "",
) -> LLMGenerateResult:
    """Run a policy-defined generator."""

    model, err = _effective_model(cfg, base_model, spec)
    if err:
        return LLMGenerateResult(spec.id, None, err, None)

    temperature = spec.llm.temperature if spec.llm.temperature is not None else cfg.llm.temperature
    max_tokens = spec.llm.max_tokens if spec.llm.max_tokens is not None else cfg.llm.max_tokens

    block = {"system": spec.system_prompt, "user": spec.user_prompt}
    schema_str = json.dumps(spec.schema, ensure_ascii=False)

    messages = render_prompt(
        block,
        schema=schema_str,
        doc_text=doc_text,
        doc_meta=doc_meta_json,
        doc_type=doc_type,
        template_id=template_id,
        bundle=bundle_json,
        options=options_json,
        feature_summary=feature_summary,
    )

    obj, raw, e = llm_json(
        client=client,
        model=model,
        messages=messages,
        schema=spec.schema,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=spec.max_retries,
    )

    return LLMGenerateResult(spec.id, obj, e, (raw or "")[:900])
