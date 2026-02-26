from __future__ import annotations

from typing import Any


def _as_list(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    return []


def _trace_doc_paths(scenario: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    # Preferred: injected __part_docs
    for p in _as_list(scenario.get("__part_docs")):
        if isinstance(p, str) and p.strip():
            out.add(p.strip())

    # Also parse trace entries
    for t in _as_list(scenario.get("trace")):
        if isinstance(t, dict):
            ref = t.get("ref")
            if isinstance(ref, str) and ref.strip():
                out.add(ref.strip())

    return out


def compute_coverage(
    *,
    feature: dict[str, Any],
    bundle_docs: list[dict[str, Any]],
    suites_by_group: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute coverage index based on trace/doc injections."""

    # docs list
    docs = []
    for d in bundle_docs:
        if not isinstance(d, dict):
            continue
        docs.append({
            "path": str(d.get("path") or ""),
            "title": str(d.get("title") or ""),
            "doc_type": str(d.get("doc_type") or ""),
        })

    by_doc: dict[str, list[str]] = {d["path"]: [] for d in docs if d["path"]}

    by_group: dict[str, Any] = {}

    for g, suite in suites_by_group.items():
        scenarios = suite.get("scenarios") or []
        if not isinstance(scenarios, list):
            scenarios = []
        by_group[g] = {
            "scenarios": len(scenarios),
            "docs": len({str(x.get("path") or "") for x in (suite.get("source_docs") or []) if isinstance(x, dict) and x.get("path")}),
        }

        for s in scenarios:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "")
            if not sid:
                continue
            for p in _trace_doc_paths(s):
                if p in by_doc:
                    by_doc[p].append(sid)

    uncovered = [p for p, ids in by_doc.items() if not ids]

    total_docs = len(by_doc)
    covered_docs = total_docs - len(uncovered)

    cov = {
        "feature": feature,
        "docs": docs,
        "by_doc": by_doc,
        "uncovered_docs": uncovered,
        "stats": {
            "total_docs": total_docs,
            "covered_docs": covered_docs,
            "coverage_pct": (round(covered_docs * 100.0 / total_docs, 2) if total_docs else 0.0),
            "total_groups": len(suites_by_group),
            "total_scenarios": sum(int(v.get("scenarios") or 0) for v in by_group.values()),
        },
        "by_group": by_group,
    }

    return cov
