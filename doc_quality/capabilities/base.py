from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CapabilityContext:
    """Common runtime context passed to capabilities.

    For now it's minimal; we will extend it as more capabilities appear.
    """

    argv: list[str]


class Capability(Protocol):
    """A unit of work exposed through CLI.

    A capability is responsible for:
      - registering its CLI subcommands
      - executing based on parsed args
    """

    name: str

    def register(self, subparsers: argparse._SubParsersAction) -> None:  # type: ignore[name-defined]
        ...

    def run(self, args: argparse.Namespace, ctx: CapabilityContext) -> int:
        ...
