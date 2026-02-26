from __future__ import annotations

from typing import Any

from .base import Renderer, RenderContext


class CoverageMarkdownV1Renderer(Renderer):
    name = "coverage_md_v1"

    def render(self, data: Any, ctx: RenderContext) -> str:
        if not isinstance(data, dict):
            return "# Coverage\n\nInvalid coverage data."

        feature = data.get("feature") or {}
        fid = feature.get("id") or ctx.feature_id or "feature"
        title = feature.get("title") or ""

        stats = data.get("stats") or {}
        total_docs = stats.get("total_docs", 0)
        covered_docs = stats.get("covered_docs", 0)
        pct = stats.get("coverage_pct", 0)
        total_scen = stats.get("total_scenarios", 0)

        lines: list[str] = []
        lines.append(f"# Coverage: {fid}{(' — ' + title) if title else ''}")
        lines.append("")
        lines.append(f"- Docs: **{covered_docs}/{total_docs}** covered ({pct}%)")
        lines.append(f"- Total scenarios: **{total_scen}**")

        by_group = data.get("by_group") or {}
        if isinstance(by_group, dict) and by_group:
            lines.append("")
            lines.append("## By group")
            lines.append("")
            lines.append("| Group | Docs | Scenarios |")
            lines.append("|---|---:|---:|")
            for g, v in sorted(by_group.items(), key=lambda x: x[0]):
                if not isinstance(v, dict):
                    continue
                lines.append(f"| {g} | {int(v.get('docs') or 0)} | {int(v.get('scenarios') or 0)} |")

        uncovered = data.get("uncovered_docs") or []
        if isinstance(uncovered, list) and uncovered:
            lines.append("")
            lines.append("## Uncovered docs")
            lines.append("")
            for p in uncovered:
                lines.append(f"- {p}")

        # Top docs by number of test cases
        by_doc = data.get("by_doc") or {}
        if isinstance(by_doc, dict) and by_doc:
            ranked = sorted(by_doc.items(), key=lambda kv: len(kv[1] or []), reverse=True)
            ranked = [x for x in ranked if x[0]]
            if ranked:
                lines.append("")
                lines.append("## Top covered docs")
                lines.append("")
                lines.append("| Doc | #TC | Examples |")
                lines.append("|---|---:|---|")
                for p, ids in ranked[:10]:
                    ids = ids or []
                    sample = ", ".join(ids[:5])
                    lines.append(f"| {p} | {len(ids)} | {sample} |")

        return "\n".join(lines) + "\n"
