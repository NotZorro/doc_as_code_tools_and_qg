from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml


ValidatorKind = Literal["section", "document"]
ValidatorInput = Literal["section_text", "doc_text"]


@dataclass(frozen=True)
class LLMOverride:
    """Per-validator LLM overrides.

    Useful when different checks have different cost/quality requirements.
    Env overrides (LLM_MODEL, etc.) still have higher priority.
    """

    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class ValidatorSpec:
    """Policy-defined LLM validator spec.

    A spec is loaded from a folder:
      validators/<id>/validator.yaml
      validators/<id>/schema.json
      validators/<id>/prompt.system.tmpl
      validators/<id>/prompt.user.tmpl
    """

    id: str
    kind: ValidatorKind
    input: ValidatorInput
    schema: dict[str, Any]
    system_prompt: str
    user_prompt: str
    max_retries: int = 2
    anti_cjk_repair: bool = True
    llm: LLMOverride = LLMOverride()


class ValidatorRegistry:
    def __init__(self, specs: dict[str, ValidatorSpec]):
        self._specs = dict(specs)

    def get(self, vid: str) -> ValidatorSpec | None:
        return self._specs.get(vid)

    def require(self, vid: str) -> ValidatorSpec:
        spec = self.get(vid)
        if spec is None:
            raise KeyError(f"Validator '{vid}' not found in validators-dir.")
        return spec

    def ids(self) -> list[str]:
        return sorted(self._specs.keys())


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_validators(validators_dir: Path) -> ValidatorRegistry:
    """Load validators from policy folder.

    Directory layout:
      <validators_dir>/<validator_id>/validator.yaml
      <validators_dir>/<validator_id>/schema.json
      <validators_dir>/<validator_id>/prompt.system.tmpl
      <validators_dir>/<validator_id>/prompt.user.tmpl
    """

    specs: dict[str, ValidatorSpec] = {}
    if not validators_dir.exists():
        return ValidatorRegistry(specs)

    for vdir in sorted([p for p in validators_dir.iterdir() if p.is_dir()]):
        vmeta = vdir / "validator.yaml"
        if not vmeta.exists():
            continue

        raw = yaml.safe_load(_read_text(vmeta)) or {}
        if not isinstance(raw, dict):
            continue

        vid = str(raw.get("id") or vdir.name).strip()
        kind = str(raw.get("kind") or "section").strip()
        input_ = str(raw.get("input") or ("section_text" if kind == "section" else "doc_text")).strip()

        if kind not in ("section", "document"):
            raise ValueError(f"Invalid validator.kind for {vid}: {kind}")
        if input_ not in ("section_text", "doc_text"):
            raise ValueError(f"Invalid validator.input for {vid}: {input_}")

        schema_path = vdir / str(raw.get("schema") or "schema.json")
        system_path = vdir / (raw.get("prompts", {}) or {}).get("system", "prompt.system.tmpl")
        user_path = vdir / (raw.get("prompts", {}) or {}).get("user", "prompt.user.tmpl")

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found for validator {vid}: {schema_path}")
        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found for validator {vid}: {system_path}")
        if not user_path.exists():
            raise FileNotFoundError(f"User prompt not found for validator {vid}: {user_path}")

        schema = json.loads(_read_text(schema_path))
        if not isinstance(schema, dict):
            raise ValueError(f"Schema for {vid} must be a JSON object")

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
        )

        spec = ValidatorSpec(
            id=vid,
            kind=kind,  # type: ignore[arg-type]
            input=input_,  # type: ignore[arg-type]
            schema=schema,
            system_prompt=_read_text(system_path),
            user_prompt=_read_text(user_path),
            max_retries=int(out_cfg.get("max_retries", 2)),
            anti_cjk_repair=bool(out_cfg.get("anti_cjk_repair", True)),
            llm=llm_override,
        )

        specs[vid] = spec

    return ValidatorRegistry(specs)
