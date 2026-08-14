"""tape-player opponent archetype — replays a fixed, observation-blind
action tape from a machine-local directory (zoo issue #59).

No test in this file may depend on the real
``~/.kaggriculture/tapes/thunder-719.json`` tape existing: every test builds
its own synthetic tape under ``tmp_path`` and points
``KAGGRICULTURE_TAPE_DIR`` at it via monkeypatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from harness.zoo import extended_zoo, gate_zoo
from harness.zoo.tape_player import discover_tapes, load_tape, make_tape_agent

PASS_ENTRY = {"farmer": ["PASS"], "hands": [], "market": []}


def _obs(step: int, num_hands: int, player: int = 0) -> dict[str, Any]:
    """A minimal observation shaped like what every other zoo member reads:
    ``obs["step"]`` and ``obs["farms"][obs["player"]]["hands"]`` (see
    harness.zoo.meta_clone / chaos_legal_random for the same accessors)."""
    return {
        "step": step,
        "player": player,
        "farms": [{"hands": [(0, 0)] * num_hands}],
    }


def _write_tape(tmp_path: Path, name: str, entries: list[Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(entries))
    return path


class TestLoadTape:
    def test_loads_a_valid_tape(self, tmp_path: Path) -> None:
        path = _write_tape(tmp_path, "ok.json", [PASS_ENTRY, PASS_ENTRY])
        tape = load_tape(path)
        assert tape == [PASS_ENTRY, PASS_ENTRY]

    def test_rejects_non_list_json(self, tmp_path: Path) -> None:
        path = _write_tape(tmp_path, "obj.json", {"not": "a list"})  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="list"):
            load_tape(path)

    def test_rejects_empty_list(self, tmp_path: Path) -> None:
        path = _write_tape(tmp_path, "empty.json", [])
        with pytest.raises(ValueError, match="empty"):
            load_tape(path)

    def test_rejects_non_dict_entry(self, tmp_path: Path) -> None:
        path = _write_tape(tmp_path, "bad_entry.json", [PASS_ENTRY, "not-a-dict"])
        with pytest.raises(ValueError, match="entry 1"):
            load_tape(path)

    def test_rejects_entry_missing_expected_keys(self, tmp_path: Path) -> None:
        path = _write_tape(tmp_path, "missing_keys.json", [{"farmer": ["PASS"]}])
        with pytest.raises(ValueError, match="missing keys"):
            load_tape(path)


class TestMakeTapeAgent:
    def test_replays_entries_in_order(self) -> None:
        tape = [
            {"farmer": ["NORTH"], "hands": [], "market": []},
            {"farmer": ["SOUTH"], "hands": [], "market": []},
        ]
        agent = make_tape_agent(tape)
        assert agent(_obs(step=0, num_hands=0))["farmer"] == ["NORTH"]
        assert agent(_obs(step=1, num_hands=0))["farmer"] == ["SOUTH"]

    def test_clips_step_index_past_the_end_of_the_tape(self) -> None:
        tape = [
            {"farmer": ["NORTH"], "hands": [], "market": []},
            {"farmer": ["SOUTH"], "hands": [], "market": [["SELL", "WHEAT", 5]]},
        ]
        agent = make_tape_agent(tape)
        far_future = agent(_obs(step=10_000, num_hands=0))
        assert far_future["farmer"] == ["SOUTH"]
        assert far_future["market"] == [["SELL", "WHEAT", 5]]

    def test_pads_hands_when_observation_has_more_hands_than_the_tape_entry(self) -> None:
        tape = [{"farmer": ["PASS"], "hands": [["EAST"]], "market": []}]
        agent = make_tape_agent(tape)
        action = agent(_obs(step=0, num_hands=3))
        assert action["hands"] == [["EAST"], ["PASS"], ["PASS"]]

    def test_truncates_hands_when_observation_has_fewer_hands_than_the_tape_entry(self) -> None:
        tape = [
            {
                "farmer": ["PASS"],
                "hands": [["EAST"], ["WEST"], ["NORTH"]],
                "market": [],
            }
        ]
        agent = make_tape_agent(tape)
        action = agent(_obs(step=0, num_hands=1))
        assert action["hands"] == [["EAST"]]

    def test_falls_back_to_all_pass_when_the_tape_entry_is_malformed(self) -> None:
        tape = [{"farmer": "not-a-list", "hands": "also-not-a-list", "market": None}]
        agent = make_tape_agent(tape)
        action = agent(_obs(step=0, num_hands=2))
        assert action == {"farmer": ["PASS"], "hands": [["PASS"], ["PASS"]], "market": []}

    def test_falls_back_to_all_pass_on_a_malformed_observation(self) -> None:
        tape = [{"farmer": ["NORTH"], "hands": [], "market": []}]
        agent = make_tape_agent(tape)
        action = agent({"nothing": "useful"})
        assert action == {"farmer": ["PASS"], "hands": [], "market": []}


class TestDiscoverTapes:
    def test_returns_empty_dict_for_a_missing_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "does-not-exist"
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(missing))
        assert discover_tapes() == {}

    def test_discovers_a_valid_tape_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        _write_tape(tmp_path, "thunder-719.json", [PASS_ENTRY])

        roster = discover_tapes()

        assert set(roster) == {"tape-thunder-719"}
        agent = roster["tape-thunder-719"]()
        assert callable(agent)
        assert agent(_obs(step=0, num_hands=0)) == PASS_ENTRY

    def test_skips_a_malformed_file_but_keeps_the_valid_ones(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        _write_tape(tmp_path, "good.json", [PASS_ENTRY])
        (tmp_path / "bad.json").write_text("{not valid json")
        _write_tape(tmp_path, "empty.json", [])

        roster = discover_tapes()

        assert set(roster) == {"tape-good"}
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_each_factory_call_returns_a_fresh_agent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        _write_tape(tmp_path, "thunder-719.json", [PASS_ENTRY])
        factory = discover_tapes()["tape-thunder-719"]
        assert factory() is not factory()


class TestZooRegistration:
    def test_gate_zoo_has_no_tape_members(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        _write_tape(tmp_path, "thunder-719.json", [PASS_ENTRY])
        assert not any(name.startswith("tape-") for name in gate_zoo())

    def test_extended_zoo_has_tape_members_when_tapes_are_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        _write_tape(tmp_path, "thunder-719.json", [PASS_ENTRY])
        assert "tape-thunder-719" in extended_zoo()

    def test_extended_zoo_has_no_tape_members_when_the_tape_dir_is_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path / "missing"))
        assert not any(name.startswith("tape-") for name in extended_zoo())
