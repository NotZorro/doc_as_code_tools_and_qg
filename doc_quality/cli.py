from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import run as run_engine, analyze_section
from .util import iter_md_files, read_paths_file
from .policy import load_templates
from .validators import load_validators
from .config import load_config
from .tools import load_tools


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
    s.add_argument("--context-paths", nargs="*", default=[], help="Extra files/dirs to include as docs-pack context for the LLM")
    s.add_argument("--context-paths-file", default=None, help="File with newline-separated paths to include as docs-pack context")
    s.add_argument("--no-llm", action="store_true", help="Disable LLM validators")
    s.add_argument("--json", action="store_true", help="Print only JSON output")
    s.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    tl = sub.add_parser("tools", help="List available LLM tools (policy)")
    tl.add_argument("--tools-dir", default=".docq/tools", help="Directory with LLM tools (policy)")

    t = sub.add_parser("tool", help="Run a policy-defined LLM tool")
    t.add_argument("--tool", required=True, help="Tool id")
    t.add_argument("--tools-dir", default=".docq/tools", help="Directory with LLM tools (policy)")
    t.add_argument("--input", default=None, help="Tool input JSON string")
    t.add_argument("--input-file", default=None, help="Path to tool input JSON file")
    t.add_argument("--file", default=None, help="Optional markdown file to provide doc/section context")
    t.add_argument("--section", default=None, help="Optional section key (from template) or heading title")
    t.add_argument("--paths", nargs="*", default=[], help="Files or directories to include as docs-pack context")
    t.add_argument("--paths-file", default=None, help="File with newline-separated paths to include as docs-pack context")
    t.add_argument("--templates-dir", default=".docq/templates", help="Directory with YAML templates")
    t.add_argument("--config", default=".docq/config.yml", help="Policy config YAML")
    t.add_argument("--no-llm", action="store_true", help="Disable LLM")
    t.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
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

        # docs-pack context = the current file + any extra paths provided
        ctx_paths: list[str] = [str(fp)]
        if args.context_paths:
            ctx_paths += list(args.context_paths)
        if args.context_paths_file:
            ctx_paths += read_paths_file(Path(args.context_paths_file))

        from .util import json_default, read_text
        from .markdown import split_frontmatter
        from .config import resolve_llm_settings
        import json

        md_files = iter_md_files(ctx_paths)
        llm_cfg = resolve_llm_settings(cfg.llm)
        per_doc_chars = max(500, min(8000, llm_cfg.max_doc_chars // max(1, len(md_files))))
        docs_pack = []
        for pth in md_files:
            raw = read_text(pth)
            m, b = split_frontmatter(raw)
            docs_pack.append({"path": str(pth), "meta": m, "text": (b or "")[:per_doc_chars]})
        docs_pack_json = json.dumps(docs_pack, ensure_ascii=False, default=json_default)
        docs_pack_text = "\n\n".join(
            [
                f"# FILE: {d['path']}\n# META: {json.dumps(d.get('meta') or {}, ensure_ascii=False, default=json_default)}\n{d.get('text') or ''}"
                for d in docs_pack
            ]
        )[: llm_cfg.max_doc_chars]

        out = analyze_section(
            path=fp,
            section_selector=str(args.section),
            templates=templates,
            validators=validators,
            cfg=cfg,
            enable_llm=(not args.no_llm),
            validator_override=(str(args.validator) if args.validator else None),
            docs_pack_json=docs_pack_json,
            docs_pack_text=docs_pack_text,
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

    if args.cmd == "tools":
        tools = load_tools(Path(args.tools_dir))
        for tid in tools.ids():
            print(tid)
        sys.exit(0)

    if args.cmd == "tool":
        from .llm.validators import make_llm_client
        from .llm.tools import run_tool
        from .markdown import split_frontmatter, build_sections, norm_heading
        from .policy import auto_detect_doc_type
        from .config import resolve_llm_settings
        from .util import read_text, json_default
        import json

        if args.no_llm:
            print("ERROR: --no-llm set, but tools are LLM-only.", file=sys.stderr)
            sys.exit(2)

        # load policy
        tools = load_tools(Path(args.tools_dir))
        spec = tools.get(str(args.tool))
        if spec is None:
            print(f"ERROR: Unknown tool '{args.tool}' (not found in tools-dir).", file=sys.stderr)
            sys.exit(2)

        cfg = load_config(Path(args.config))
        client, model, err = make_llm_client(cfg)
        if err or client is None or model is None:
            print(f"ERROR: {err or 'LLM is not available'}", file=sys.stderr)
            sys.exit(2)

        # parse tool input
        tool_input: dict[str, object] = {}
        if args.input and args.input_file:
            print("ERROR: Provide either --input or --input-file, not both.", file=sys.stderr)
            sys.exit(2)
        if args.input_file:
            tool_input = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
        elif args.input:
            tool_input = json.loads(str(args.input))
        if tool_input is None:
            tool_input = {}
        if not isinstance(tool_input, dict):
            print("ERROR: Tool input must be a JSON object.", file=sys.stderr)
            sys.exit(2)

        # build docs-pack context
        ctx: list[str] = []
        if args.file:
            ctx.append(str(args.file))
        if args.paths:
            ctx += list(args.paths)
        if args.paths_file:
            ctx += read_paths_file(Path(args.paths_file))
        if not ctx:
            ctx = ["."]

        md_files = iter_md_files(ctx)
        llm_cfg = resolve_llm_settings(cfg.llm)
        per_doc_chars = max(500, min(8000, llm_cfg.max_doc_chars // max(1, len(md_files))))
        docs_pack = []
        for pth in md_files:
            raw = read_text(pth)
            m, b = split_frontmatter(raw)
            docs_pack.append({"path": str(pth), "meta": m, "text": (b or "")[:per_doc_chars]})
        docs_pack_json = json.dumps(docs_pack, ensure_ascii=False, default=json_default)
        docs_pack_text = "\n\n".join(
            [
                f"# FILE: {d['path']}\n# META: {json.dumps(d.get('meta') or {}, ensure_ascii=False, default=json_default)}\n{d.get('text') or ''}"
                for d in docs_pack
            ]
        )[: llm_cfg.max_doc_chars]

        # optional doc/section context
        doc_text = ""
        section_text = ""
        section_title = ""
        doc_meta_json = "{}"
        doc_type = ""
        template_id = ""

        if args.file:
            fp = Path(args.file)
            raw_md = read_text(fp)
            meta, body = split_frontmatter(raw_md)
            doc_text = body[: llm_cfg.max_doc_chars]
            doc_meta_json = json.dumps(meta, ensure_ascii=False, default=json_default)

            templates = load_templates(Path(args.templates_dir))
            headings, sections_by_title = build_sections(body)
            template, sel = auto_detect_doc_type(meta, headings, templates)
            if sel:
                doc_type = sel.doc_type
                template_id = sel.template_id

            def _pick_first(titles: list[str]):
                for t in titles or []:
                    k = norm_heading(str(t))
                    if k in sections_by_title and sections_by_title[k]:
                        return sections_by_title[k][0]
                return None

            if args.section:
                m = None
                # try template selector (key or any of titles)
                if template:
                    sec_def = None
                    sel_norm = norm_heading(str(args.section))
                    for s in template.get("sections", []) or []:
                        key = str(s.get("key"))
                        if norm_heading(key) == sel_norm:
                            sec_def = s
                            break
                        for t in s.get("titles", []) or []:
                            if norm_heading(str(t)) == sel_norm:
                                sec_def = s
                                break
                        if sec_def:
                            break
                    if sec_def is not None:
                        m = _pick_first([str(x) for x in (sec_def.get("titles") or [])])

                # fallback: direct heading title
                if m is None:
                    k = norm_heading(str(args.section))
                    if k in sections_by_title and sections_by_title[k]:
                        m = sections_by_title[k][0]

                if m is None:
                    print(f"ERROR: Section '{args.section}' not found in file '{fp}'.", file=sys.stderr)
                    sys.exit(2)

                section_text = (m.get("text", "") or "")[: llm_cfg.max_section_chars]
                section_title = str(m.get("title") or "")

        try:
            res = run_tool(
                cfg=cfg,
                client=client,
                model=model,
                spec=spec,
                tool_input=tool_input,
                section_text=section_text,
                doc_text=doc_text,
                section_title=section_title,
                doc_meta_json=doc_meta_json,
                doc_type=doc_type,
                template_id=template_id,
                docs_pack_json=docs_pack_json,
                docs_pack_text=docs_pack_text,
            )
        finally:
            try:
                client.close()
            except Exception:
                pass

        if res.error:
            print(json.dumps({"tool": res.tool, "error": res.error, "raw_head": res.raw_head}, ensure_ascii=False, indent=(2 if args.pretty else None)))
            sys.exit(2)

        print(json.dumps(res.result, ensure_ascii=False, indent=(2 if args.pretty else None)))
        sys.exit(0)

    p.print_help()
    sys.exit(2)


if __name__ == '__main__':
    main()
