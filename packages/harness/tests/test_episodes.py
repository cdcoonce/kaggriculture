"""Agent spec resolution and single-game execution (eval protocol, issue #4)."""

from __future__ import annotations

import pytest
from harness.episodes import classify_outcome, play_game, resolve_agent

TINY_CONFIG = {"episodeSteps": 48}


class TestResolveAgent:
    def test_builtin_prefix_strips_to_bare_string(self) -> None:
        assert resolve_agent("builtin:starter") == "starter"

    def test_unknown_spec_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="mystery"):
            resolve_agent("mystery")

    def test_champion_spec_returns_a_fresh_callable(self) -> None:
        agent = resolve_agent("champion")
        assert callable(agent)

    def test_champion_unshelled_spec_returns_a_fresh_callable(self) -> None:
        agent = resolve_agent("champion-unshelled")
        assert callable(agent)

    def test_zoo_prefix_resolves_a_plain_string_member(self) -> None:
        # "starter" is a BUILTIN_ANCHORS member that maps to itself.
        assert resolve_agent("zoo:starter") == "starter"

    def test_zoo_prefix_calls_a_factory_member(self) -> None:
        import harness.zoo as zoo_module

        zoo_module.SCRIPTED["_test_factory_member"] = lambda: "sentinel-agent"
        try:
            assert resolve_agent("zoo:_test_factory_member") == "sentinel-agent"
        finally:
            del zoo_module.SCRIPTED["_test_factory_member"]

    def test_champion_spec_forwards_agent_config_as_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Wiring test for the resolve_agent -> make_policy seam: the dict
        # handed to resolve_agent must arrive at make_policy as an actual
        # PolicyConfig, not get silently dropped.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent("champion", {"soft_budget_seconds": 0.0})
        assert captured["policy_config"] == policy_module.PolicyConfig(soft_budget_seconds=0.0)

    def test_champion_spec_with_no_agent_config_passes_none_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent("champion")
        assert captured["policy_config"] is None

    def test_agent_config_raises_for_builtin_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("builtin:starter", {"soft_budget_seconds": 0.0})

    def test_agent_config_raises_for_zoo_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("zoo:starter", {"soft_budget_seconds": 0.0})

    def test_agent_config_raises_for_frozen_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("frozen:m1", {"soft_budget_seconds": 0.0})

    def test_agent_config_raises_for_champion_unshelled_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("champion-unshelled", {"soft_budget_seconds": 0.0})


class TestClassifyOutcome:
    def test_candidate_wins_on_higher_money(self) -> None:
        assert classify_outcome(3000, 2000, candidate_crashed=False) == "win"

    def test_candidate_loses_on_lower_money(self) -> None:
        assert classify_outcome(2000, 3000, candidate_crashed=False) == "loss"

    def test_equal_money_is_a_tie(self) -> None:
        assert classify_outcome(3000, 3000, candidate_crashed=False) == "tie"

    def test_crash_is_a_loss_even_with_more_money(self) -> None:
        assert classify_outcome(5000, 100, candidate_crashed=True) == "loss"


class TestPlayGame:
    def test_seed_5_fixture_candidate_seat_0(self) -> None:
        row = play_game(
            seed=5,
            candidate_seat=0,
            candidate="builtin:starter",
            opponent="builtin:pass",
            extra_config=TINY_CONFIG,
        )
        assert row.seed == 5
        assert row.candidate_seat == 0
        assert row.candidate_money > 0
        assert row.opponent_money > 0
        assert row.candidate_crashed is False
        assert row.opponent_crashed is False
        assert row.outcome == "loss"

    def test_seed_5_fixture_candidate_seat_1_same_outcome(self) -> None:
        # Same matchup, seats swapped: the candidate (starter) still loses to
        # pass, from the candidate's perspective, regardless of which seat
        # it occupies.
        row = play_game(
            seed=5,
            candidate_seat=1,
            candidate="builtin:starter",
            opponent="builtin:pass",
            extra_config=TINY_CONFIG,
        )
        assert row.candidate_seat == 1
        assert row.candidate_money > 0
        assert row.opponent_money > 0
        assert row.candidate_crashed is False
        assert row.opponent_crashed is False
        assert row.outcome == "loss"
