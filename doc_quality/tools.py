from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


ToolKind = Literal["section", "document", "bundle"]


@dataclass(frozen=True)
class ToolSpec:
    """Policy-defined LLM tool spec.

    A spec is loaded from a folder:
      tools/<id>/tool.yaml
      tools/<id>/input.schema.json   (optional)
      tools/<id>/output.schema.json
      tools/<id>/prompt.system.tmpl
      tools/<id>/prompt.user.tmpl
    """

    id: str
    kind: ToolKind
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any]
    system_prompt: str
    user_prompt: str
    max_retries: int = 2
    anti_cjk_repair: bool = True


class ToolRegistry:
    def __init__(self, specs: dict[str, ToolSpec]):
        self._specs = dict(specs)

    def get(self, tid: str) -> ToolSpec | None:
        return self._specs.get(tid)

    def require(self, tid: str) -> ToolSpec:
        spec = self.get(tid)
        if spec is None:
            raise KeyError(f"Tool '{tid}' not found in tools-dir.")
        return spec

    def ids(self) -> list[str]:
        return sorted(self._specs.keys())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_tools(tools_dir: Path) -> ToolRegistry:
    """Load tools from policy folder.

    Directory layout:
      <tools_dir>/<tool_id>/tool.yaml
      <tools_dir>/<tool_id>/input.schema.json   (optional)
      <tools_dir>/<tool_id>/output.schema.json
      <tools_dir>/<tool_id>/prompt.system.tmpl
      <tools_dir>/<tool_id>/prompt.user.tmpl
    """

    specs: dict[str, ToolSpec] = {}
    if not tools_dir.exists():
        return ToolRegistry(specs)

    for tdir in sorted([p for p in tools_dir.iterdir() if p.is_dir()]):
        tmeta = tdir / "tool.yaml"
        if not tmeta.exists():
            continue

        raw = yaml.safe_load(_read_text(tmeta)) or {}
        if not isinstance(raw, dict):
            continue

        tid = str(raw.get("id") or tdir.name).strip()
        kind = str(raw.get("kind") or "document").strip()
        if kind not in ("section", "document", "bundle"):
            raise ValueError(f"Invalid tool.kind for {tid}: {kind}")

        in_path = tdir / str(raw.get("input_schema") or "input.schema.json")
        out_path = tdir / str(raw.get("output_schema") or "output.schema.json")
        system_path = tdir / (raw.get("prompts", {}) or {}).get("system", "prompt.system.tmpl")
        user_path = tdir / (raw.get("prompts", {}) or {}).get("user", "prompt.user.tmpl")

        input_schema: dict[str, Any] | None = None
        if in_path.exists():
            obj = json.loads(_read_text(in_path))
            if obj is not None and not isinstance(obj, dict):
                raise ValueError(f"input.schema for {tid} must be a JSON object")
            input_schema = obj

        if not out_path.exists():
            raise FileNotFoundError(f"Output schema not found for tool {tid}: {out_path}")
        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found for tool {tid}: {system_path}")
        if not user_path.exists():
            raise FileNotFoundError(f"User prompt not found for tool {tid}: {user_path}")

        out_schema = json.loads(_read_text(out_path))
        if not isinstance(out_schema, dict):
            raise ValueError(f"output.schema for {tid} must be a JSON object")

        out_cfg = raw.get("output") or {}
        if not isinstance(out_cfg, dict):
            out_cfg = {}

        specs[tid] = ToolSpec(
            id=tid,
            kind=kind,  # type: ignore[arg-type]
            input_schema=input_schema,
            output_schema=out_schema,
            system_prompt=_read_text(system_path),
            user_prompt=_read_text(user_path),
            max_retries=int(out_cfg.get("max_retries", 2)),
            anti_cjk_repair=bool(out_cfg.get("anti_cjk_repair", True)),
        )

    return ToolRegistry(specs)
