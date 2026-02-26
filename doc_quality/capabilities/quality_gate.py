from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .base import Capability, CapabilityContext
from ..engine import run as run_engine, analyze_section
from ..util import iter_md_files, read_paths_file
from ..policy import load_templates
from ..validators import load_validators
from ..config import load_config
from ..pbc import resolve_pbc_paths


class QualityGateCapability:
    """Quality Gate capability.

    This capability keeps backward compatible commands:
      - `doc-quality run`
      - `doc-quality section`
    Internally we treat them as one capability so we can later add more.
    """

    name = "quality_gate"

    def register(self, subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
        r = subparsers.add_parser("run", help="Run quality gate on markdown files")
        r.add_argument("--paths", nargs="*", default=[], help="Files or directories to scan for *.md")
        r.add_argument("--paths-file", default=None, help="File with newline-separated paths to check")
        r.add_argument("--policy-root", default=".docq", help="Policy root directory (contains pbc/* or legacy templates/validators)")
        r.add_argument("--pbc", default="quality_gate", help="Policy bundle name (pbc) to use")
        r.add_argument("--templates-dir", default=None, help="Directory with YAML templates (overrides --policy-root/--pbc)")
        r.add_argument("--validators-dir", default=None, help="Directory with LLM validators (overrides --policy-root/--pbc)")
        r.add_argument("--config", default=None, help="Policy config YAML (LLM settings) (overrides --policy-root/--pbc)")
        r.add_argument("--layout", choices=["flat","mirror"], default="flat", help="Report layout: flat (one folder) or mirror (by doc path)")
        r.add_argument("--out-dir", default="reports", help="Output directory for reports")
        r.add_argument("--no-llm", action="store_true", help="Disable LLM validators")
        r.add_argument("--fail-on-warn", action="store_true", help="Exit code != 0 if there are warnings")
        r.set_defaults(_cap=self.name, _cap_action="run")

        s = subparsers.add_parser("section", help="Validate a single section in a single markdown file (fast feedback)")
        s.add_argument("--file", required=True, help="Path to markdown file")
        s.add_argument("--policy-root", default=".docq", help="Policy root directory")
        s.add_argument("--pbc", default="quality_gate", help="Policy bundle name (pbc) to use")
        s.add_argument("--section", required=True, help="Section key (from template) or a heading title")
        s.add_argument("--validator", default=None, help="Override validator id (runs only this one)")
        s.add_argument("--templates-dir", default=None, help="Directory with YAML templates (overrides --policy-root/--pbc)")
        s.add_argument("--validators-dir", default=".docq/validators", help="Directory with LLM validators (policy)")
        s.add_argument("--config", default=None, help="Policy config YAML (overrides --policy-root/--pbc)")
        s.add_argument("--no-llm", action="store_true", help="Disable LLM validators")
        s.add_argument("--json", action="store_true", help="Print only JSON output")
        s.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
        s.set_defaults(_cap=self.name, _cap_action="section")

    def run(self, args: argparse.Namespace, ctx: CapabilityContext) -> int:
        action = getattr(args, "_cap_action", None)
        if action == "run":
            return self._run_gate(args)
        if action == "section":
            return self._run_section(args)
        print(f"Unknown action for capability '{self.name}': {action}", file=sys.stderr)
        return 2

@staticmethod
def _run_gate(args: argparse.Namespace) -> int:
    all_paths: list[str] = []
    if args.paths:
        all_paths += list(args.paths)
    if args.paths_file:
        all_paths += read_paths_file(Path(args.paths_file))
    if not all_paths:
        all_paths = ["."]
    md_files = iter_md_files(all_paths)
    if not md_files:
        print("No markdown files found.", file=sys.stderr)
        return 0

    pbc_paths = resolve_pbc_paths(
        policy_root=Path(args.policy_root),
        pbc=str(args.pbc),
        templates_dir=Path(args.templates_dir) if args.templates_dir else None,
        validators_dir=Path(args.validators_dir) if args.validators_dir else None,
        config_path=Path(args.config) if args.config else None,
    )
    if not pbc_paths.templates_dir or not pbc_paths.validators_dir:
        print(f"Policy paths not found under {pbc_paths.policy_root} for pbc={pbc_paths.pbc}", file=sys.stderr)
        return 2

    code, summary = run_engine(
        paths=md_files,
        templates_dir=pbc_paths.templates_dir,
        validators_dir=pbc_paths.validators_dir,
        config_path=pbc_paths.config_path or Path(".docq/config.yml"),
        out_dir=Path(args.out_dir),
        enable_llm=(not bool(args.no_llm)),
        fail_on_warn=bool(args.fail_on_warn),
        layout=str(args.layout),
    )

    print(f"Checked: {summary['total_files']} file(s). Blockers: {summary['blockers']}. Warnings: {summary['warnings']}.")
    print(f"Reports: {Path(args.out_dir).resolve()}")
    return int(code)

@staticmethod
def _run_section(args: argparse.Namespace) -> int:
    fp = Path(args.file)

    pbc_paths = resolve_pbc_paths(
        policy_root=Path(args.policy_root),
        pbc=str(args.pbc),
        templates_dir=Path(args.templates_dir) if args.templates_dir else None,
        validators_dir=Path(args.validators_dir) if args.validators_dir else None,
        config_path=Path(args.config) if args.config else None,
    )
    if not pbc_paths.templates_dir or not pbc_paths.validators_dir:
        print(f"Policy paths not found under {pbc_paths.policy_root} for pbc={pbc_paths.pbc}", file=sys.stderr)
        return 2

    templates = load_templates(pbc_paths.templates_dir)
    validators = load_validators(pbc_paths.validators_dir)
    cfg = load_config(pbc_paths.config_path or Path(".docq/config.yml"))

    out = analyze_section(
        path=fp,
        section_selector=str(args.section),
        templates=templates,
        validators=validators,
        cfg=cfg,
        enable_llm=(not bool(args.no_llm)),
        validator_override=(str(args.validator) if args.validator else None),
    )

    if args.json or args.pretty:
        indent = 2 if args.pretty else None
        print(json.dumps(out, ensure_ascii=False, indent=indent))
    else:
        qg = out.get("quality_gate", {}) or {}
        print(f"Status: {qg.get('status')}")
        for i in (qg.get('issues') or []):
            sev = i.get("severity")
            code = i.get("code")
            msg = i.get("message")
            section = i.get("section")
            print(f"- {sev}: {code} [{section}] {msg}")

    return 0

