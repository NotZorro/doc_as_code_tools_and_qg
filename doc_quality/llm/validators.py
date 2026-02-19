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


def make_llm_client(cfg: EngineConfig) -> tuple[OpenAICompatClient | None, str | None, str | None]:
    """Returns (client, model, error). api_key only from env LLMOPS_API_KEY."""
    api_key = env("LLMOPS_API_KEY")
    if not api_key:
        return None, None, "LLMOPS_API_KEY is not set (LLM is disabled)."

    llm_cfg = resolve_llm_settings(cfg.llm)
    client = OpenAICompatClient(base_url=llm_cfg.base_url, api_key=api_key, timeout_s=llm_cfg.timeout_s)
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
        model=model,
        messages=messages,
        schema=spec.schema,
        temperature=cfg.llm.temperature,
        max_tokens=cfg.llm.max_tokens,
        retries=spec.max_retries,
    )

    return LLMRunResult(spec.id, obj, err, (raw or "")[:900])
