from __future__ import annotations

import json
import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .markdown import split_frontmatter, extract_headings
from .util import read_text


@dataclass(frozen=True)
class IndexedDoc:
    path: Path
    meta: dict[str, Any]
    body: str
    title: str


def _doc_title(meta: dict[str, Any], body: str, path: Path) -> str:
    t = meta.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    # first heading if any
    hs = extract_headings(body)
    if hs:
        return hs[0].title
    return path.stem


def index_documents(md_files: list[Path]) -> list[IndexedDoc]:
    docs: list[IndexedDoc] = []
    for p in md_files:
        try:
            raw = read_text(p)
        except Exception:
            continue
        meta, body = split_frontmatter(raw)
        docs.append(IndexedDoc(path=p, meta=meta, body=body, title=_doc_title(meta, body, p)))
    return docs


def resolve_feature_bundle(
    *,
    feature_path: Path,
    docs: list[IndexedDoc],
    mode: str = "auto",
    max_chars_per_doc: int = 20000,
) -> dict[str, Any]:
    """Return a bundle dict for generator prompts.

    mode:
      - none: only feature doc
      - auto: try to attach docs with the same 'task' meta, plus explicit related_docs

    Notes:
      - We keep selection deterministic and explainable.
      - This is NOT RAG; it's simple metadata-based bundling.
    """

    feature_doc = None
    for d in docs:
        if d.path.resolve() == feature_path.resolve():
            feature_doc = d
            break
    if feature_doc is None:
        raw = read_text(feature_path)
        meta, body = split_frontmatter(raw)
        feature_doc = IndexedDoc(path=feature_path, meta=meta, body=body, title=_doc_title(meta, body, feature_path))

    feature_meta = feature_doc.meta
    task = feature_meta.get("task")
    if isinstance(task, str):
        task = task.strip()

    related: list[dict[str, Any]] = []

    if mode == "auto":
        if task:
            for d in docs:
                if d.path.resolve() == feature_doc.path.resolve():
                    continue
                dtask = d.meta.get("task")
                if isinstance(dtask, str) and dtask.strip() == task:
                    related.append({
                        "path": str(d.path),
                        "title": d.title,
                        "doc_type": d.meta.get("doc_type"),
                        "meta": d.meta,
                        "text": (d.body or "")[:max_chars_per_doc],
                    })

        rel_list = feature_meta.get("related_docs") or feature_meta.get("related")
        if isinstance(rel_list, list):
            for item in rel_list:
                if not item:
                    continue
                try:
                    rp = (feature_doc.path.parent / str(item)).resolve()
                except Exception:
                    continue
                for d in docs:
                    if d.path.resolve() == rp:
                        related.append({
                            "path": str(d.path),
                            "title": d.title,
                            "doc_type": d.meta.get("doc_type"),
                            "meta": d.meta,
                            "text": (d.body or "")[:max_chars_per_doc],
                        })
                        break

    # de-dup by path
    seen: set[str] = set()
    dedup: list[dict[str, Any]] = []
    for r in related:
        p = str(r.get("path"))
        if p in seen:
            continue
        seen.add(p)
        dedup.append(r)

    bundle = {
        "feature": {
            "path": str(feature_doc.path),
            "title": feature_doc.title,
            "doc_type": feature_meta.get("doc_type"),
            "meta": feature_meta,
            "text": (feature_doc.body or "")[:max_chars_per_doc],
        },
        "related": dedup,
    }
    return bundle



def _json_default(obj: Any) -> Any:
    """JSON serializer for prompt bundles (be permissive, preserve signal)."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    # Fall back to string to avoid hard failures on exotic types (e.g., YAML tags).
    return str(obj)

def bundle_to_json(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle, ensure_ascii=False, default=_json_default)