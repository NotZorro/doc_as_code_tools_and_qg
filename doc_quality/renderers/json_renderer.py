from __future__ import annotations

import json
from typing import Any

from ..util import json_default
from .base import RenderContext, Renderer


class JSONRenderer:
    name = "json"

    def render(self, data: Any, ctx: RenderContext) -> str:
        # Keep it stable: pretty JSON, UTF-8, custom fallback for non-serializable values.
        return json.dumps(data, ensure_ascii=False, indent=2, default=json_default)
