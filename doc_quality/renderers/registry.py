from __future__ import annotations

from .base import Renderer
from .coverage_md_v1 import CoverageMarkdownV1Renderer
from .json_renderer import JSONRenderer
from .test_suite_md_v1 import TestSuiteMarkdownV1Renderer
from .text_renderer import TextRenderer


_BUILTINS: list[Renderer] = [
    JSONRenderer(),
    TextRenderer(),
    TestSuiteMarkdownV1Renderer(),
    CoverageMarkdownV1Renderer(),
]


def get_renderer(name: str) -> Renderer:
    for r in _BUILTINS:
        if r.name == name:
            return r
    raise KeyError(f"Unknown renderer: {name}")


def list_renderers() -> list[str]:
    return sorted({r.name for r in _BUILTINS})
