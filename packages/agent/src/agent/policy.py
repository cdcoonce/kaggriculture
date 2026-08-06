"""Policy v0 — deliberate PASS placeholder.

Chassis v1 (wheat rush + goose + index-0 price-aware selling) replaces this
under TDD. The scaffold ships PASS so the pipeline is provable end to end.
"""

from __future__ import annotations

from typing import Any

from agent.shell import Action, Observation, pass_action
from agent.state import StateTracker


def make_policy() -> Any:
    """Build the policy callable with its episode-scoped tracker closed over."""
    tracker = StateTracker()

    def decide(obs: Observation, config: dict[str, Any] | None = None) -> Action:
        tracker.observe(obs)
        return pass_action()

    return decide
