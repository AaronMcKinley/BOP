"""seed_registry.py: track battle seeds that have already been used.

Both sides of the pipeline share this one file so a published seed is never
simulated again:

  * simulate.py  skips seeds already in the registry when rolling fresh
  * save.py      records the seed when a battle is saved

The registry lives at config/used_seeds.json as a plain JSON list of ints.
"""

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "used_seeds.json"


def load_used_seeds(path=None) -> list:
    """Seeds already used (sorted). Empty list if the file is missing/broken."""
    path = Path(path) if path is not None else DEFAULT_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return sorted(int(s) for s in data) if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return []


def record_seed(seed: int, path=None) -> bool:
    """Append a seed to the registry if it's not already there.

    Returns True when the registry changed (new seed recorded), False if the
    seed was already present.
    """
    path = Path(path) if path is not None else DEFAULT_PATH
    used = load_used_seeds(path)
    if seed in used:
        return False
    used.append(seed)
    used.sort()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(used, indent=2), encoding="utf-8")
    return True
