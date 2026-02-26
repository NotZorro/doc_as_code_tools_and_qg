import sys
from pathlib import Path
from dataclasses import dataclass
import pytest
import json

# Make repo importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@dataclass
class DummyResp:
    content: str
    raw: dict

class _DummyClient:
    """LLM client stub for unit tests."""
    def __init__(self, outputs):
        self._it = iter(outputs)

    def chat(self, **kwargs):
        try:
            out = next(self._it)
        except StopIteration:
            out = "{}"
        return DummyResp(content=out, raw={})

@pytest.fixture
def DummyClient():
    return _DummyClient
