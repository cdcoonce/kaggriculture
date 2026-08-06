"""Safety shell — the never-crash boundary around the policy.

A crashed or malformed-return agent gets a sticky ERROR status on Kaggle and
is never called again (frozen farm, near-certain loss), and the self-play
validation episode is all-or-nothing. The shell therefore guarantees that the
callable handed to the runner always returns a well-formed action dict, no
matter what the policy does.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Observation = dict[str, Any]
Action = dict[str, Any]
Policy = Callable[[Observation, dict[str, Any] | None], Action]


def pass_action() -> Action:
    """A fresh, always-legal action dict (never share a mutable global)."""
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _coerce(raw: Any) -> Action:
    """Return ``raw`` if it is a structurally valid action dict, else PASS."""
    if not isinstance(raw, dict):
        return pass_action()
    farmer = raw.get("farmer")
    hands = raw.get("hands", [])
    market = raw.get("market", [])
    if not isinstance(farmer, list) or not farmer:
        return pass_action()
    if not isinstance(hands, list) or not isinstance(market, list):
        return pass_action()
    return {"farmer": farmer, "hands": hands, "market": market}


def wrap(policy: Policy) -> Policy:
    """Wrap ``policy`` so exceptions and malformed returns become PASS.

    The wrapped callable never raises and always returns a dict the engine
    accepts. Timing discipline stays the policy's job (it must check elapsed
    time at loop boundaries); the shell's job is purely crash/shape safety.
    """

    def guarded(obs: Observation, config: dict[str, Any] | None = None) -> Action:
        try:
            return _coerce(policy(obs, config))
        except BaseException:
            return pass_action()

    return guarded
