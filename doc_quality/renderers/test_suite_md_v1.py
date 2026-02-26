from __future__ import annotations

from typing import Any

from .base import RenderContext, Renderer


class TestSuiteMarkdownV1Renderer:
    """Human-readable markdown from canonical test_suite.json.

    Deterministic renderer. No LLM here.
    """

    name = "test_suite_md_v1"

    def render(self, data: Any, ctx: RenderContext) -> str:
        if not isinstance(data, dict):
            return "# Test Suite\n\nERROR: invalid test suite data"

        feature = data.get("feature") or {}
        fid = feature.get("id") or ctx.feature_id or "<unknown>"
        title = feature.get("title") or ""
        task = feature.get("task")

        lines: list[str] = []
        lines.append(f"# Test Suite: {fid}{(' - ' + title) if title else ''}")
        if task:
            lines.append("")
            lines.append(f"**Task:** {task}")

        assumptions = data.get("assumptions") or []
        if assumptions:
            lines.append("\n## Assumptions")
            for a in assumptions:
                lines.append(f"- {a}")

        scope = data.get("scope") or {}
        scope_in = scope.get("in") or []
        scope_out = scope.get("out") or []
        if scope_in or scope_out:
            lines.append("\n## Scope")
            if scope_in:
                lines.append("\n### In scope")
                for x in scope_in:
                    lines.append(f"- {x}")
            if scope_out:
                lines.append("\n### Out of scope")
                for x in scope_out:
                    lines.append(f"- {x}")

        scenarios = data.get("scenarios") or []
        lines.append("\n## Scenarios")
        if not scenarios:
            lines.append("\n_Нет сценариев (похоже, генератор отдал пустой результат)._\n")
        else:
            for s in scenarios:
                if not isinstance(s, dict):
                    continue
                sid = s.get("id") or "<id>"
                stitle = s.get("title") or ""
                stype = s.get("type") or ""
                prio = s.get("priority") or ""

                lines.append(f"\n### {sid}{(' - ' + stitle) if stitle else ''}")
                meta_bits = []
                if stype:
                    meta_bits.append(f"type={stype}")
                if prio:
                    meta_bits.append(f"priority={prio}")
                if meta_bits:
                    lines.append(f"_{', '.join(meta_bits)}_")

                pre = s.get("preconditions") or []
                if pre:
                    lines.append("\n**Preconditions**")
                    for x in pre:
                        lines.append(f"- {x}")

                steps = s.get("steps") or []
                if steps:
                    lines.append("\n**Steps**")
                    for i, x in enumerate(steps, start=1):
                        lines.append(f"{i}. {x}")

                exp = s.get("expected") or []
                if exp:
                    lines.append("\n**Expected**")
                    for x in exp:
                        lines.append(f"- {x}")

                mocks = s.get("mocks") or []
                if mocks:
                    lines.append("\n**Suggested mocks/stubs**")
                    for m in mocks:
                        if isinstance(m, dict):
                            sys_ = m.get("system") or "system"
                            beh = m.get("behavior") or ""
                            lines.append(f"- **{sys_}**: {beh}")
                        else:
                            lines.append(f"- {m}")

                trace = s.get("trace") or []
                if trace:
                    lines.append("\n**Trace**")
                    for t in trace:
                        if isinstance(t, dict):
                            src = t.get("source") or "source"
                            ref = t.get("ref") or ""
                            lines.append(f"- {src}: {ref}")
                        else:
                            lines.append(f"- {t}")

        oq = data.get("open_questions") or []
        if oq:
            lines.append("\n## Open questions")
            for q in oq:
                lines.append(f"- {q}")

        lines.append("")
        return "\n".join(lines)
