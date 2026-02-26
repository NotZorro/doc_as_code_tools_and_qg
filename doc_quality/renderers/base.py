from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RenderContext:
    """Renderer context.

    Renderers are intentionally simple: they get data + context and return text.
    If you need binary output later (e.g., images), extend this.
    """

    # Optional metadata
    feature_id: str | None = None
    source_path: str | None = None


class Renderer(Protocol):
    name: str

    def render(self, data: Any, ctx: RenderContext) -> str:
        ...
