"""Loading the pre-registered public-leader opponent panel as harness agents.

Covers the ``public:<id>`` agent spec (``harness.public_leaders``, wired into
``harness.episodes.resolve_agent``): kaggle-exact entrypoint selection via
``kaggle_environments.agent.get_last_callable``, a brand-new globals namespace
on every resolution (the harness reuses worker processes across games), the
SHA-256 provenance check against ``eval/opponents/public-leaders/panel.json``,
and end-to-end game smoke coverage against ``builtin:starter``.

The panel itself (its notebooks, decoded agents, and ``panel.json``) is
pinned for a registered experiment and is read-only from here -- see
``tests/test_public_leader_provenance.py`` for the panel's own integrity
contract. This file only exercises the NEW loading path.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from harness.episodes import play_game, resolve_agent
from kaggle_environments.agent import get_last_callable

PANEL_ROOT = Path(__file__).resolve().parents[3] / "eval" / "opponents" / "public-leaders"
PANEL_IDS = ("sokolovsky-v12", "rayk-v11", "kaito-v4")

# Seeds 900000-901249 are reserved for the registered demand-aware-seasonal-
# controller experiment (eval/prereg/2026-09-08-demand-aware-seasonal-controller.md).
# Never use anything in that band here.
SMOKE_SEED = 777001


def _panel_entry(agent_id: str) -> dict[str, Any]:
    panel = json.loads((PANEL_ROOT / "panel.json").read_text(encoding="utf-8"))
    opponents: list[dict[str, Any]] = panel["opponents"]
    return next(opponent for opponent in opponents if opponent["id"] == agent_id)


class TestEntrypointFidelity:
    """Requirement 1: select the callable exactly the way kaggle_environments
    does for a file agent, not "whichever function is named agent"."""

    @pytest.mark.parametrize("agent_id", PANEL_IDS)
    def test_resolves_to_whatever_kaggle_environments_would_pick(self, agent_id: str) -> None:
        entry = _panel_entry(agent_id)
        path = PANEL_ROOT / entry["decoded_agent_path"]
        oracle = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))

        fn = resolve_agent(f"public:{agent_id}")

        assert fn.__name__ == oracle.__name__

    def test_kaito_v4_last_callable_is_the_submission_wrapper_not_agent(self) -> None:
        # The specific gotcha this requirement exists to catch: kaito-v4/main.py
        # defines `agent` and then, AFTER it, a thin `_kaggle_submission_entrypoint`
        # wrapper. get_last_callable picks the LAST module-level callable, which
        # is the wrapper -- and that is what the live ladder actually runs. A
        # resolver that naively picked "the function named agent" would silently
        # run the wrong policy.
        fn = resolve_agent("public:kaito-v4")
        assert fn.__name__ == "_kaggle_submission_entrypoint"


class TestFreshNamespacePerResolution:
    """Requirement 2 (the most important one): the harness reuses worker
    processes across games, and all three panel files keep mutable
    module-level globals, so two resolutions of the same id must never share
    a globals dict -- a caching implementation must fail this test."""

    @pytest.mark.parametrize(
        ("agent_id", "global_name", "original_value"),
        [
            ("sokolovsky-v12", "_LAST_STEP", -1),
            ("rayk-v11", "_LAST_STEP", -1),
            ("kaito-v4", "_WEED_STATE", {0: {}, 1: {}}),
        ],
    )
    def test_mutating_one_resolutions_globals_does_not_leak_into_the_next(
        self, agent_id: str, global_name: str, original_value: object
    ) -> None:
        first = resolve_agent(f"public:{agent_id}")
        second = resolve_agent(f"public:{agent_id}")

        # Two independent resolutions never share a namespace object...
        assert first.__globals__ is not second.__globals__
        assert first.__globals__[global_name] == original_value

        # ...and mutating through one's __globals__ must not leak into a
        # resolution made AFTER the mutation -- the failure mode a cached
        # module object or a shared exec namespace would produce.
        first.__globals__[global_name] = "MUTATED-BY-TEST"

        third = resolve_agent(f"public:{agent_id}")

        assert third.__globals__ is not first.__globals__
        assert third.__globals__[global_name] == original_value


class TestNoDunderFile:
    """Requirement 4: mirror kaggle_environments, which execs file agents
    into a bare ``{}`` and never injects ``__file__``."""

    @pytest.mark.parametrize("agent_id", PANEL_IDS)
    def test_resolved_agent_has_no_dunder_file(self, agent_id: str) -> None:
        fn = resolve_agent(f"public:{agent_id}")
        assert "__file__" not in fn.__globals__


class TestProvenance:
    """Requirement 3: verify the decoded agent file's SHA-256 against
    panel.json before executing anything. Both refusal paths are exercised
    against a COPY in a tmp dir (via the KAGG_PUBLIC_LEADERS_ROOT override) --
    the pinned files under eval/opponents/public-leaders/ are never touched."""

    def test_unknown_id_raises_naming_the_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        shutil.copy(PANEL_ROOT / "panel.json", tmp_path / "panel.json")
        monkeypatch.setenv("KAGG_PUBLIC_LEADERS_ROOT", str(tmp_path))

        # Matched narrowly on purpose: resolve_agent's generic fallback
        # ("unknown agent spec: 'public:does-not-exist'") also contains the
        # substring "does-not-exist", so a loose match here would pass even
        # against a resolver that never wired up "public:" at all. Anchoring
        # on "unknown public leader id" proves THIS module's own id lookup
        # actually ran and rejected it.
        with pytest.raises(ValueError, match="unknown public leader id 'does-not-exist'"):
            resolve_agent("public:does-not-exist")

    def test_tampered_agent_file_fails_provenance_naming_expected_and_actual_hash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _panel_entry("sokolovsky-v12")
        shutil.copy(PANEL_ROOT / "panel.json", tmp_path / "panel.json")
        dest_dir = tmp_path / "sokolovsky-v12"
        dest_dir.mkdir()
        dest_file = dest_dir / "main.py"
        shutil.copy(PANEL_ROOT / entry["decoded_agent_path"], dest_file)

        # Tamper with the COPY only -- the pinned original is read-only.
        dest_file.write_bytes(dest_file.read_bytes() + b"\n# tampered\n")
        tampered_hash = hashlib.sha256(dest_file.read_bytes()).hexdigest()
        expected_hash = entry["decoded_agent_sha256"]
        assert tampered_hash != expected_hash

        monkeypatch.setenv("KAGG_PUBLIC_LEADERS_ROOT", str(tmp_path))

        with pytest.raises(ValueError) as excinfo:
            resolve_agent("public:sokolovsky-v12")

        message = str(excinfo.value)
        assert "sokolovsky-v12" in message
        assert expected_hash in message
        assert tampered_hash in message


class TestFileSpec:
    """The ``file:<repo-relative-path>`` spec (``harness.episodes.
    resolve_agent`` -> ``harness.public_leaders.resolve_file_agent``): an
    arbitrary single-file agent outside the pinned panel -- e.g. a local fork
    under ``forks/`` with no ``panel.json`` entry -- loaded with the same
    entrypoint-selection and fresh-namespace-per-resolution semantics as
    ``public:``, but with no SHA-256 provenance check.
    """

    _RELPATH = "eval/opponents/public-leaders/sokolovsky-v12/main.py"

    def test_resolves_to_whatever_kaggle_environments_would_pick(self) -> None:
        path = PANEL_ROOT / "sokolovsky-v12" / "main.py"
        oracle = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))

        fn = resolve_agent(f"file:{self._RELPATH}")

        assert fn.__name__ == oracle.__name__

    def test_fresh_namespace_per_resolution_not_cached(self) -> None:
        first = resolve_agent(f"file:{self._RELPATH}")
        second = resolve_agent(f"file:{self._RELPATH}")

        assert first.__globals__ is not second.__globals__
        assert first.__globals__["_LAST_STEP"] == -1

        # Mutating one resolution's globals must not leak into a resolution
        # made AFTER the mutation -- the failure mode a cache would produce.
        first.__globals__["_LAST_STEP"] = "MUTATED-BY-TEST"

        third = resolve_agent(f"file:{self._RELPATH}")
        assert third.__globals__ is not first.__globals__
        assert third.__globals__["_LAST_STEP"] == -1

    def test_no_dunder_file_in_resolved_globals(self) -> None:
        fn = resolve_agent(f"file:{self._RELPATH}")
        assert "__file__" not in fn.__globals__

    def test_missing_path_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_agent("file:eval/opponents/public-leaders/does-not-exist/main.py")


class TestPublicLeaderSmoke:
    """Requirement 6: one full game per panel id against builtin:starter,
    using the harness's own play_game (same function the gates use). Not the
    registered experiment's selection/confirmation gate -- that needs a real
    candidate and the reserved 900000-901249 seed bands; this only proves the
    opponent spec plays a complete, crash-free game and is genuinely strong.
    """

    @pytest.mark.slow
    @pytest.mark.parametrize("agent_id", PANEL_IDS)
    def test_plays_a_complete_game_and_beats_starter(self, agent_id: str) -> None:
        from kaggle_environments import make

        # The env's own default episodeSteps (kaggriculture.json) is 720; no
        # extra_config override is passed below, so this game runs the full
        # default length.
        assert make("kaggriculture").configuration.episodeSteps == 720

        row = play_game(
            seed=SMOKE_SEED,
            candidate_seat=0,
            candidate=f"public:{agent_id}",
            opponent="builtin:starter",
        )

        assert row.candidate_crashed is False
        assert row.opponent_crashed is False
        assert row.candidate_money > row.opponent_money * 2
