from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .markdown import norm_heading


@dataclass(frozen=True)
class TemplateSelectInfo:
    doc_type: str
    template_id: str
    mode: str
    score: int


def load_templates(templates_dir: Path) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    if not templates_dir.exists():
        return templates
    for p in sorted(templates_dir.glob("*.y*ml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        dt = data.get("doc_type")
        tid = data.get("id")
        if not dt or not tid:
            continue
        templates[str(dt)] = data
    return templates


def auto_detect_doc_type(meta: dict[str, Any], headings: list[Any], templates: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], TemplateSelectInfo] | tuple[None, None]:
    if not templates:
        return None, None

    # 1) Explicit doc_type
    dt = meta.get("doc_type")
    if dt and str(dt) in templates:
        t = templates[str(dt)]
        return t, TemplateSelectInfo(doc_type=str(dt), template_id=str(t.get("id")), mode="from_frontmatter", score=10**6)

    # 2) Score templates by matching section titles
    doc_titles = {norm_heading(h.title) for h in headings if getattr(h, "title", None)}

    best_t = None
    best = TemplateSelectInfo(doc_type="", template_id="", mode="auto_detect", score=-1)

    for dt_key, t in templates.items():
        score = 0
        required_hits = 0
        for sec in t.get("sections", []) or []:
            titles = sec.get("titles") or []
            hit = any(norm_heading(x) in doc_titles for x in titles)
            if hit:
                score += 2
                if sec.get("required", False):
                    required_hits += 1
            else:
                if sec.get("required", False):
                    score -= 1
        score += required_hits * 3
        if score > best.score:
            best_t = t
            best = TemplateSelectInfo(doc_type=str(dt_key), template_id=str(t.get("id")), mode="auto_detect", score=score)

    if best_t is None:
        # fallback: first template in order
        dt_key = next(iter(templates.keys()))
        t = templates[dt_key]
        return t, TemplateSelectInfo(doc_type=str(dt_key), template_id=str(t.get("id")), mode="fallback_first", score=0)

    return best_t, best
