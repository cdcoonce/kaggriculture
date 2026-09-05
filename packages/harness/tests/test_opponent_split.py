"""Teeth for the opponent-money mechanism split (kaggriculture#82, the
2026-09-05 hand-mule-load successor registration).

Fast tests (1-5 below, plus the extra_config guard) build
``harness.settlement.Settlement`` fixtures by hand -- no engine, no tape.
Test 6 is the end-to-end teeth: it fails if settlement hooks, seat mapping,
or seat-averaging drift from ``harness.gate``'s reality.
"""

from __future__ import annotations

import pytest
from harness.opponent_split import (
    SeedSplit,
    bucket_seed,
    champion_traded_items,
    episode_opponent_flows,
    episode_residual,
    opponent_flows,
    split_ledger,
)
from harness.settlement import Settlement

# --- 1. opponent_flows -------------------------------------------------


def test_sell_revenue_and_buyback_cost_net_in_per_item_market():
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 0.0],
        revenue={0: {}, 1: {"WHEAT": 100.0}},
        spend={0: {}, 1: {"BUY_PRODUCT:WHEAT": 20.0, "BUY_SEED:WHEAT": 5.0}},
    )
    per_item_market, fixed_price_map = opponent_flows(settlement, opponent_seat=1)

    assert per_item_market == {"WHEAT": 80.0}
    assert fixed_price_map == {"BUY_SEED:WHEAT": -5.0}


def test_fixed_price_keys_are_negative_contributions():
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 0.0],
        spend={
            0: {},
            1: {
                "BUY_SEED:WHEAT": 10.0,
                "BUY_ANIMAL:COW": 400.0,
                "HIRE": 8.0,
                "BUY_LAND": 1000.0,
            },
        },
    )
    _, fixed_price_map = opponent_flows(settlement, opponent_seat=1)

    assert fixed_price_map == {
        "BUY_SEED:WHEAT": -10.0,
        "BUY_ANIMAL:COW": -400.0,
        "HIRE": -8.0,
        "BUY_LAND": -1000.0,
    }


def test_a_buyback_only_item_still_appears_in_per_item_market():
    """An item with only a BUY_PRODUCT cost and no SELL must still show up,
    priced as a pure negative -- not silently dropped for lack of a sell."""
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 0.0],
        revenue={0: {}, 1: {}},
        spend={0: {}, 1: {"BUY_PRODUCT:EGG": 15.0}},
    )
    per_item_market, _ = opponent_flows(settlement, opponent_seat=1)

    assert per_item_market == {"EGG": -15.0}


# --- 2. conservation helper ---------------------------------------------


def test_residual_is_zero_on_a_consistent_episode():
    # starting 3000 + 150 revenue - 50 seed spend = 3100
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 3100.0],
        revenue={0: {}, 1: {"WHEAT": 150.0}},
        spend={0: {}, 1: {"BUY_SEED:WHEAT": 50.0}},
    )
    residual = episode_residual(settlement, seat=1, final_money=3100.0, starting_money=3000.0)
    assert residual == 0.0


def test_residual_is_nonzero_when_the_spend_side_is_dropped():
    """Mutation teeth: drop a real flow (the spend side) and the identity
    must fail loudly rather than silently balancing."""
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 3100.0],
        revenue={0: {}, 1: {"WHEAT": 150.0}},
        spend={0: {}, 1: {}},  # the real $50 BUY_SEED spend is missing
    )
    residual = episode_residual(settlement, seat=1, final_money=3100.0, starting_money=3000.0)
    assert residual != 0.0
    assert residual == -50.0


# --- 3. champion_traded_items --------------------------------------------


def test_sell_only_and_buy_product_only_items_are_included_buy_seed_is_not():
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 0.0],
        revenue={0: {"WHEAT": 50.0}, 1: {}},
        spend={0: {"BUY_PRODUCT:EGG": 10.0, "BUY_SEED:MELON": 5.0}, 1: {}},
    )
    items = champion_traded_items([settlement], [0])

    assert items == {"WHEAT", "EGG"}
    assert "MELON" not in items


def test_traded_items_union_across_arms_and_seats():
    a = Settlement(seed=1, final_money=[0.0, 0.0], revenue={0: {"WHEAT": 1.0}, 1: {}})
    b = Settlement(seed=2, final_money=[0.0, 0.0], revenue={0: {}, 1: {"EGG": 1.0}})

    items = champion_traded_items([a, b], [0, 1])

    assert items == {"WHEAT", "EGG"}


def test_champion_traded_items_rejects_mismatched_lengths():
    settlement = Settlement(seed=1, final_money=[0.0, 0.0])
    with pytest.raises(ValueError):
        champion_traded_items([settlement, settlement], [0])


# --- 4. bucketing/diff arithmetic ----------------------------------------


def test_bucket_seed_seat_averages_then_arm_diffs_and_buckets_by_traded_items():
    # (per_item_market, fixed_price_map) per episode, opponent's seat.
    candidate_ep0 = ({"WHEAT": 100.0, "EGG": 5.0}, {"BUY_SEED:WHEAT": -10.0})
    candidate_ep1 = ({"WHEAT": 120.0, "EGG": 15.0}, {"BUY_SEED:WHEAT": -30.0})
    baseline_ep0 = ({"WHEAT": 40.0, "EGG": 2.0}, {"BUY_SEED:WHEAT": -5.0})
    baseline_ep1 = ({"WHEAT": 60.0, "EGG": 8.0}, {"BUY_SEED:WHEAT": -15.0})
    traded_items = {"WHEAT"}  # EGG is untraded

    result = bucket_seed(7, candidate_ep0, candidate_ep1, baseline_ep0, baseline_ep1, traded_items)

    # candidate WHEAT seat-avg (100+120)/2=110, baseline (40+60)/2=50, diff 60
    assert result.seed == 7
    assert result.traded_market == 60.0
    # candidate EGG seat-avg (5+15)/2=10, baseline (2+8)/2=5, diff 5
    assert result.untraded_market == 5.0
    # candidate fixed seat-avg -20, baseline -10, diff -10
    assert result.fixed_price == -10.0
    assert result.total == 55.0
    assert result.total == result.traded_market + result.untraded_market + result.fixed_price


def test_bucket_seed_arm_swap_flips_every_sign():
    """Mutation teeth: swapping candidate/baseline must flip every bucket."""
    candidate_ep0 = ({"WHEAT": 100.0}, {"BUY_SEED:WHEAT": -10.0})
    candidate_ep1 = ({"WHEAT": 120.0}, {"BUY_SEED:WHEAT": -30.0})
    baseline_ep0 = ({"WHEAT": 40.0}, {"BUY_SEED:WHEAT": -5.0})
    baseline_ep1 = ({"WHEAT": 60.0}, {"BUY_SEED:WHEAT": -15.0})
    traded_items = {"WHEAT"}

    forward = bucket_seed(1, candidate_ep0, candidate_ep1, baseline_ep0, baseline_ep1, traded_items)
    swapped = bucket_seed(1, baseline_ep0, baseline_ep1, candidate_ep0, candidate_ep1, traded_items)

    assert swapped.traded_market == -forward.traded_market
    assert swapped.untraded_market == -forward.untraded_market
    assert swapped.fixed_price == -forward.fixed_price
    assert swapped.total == -forward.total
    # sanity: the fixture actually moves money, so the flip is a real check.
    assert forward.total != 0.0


# --- 5. seat resolution ---------------------------------------------------


def test_episode_opponent_flows_maps_candidate_seat_to_the_other_seat():
    """Mutation teeth: using candidate_seat directly instead of
    1 - candidate_seat would read the WRONG seat's (asymmetric) flows here."""
    settlement = Settlement(
        seed=1,
        final_money=[0.0, 0.0],
        revenue={0: {"WHEAT": 999.0}, 1: {"EGG": 111.0}},
    )

    market_for_candidate_seat_0, _ = episode_opponent_flows(settlement, candidate_seat=0)
    market_for_candidate_seat_1, _ = episode_opponent_flows(settlement, candidate_seat=1)

    assert market_for_candidate_seat_0 == {"EGG": 111.0}
    assert market_for_candidate_seat_1 == {"WHEAT": 999.0}


# --- split_ledger guard (fast: raises before any replay) -----------------


def test_split_ledger_refuses_a_non_null_extra_config_before_any_replay():
    """extra_config replay is out of scope (play_with_settlement does not
    forward it), and this must fail LOUDLY before touching the engine, not
    silently replay under the wrong configuration."""
    ledger = {
        "identity": {
            "candidate": "champion",
            "opponent": "zoo:pass",
            "baseline": "champion",
            "agent_config": None,
            "baseline_agent_config": None,
            "extra_config": {"startingMoney": 5000},
        },
        "seed_manifest": {"seeds": [1]},
        "rows": [],
        "baseline_rows": [],
        "money_verdict": {"opponent_mean_delta": 0.0},
    }
    with pytest.raises(NotImplementedError):
        split_ledger(ledger)


# --- 6. end-to-end (slow, real engine, no tapes) --------------------------


@pytest.mark.slow
def test_split_ledger_matches_a_real_money_gate_ledger():
    """Play a real (tiny) money gate with harness.gate.run_money_gate, build
    a ledger dict from it exactly as harness.ledger.write_money_ledger does,
    and check split_ledger reproduces it: conservation holds on all four
    episodes, every row's opponent money matches, and the buckets sum to the
    ledger's own recorded opponent_mean_delta EXACTLY.
    """
    import json

    from harness.gate import run_money_gate
    from harness.ledger import write_money_ledger

    result = run_money_gate(
        candidate="champion",
        opponent="zoo:pass",
        n_seeds=1,
        seed_base=663400,
        baseline="champion",
        agent_config={"hand_mule_load": 20},
        baseline_agent_config=None,
        workers=1,
        run_canary=False,
    )

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = write_money_ledger(
            result, Path(tmp), candidate_commit="test", timestamp="19700101T000000Z"
        )
        ledger = json.loads(path.read_text(encoding="utf-8"))

    seen_progress: list[tuple[int, int]] = []
    split = split_ledger(ledger, progress=lambda i, n: seen_progress.append((i, n)))

    assert seen_progress == [(0, 1)]
    assert len(split.seeds) == 1
    assert isinstance(split.seeds[0], SeedSplit)
    assert split.seeds[0].seed == 663400

    seed = split.seeds[0]
    assert seed.total == seed.traded_market + seed.untraded_market + seed.fixed_price
    assert split.mean_total == seed.total
    assert split.mean_total == ledger["money_verdict"]["opponent_mean_delta"]
    assert split.max_residual == 0.0
