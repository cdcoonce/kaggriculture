"""Safety-shell unit tests, including the teeth-check (gate-set decision #3):
the shell's crash-catching is proven against a policy that actually crashes.
"""

from __future__ import annotations

from typing import Any

import pytest
from agent.shell import pass_action, wrap


def test_wrapped_exception_becomes_pass() -> None:
    def exploding(obs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError("boom")

    assert wrap(exploding)({"step": 3}) == pass_action()


def test_malformed_returns_become_pass() -> None:
    for bad in (None, 42, "PASS", [], {"farmer": "PASS"}, {"farmer": []}, {"hands": []}):

        def policy(
            obs: dict[str, Any], config: dict[str, Any] | None = None, _bad: Any = bad
        ) -> Any:
            return _bad

        assert wrap(policy)({"step": 0}) == pass_action()


def test_valid_action_passes_through_with_defaults() -> None:
    def policy(obs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"farmer": ["PLANT", "WHEAT"], "market": [["BUY_SEED", "WHEAT", 1]]}

    out = wrap(policy)({"step": 1})
    assert out == {
        "farmer": ["PLANT", "WHEAT"],
        "hands": [],
        "market": [["BUY_SEED", "WHEAT", 1]],
    }


def test_teeth_unwrapped_policy_does_crash() -> None:
    """Teeth-check: the defect the shell guards against is real — an unwrapped
    crashing policy raises. If this stops raising, the shell test above is
    testing nothing."""

    def exploding(obs: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        exploding({"step": 3})
