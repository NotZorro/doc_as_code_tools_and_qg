from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .base import CapabilityContext
from ..config import load_config, resolve_llm_settings
from ..generators import load_generators
from ..pbc import resolve_pbc_paths
from ..llm.validators import make_llm_client
from ..llm.generators import run_generator
from ..renderers import get_renderer
from ..renderers.base import RenderContext
from ..util import ensure_dir, json_default, read_text, iter_md_files, read_paths_file
from ..bundles import index_documents, resolve_feature_bundle, bundle_to_json
from ..markdown import split_frontmatter
from ..test_design import build_split_plan, merge_group_fragments, compute_coverage
from ..test_design.plan import plan_to_json


class TestDesignCapability:
    """Generate test suites (assist-mode) from a feature doc.

    Modes:
      - single: one generator call, one suite
      - split (B1): Map→Reduce by doc_type (multiple suites + coverage)
    """

    name = "test_design"

    def register(self, subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
        p = subparsers.add_parser("test-design", help="Generate test suite (json + md) from a feature doc")
        p.add_argument("--feature", required=True, help="Path to feature markdown file")
        p.add_argument("--paths", nargs="*", default=[], help="Files or directories to scan for related docs")
        p.add_argument("--paths-file", default=None, help="File with newline-separated paths (for related docs scan)")
        p.add_argument("--bundle", choices=["none", "auto"], default="auto", help="How to build context bundle")
        p.add_argument("--policy-root", default=".docq", help="Policy root directory (contains pbc/* or legacy generators/)")
        p.add_argument("--pbc", default="test_design", help="Policy bundle name (pbc) to use for generators")
        p.add_argument("--generators-dir", default=None, help="Directory with LLM generators (overrides --policy-root/--pbc)")
        p.add_argument("--generator", default="test_design_v1", help="Default generator id to use")
        p.add_argument("--config", default=None, help="Policy config YAML (LLM settings) (overrides --policy-root/--pbc)")
        p.add_argument("--out-dir", default="reports", help="Output directory")
        p.add_argument("--result-id", default=None, help="Result id used in output file names (defaults to feature id)")
        p.add_argument("--layout", choices=["flat","grouped"], default="flat", help="Output layout: flat (one folder) or grouped (subfolders by doc_type)")
        p.add_argument("--no-llm", action="store_true", help="Disable LLM (will fail)")

        # Generation options
        p.add_argument("--include-negative", action="store_true", help="Ask generator to include negative scenarios")
        p.add_argument("--include-edge", action="store_true", help="Ask generator to include edge-case scenarios")
        p.add_argument("--include-nfr", action="store_true", help="Ask generator to include NFR-related checks")

        # Outputs
        p.add_argument("--emit-json", action="store_true", help="Write canonical test_suite.json")
        p.add_argument("--emit-md", action="store_true", help="Write markdown test plan")
        p.add_argument("--no-coverage", action="store_true", help="Disable coverage index output (split mode)")

        # Split mode (B1)
        p.add_argument("--mode", choices=["single", "split"], default="single", help="Execution mode")
        p.add_argument("--split-by", choices=["doc_type"], default="doc_type", help="Split key (split mode)")
        p.add_argument(
            "--doc-types",
            default=None,
            help="Comma-separated allow-list of doc_type groups to generate (split mode). If omitted: all found.",
        )
        p.add_argument(
            "--generators-map",
            default=None,
            help="Comma-separated mapping group=generator_id for split mode. Example: api=test_design_api_v1,algorithm=test_design_algo_v1",
        )
        p.add_argument("--max-input-chars", type=int, default=12000, help="Max input chars per LLM call (split mode)")
        p.add_argument("--max-scenarios", type=int, default=12, help="Target max scenarios per part (split mode)")
        p.add_argument("--emit-plan", action="store_true", help="Write execution plan JSON (debug)")
        p.add_argument("--keep-fragments", action="store_true", help="Write per-part fragments JSON (debug)")

        p.set_defaults(_cap=self.name)

    def _parse_generators_map(self, s: str | None) -> dict[str, str]:
        out: dict[str, str] = {}
        if not s:
            return out
        for item in s.split(","):
            item = item.strip()
            if not item:
                continue
            if "=" not in item:
                continue
            k, v = item.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k and v:
                out[k] = v
        return out

    def _doc_types_list(self, s: str | None) -> list[str] | None:
        if not s:
            return None
        xs = [x.strip() for x in s.split(",")]
        xs = [x for x in xs if x]
        return xs or None

    def _inject_trace(self, scenario: dict[str, Any], doc_paths: list[str], group: str) -> None:
        scenario["__part_docs"] = doc_paths
        tr = scenario.get("trace")
        if not isinstance(tr, list) or not tr:
            # minimal trace for coverage
            scenario["trace"] = [{"source": group, "ref": p} for p in doc_paths[:2]]
            return
        # ensure at least one path-like ref exists
        has_path = False
        for t in tr:
            if isinstance(t, dict) and isinstance(t.get("ref"), str) and t.get("ref").strip():
                has_path = True
                break
        if not has_path and doc_paths:
            tr.append({"source": group, "ref": doc_paths[0]})

    def run(self, args: argparse.Namespace, ctx: CapabilityContext) -> int:
        feature_path = Path(args.feature)
        if not feature_path.exists():
            print(f"Feature file not found: {feature_path}", file=sys.stderr)
            return 2

        pbc_paths = resolve_pbc_paths(
            policy_root=Path(args.policy_root),
            pbc=str(args.pbc),
            generators_dir=Path(args.generators_dir) if args.generators_dir else None,
            config_path=Path(args.config) if args.config else None,
        )
        if not pbc_paths.generators_dir:
            print(f"Generators directory not found under {pbc_paths.policy_root} for pbc={pbc_paths.pbc}", file=sys.stderr)
            return 2

        cfg = load_config(pbc_paths.config_path or Path(".docq/config.yml"))
        llm_cfg = resolve_llm_settings(cfg.llm)

        # Default outputs: both json and md.
        emit_json = bool(args.emit_json) or (not bool(args.emit_json) and not bool(args.emit_md))
        emit_md = bool(args.emit_md) or (not bool(args.emit_json) and not bool(args.emit_md))

        if args.no_llm or not cfg.llm.enabled:
            print("LLM is disabled. test-design requires LLM.", file=sys.stderr)
            return 2

        generators = load_generators(pbc_paths.generators_dir)

        # Build bundle context (selection + truncation)
        scan_paths: list[str] = []
        if args.paths:
            scan_paths += list(args.paths)
        if args.paths_file:
            scan_paths += read_paths_file(Path(args.paths_file))
        if not scan_paths:
            scan_paths = [str(feature_path.parent), "."]

        md_files = iter_md_files(scan_paths)
        docs = index_documents(md_files)

        bundle = resolve_feature_bundle(
            feature_path=feature_path,
            docs=docs,
            mode=str(args.bundle),
            max_chars_per_doc=llm_cfg.max_doc_chars,
        )

        # Extract feature identity
        raw = read_text(feature_path)
        meta, body = split_frontmatter(raw)
        feature_id = str(meta.get("id") or meta.get("feature_id") or feature_path.stem)
        feature_title = str(meta.get("title") or bundle.get("feature", {}).get("title") or "")
        task = meta.get("task")
        task_str = str(task) if task is not None else ""
        feature_obj = {"id": feature_id, "title": feature_title, **({"task": task_str} if task_str else {})}

        options = {
            "include_negative": bool(args.include_negative),
            "include_edge": bool(args.include_edge),
            "include_nfr": bool(args.include_nfr),
        }

        out_dir = Path(args.out_dir)
        ensure_dir(out_dir)
        result_id = str(args.result_id or feature_id)
        layout = str(args.layout)

        if str(args.mode) == "single":
            # Preserve existing behavior.
            try:
                spec = generators.require(str(args.generator))
            except Exception as e:
                print(f"Generator not found: {e}", file=sys.stderr)
                return 2

            bundle_json = bundle_to_json(bundle)
            options_json = json.dumps(options, ensure_ascii=False, default=json_default)

            client, base_model, err = make_llm_client(cfg, override_base_url=spec.llm.base_url, override_timeout_s=spec.llm.timeout_s)
            if err or client is None or base_model is None:
                print(f"LLM client error: {err}", file=sys.stderr)
                return 2

            try:
                res = run_generator(
                    cfg=cfg,
                    client=client,
                    base_model=base_model,
                    spec=spec,
                    doc_text=body[: llm_cfg.max_doc_chars],
                    doc_meta_json=json.dumps(meta, ensure_ascii=False, default=json_default),
                    doc_type=str(meta.get("doc_type") or ""),
                    template_id="",
                    bundle_json=bundle_json,
                    options_json=options_json,
                )
            finally:
                try:
                    client.close()
                except Exception:
                    pass

            if res.error or not res.result:
                print(f"Generator error: {res.error}", file=sys.stderr)
                return 2

            out_obj = dict(res.result)
            out_obj.setdefault("feature", {})
            if isinstance(out_obj["feature"], dict):
                out_obj["feature"].setdefault("id", feature_id)
                out_obj["feature"].setdefault("title", feature_title)
                if task_str:
                    out_obj["feature"].setdefault("task", task_str)

            if layout == "grouped":
                base = out_dir / "test_design" / feature_id
                ensure_dir(base.parent)
            else:
                base = out_dir / f"td.{args.generator}.{result_id}"

            if emit_json:
                json_path = base.with_suffix(".test_suite.json")
                json_path.write_text(
                    get_renderer("json").render(out_obj, RenderContext(feature_id=feature_id, source_path=str(feature_path))),
                    encoding="utf-8",
                )
                print(f"Wrote: {json_path}")

            if emit_md:
                md_path = base.with_suffix(".test_suite.md")
                md_text = get_renderer("test_suite_md_v1").render(out_obj, RenderContext(feature_id=feature_id, source_path=str(feature_path)))
                md_path.write_text(md_text, encoding="utf-8")
                print(f"Wrote: {md_path}")

            return 0

        # --- split mode (B1 Map→Reduce) ---

        gen_map = self._parse_generators_map(args.generators_map)
        allow_doc_types = self._doc_types_list(args.doc_types)

        # Build plan.
        plan = build_split_plan(
            feature=feature_obj,
            bundle=bundle,
            generator_map=gen_map,
            default_generator=str(args.generator),
            doc_types=allow_doc_types,
            max_input_chars=int(args.max_input_chars),
            max_scenarios_per_part=int(args.max_scenarios),
        )

        # Validate generator ids exist.
        needed = {j.generator_id for j in plan.jobs}
        missing: list[str] = []
        for gid in sorted(needed):
            try:
                generators.require(gid)
            except Exception:
                missing.append(gid)
        if missing:
            print(f"Missing generator(s) in {pbc_paths.generators_dir}: {', '.join(missing)}", file=sys.stderr)
            return 2

        # Debug plan output
        debug_dir = (out_dir / "test_design" / "_debug") if layout == "grouped" else out_dir
        if bool(args.emit_plan):
            ensure_dir(debug_dir)
            pth = (debug_dir / f"{feature_id}.plan.json") if layout == "grouped" else (out_dir / f"td.{result_id}.plan.json")
            pth.write_text(plan_to_json(plan), encoding="utf-8")
            print(f"Wrote: {pth}")

        # Prepare minimal bundle summary to keep prompts small.
        rel_index = []
        for r in (bundle.get("related") or []):
            if isinstance(r, dict):
                rel_index.append({"path": r.get("path"), "title": r.get("title"), "doc_type": r.get("doc_type")})
        bundle_summary = {
            "feature": {"path": bundle.get("feature", {}).get("path"), "title": bundle.get("feature", {}).get("title"), "task": task_str},
            "related_index": rel_index,
        }

        fragments_by_group: dict[str, list[dict[str, Any]]] = {g: [] for g in plan.groups}

        # Client cache by (base_url, timeout)
        client_cache: dict[tuple[str, float], tuple[Any, str]] = {}

        def get_client_for(spec) -> tuple[Any, str] | tuple[None, None]:
            base_url = spec.llm.base_url
            timeout_s = spec.llm.timeout_s
            # make_llm_client applies env overrides and cfg defaults.
            c, base_model, err = make_llm_client(cfg, override_base_url=base_url, override_timeout_s=timeout_s)
            if err or c is None or base_model is None:
                print(f"LLM client error: {err}", file=sys.stderr)
                return None, None
            key = (c.base_url, getattr(c, 'timeout_s', timeout_s))
            if key not in client_cache:
                client_cache[key] = (c, base_model)
            else:
                # close the extra client we just created
                try:
                    c.close()
                except Exception:
                    pass
            return client_cache[key][0], client_cache[key][1]

        # Run jobs
        for job in plan.jobs:
            spec = generators.require(job.generator_id)

            client, base_model = get_client_for(spec)
            if client is None or base_model is None:
                return 2

            # Per-part meta and options
            doc_paths = [str(d.get("path") or "") for d in job.part.docs if isinstance(d, dict) and d.get("path")]
            part_meta = {
                "feature": feature_obj,
                "group": job.group,
                "part": {"index": job.part.index, "total": job.part.total, "docs": job.part.docs},
            }
            options2 = dict(options)
            options2.update({"mode": "split", "group": job.group, "max_scenarios": job.max_scenarios})

            res = run_generator(
                cfg=cfg,
                client=client,
                base_model=base_model,
                spec=spec,
                doc_text=job.part.text[: int(args.max_input_chars)],
                doc_meta_json=json.dumps(part_meta, ensure_ascii=False, default=json_default),
                doc_type=job.group,
                template_id="",
                bundle_json=json.dumps(bundle_summary, ensure_ascii=False, default=json_default),
                options_json=json.dumps(options2, ensure_ascii=False, default=json_default),
            )

            if res.error or not res.result:
                # Write raw head for debug
                ensure_dir(debug_dir)
                pth = (debug_dir / f"{feature_id}.error.{job.group}.part{job.part.index:02d}.txt") if layout == "grouped" else (out_dir / f"td.{result_id}.error.{job.group}.part{job.part.index:02d}.txt")
                pth.write_text((res.raw_head or "") + "\n\n" + (res.error or ""), encoding="utf-8")
                print(f"Generator error: {res.error}", file=sys.stderr)
                print(f"Debug: {pth}", file=sys.stderr)
                return 2

            fr = dict(res.result)
            fr.setdefault("feature", {})
            if isinstance(fr["feature"], dict):
                fr["feature"].setdefault("id", feature_id)
                fr["feature"].setdefault("title", feature_title)
                if task_str:
                    fr["feature"].setdefault("task", task_str)

            # Ensure scenarios + inject trace for coverage.
            scenarios = fr.get("scenarios")
            if not isinstance(scenarios, list):
                scenarios = []
                fr["scenarios"] = scenarios
            for s in scenarios:
                if isinstance(s, dict):
                    self._inject_trace(s, doc_paths, job.group)

            fr["group"] = job.group
            fr["part"] = {"index": job.part.index, "total": job.part.total}
            fr["source_docs"] = job.part.docs

            fragments_by_group[job.group].append(fr)

            if bool(args.keep_fragments):
                if layout == "grouped":
                    pdir = debug_dir / "fragments" / job.group
                    ensure_dir(pdir)
                    fp = pdir / f"{feature_id}.part{job.part.index:02d}.json"
                else:
                    fp = out_dir / f"td.{job.group}.{result_id}.part{job.part.index:02d}.fragment.json"
                fp.write_text(json.dumps(fr, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")

        # Close clients
        for c, _m in client_cache.values():
            try:
                c.close()
            except Exception:
                pass

        # Merge per group and write outputs
        suites_by_group: dict[str, dict[str, Any]] = {}
        for g in plan.groups:
            frs = fragments_by_group.get(g) or []
            if not frs:
                continue
            # source docs union
            sd_seen: set[str] = set()
            source_docs: list[dict[str, Any]] = []
            for fr in frs:
                for d in (fr.get("source_docs") or []):
                    if not isinstance(d, dict):
                        continue
                    p = str(d.get("path") or "")
                    if not p or p in sd_seen:
                        continue
                    sd_seen.add(p)
                    source_docs.append({"path": p, "title": d.get("title"), "doc_type": d.get("doc_type")})

            suite = merge_group_fragments(group=g, feature=feature_obj, source_docs=source_docs, fragments=frs)
            suites_by_group[g] = suite

            if layout == "grouped":
                group_dir = out_dir / "test_design" / g
                ensure_dir(group_dir)
                base = group_dir / feature_id
            else:
                base = out_dir / f"td.{g}.{result_id}"

            if emit_json:
                json_path = base.with_suffix(".test_suite.json")
                json_path.write_text(
                    get_renderer("json").render(suite, RenderContext(feature_id=feature_id, source_path=str(feature_path))),
                    encoding="utf-8",
                )
                print(f"Wrote: {json_path}")

            if emit_md:
                md_path = base.with_suffix(".test_suite.md")
                md_text = get_renderer("test_suite_md_v1").render(suite, RenderContext(feature_id=feature_id, source_path=str(feature_path)))
                md_path.write_text(md_text, encoding="utf-8")
                print(f"Wrote: {md_path}")

        # Coverage index
        if not bool(args.no_coverage) and suites_by_group:
            bundle_docs = []
            f = bundle.get("feature") or {}
            if isinstance(f, dict):
                bundle_docs.append({"path": f.get("path"), "title": f.get("title"), "doc_type": f.get("doc_type")})
            for r in (bundle.get("related") or []):
                if isinstance(r, dict):
                    bundle_docs.append({"path": r.get("path"), "title": r.get("title"), "doc_type": r.get("doc_type")})

            cov = compute_coverage(feature=feature_obj, bundle_docs=bundle_docs, suites_by_group=suites_by_group)
            if layout == "grouped":
                idx_dir = out_dir / "test_design" / "_index"
                ensure_dir(idx_dir)
                cov_json = idx_dir / f"{feature_id}.coverage.json"
            else:
                cov_json = out_dir / f"td.{result_id}.coverage.json"
            cov_json.write_text(get_renderer("json").render(cov, RenderContext(feature_id=feature_id, source_path=str(feature_path))), encoding="utf-8")
            print(f"Wrote: {cov_json}")

            if emit_md:
                cov_md = (idx_dir / f"{feature_id}.coverage.md") if layout == "grouped" else (out_dir / f"td.{result_id}.coverage.md")
                cov_md.write_text(get_renderer("coverage_md_v1").render(cov, RenderContext(feature_id=feature_id, source_path=str(feature_path))), encoding="utf-8")
                print(f"Wrote: {cov_md}")

        return 0
