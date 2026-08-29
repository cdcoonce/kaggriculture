"""Tests for the shop-roster coupling instrument (kaggriculture#82).

The arithmetic in ``draw_days`` is the load-bearing part: it decides how many
of an episode's rng draws an occupancy-moving arm can possibly disturb, and
therefore how large the precision penalty on such a gate is. It is pinned
here against the engine's own ``_end_of_day`` logic rather than against a
remembered figure.
"""

from __future__ import annotations

import pytest
from harness.shop_roster import (
    DEFAULT_MAX_INSTANCES,
    DEFAULT_UNLOCK_INTERVAL,
    TURNS_PER_DAY,
    CouplingProfile,
    compare_profiles,
    draw_days,
    profile,
)


class _FakeEnv:
    """A 30-day episode whose bare-tile count changes WITHIN each day.

    ``bare_at(step_index)`` decides the board, so a sampler reading the wrong
    turn of the day reads a different number -- which is what makes the
    end-of-day sampling assertion below have teeth.
    """

    def __init__(self, bare_at, roster=None, n_days=30):
        self.steps = [
            [
                {
                    "observation": {
                        "farms": [
                            {"tiles": [[None] * bare_at(i)]},
                            {"tiles": [[{"kind": "WEED"}], ["LOCKED"]]},
                        ],
                        "town": {"unlocked_shops": list(roster or [])},
                    }
                }
            ]
            for i in range(n_days * TURNS_PER_DAY)
        ]


class TestDrawDays:
    def test_default_game_has_exactly_eight_draws(self):
        """30 days, interval 3, cap 8 -> the roster caps before the game ends.

        This is the whole bound: there are ten interval hits in a 30-day game
        (next_day 3,6,...,30) but only the first eight can draw, because
        ``len(unlocked_shops) < MAX_SHOP_INSTANCES`` fails from then on.
        """
        assert draw_days(30, DEFAULT_UNLOCK_INTERVAL, DEFAULT_MAX_INSTANCES) == [
            2,
            5,
            8,
            11,
            14,
            17,
            20,
            23,
        ]

    def test_no_draw_after_the_roster_caps(self):
        days = draw_days(30, DEFAULT_UNLOCK_INTERVAL, DEFAULT_MAX_INSTANCES)
        assert max(days) == 23
        assert all(d <= 23 for d in days)

    def test_days_are_end_of_day_indices_not_visible_days(self):
        """The draw is DECIDED at end-of-day d and VISIBLE from day d+1.

        Off-by-one here silently censuses the wrong day's bare-tile count,
        which is exactly the read the coupling depends on.
        """
        days = draw_days(30, DEFAULT_UNLOCK_INTERVAL, DEFAULT_MAX_INSTANCES)
        # next_day == day + 1 is what the engine tests against the interval.
        assert all((d + 1) % DEFAULT_UNLOCK_INTERVAL == 0 for d in days)

    def test_cap_binds_before_the_interval_runs_out(self):
        """A cap of 3 truncates to the first three interval hits."""
        assert draw_days(30, 3, 3) == [2, 5, 8]

    def test_interval_binds_when_the_cap_is_generous(self):
        """With no cap pressure every interval hit draws."""
        assert draw_days(12, 3, 99) == [2, 5, 8, 11]

    def test_short_game_can_leave_the_roster_unfilled(self):
        assert draw_days(6, 3, 8) == [2, 5]

    def test_interval_of_one_draws_every_day_until_the_cap(self):
        assert draw_days(30, 1, 8) == [0, 1, 2, 3, 4, 5, 6, 7]

    @pytest.mark.parametrize("bad", [0, -1])
    def test_non_positive_interval_is_rejected(self, bad):
        """The engine clamps with max(1, ...); mirroring that silently here
        would hide a caller passing nonsense."""
        with pytest.raises(ValueError):
            draw_days(30, bad, 8)

    def test_zero_cap_draws_nothing(self):
        assert draw_days(30, 3, 0) == []


class TestCompareProfiles:
    def _profile(self, bare_by_day):
        return CouplingProfile(bare_by_day=bare_by_day, roster=["BAKERY"])

    def test_identical_bare_counts_mean_no_coupling(self):
        a = self._profile({2: 28, 5: 49, 8: 38, 11: 60})
        b = self._profile({2: 28, 5: 49, 8: 38, 11: 60})
        result = compare_profiles(a, b)
        assert result.first_divergent_day is None
        assert result.coupled_draws == 0

    def test_late_divergence_bounds_the_coupled_draws(self):
        """The measured max_owned_quadrants 4-vs-3 shape: the first four
        draw-days agree, so only the last four draws can be disturbed."""
        a = self._profile({2: 28, 5: 49, 8: 38, 11: 60, 14: 50, 17: 77, 20: 49, 23: 76})
        b = self._profile({2: 28, 5: 49, 8: 38, 11: 60, 14: 45, 17: 52, 20: 36, 23: 60})
        result = compare_profiles(a, b)
        assert result.first_divergent_day == 14
        assert result.coupled_draws == 4

    def test_coupling_counts_every_draw_from_the_first_divergence(self):
        """Once the streams desync the cursor never re-aligns, so a draw-day
        that happens to match again is still downstream of a diverged stream
        and must NOT be subtracted from the count."""
        a = self._profile({2: 10, 5: 20, 8: 30, 11: 40})
        b = self._profile({2: 10, 5: 99, 8: 30, 11: 40})
        result = compare_profiles(a, b)
        assert result.first_divergent_day == 5
        assert result.coupled_draws == 3

    def test_divergence_on_the_first_draw_couples_everything(self):
        a = self._profile({2: 10, 5: 20, 8: 30})
        b = self._profile({2: 11, 5: 20, 8: 30})
        result = compare_profiles(a, b)
        assert result.first_divergent_day == 2
        assert result.coupled_draws == 3

    def test_mismatched_draw_days_are_rejected(self):
        """Comparing profiles sampled on different schedules would silently
        report a bound for a game that neither arm played."""
        a = self._profile({2: 10, 5: 20})
        b = self._profile({2: 10, 8: 20})
        with pytest.raises(ValueError):
            compare_profiles(a, b)

    def test_profile_samples_the_LAST_turn_of_each_draw_day(self):
        """The rng is consumed during end-of-day processing, so an hour-0 read
        measures a board a full day of planting and harvesting away from the
        one ``_spawn_weeds`` saw. Encode the hour, not just the day."""
        # Bare count == the turn's index within its day, so the first turn of
        # a day reads 0 and the last reads 23.
        env = _FakeEnv(lambda i: i % TURNS_PER_DAY)
        result = profile(env)
        assert set(result.bare_by_day) == {2, 5, 8, 11, 14, 17, 20, 23}
        assert all(v == TURNS_PER_DAY - 1 for v in result.bare_by_day.values())

    def test_profile_counts_bare_across_BOTH_farms(self):
        """_spawn_weeds runs for both players off the one rng before the shop
        draw, so it is the COMBINED count that positions the cursor."""
        env = _FakeEnv(lambda i: 4)
        # farm 0 contributes 4 None tiles; farm 1 contributes a WEED (a dict)
        # and a LOCKED (a str), neither of which the engine draws for.
        assert set(profile(env).bare_by_day.values()) == {4}

    def test_profile_reads_the_final_roster(self):
        env = _FakeEnv(lambda i: 1, roster=["BAKERY", "YARN_STORE"])
        assert sorted(profile(env).roster) == ["BAKERY", "YARN_STORE"]

    def test_roster_identity_is_reported_separately_from_coupling(self):
        """Rosters can coincide by luck (8 shop types, drawn with
        replacement) even on a diverged stream -- so an identical roster is
        NOT evidence that no coupling occurred."""
        a = CouplingProfile(bare_by_day={2: 10, 5: 20}, roster=["BAKERY", "PET_CAFE"])
        b = CouplingProfile(bare_by_day={2: 11, 5: 20}, roster=["PET_CAFE", "BAKERY"])
        result = compare_profiles(a, b)
        assert result.roster_identical is True
        assert result.coupled_draws == 2
