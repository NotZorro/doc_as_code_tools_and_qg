from __future__ import annotations

import re
from typing import Any


def issue(severity: str, code: str, message: str, section: str, line: int | None = None) -> dict[str, Any]:
    out = {"severity": severity, "code": code, "message": message, "section": section}
    if line is not None:
        out["line"] = line
    return out


def check_meta(meta: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required = (template.get("meta", {}) or {}).get("required", []) or []
    for k in required:
        if not meta.get(k):
            issues.append(issue("blocker", "META_MISSING", f"Нет обязательного метаполя: {k}", "frontmatter"))
    return issues


def apply_section_rules(section_key: str, text: str, rules: dict[str, Any], start_line: int | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    txt = (text or "").strip()

    min_chars = rules.get("min_chars")
    if min_chars is not None:
        min_chars = int(min_chars)
        if len(txt) < min_chars:
            sev = "warning" if len(txt) > 0 else "blocker"
            issues.append(issue(sev, "SECTION_TOO_SHORT", f"Раздел слишком короткий: {len(txt)} < {min_chars}", section_key, start_line))

    for patt in (rules.get("forbid_regex") or []) or []:
        if patt and re.search(str(patt), txt):
            issues.append(issue("warning", "FORBIDDEN_PATTERN", f"Найден анти-паттерн по regex: {patt}", section_key, start_line))

    must_any = (rules.get("must_have_any_regex") or []) or []
    if must_any:
        ok = any(re.search(str(patt), txt) for patt in must_any if patt)
        if not ok:
            issues.append(issue("warning", "MISSING_SIGNAL", "Не найден ни один ожидаемый сигнал (must_have_any_regex).", section_key, start_line))

    return issues


def check_order(template: dict[str, Any], matches: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    ordered = sorted(template.get("sections", []) or [], key=lambda s: s.get("order", 10**9))
    seen = []
    for s in ordered:
        key = s.get("key")
        if key in matches:
            seen.append((s.get("order", 10**9), matches[key].get("start_line"), key))

    start_lines = [x[1] for x in seen if x[1] is not None]
    if start_lines and start_lines != sorted(start_lines):
        issues.append(issue("warning", "ORDER_SUSPECT", "Порядок секций подозрительный: секции идут не по шаблону.", "structure"))
    return issues
