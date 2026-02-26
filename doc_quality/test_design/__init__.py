"""Test design helpers (B1 Map→Reduce).

This package contains deterministic planning/merging utilities used by the
`test-design` capability.

Design goals:
- deterministic selection and chunking (no hidden magic)
- bounded prompts/output sizes
- reproducible merge + coverage computation
"""

from .plan import ExecutionPlan, Job, Part, BundleDoc, build_split_plan
from .merge import merge_group_fragments
from .coverage import compute_coverage

__all__ = [
    "ExecutionPlan",
    "Job",
    "Part",
    "BundleDoc",
    "build_split_plan",
    "merge_group_fragments",
    "compute_coverage",
]
