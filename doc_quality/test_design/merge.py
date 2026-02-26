from __future__ import annotations

import re
from typing import Any


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "group"


def _prefix(group: str) -> str:
    g = _slug(group).upper()
    g = g[:12]
    return g or "GROUP"


def _as_list(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    return []


def _merge_text_lists(fragments: list[dict[str, Any]], key: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for fr in fragments:
        for x in _as_list(fr.get(key)):
            if not isinstance(x, str):
                continue
            t = x.strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
    return out


def _dedup_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in scenarios:
        title = str(s.get("title") or "").strip().lower()
        steps = "|".join([str(x).strip().lower() for x in _as_list(s.get("steps"))])
        key = f"{title}::{steps[:200]}"
        if not title and not steps:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def merge_group_fragments(
    *,
    group: str,
    feature: dict[str, Any],
    source_docs: list[dict[str, Any]],
    fragments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge multiple suite fragments into one suite per group."""

    scenarios: list[dict[str, Any]] = []
    for fr in fragments:
        for s in _as_list(fr.get("scenarios")):
            if isinstance(s, dict):
                scenarios.append(dict(s))

    scenarios = _dedup_scenarios(scenarios)

    # Renumber ids to a stable scheme TC-<GROUP>-NNN
    pref = _prefix(group)
    for i, s in enumerate(scenarios, start=1):
        old = s.get("id")
        s["id"] = f"TC-{pref}-{i:03d}"
        if old and old != s["id"]:
            s.setdefault("notes", "")
            if isinstance(s["notes"], str):
                if s["notes"].strip():
                    s["notes"] += "\n"
                s["notes"] += f"original_id: {old}"

    suite: dict[str, Any] = {
        "feature": feature,
        "group": group,
        "source_docs": source_docs,
        "scenarios": scenarios,
        "assumptions": _merge_text_lists(fragments, "assumptions"),
        "open_questions": _merge_text_lists(fragments, "open_questions"),
    }

    # Keep scope if any fragment provides it.
    for fr in fragments:
        sc = fr.get("scope")
        if isinstance(sc, dict):
            suite["scope"] = sc
            break

    return suite
