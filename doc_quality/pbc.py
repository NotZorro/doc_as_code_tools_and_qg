from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PBCPaths:
    policy_root: Path
    pbc: str
    templates_dir: Path | None = None
    validators_dir: Path | None = None
    generators_dir: Path | None = None
    config_path: Path | None = None


def resolve_pbc_paths(
    *,
    policy_root: Path,
    pbc: str,
    templates_dir: Path | None = None,
    validators_dir: Path | None = None,
    generators_dir: Path | None = None,
    config_path: Path | None = None,
) -> PBCPaths:
    """Resolve policy-content directories for a given PBC.

    Supports both:
    - new layout: <policy_root>/pbc/<pbc>/{templates,validators,generators} and <policy_root>/pbc/<pbc>/config.yml
    - legacy layout: <policy_root>/{templates,validators,generators} and <policy_root>/config.yml
    """
    policy_root = policy_root.resolve()

    pbc_root = policy_root / "pbc" / pbc

    def pick_dir(explicit: Path | None, new_path: Path, legacy_path: Path) -> Path | None:
        if explicit is not None:
            return explicit
        if new_path.exists():
            return new_path
        if legacy_path.exists():
            return legacy_path
        return None

    tdir = pick_dir(templates_dir, pbc_root / "templates", policy_root / "templates")
    vdir = pick_dir(validators_dir, pbc_root / "validators", policy_root / "validators")
    gdir = pick_dir(generators_dir, pbc_root / "generators", policy_root / "generators")

    # Config: prefer explicit; else per-PBC config; else root config.yml
    if config_path is not None:
        cpath = config_path
    else:
        if (pbc_root / "config.yml").exists():
            cpath = pbc_root / "config.yml"
        elif (policy_root / "config.yml").exists():
            cpath = policy_root / "config.yml"
        else:
            cpath = policy_root / "config.yml"  # may not exist; caller will error clearly

    return PBCPaths(
        policy_root=policy_root,
        pbc=pbc,
        templates_dir=tdir,
        validators_dir=vdir,
        generators_dir=gdir,
        config_path=cpath,
    )
