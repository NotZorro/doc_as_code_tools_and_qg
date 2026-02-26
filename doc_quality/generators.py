from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


GeneratorKind = Literal["document", "bundle"]
GeneratorInput = Literal["doc_text", "bundle_json"]


@dataclass(frozen=True)
class LLMOverride:
    """Per-generator LLM overrides."""

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    base_url: str | None = None
    timeout_s: float | None = None


@dataclass(frozen=True)
class GeneratorSpec:
    """Policy-defined LLM generator spec.

    Layout:
      <generators_dir>/<generator_id>/generator.yaml
      <generators_dir>/<generator_id>/schema.json
      <generators_dir>/<generator_id>/prompt.system.tmpl
      <generators_dir>/<generator_id>/prompt.user.tmpl
    """

    id: str
    kind: GeneratorKind
    input: GeneratorInput
    schema: dict[str, Any]
    system_prompt: str
    user_prompt: str
    max_retries: int = 2
    anti_cjk_repair: bool = True
    llm: LLMOverride = LLMOverride()


class GeneratorRegistry:
    def __init__(self, specs: dict[str, GeneratorSpec]):
        self._specs = dict(specs)

    def get(self, gid: str) -> GeneratorSpec | None:
        return self._specs.get(gid)

    def require(self, gid: str) -> GeneratorSpec:
        spec = self.get(gid)
        if spec is None:
            raise KeyError(f"Generator '{gid}' not found in generators-dir.")
        return spec

    def ids(self) -> list[str]:
        return sorted(self._specs.keys())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_generators(generators_dir: Path) -> GeneratorRegistry:
    specs: dict[str, GeneratorSpec] = {}
    if not generators_dir.exists():
        return GeneratorRegistry(specs)

    for gdir in sorted([p for p in generators_dir.iterdir() if p.is_dir()]):
        gmeta = gdir / "generator.yaml"
        if not gmeta.exists():
            continue

        raw = yaml.safe_load(_read_text(gmeta)) or {}
        if not isinstance(raw, dict):
            continue

        gid = str(raw.get("id") or gdir.name).strip()
        kind = str(raw.get("kind") or "document").strip()
        input_ = str(raw.get("input") or ("doc_text" if kind == "document" else "bundle_json")).strip()

        if kind not in ("document", "bundle"):
            raise ValueError(f"Invalid generator.kind for {gid}: {kind}")
        if input_ not in ("doc_text", "bundle_json"):
            raise ValueError(f"Invalid generator.input for {gid}: {input_}")

        schema_path = gdir / str(raw.get("schema") or "schema.json")
        system_path = gdir / (raw.get("prompts", {}) or {}).get("system", "prompt.system.tmpl")
        user_path = gdir / (raw.get("prompts", {}) or {}).get("user", "prompt.user.tmpl")

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found for generator {gid}: {schema_path}")
        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found for generator {gid}: {system_path}")
        if not user_path.exists():
            raise FileNotFoundError(f"User prompt not found for generator {gid}: {user_path}")

        schema = json.loads(_read_text(schema_path))
        if not isinstance(schema, dict):
            raise ValueError(f"Schema for {gid} must be a JSON object")

        out_cfg = raw.get("output") or {}
        if not isinstance(out_cfg, dict):
            out_cfg = {}

        llm_cfg = raw.get("llm") or {}
        if not isinstance(llm_cfg, dict):
            llm_cfg = {}

        llm_override = LLMOverride(
            model=(str(llm_cfg.get("model")).strip() if llm_cfg.get("model") else None),
            temperature=(float(llm_cfg.get("temperature")) if llm_cfg.get("temperature") is not None else None),
            max_tokens=(int(llm_cfg.get("max_tokens")) if llm_cfg.get("max_tokens") is not None else None),
            base_url=(str(llm_cfg.get("base_url")).strip() if llm_cfg.get("base_url") else None),
            timeout_s=(float(llm_cfg.get("timeout_s")) if llm_cfg.get("timeout_s") is not None else None),
        )

        spec = GeneratorSpec(
            id=gid,
            kind=kind,  # type: ignore[arg-type]
            input=input_,  # type: ignore[arg-type]
            schema=schema,
            system_prompt=_read_text(system_path),
            user_prompt=_read_text(user_path),
            max_retries=int(out_cfg.get("max_retries", 2)),
            anti_cjk_repair=bool(out_cfg.get("anti_cjk_repair", True)),
            llm=llm_override,
        )

        specs[gid] = spec

    return GeneratorRegistry(specs)
