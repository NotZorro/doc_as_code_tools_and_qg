"""Renderers turn structured results into files.

We keep renderers in CORE so multiple capabilities can reuse them:
- quality gate reports (json)
- test-suite docs (md)
- future: junit, allure, contract stubs, etc.
"""

from .registry import get_renderer, list_renderers

__all__ = ["get_renderer", "list_renderers"]
