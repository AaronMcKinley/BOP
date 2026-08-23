"""Ensure the project root is importable so `from simulation.physics import ...` works."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
