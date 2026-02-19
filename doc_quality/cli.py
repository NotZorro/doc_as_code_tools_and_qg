from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import run as run_engine, analyze_section
from .util import iter_md_files, read_paths_file
from .policy import load_templates
from .validators import load_validators
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="doc-quality", description="Doc Quality Gate engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run quality gate on markdown files")
    r.add_argument("--paths", nargs="*", default=[], help="Files or directories to scan for *.md")
    r.add_argument("--paths-file", default=None, help="File with newline-separated paths to check")
    r.add_argument("--templates-dir", default=".docq/templates", help="Directory with YAML templates")
    r.add_argument("--validators-dir", default=".docq/validators", help="Directory with LLM validators (policy)")
    r.add_argument("--config", default=".docq/config.yml", help="Policy config YAML (LLM settings)")
    r.add_argument("--out-dir", default="reports", help="Output directory for reports")
    r.add_argument("--no-llm", action="store_true", help="Disable LLM validators")
    r.add_argument("--fail-on-warn", action="store_true", help="Exit code != 0 if there are warnings")

    s = sub.add_parser("section", help="Validate a single section in a single markdown file (fast feedback)")
    s.add_argument("--file", required=True, help="Path to markdown file")
    s.add_argument("--section", required=True, help="Section key (from template) or a heading title")
    s.add_argument("--validator", default=None, help="Override validator id (runs only this one)")
    s.add_argument("--templates-dir", default=".docq/templates", help="Directory with YAML templates")
    s.add_argument("--validators-dir", default=".docq/validators", help="Directory with LLM validators (policy)")
    s.add_argument("--config", default=".docq/config.yml", help="Policy config YAML")
    s.add_argument("--no-llm", action="store_true", help="Disable LLM validators")
    s.add_argument("--json", action="store_true", help="Print only JSON output")
    s.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return p


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "run":
        all_paths: list[str] = []
        if args.paths:
            all_paths += args.paths
        if args.paths_file:
            all_paths += read_paths_file(Path(args.paths_file))
        if not all_paths:
            all_paths = ["."]

        md_files = iter_md_files(all_paths)
        if not md_files:
            print("No markdown files found.", file=sys.stderr)
            sys.exit(0)

        code, summary = run_engine(
            paths=md_files,
            templates_dir=Path(args.templates_dir),
            validators_dir=Path(args.validators_dir),
            config_path=Path(args.config),
            out_dir=Path(args.out_dir),
            enable_llm=(not args.no_llm),
            fail_on_warn=bool(args.fail_on_warn),
        )

        # human-readable summary
        print(f"Checked: {summary['total_files']} file(s). Blockers: {summary['blockers']}. Warnings: {summary['warnings']}.")
        print(f"Reports: {Path(args.out_dir).resolve()}")
        sys.exit(code)

    if args.cmd == "section":
        fp = Path(args.file)
        templates = load_templates(Path(args.templates_dir))
        validators = load_validators(Path(args.validators_dir))
        cfg = load_config(Path(args.config))

        out = analyze_section(
            path=fp,
            section_selector=str(args.section),
            templates=templates,
            validators=validators,
            cfg=cfg,
            enable_llm=(not args.no_llm),
            validator_override=(str(args.validator) if args.validator else None),
        )

        import json

        if args.json or args.pretty:
            indent = 2 if args.pretty else None
            print(json.dumps(out, ensure_ascii=False, indent=indent))
        else:
            # human-readable
            if out.get("error"):
                print(f"ERROR: {out.get('error')}: {out.get('message')}")
                sys.exit(2)
            sec = out.get("section") or {}
            print(f"File: {out.get('file')}")
            print(f"Doc type: {out.get('doc_type')} (template: {out.get('template_id')})")
            print(f"Section: {sec.get('key')} | {sec.get('title')} | line {sec.get('start_line')} | chars {sec.get('chars')}")

            rules = out.get("rules") or {}
            print(f"Rules status: {rules.get('status')}")
            for iss in (rules.get("issues") or []):
                print(f"- [{iss.get('severity')}] {iss.get('code')}: {iss.get('message')}")

            llm = out.get("llm") or {}
            if llm.get("enabled"):
                print("LLM validators:")
                for vid, rr in (llm.get("validators") or {}).items():
                    if rr.get("error"):
                        print(f"- {vid}: ERROR: {rr.get('error')}")
                    else:
                        print(f"- {vid}: ok")
            else:
                if llm.get("error"):
                    print(f"LLM disabled: {llm.get('error')}")
                else:
                    print("LLM disabled")
        sys.exit(0)

    p.print_help()
    sys.exit(2)


if __name__ == '__main__':
    main()
