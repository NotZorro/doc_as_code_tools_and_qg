from __future__ import annotations

from .base import Capability
from .quality_gate import QualityGateCapability
from .test_design import TestDesignCapability
from .test_codegen import TestCodegenCapability
from .mockgen import MockGenCapability


def get_capabilities() -> list[Capability]:
    """Return built-in capabilities.

    Note: We keep this simple (no dynamic plugin loading) on purpose.
    Policy-defined extensions live in the docs repo; code extensions are rare.
    """

    return [
        QualityGateCapability(),
        TestDesignCapability(),
        TestCodegenCapability(),
        MockGenCapability(),
    ]
