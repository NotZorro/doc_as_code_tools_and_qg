"""Capabilities (jobs) executed by the engine.

Historically this repository implemented a single capability: "quality gate".
As the tool grows (e.g. test-design generation), we keep the core CLI stable
while routing the actual work through capability modules.

This package provides a tiny registry used by the CLI.
"""

from .registry import get_capabilities

__all__ = ["get_capabilities"]
