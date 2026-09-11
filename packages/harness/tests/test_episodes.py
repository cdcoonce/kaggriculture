"""Agent spec resolution and single-game execution (eval protocol, issue #4)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from harness.episodes import classify_outcome, play_game, resolve_agent
from harness.frozen import freeze_incumbent, frozen_package_name

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

    def test_zoo_prefix_resolves_an_extended_only_member(self) -> None:
        # Regression: resolve_agent looked members up in gate_zoo(), so every
        # EXTENDED-only member was unreachable by spec -- chaos-legal-random
        # (#39) had been unrunnable since it landed, and the nightly sweep the
        # zoo docstring describes could not have worked. Uses a real EXTENDED
        # member rather than a machine-local tape so the test is portable.
        import harness.zoo as zoo_module

        assert "chaos-legal-random" in zoo_module.EXTENDED
        assert "chaos-legal-random" not in zoo_module.gate_zoo()
        assert callable(resolve_agent("zoo:chaos-legal-random"))

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

    def test_champion_unshelled_spec_returns_a_fresh_callable(self) -> None:
        agent = resolve_agent("champion-unshelled")
        assert callable(agent)

    def test_champion_unshelled_forwards_agent_config_as_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent("champion-unshelled", {"soft_budget_seconds": 0.0})
        assert captured["policy_config"] == policy_module.PolicyConfig(soft_budget_seconds=0.0)

    def test_champion_unshelled_propagates_exceptions_unlike_champion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The whole point of "champion-unshelled": no agent.shell.wrap
        # boundary, so a raising policy call surfaces instead of degrading
        # to PASS the way the shelled "champion" spec would.
        import agent.policy as policy_module

        def raising_policy(obs: object, config: object = None) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            policy_module, "make_policy", lambda clock=None, policy_config=None: raising_policy
        )
        unshelled = resolve_agent("champion-unshelled")
        with pytest.raises(RuntimeError, match="boom"):
            unshelled(None)

        shelled = resolve_agent("champion")
        assert shelled(None) == {"farmer": ["PASS"], "hands": [], "market": []}

    def test_agent_config_raises_for_builtin_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("builtin:starter", {"soft_budget_seconds": 0.0})

    def test_agent_config_raises_for_zoo_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("zoo:starter", {"soft_budget_seconds": 0.0})

    def test_agent_config_raises_for_public_spec(self) -> None:
        with pytest.raises(ValueError, match="champion"):
            resolve_agent("public:kaito-v4", {"soft_budget_seconds": 0.0})

    def test_frozen_spec_accepts_an_agent_config(self) -> None:
        """A frozen incumbent is tunable, because an A/B on a CODE change has
        to be run at the same knob setting on both arms.

        ``agent_config`` used to raise for every non-champion spec, which made
        a whole class of gate unrunnable: a code change measured at a
        non-default knob could only be compared against a baseline pinned at
        the DEFAULT, which prices the knob and the code change together and
        then attributes the sum to the code. The rule the original guard
        protected -- an override that cannot take effect must be loud, never
        silently dropped -- is what the next test pins.

        That the override actually reaches the frozen policy's decisions is
        proved behaviourally, not here: the gate protocol in
        eval/prereg/2026-08-28-strawberry-zone-fallthrough-seed.md requires the
        frozen incumbent to reproduce its build's occupancy signature at the
        arm being gated before any seed is burned.
        """
        root = Path(__file__).resolve().parents[3]
        dest = root / "eval" / "frozen"
        name = "cfgprobe"
        freeze_incumbent("HEAD", name, root, dest)
        try:
            agent = resolve_agent(f"frozen:{name}", {"strawberry_tile_target": 31})
            assert callable(agent)
        finally:
            shutil.rmtree(dest / frozen_package_name(name), ignore_errors=True)

    def test_agent_config_coerces_a_strawberry_frame_list_to_a_tuple(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # JSON has no tuple type, so a CLI --agent-config
        # '{"strawberry_frame_quadrants": ["SW"]}' arrives here as a Python
        # list. A list is unhashable (crashes any @cache function it reaches,
        # and PolicyConfig's own generated __hash__ along with it) and never
        # equals the tuple default, so PolicyConfig must coerce it before it
        # goes anywhere near constants.strawberry_tiles_for_frame/
        # target_tiles.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent("champion", {"strawberry_frame_quadrants": ["SW"]})

        config = captured["policy_config"]
        assert isinstance(config, policy_module.PolicyConfig)
        assert config.strawberry_frame_quadrants == ("SW",)
        assert isinstance(config.strawberry_frame_quadrants, tuple)
        hash(config)  # must not raise TypeError: unhashable type: 'list'

    def test_agent_config_rejects_an_unknown_quadrant_name(self) -> None:
        with pytest.raises(ValueError, match="XX"):
            resolve_agent("champion", {"strawberry_frame_quadrants": ["XX"]})

    def test_agent_config_rejects_an_unknown_strawberry_fert_reserve_value(self) -> None:
        with pytest.raises(ValueError, match="strawberry_fert_reserve"):
            resolve_agent("champion", {"strawberry_fert_reserve": "bogus"})

    def test_agent_config_flows_strawberry_fert_reserve_and_priority_to_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The other JSON-shaped-config wiring proof, alongside the
        # strawberry_frame_quadrants coercion test above: a CLI --agent-config
        # '{"strawberry_fert_reserve": "planted", "strawberry_plant_priority": 2}'
        # must reach make_policy as an actual PolicyConfig with both fields
        # set, not get silently dropped or partially applied.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent(
            "champion",
            {"strawberry_fert_reserve": "planted", "strawberry_plant_priority": 2},
        )

        config = captured["policy_config"]
        assert isinstance(config, policy_module.PolicyConfig)
        assert config.strawberry_fert_reserve == "planted"
        assert config.strawberry_plant_priority == 2

    def test_agent_config_flows_all_three_labor_knobs_to_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The JSON-shaped-config wiring proof for the labor knobs (kaggriculture
        # diagnosis, 2026-09-11): a CLI --agent-config
        # '{"max_hires_per_turn": 10, "wheat_plant_priority": 2,
        # "wheat_plant_hour_cutoff": 22}' must reach make_policy as an actual
        # PolicyConfig with all three fields set, not get silently dropped or
        # partially applied -- mirrors
        # test_agent_config_flows_strawberry_fert_reserve_and_priority_to_policy_config
        # above.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent(
            "champion",
            {
                "max_hires_per_turn": 10,
                "wheat_plant_priority": 2,
                "wheat_plant_hour_cutoff": 22,
            },
        )

        config = captured["policy_config"]
        assert isinstance(config, policy_module.PolicyConfig)
        assert config.max_hires_per_turn == 10
        assert config.wheat_plant_priority == 2
        assert config.wheat_plant_hour_cutoff == 22

    def test_agent_config_rejects_an_out_of_range_labor_knob(self) -> None:
        with pytest.raises(ValueError, match="max_hires_per_turn"):
            resolve_agent("champion", {"max_hires_per_turn": 0})

    def test_agent_config_flows_extra_hands_to_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The JSON-shaped-config wiring proof for extra_hands (labor SUPPLY,
        # kaggriculture diagnosis 2026-09-11 continuation of the labor knobs
        # above): a CLI --agent-config '{"extra_hands": 2}' must reach
        # make_policy as an actual PolicyConfig with the field set, not get
        # silently dropped -- mirrors
        # test_agent_config_flows_all_three_labor_knobs_to_policy_config
        # above.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent("champion", {"extra_hands": 2})

        config = captured["policy_config"]
        assert isinstance(config, policy_module.PolicyConfig)
        assert config.extra_hands == 2

    def test_agent_config_rejects_an_out_of_range_extra_hands(self) -> None:
        with pytest.raises(ValueError, match="extra_hands"):
            resolve_agent("champion", {"extra_hands": 6})
        with pytest.raises(ValueError, match="extra_hands"):
            resolve_agent("champion", {"extra_hands": -1})

    def test_agent_config_flows_ne_land_min_day_and_animal_buy_order_to_policy_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The JSON-shaped-config wiring proof for the two opening knobs
        # (kaggriculture, 2026-09-11): a CLI --agent-config
        # '{"ne_land_min_day": 6, "animal_buy_order": ["SHEEP", "COW"]}' must
        # reach make_policy as an actual PolicyConfig with both fields set,
        # not get silently dropped or partially applied -- mirrors
        # test_agent_config_flows_all_three_labor_knobs_to_policy_config
        # above. animal_buy_order also arrives as a JSON list (no tuple type
        # in JSON), so this doubles as the coercion proof through the real
        # resolve_agent path, the same way
        # test_agent_config_coerces_a_strawberry_frame_list_to_a_tuple checks
        # strawberry_frame_quadrants.
        import agent.policy as policy_module

        captured: dict[str, object] = {}

        def fake_make_policy(clock: object = None, policy_config: object = None) -> object:
            captured["policy_config"] = policy_config
            return lambda obs, config=None: {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(policy_module, "make_policy", fake_make_policy)
        resolve_agent(
            "champion",
            {"ne_land_min_day": 6, "animal_buy_order": ["SHEEP", "COW"]},
        )

        config = captured["policy_config"]
        assert isinstance(config, policy_module.PolicyConfig)
        assert config.ne_land_min_day == 6
        assert config.animal_buy_order == ("SHEEP", "COW")
        assert isinstance(config.animal_buy_order, tuple)
        hash(config)  # must not raise TypeError: unhashable type: 'list'

    def test_agent_config_rejects_an_out_of_range_ne_land_min_day(self) -> None:
        with pytest.raises(ValueError, match="ne_land_min_day"):
            resolve_agent("champion", {"ne_land_min_day": -1})
        with pytest.raises(ValueError, match="ne_land_min_day"):
            resolve_agent("champion", {"ne_land_min_day": 30})

    def test_agent_config_rejects_a_non_permutation_animal_buy_order(self) -> None:
        with pytest.raises(ValueError, match="animal_buy_order"):
            resolve_agent("champion", {"animal_buy_order": ["COW", "COW"]})
        with pytest.raises(ValueError, match="animal_buy_order"):
            resolve_agent("champion", {"animal_buy_order": ["COW"]})

    def test_frozen_spec_raises_on_a_knob_its_own_build_never_had(self) -> None:
        """The guard that matters, kept. A frozen package that predates the
        knob it is handed must reject it LOUDLY, naming the frozen package --
        never run the baseline at defaults and report a delta that is really
        the knob."""
        root = Path(__file__).resolve().parents[3]
        dest = root / "eval" / "frozen"
        name = "cfgprobe2"
        freeze_incumbent("HEAD", name, root, dest)
        try:
            with pytest.raises(TypeError, match="cfgprobe2"):
                resolve_agent(f"frozen:{name}", {"knob_that_never_existed": 1})
        finally:
            shutil.rmtree(dest / frozen_package_name(name), ignore_errors=True)


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
