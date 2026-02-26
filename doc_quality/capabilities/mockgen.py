from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .base import CapabilityContext
from ..util import ensure_dir


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "artifact"


class MockGenCapability:
    """Generate simple mock/stub placeholders from canonical test_suite.json.

    Today: deterministic placeholders.
    Tomorrow: richer formats (WireMock, Pact, etc.).
    """

    name = "mockgen"

    def register(self, subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
        p = subparsers.add_parser("mockgen", help="Generate mock placeholders from test_suite.json")
        p.add_argument("--test-suite", required=True, help="Path to *.test_suite.json")
        p.add_argument("--out-dir", default="generated", help="Output directory")
        p.add_argument("--format", choices=["wiremock"], default="wiremock")
        p.set_defaults(_cap=self.name)

    def run(self, args: argparse.Namespace, ctx: CapabilityContext) -> int:
        suite_path = Path(args.test_suite)
        if not suite_path.exists():
            print(f"Test suite not found: {suite_path}", file=sys.stderr)
            return 2

        try:
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            return 2

        if not isinstance(suite, dict):
            print("Invalid test suite format: expected JSON object", file=sys.stderr)
            return 2

        feature = suite.get("feature") or {}
        feature_id = str(feature.get("id") or suite_path.stem)
        fid_slug = _slug(feature_id)

        scenarios = suite.get("scenarios") or []
        if not isinstance(scenarios, list):
            scenarios = []

        out_root = Path(args.out_dir) / "mocks" / fid_slug
        ensure_dir(out_root)

        # README explaining placeholders.
        readme = out_root / "README.md"
        lines: list[str] = []
        lines.append(f"# Mocks for {feature_id}")
        lines.append("")
        lines.append("These are placeholders generated from test_suite.json.")
        lines.append("Fill request/response bodies, headers, and matching rules.")
        lines.append("")

        mapping_dir = out_root / "wiremock_mappings"
        ensure_dir(mapping_dir)

        n = 0
        for i, s in enumerate(scenarios, start=1):
            if not isinstance(s, dict):
                continue
            mocks = s.get("mocks") or []
            if not mocks:
                continue

            sid = str(s.get("id") or f"S{i}")
            for mi, m in enumerate(mocks, start=1):
                if isinstance(m, dict):
                    system = str(m.get("system") or "system")
                    behavior = str(m.get("behavior") or "")
                else:
                    system = "system"
                    behavior = str(m)

                fname = f"{_slug(sid)}_{_slug(system)}_{mi}.json"
                mapping = {
                    "comment": f"{feature_id} | {sid} | {system}",
                    "request": {
                        "method": "ANY",
                        "urlPath": "/TODO",
                    },
                    "response": {
                        "status": 200,
                        "jsonBody": {"TODO": "fill"},
                    },
                    "metadata": {
                        "generated_from": str(suite_path),
                        "behavior": behavior,
                    },
                }
                (mapping_dir / fname).write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
                n += 1

        lines.append(f"Generated {n} mapping placeholder(s) in `{mapping_dir.name}/`." )
        lines.append("")
        readme.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote: {readme}")
        print(f"Wrote mappings: {mapping_dir}")
        return 0
