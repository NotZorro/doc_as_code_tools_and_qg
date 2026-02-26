from __future__ import annotations

from typing import Any

from .base import RenderContext, Renderer


class TextRenderer:
    name = "text"

    def render(self, data: Any, ctx: RenderContext) -> str:
        return "" if data is None else str(data)
