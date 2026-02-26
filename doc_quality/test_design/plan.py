from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BundleDoc:
    path: str
    title: str
    doc_type: str
    meta: dict[str, Any]
    text: str


@dataclass(frozen=True)
class Part:
    group: str
    index: int
    total: int
    docs: list[dict[str, Any]]  # {path,title,doc_type,segment?}
    text: str


@dataclass(frozen=True)
class Job:
    group: str
    generator_id: str
    part: Part
    max_scenarios: int


@dataclass(frozen=True)
class ExecutionPlan:
    feature: dict[str, Any]
    groups: list[str]
    jobs: list[Job]


def _clean_group_key(s: str) -> str:
    s = (s or "").strip()
    return s or "unknown"


def _segment_text(text: str, max_chars: int) -> list[str]:
    """Split a long text into chunks that fit max_chars.

    We prefer to split on heading boundaries (markdown '#', '##', etc.)
    if possible. Otherwise we do a plain chunk split.
    """

    t = (text or "").strip()
    if not t:
        return [""]
    if len(t) <= max_chars:
        return [t]

    # Try split by top-level headings first.
    # We keep the heading with the section text.
    blocks: list[str] = []
    cur: list[str] = []
    for line in t.splitlines():
        if re.match(r"^#{1,3}\\s+", line) and cur:
            blocks.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur).strip())

    # If headings didn't help (still just 1 huge block), fall back to chunking.
    if len(blocks) == 1 and len(blocks[0]) > max_chars:
        out: list[str] = []
        overlap = min(300, max_chars // 10)
        step = max_chars - overlap
        for i in range(0, len(t), step):
            out.append(t[i : i + max_chars].strip())
        return [x for x in out if x]

    # Pack heading blocks into chunks.
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for b in blocks:
        if not b:
            continue
        add = len(b) + 2
        if buf and size + add > max_chars:
            out.append("\n\n".join(buf).strip())
            buf = [b]
            size = len(b)
        else:
            buf.append(b)
            size += add
    if buf:
        out.append("\n\n".join(buf).strip())

    # Ensure hard cap.
    final: list[str] = []
    for x in out:
        if len(x) <= max_chars:
            final.append(x)
        else:
            final.extend(_segment_text(x, max_chars))
    return [x for x in final if x]


def _pack_docs_into_parts(
    *,
    group: str,
    docs: list[BundleDoc],
    max_input_chars: int,
) -> list[Part]:
    """Create parts with bounded size by packing docs and splitting large docs."""

    parts_raw: list[dict[str, Any]] = []
    cur_docs: list[dict[str, Any]] = []
    cur_chunks: list[str] = []
    cur_len = 0

    def flush():
        nonlocal cur_docs, cur_chunks, cur_len
        if not cur_chunks:
            return
        parts_raw.append({
            "docs": list(cur_docs),
            "text": "\n\n".join(cur_chunks).strip(),
        })
        cur_docs = []
        cur_chunks = []
        cur_len = 0

    for d in docs:
        segments = _segment_text(d.text, max_input_chars)
        for si, seg in enumerate(segments, start=1):
            header = (
                f"# SOURCE_DOC\n"
                f"path: {d.path}\n"
                f"title: {d.title}\n"
                f"doc_type: {d.doc_type}\n"
            )
            if len(segments) > 1:
                header += f"segment: {si}/{len(segments)}\n"

            chunk = header + "\n" + (seg or "")
            if cur_chunks and (cur_len + len(chunk) + 2) > max_input_chars:
                flush()

            cur_chunks.append(chunk)
            cur_len += len(chunk) + 2
            cur_docs.append({
                "path": d.path,
                "title": d.title,
                "doc_type": d.doc_type,
                **({"segment": f"{si}/{len(segments)}"} if len(segments) > 1 else {}),
            })

            # If a single doc segment is already near max, flush to keep bounded.
            if cur_len >= max_input_chars * 0.9:
                flush()

    flush()

    total = len(parts_raw) or 1
    out: list[Part] = []
    for idx, p in enumerate(parts_raw, start=1):
        out.append(Part(group=group, index=idx, total=total, docs=p["docs"], text=p["text"]))
    return out


def build_split_plan(
    *,
    feature: dict[str, Any],
    bundle: dict[str, Any],
    generator_map: dict[str, str],
    default_generator: str,
    doc_types: list[str] | None,
    max_input_chars: int,
    max_scenarios_per_part: int,
) -> ExecutionPlan:
    """Build deterministic execution plan for split (B1 Map→Reduce).

    - groups by doc_type
    - chunks each group into bounded parts
    - assigns generator per group
    """

    # Flatten bundle into docs list.
    docs: list[BundleDoc] = []

    f = bundle.get("feature") or {}
    f_meta = f.get("meta") or {}
    f_doc_type = str(f.get("doc_type") or f_meta.get("doc_type") or "feature")
    docs.append(BundleDoc(
        path=str(f.get("path") or ""),
        title=str(f.get("title") or ""),
        doc_type=f_doc_type,
        meta=dict(f_meta) if isinstance(f_meta, dict) else {},
        text=str(f.get("text") or ""),
    ))

    for r in (bundle.get("related") or []):
        if not isinstance(r, dict):
            continue
        meta = r.get("meta") or {}
        docs.append(BundleDoc(
            path=str(r.get("path") or ""),
            title=str(r.get("title") or ""),
            doc_type=str(r.get("doc_type") or (meta.get("doc_type") if isinstance(meta, dict) else "") or "unknown"),
            meta=dict(meta) if isinstance(meta, dict) else {},
            text=str(r.get("text") or ""),
        ))

    # Group by doc_type.
    groups: dict[str, list[BundleDoc]] = {}
    for d in docs:
        g = _clean_group_key(d.doc_type)
        groups.setdefault(g, []).append(d)

    # Filter groups if doc_types specified.
    if doc_types:
        allow = {x.strip() for x in doc_types if x.strip()}
        groups = {k: v for k, v in groups.items() if k in allow}

    # Build jobs.
    jobs: list[Job] = []
    group_names = sorted(groups.keys())
    for g in group_names:
        parts = _pack_docs_into_parts(group=g, docs=groups[g], max_input_chars=max_input_chars)
        gen = generator_map.get(g) or default_generator
        for part in parts:
            jobs.append(Job(group=g, generator_id=gen, part=part, max_scenarios=max_scenarios_per_part))

    return ExecutionPlan(feature=feature, groups=group_names, jobs=jobs)


def plan_to_json(plan: ExecutionPlan) -> str:
    def _j(o: Any) -> Any:
        if isinstance(o, ExecutionPlan):
            return {"feature": o.feature, "groups": o.groups, "jobs": [_j(j) for j in o.jobs]}
        if isinstance(o, Job):
            return {"group": o.group, "generator_id": o.generator_id, "max_scenarios": o.max_scenarios, "part": _j(o.part)}
        if isinstance(o, Part):
            return {"group": o.group, "index": o.index, "total": o.total, "docs": o.docs, "text_chars": len(o.text)}
        return str(o)

    return json.dumps(_j(plan), ensure_ascii=False, indent=2)
