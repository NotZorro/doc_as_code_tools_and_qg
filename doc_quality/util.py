from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path
from typing import Any, Iterable


_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def json_default(o: Any) -> Any:
    # YAML может превратить дату в datetime.date / datetime.datetime
    if isinstance(o, (_dt.date, _dt.datetime)):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(list(o))
    return str(o)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def iter_md_files(paths: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        pp = Path(p)
        if pp.is_file() and pp.suffix.lower() == ".md":
            out.append(pp)
        elif pp.is_dir():
            for f in pp.rglob("*.md"):
                # cheap ignores
                if any(part in {".git", ".venv", "node_modules", "reports"} for part in f.parts):
                    continue
                out.append(f)
    # stable order
    out = sorted({f.resolve() for f in out})
    return out


def read_paths_file(paths_file: Path) -> list[str]:
    lines = read_text(paths_file).splitlines()
    paths: list[str] = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        paths.append(ln)
    return paths


def env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v
