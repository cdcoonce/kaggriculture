"""Integrity contract for the preregistered public-leader opponent panel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PANEL = ROOT / "eval" / "opponents" / "public-leaders"


def test_public_leader_panel_is_pinned_and_independently_authored() -> None:
    panel = json.loads((PANEL / "panel.json").read_text(encoding="utf-8"))
    opponents = panel["opponents"]

    assert (PANEL / "LICENSE-APACHE-2.0.txt").is_file()
    assert len(opponents) == 3
    assert len({opponent["author_handle"] for opponent in opponents}) == 3
    assert all(opponent["public_score"] >= 2800 for opponent in opponents)
    assert all(opponent["license"] == "Apache-2.0" for opponent in opponents)
    assert all(opponent["is_public"] is True for opponent in opponents)

    for opponent in opponents:
        artifact = PANEL / opponent["artifact_path"]
        assert artifact.is_file()
        assert hashlib.sha256(artifact.read_bytes()).hexdigest() == opponent["artifact_sha256"]

        agent = PANEL / opponent["decoded_agent_path"]
        assert agent.is_file()
        assert hashlib.sha256(agent.read_bytes()).hexdigest() == opponent["decoded_agent_sha256"]
        compile(agent.read_bytes(), str(agent), "exec")


def test_registered_gate_is_exactly_the_authorized_two_stage_design() -> None:
    gate = json.loads((PANEL / "gate.json").read_text(encoding="utf-8"))

    assert gate["selection"] == {
        "seeds_per_opponent": 100,
        "both_seat_games_per_opponent": 200,
        "aggregate_uplift_min": 0.15,
        "per_opponent_uplift_min": 0.10,
        "absolute_aggregate_score_rate_min": 0.25,
        "each_seat_score_rate_strictly_greater_than": 0.15,
        "max_crashes": 0,
        "max_fallbacks": 0,
    }
    assert gate["confirmation"] == {
        "fresh_seeds_per_opponent": 250,
        "both_seat_games_per_opponent": 500,
        "aggregate_uplift_min": 0.15,
        "per_opponent_uplift_min": 0.10,
        "stratified_paired_95pct_lower_bound_strictly_greater_than": 0.10,
        "absolute_aggregate_score_rate_min": 0.30,
        "max_crashes": 0,
        "max_fallbacks": 0,
    }
    assert gate["integrity"] == {
        "selection_and_confirmation_seed_bands_disjoint": True,
        "opponent_independence_and_provenance_required": True,
        "any_miss_closes_whole_slice": True,
        "threshold_revisions_after_registration_allowed": False,
        "opponent_substitution_after_registration_allowed": False,
        "seed_band_reuse_allowed": False,
        "component_salvage_allowed": False,
    }
