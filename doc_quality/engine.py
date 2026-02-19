from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import EngineConfig, load_config, resolve_llm_settings
from .markdown import split_frontmatter, build_sections, norm_heading
from .policy import load_templates, auto_detect_doc_type
from .rules import check_meta, apply_section_rules, check_order, issue
from .util import ensure_dir, json_default, read_text

from .validators import load_validators, ValidatorRegistry
from .llm.validators import make_llm_client, run_validator


def _status_from_issues(issues: list[dict[str, Any]]) -> str:
    if any(x.get("severity") == "blocker" for x in issues):
        return "fail"
    if any(x.get("severity") == "warning" for x in issues):
        return "warn"
    return "pass"


def _pick_first_section_match(section_def: dict[str, Any], sections_by_title: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    for title in section_def.get("titles", []) or []:
        key = norm_heading(str(title))
        if key in sections_by_title and sections_by_title[key]:
            return sections_by_title[key][0]
    return None


def analyze_file(
    *,
    path: Path,
    templates: dict[str, Any],
    validators: ValidatorRegistry,
    cfg: EngineConfig,
    enable_llm: bool,
) -> dict[str, Any]:
    raw_md = read_text(path)
    meta, body = split_frontmatter(raw_md)

    headings, sections_by_title = build_sections(body)
    template, sel = auto_detect_doc_type(meta, headings, templates)

    issues: list[dict[str, Any]] = []
    matches: dict[str, dict[str, Any]] = {}
    sections_text: dict[str, str] = {}

    if template is None or sel is None:
        issues.append(issue("blocker", "NO_TEMPLATE", "Не найден ни один шаблон (templates пустые?)", "structure"))
        qg = {"doc_type": None, "template_id": None, "template_mode": None, "issues": issues, "status": _status_from_issues(issues)}
        return {"file": str(path), "meta": meta, "quality_gate": qg}

    issues += check_meta(meta, template)

    for s in template.get("sections", []) or []:
        key = str(s.get("key"))
        m = _pick_first_section_match(s, sections_by_title)
        if not m:
            if s.get("required", False):
                issues.append(issue("blocker", "SECTION_MISSING", f"Нет обязательного раздела: {key} (ожидались заголовки: {s.get('titles')})", key))
            continue

        matches[key] = m
        sections_text[key] = m.get("text", "")

        rules = s.get("rules", {}) or {}
        issues += apply_section_rules(key, m.get("text", ""), rules, start_line=m.get("start_line"))

    issues += check_order(template, matches)

    qg = {
        "doc_type": sel.doc_type,
        "template_id": sel.template_id,
        "template_mode": sel.mode,
        "template_score": sel.score,
        "issues": issues,
        "status": _status_from_issues(issues),
    }

    llm_results: dict[str, Any] = {}
    llm_error: str | None = None

    llm_enabled_effective = False

    if enable_llm and cfg.llm.enabled:
        client, model, err = make_llm_client(cfg)
        if err:
            llm_error = err
        else:
            llm_enabled_effective = True
            # truncate inputs
            llm_cfg = resolve_llm_settings(cfg.llm)
            try:
                # section validators declared in template
                for s in template.get("sections", []) or []:
                    key = str(s.get("key"))
                    if key not in sections_text:
                        continue

                    vids: list[str] = []
                    if isinstance(s.get("validators"), list):
                        vids = [str(x) for x in (s.get("validators") or [])]
                    else:
                        # backward-compatible: rules.llm_validator
                        rules = s.get("rules", {}) or {}
                        vid = rules.get("llm_validator")
                        if vid:
                            vids = [str(vid)]

                    if not vids:
                        continue

                    section_text = sections_text[key][: llm_cfg.max_section_chars]

                    sec_title = str(matches.get(key, {}).get("title") or "")
                    meta_json = json.dumps(meta, ensure_ascii=False, default=json_default)
                    for vid in vids:
                        spec = validators.get(vid)
                        if spec is None:
                            llm_results.setdefault(key, {})[vid] = {
                                "validator": vid,
                                "result": None,
                                "error": f"Unknown validator: {vid} (not found in validators-dir)",
                                "raw_head": None,
                            }
                            continue
                        if spec.kind != "section":
                            llm_results.setdefault(key, {})[vid] = {
                                "validator": vid,
                                "result": None,
                                "error": f"Validator '{vid}' has kind='{spec.kind}', expected 'section'", 
                                "raw_head": None,
                            }
                            continue

                        res = run_validator(
                            cfg=cfg,
                            client=client,
                            model=model,
                            spec=spec,
                            section_text=section_text,
                            doc_text=body[: llm_cfg.max_doc_chars],
                            section_title=sec_title,
                            doc_meta_json=meta_json,
                            doc_type=sel.doc_type,
                            template_id=sel.template_id,
                        )
                        llm_results.setdefault(key, {})[vid] = asdict(res)

            finally:
                try:
                    client.close()
                except Exception:
                    pass

    report = {
        "file": str(path),
        "meta": meta,
        "quality_gate": qg,
        "llm": {
            "enabled": bool(llm_enabled_effective),
            "error": llm_error,
            "section_validators": llm_results,
        },
    }
    return report


def analyze_section(
    *,
    path: Path,
    section_selector: str,
    templates: dict[str, Any],
    validators: ValidatorRegistry,
    cfg: EngineConfig,
    enable_llm: bool,
    validator_override: str | None = None,
) -> dict[str, Any]:
    """Analyze a single section of a single markdown file.

    This is meant for analysts: fast feedback while editing.
    """
    raw_md = read_text(path)
    meta, body = split_frontmatter(raw_md)
    headings, sections_by_title = build_sections(body)
    template, sel = auto_detect_doc_type(meta, headings, templates)

    if template is None or sel is None:
        return {
            "file": str(path),
            "error": "NO_TEMPLATE",
            "message": "Не найден ни один шаблон (templates пустые?)",
        }

    # find section definition by key or title
    sec_def = None
    sec_key = None
    norm_sel = norm_heading(section_selector)
    for s in template.get("sections", []) or []:
        key = str(s.get("key"))
        if norm_heading(key) == norm_sel:
            sec_def = s
            sec_key = key
            break
        for t in s.get("titles", []) or []:
            if norm_heading(str(t)) == norm_sel:
                sec_def = s
                sec_key = key
                break
        if sec_def:
            break

    if sec_def is None or sec_key is None:
        return {
            "file": str(path),
            "doc_type": sel.doc_type,
            "template_id": sel.template_id,
            "error": "SECTION_NOT_FOUND",
            "message": f"Раздел '{section_selector}' не найден в шаблоне '{sel.doc_type}'.",
        }

    # locate section text in markdown
    m = _pick_first_section_match(sec_def, sections_by_title)
    if not m:
        return {
            "file": str(path),
            "doc_type": sel.doc_type,
            "template_id": sel.template_id,
            "section": {"key": sec_key, "selector": section_selector},
            "error": "SECTION_MISSING_IN_DOC",
            "message": f"В документе нет раздела '{sec_key}' (ожидались заголовки: {sec_def.get('titles')}).",
        }

    section_text = (m.get("text", "") or "")
    sec_title = str(m.get("title") or "")
    start_line = m.get("start_line")

    # deterministic rules for this section
    issues: list[dict[str, Any]] = []
    rules = sec_def.get("rules", {}) or {}
    issues += apply_section_rules(sec_key, section_text, rules, start_line=start_line)

    llm_out: dict[str, Any] = {}
    llm_error: str | None = None

    if enable_llm and cfg.llm.enabled:
        client, model, err = make_llm_client(cfg)
        if err:
            llm_error = err
        else:
            llm_cfg = resolve_llm_settings(cfg.llm)
            try:
                if validator_override:
                    vids = [validator_override]
                else:
                    if isinstance(sec_def.get("validators"), list):
                        vids = [str(x) for x in (sec_def.get("validators") or [])]
                    else:
                        vid = (rules.get("llm_validator") if isinstance(rules, dict) else None)
                        vids = [str(vid)] if vid else []

                meta_json = json.dumps(meta, ensure_ascii=False, default=json_default)
                for vid in vids:
                    spec = validators.get(vid)
                    if spec is None:
                        llm_out[vid] = {"validator": vid, "result": None, "error": "Unknown validator (not found in validators-dir)", "raw_head": None}
                        continue
                    if spec.kind != "section":
                        llm_out[vid] = {"validator": vid, "result": None, "error": f"Validator kind='{spec.kind}', expected 'section'", "raw_head": None}
                        continue

                    res = run_validator(
                        cfg=cfg,
                        client=client,
                        model=model,
                        spec=spec,
                        section_text=section_text[: llm_cfg.max_section_chars],
                        doc_text=body[: llm_cfg.max_doc_chars],
                        section_title=sec_title,
                        doc_meta_json=meta_json,
                        doc_type=sel.doc_type,
                        template_id=sel.template_id,
                    )
                    llm_out[vid] = asdict(res)
            finally:
                try:
                    client.close()
                except Exception:
                    pass

    return {
        "file": str(path),
        "doc_type": sel.doc_type,
        "template_id": sel.template_id,
        "section": {
            "key": sec_key,
            "title": sec_title,
            "start_line": start_line,
            "chars": len(section_text),
        },
        "rules": {"issues": issues, "status": _status_from_issues(issues)},
        "llm": {"enabled": bool(enable_llm and cfg.llm.enabled and llm_error is None), "error": llm_error, "validators": llm_out},
    }


def write_report(out_dir: Path, file_path: Path, report: dict[str, Any], root: Path) -> Path:
    try:
        rel = file_path.resolve().relative_to(root.resolve())
    except Exception:
        rel = Path(file_path.name)

    out_path = out_dir / rel
    out_path = out_path.with_suffix(out_path.suffix + ".report.json")
    ensure_dir(out_path.parent)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    return out_path


def run(
    *,
    paths: list[Path],
    templates_dir: Path,
    validators_dir: Path,
    config_path: Path,
    out_dir: Path,
    enable_llm: bool,
    fail_on_warn: bool = False,
) -> tuple[int, dict[str, Any]]:
    templates = load_templates(templates_dir)
    validators = load_validators(validators_dir)
    cfg = load_config(config_path)

    ensure_dir(out_dir)

    reports = []
    for p in paths:
        reports.append(analyze_file(path=p, templates=templates, validators=validators, cfg=cfg, enable_llm=enable_llm))

    summary_items = []
    for r in reports:
        qg = r.get("quality_gate", {}) or {}
        summary_items.append({
            "file": r.get("file"),
            "status": qg.get("status"),
            "blockers": sum(1 for i in (qg.get("issues") or []) if i.get("severity") == "blocker"),
            "warnings": sum(1 for i in (qg.get("issues") or []) if i.get("severity") == "warning"),
        })

    summary = {
        "total_files": len(reports),
        "files": summary_items,
        "blockers": sum(x["blockers"] for x in summary_items),
        "warnings": sum(x["warnings"] for x in summary_items),
    }

    # write reports mirroring folder structure relative to cwd
    root = Path.cwd()
    for r in reports:
        fp = Path(r["file"])
        write_report(out_dir, fp, r, root)

    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    exit_code = 0
    if summary["blockers"] > 0:
        exit_code = 2
    elif fail_on_warn and summary["warnings"] > 0:
        exit_code = 1

    return exit_code, summary
