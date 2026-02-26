from __future__ import annotations

import argparse
import sys

from .capabilities import get_capabilities
from .capabilities.base import CapabilityContext


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="doc-quality", description="Doc Quality Gate engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Register all built-in capabilities.
    for cap in get_capabilities():
        cap.register(sub)
    return p


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    p = build_parser()
    args = p.parse_args(argv)

    cmd = getattr(args, "cmd", None)
    ctx = CapabilityContext(argv=list(argv))

    for cap in get_capabilities():
        # `argparse` stores subcommand name into args.cmd
        # and we additionally store capability routing hints in args._cap.
        if getattr(args, "_cap", None) == cap.name:
            sys.exit(int(cap.run(args, ctx)))

    # Fallback: should not happen if parsers are registered correctly.
    print(f"Unknown command: {cmd}", file=sys.stderr)
    sys.exit(2)


if __name__ == '__main__':
    main()
