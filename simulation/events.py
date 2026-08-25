"""events.py: the battle-event library.

Events are small functions that reconfigure a Battle. A battle doesn't need
one: simulate.py can call a specific event, roll a random one (with a chance),
or none at all. Each event returns the dict it records in battle.events
(-> events.json) so downstream (renderer banner, announcer, future events) can
react.

Current events:
  sudden_death  - no NEW lifelines from a time on; the web can only shrink
  immunity      - no eliminations for a grace window (keeps short seeds alive)
  speed_boost   - the whole field surges for a few seconds

New events (walls, the musical drop) are one function + one entry in
RANDOM_EVENTS. sudden_death is deliberately left out of the random pool - it
is the scheduled battle backstop, not a random roll.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from simulation.physics import Battle


def sudden_death(battle: "Battle", at: Optional[float] = None) -> dict:
    """Stop NEW lifelines from `at` on (default: immediately). The web can only
    shrink, so the battle must resolve by decay. Scheduled - the battle emits
    the event when its time reaches `at`."""
    at = battle.time if at is None else at
    battle.sudden_death_at = at
    return {"type": "sudden_death", "t": at}


def immunity(battle: "Battle", seconds: float = 15.0) -> dict:
    """No eliminations for the next `seconds` - a grace window that stops a
    short seed from ending before the battle has a chance to develop."""
    battle.immunity_until = max(battle.immunity_until, battle.time + seconds)
    event = {"type": "immunity", "t": battle.time, "until": battle.immunity_until}
    battle.events.append(event)
    return event


def speed_boost(battle: "Battle", seconds: float = 10.0, mult: float = 1.5) -> dict:
    """The whole field moves at `mult` x its normal speed for `seconds`."""
    battle.speed_boost_mult = mult
    battle.speed_boost_until = max(battle.speed_boost_until, battle.time + seconds)
    event = {"type": "speed_boost", "t": battle.time,
             "until": battle.speed_boost_until}
    battle.events.append(event)
    return event


# Random-event pool. sudden_death is excluded on purpose (it is the scheduled
# backstop). Walls and the musical drop join here when they are designed.
RANDOM_EVENTS = {
    "immunity": immunity,
    "speed_boost": speed_boost,
}


def roll(battle: "Battle", rng: random.Random, chance: float = 0.1) -> Optional[dict]:
    """Roll a random event with probability `chance` (0..1).

    Returns the event dict, or None if the roll fails (or the pool is empty).
    Using the battle's own seeded rng keeps the roll deterministic per seed.
    """
    if not RANDOM_EVENTS or rng.random() >= chance:
        return None
    name = rng.choice(list(RANDOM_EVENTS))
    return RANDOM_EVENTS[name](battle)
