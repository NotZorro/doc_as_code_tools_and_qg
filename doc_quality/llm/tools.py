from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from jsonschema import validate as jsonschema_validate

from ..config import EngineConfig, render_prompt
from ..tools import ToolSpec
from .client import OpenAICompatClient
from .json_mode import llm_json


@dataclass
class ToolRunResult:
    tool: str
    result: dict[str, Any] | None
    error: str | None
    raw_head: str | None


def run_tool(
    *,
    cfg: EngineConfig,
    client: OpenAICompatClient,
    model: str,
    spec: ToolSpec,
    tool_input: dict[str, Any] | None,
    section_text: str = "",
    doc_text: str = "",
    section_title: str = "",
    doc_meta_json: str = "{}",
    doc_type: str = "",
    template_id: str = "",
    docs_pack_json: str = "[]",
    docs_pack_text: str = "",
) -> ToolRunResult:
    """Run a policy-defined tool. CORE does not know tool internals."""

    tool_input = tool_input or {}
    if spec.input_schema is not None:
        # throws jsonschema.ValidationError (handled by CLI)
        jsonschema_validate(instance=tool_input, schema=spec.input_schema)

    block = {"system": spec.system_prompt, "user": spec.user_prompt}
    out_schema_str = json.dumps(spec.output_schema, ensure_ascii=False)
    in_json_str = json.dumps(tool_input, ensure_ascii=False)

    messages = render_prompt(
        block,
        schema=out_schema_str,
        tool_input=in_json_str,
        section_text=section_text,
        doc_text=doc_text,
        section_title=section_title,
        doc_meta=doc_meta_json,
        doc_type=doc_type,
        template_id=template_id,
        docs_pack=docs_pack_text,
        docs_pack_json=docs_pack_json,
    )

    obj, raw, err = llm_json(
        client=client,
        model=model,
        messages=messages,
        schema=spec.output_schema,
        temperature=cfg.llm.temperature,
        max_tokens=cfg.llm.max_tokens,
        retries=spec.max_retries,
    )

    return ToolRunResult(spec.id, obj, err, (raw or "")[:900])
