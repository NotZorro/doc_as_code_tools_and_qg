import sys
from pathlib import Path

# Some pytest setups use importlib mode and don't reliably prepend the repo root.
# Make imports deterministic.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
