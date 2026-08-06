"""Per-episode state tracking.

The runner may reuse a process across episodes, so the tracker resets itself
whenever it sees step 0 (runner-facts decision, issue #15). Chassis v1 will
grow this into full state reconstruction (opponent census, market deltas).
"""

from __future__ import annotations

from typing import Any


class StateTracker:
    """Minimal episode-scoped memory with a step-0 reset guard."""

    def __init__(self) -> None:
        self.episode_turns: int = 0
        self.last_step: int = -1

    def observe(self, obs: dict[str, Any]) -> None:
        step = int(obs.get("step", 0))
        if step == 0 or step < self.last_step:
            self.reset()
        self.last_step = step
        self.episode_turns += 1

    def reset(self) -> None:
        self.episode_turns = 0
        self.last_step = -1
