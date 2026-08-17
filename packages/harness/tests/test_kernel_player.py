"""kernel-player opponent archetype -- plays a decoded action plan ported
from a published Kaggle competitor solution, self-repairing against the live
observation (see harness.zoo.kernel_player's module docstring for the full
design and, especially, the "Closure state" and "Fallback observability"
sections these tests exist to defend).

No test in this file may depend on the real
``~/.kaggriculture/kernels/sokolovsky-2883.json`` plan existing: every test
builds its own synthetic plan (under ``tmp_path`` when a discovered file is
needed) and points ``KAGGRICULTURE_KERNEL_DIR`` at it via monkeypatch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from harness.gate import opponent_digest
from harness.zoo import extended_zoo, gate_zoo
from harness.zoo.kernel_player import discover_kernels, kernel_path, load_plan, make_kernel_agent
from kaggle_environments import make

PASS_ENTRY = {"farmer": ["PASS"], "hands": [], "market": []}


def _write_plan(tmp_path: Path, name: str, entries: list[Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(entries))
    return path


def _minimal_plan(n: int = 4) -> list[dict[str, Any]]:
    return [dict(PASS_ENTRY) for _ in range(n)]


def _obs(
    step: int,
    *,
    player: int = 0,
    shed: dict[str, int] | None = None,
    town_shops: list[str] | None = None,
    farmer: list[int] | None = None,
    tiles: list[list[Any]] | None = None,
    num_hands: int = 0,
) -> dict[str, Any]:
    """A minimal engine-shaped observation carrying every field the ported
    repair passes read: ``step``/``player``/``farms[*].hands`` (same
    accessors as every other zoo member -- see harness.zoo.meta_clone /
    harness.zoo.tape_player), plus ``farms[*].tiles``/``farmer``,
    ``private.shed``/``inventories``, and ``town.unlocked_shops``."""
    if tiles is None:
        tiles = [[None for _ in range(10)] for _ in range(10)]
    farm = {
        "farmer": farmer or [9, 9],
        "hands": [(0, 0)] * num_hands,
        "tiles": tiles,
        "money": 1000.0,
    }
    return {
        "step": step,
        "player": player,
        "farms": [farm, farm],
        "town": {"unlocked_shops": town_shops or []},
        "private": {
            "seeds": {},
            "shed": shed or {},
            "inventories": [{} for _ in range(num_hands + 1)],
        },
        "market": {"prices": {}},
    }


def _synth_plan(steps: int = 720) -> list[dict[str, Any]]:
    """A deterministic, non-trivial plan: the farmer cycles through the four
    cardinal directions and a HIRE order lands once a day -- enough that a
    correctly-functioning agent's emitted actions are never all-PASS, without
    depending on the real (uncommitted) Sokolovsky plan."""
    directions = ["NORTH", "SOUTH", "EAST", "WEST"]
    plan = []
    for i in range(steps):
        market: list[list[Any]] = [["HIRE"]] if i % 24 == 0 else []
        plan.append({"farmer": [directions[i % 4]], "hands": [], "market": market})
    return plan


class TestLoadPlan:
    def test_loads_a_valid_plan(self, tmp_path: Path) -> None:
        path = _write_plan(tmp_path, "ok.json", [PASS_ENTRY, PASS_ENTRY])
        plan = load_plan(path)
        assert plan == [PASS_ENTRY, PASS_ENTRY]

    def test_rejects_non_list_json(self, tmp_path: Path) -> None:
        path = _write_plan(tmp_path, "obj.json", {"not": "a list"})  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="list"):
            load_plan(path)

    def test_rejects_empty_list(self, tmp_path: Path) -> None:
        path = _write_plan(tmp_path, "empty.json", [])
        with pytest.raises(ValueError, match="empty"):
            load_plan(path)

    def test_rejects_non_dict_entry(self, tmp_path: Path) -> None:
        path = _write_plan(tmp_path, "bad_entry.json", [PASS_ENTRY, "not-a-dict"])
        with pytest.raises(ValueError, match="entry 1"):
            load_plan(path)

    def test_rejects_entry_missing_expected_keys(self, tmp_path: Path) -> None:
        path = _write_plan(tmp_path, "missing_keys.json", [{"farmer": ["PASS"]}])
        with pytest.raises(ValueError, match="missing keys"):
            load_plan(path)


class TestDiscoverKernels:
    def test_returns_empty_dict_for_a_missing_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does-not-exist"
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(missing))
        assert discover_kernels() == {}

    def test_discovers_a_valid_plan_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())

        roster = discover_kernels()

        assert set(roster) == {"kernel-sokolovsky-2883"}
        agent = roster["kernel-sokolovsky-2883"]()
        assert callable(agent)
        assert agent(_obs(step=0))["farmer"] == ["PASS"]

    def test_skips_a_malformed_file_but_keeps_the_valid_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "good.json", _minimal_plan())
        (tmp_path / "bad.json").write_text("{not valid json")
        _write_plan(tmp_path, "empty.json", [])

        roster = discover_kernels()

        assert set(roster) == {"kernel-good"}
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_ignores_a_sibling_research_artifact_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mirrors the real layout: sokolovsky-2883.json sits next to a
        # sokolovsky-2883/ directory of research artifacts. A top-level
        # glob("*.json") must not be confused by the directory sharing a stem.
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())
        research_dir = tmp_path / "sokolovsky-2883"
        research_dir.mkdir()
        (research_dir / "notes.json").write_text(json.dumps(_minimal_plan()))

        roster = discover_kernels()

        assert set(roster) == {"kernel-sokolovsky-2883"}

    def test_each_factory_call_returns_a_fresh_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())
        factory = discover_kernels()["kernel-sokolovsky-2883"]
        assert factory() is not factory()


class TestZooRegistration:
    def test_gate_zoo_has_no_kernel_members(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())
        assert not any(name.startswith("kernel-") for name in gate_zoo())

    def test_extended_zoo_has_kernel_members_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())
        assert "kernel-sokolovsky-2883" in extended_zoo()

    def test_extended_zoo_has_no_kernel_members_when_the_kernel_dir_is_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path / "missing"))
        assert not any(name.startswith("kernel-") for name in extended_zoo())

    def test_registering_did_not_breach_the_gate_roster_cap(self) -> None:
        # kernel-player is extended-only (never gate_zoo()) precisely so it
        # can never be the member that breaches this cap.
        assert len(gate_zoo()) <= 10


class TestFactoryIsolation:
    """Teeth-check (d): two agents from two separate factory() calls must
    never see each other's lead/recovery state. The scenario below is
    designed to FAIL if that state were hoisted back to a module-level dict
    (even one keyed by seat, as the original submission's ``_LEAD_BOOK`` was)
    -- see this class's docstring-length comment inline for the exact
    mechanism, and the task report for the red-first run that confirmed it.
    """

    def _plan(self) -> list[dict[str, Any]]:
        plan = _minimal_plan(8)
        plan[5] = {"farmer": ["PASS"], "hands": [], "market": []}
        plan[6] = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", 10]]}
        return plan

    def _melon_sell(self, action: dict[str, Any]) -> list[Any] | None:
        for order in action["market"]:
            if isinstance(order, list) and len(order) >= 3 and order[:2] == ["SELL", "MELON"]:
                return order
        return None

    def test_lead_forward_state_does_not_leak_between_agents(self) -> None:
        plan = self._plan()
        agent1 = make_kernel_agent(plan)
        agent2 = make_kernel_agent(plan)

        # Step 5: agent1 has 10 MELON in the shed and no town pull, so it
        # pulls tomorrow's (step 6) SELL MELON 10 forward into today, and
        # remembers a "due" of 10 MELON at step 6 in ITS OWN lead-state.
        action1 = agent1(_obs(step=5, shed={"MELON": 10}))
        assert self._melon_sell(action1) == ["SELL", "MELON", 10]

        # Step 5, agent2: an empty shed, so nothing is pulled forward, and
        # agent2 never records any "due" quantity of its own. (The original
        # only ever writes due_step/due when something actually moved, so a
        # shared book would be left holding agent1's entry, untouched, by
        # this call.)
        action2 = agent2(_obs(step=5, shed={"MELON": 0}))
        assert self._melon_sell(action2) is None

        # Step 6, agent2 goes FIRST this time. agent2 never pulled anything
        # forward, so its own plan SELL MELON 10 at step 6 must survive
        # untouched. Under a shared module-level book, agent1's leftover
        # step-6 "due" entry would still be sitting there and would
        # incorrectly zero out agent2's real, un-pre-sold order.
        action2_next = agent2(_obs(step=6, shed={"MELON": 0}))
        assert self._melon_sell(action2_next) == ["SELL", "MELON", 10]

        # Step 6, agent1 goes second. It should settle its OWN step-6
        # due-book -- it sold those 10 MELON yesterday, so today's plan
        # SELL MELON 10 must be fully offset. Under a shared book, agent2's
        # step-6 call above would already have consumed (and cleared) the
        # due entry agent1 needs, leaving agent1's sale un-settled --
        # silently double-selling the same 10 MELON.
        action1_next = agent1(_obs(step=6, shed={"MELON": 0}))
        assert self._melon_sell(action1_next) is None


class TestFallbackTeeth:
    """Teeth-check (e): a full episode must not silently degrade to all-PASS.
    Reuses the same env.run machinery test_melon_dumper.py / test_meta_clone.py
    use for their own full-game checks."""

    @pytest.mark.slow
    def test_full_episode_never_falls_back_and_is_not_all_pass(self) -> None:
        plan = _synth_plan(720)
        agent = make_kernel_agent(plan)
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([agent, "pass"])

        assert agent.fallback_count == 0, (
            f"kernel-player fell back {agent.fallback_count} time(s); "
            f"last_error={agent.last_error!r}"
        )

        farmer_orders = [step[0].action.get("farmer") for step in env.steps[1:] if step[0].action]
        assert any(order != ["PASS"] for order in farmer_orders if order is not None), (
            "every emitted farmer order was PASS -- the opponent silently "
            "paralyzed instead of playing"
        )


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        def _run() -> Any:
            plan = _synth_plan(96)
            env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 96})
            env.run([make_kernel_agent(plan), "pass"])
            return env

        env1 = _run()
        env2 = _run()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        assert money1 == money2

        action1 = env1.steps[1][0].action  # type: ignore[attr-defined]
        action2 = env2.steps[1][0].action  # type: ignore[attr-defined]
        assert action1 == action2


class TestOpponentDigest:
    def test_kernel_digest_matches_hash_and_absent_stem_and_tape_are_unaffected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        plan_path = _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan())

        digest = opponent_digest("zoo:kernel-sokolovsky-2883")
        assert digest == "sha256:" + hashlib.sha256(plan_path.read_bytes()).hexdigest()

        assert opponent_digest("zoo:kernel-absent") is None
        assert opponent_digest("builtin:pass") is None
        assert opponent_digest("champion") is None
        assert opponent_digest("zoo:meta-clone") is None

        _write_plan(tmp_path, "sokolovsky-2883.json", _minimal_plan(6))
        assert opponent_digest("zoo:kernel-sokolovsky-2883") != digest

    def test_tape_digest_behavior_is_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        tape_entry = {"farmer": ["PASS"], "hands": [], "market": []}
        tape_path = tmp_path / "thunder-719.json"
        tape_path.write_text(json.dumps([tape_entry, tape_entry]))

        digest = opponent_digest("zoo:tape-thunder-719")
        assert digest == "sha256:" + hashlib.sha256(tape_path.read_bytes()).hexdigest()
        assert opponent_digest("zoo:tape-absent") is None


class TestKernelPathHelper:
    def test_kernel_path_matches_discovery(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_KERNEL_DIR", str(tmp_path))
        assert kernel_path("sokolovsky-2883") == tmp_path / "sokolovsky-2883.json"
