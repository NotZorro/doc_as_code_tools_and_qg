from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml
from markdown_it import MarkdownIt


md_parser = MarkdownIt()


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", flags=re.DOTALL)

# Убираем префикс-нумерацию заголовка:
# примеры:
# "1 Контекст", "1. Контекст", "1.2 Контекст", "1.2.3. Контекст"
# "1) Контекст", "1 - Контекст", "1: Контекст"
_HEADING_NUM_PREFIX = re.compile(
    r"""^\s*
        (?:\d+(?:\.\d+)*)   # 1 или 1.2 или 1.2.3
        \.?\s*               # опциональная точка и пробелы
        (?:[\)\:\-–—]\s*)?  # опционально: ) : - – —
    """,
    re.VERBOSE,
)


def split_frontmatter(md_text: str) -> tuple[dict[str, Any], str]:
    """Если файл начинается с YAML frontmatter --- ... ---, вернём (meta, body)."""
    if not (md_text or "").lstrip().startswith("---"):
        return {}, md_text
    m = _FRONTMATTER_RE.match(md_text.lstrip())
    if not m:
        return {}, md_text
    meta_raw, body = m.group(1), m.group(2)
    meta = yaml.safe_load(meta_raw) or {}
    if not isinstance(meta, dict):
        meta = {}
    # позволяем двум стилям:
    # 1) поля на верхнем уровне
    # 2) вложенный блок meta:
    if isinstance(meta.get("meta"), dict):
        merged = dict(meta["meta"])
        for k, v in meta.items():
            if k == "meta":
                continue
            merged[k] = v
        meta = merged
    return meta, body


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def norm_heading(title: str) -> str:
    t = (title or "").strip()
    t = _HEADING_NUM_PREFIX.sub("", t).strip()
    return norm_text(t)


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    start_line: int | None
    end_line: int | None


def extract_headings(md: str) -> list[Heading]:
    tokens = md_parser.parse(md)
    headings: list[Heading] = []
    for i, t in enumerate(tokens):
        if t.type == "heading_open":
            level = int(t.tag[1])
            title = tokens[i + 1].content.strip() if i + 1 < len(tokens) else ""
            start_line = t.map[0] if t.map else None
            end_line = t.map[1] if t.map else None
            headings.append(Heading(level=level, title=title, start_line=start_line, end_line=end_line))
    return headings


def build_sections(md: str) -> tuple[list[Heading], dict[str, list[dict[str, Any]]]]:
    """
    Возвращает:
      - headings: список заголовков с линиями
      - sections_by_title_norm: dict {normalized_title: [ {title,start_line,text}, ... ] }
    """
    lines = md.splitlines()
    headings = extract_headings(md)
    sections: dict[str, list[dict[str, Any]]] = {}
    for idx, h in enumerate(headings):
        title_n = norm_heading(h.title)
        start = h.end_line if h.end_line is not None else ((h.start_line + 1) if h.start_line is not None else 0)
        # IMPORTANT: section extent is until the next heading of the SAME or HIGHER level.
        # Example: for H2 we include all nested H3/H4/... content until next H2 (or H1).
        next_start = len(lines)
        for j in range(idx + 1, len(headings)):
            hj = headings[j]
            if hj.start_line is None:
                continue
            if hj.level <= h.level:
                next_start = hj.start_line
                break
        text = "\n".join(lines[start:next_start]).strip()
        sections.setdefault(title_n, []).append(
            {"title": h.title, "start_line": h.start_line, "text": text}
        )
    # стабилизируем: ранние секции первыми
    for k in list(sections.keys()):
        sections[k] = sorted(sections[k], key=lambda x: (x.get("start_line") is None, x.get("start_line") or 10**9))
    return headings, sections
