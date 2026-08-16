"""`uv run python -m harness.money_gate` — stdout contract and exit codes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from harness.episodes import GameRow
from harness.gate import GateResult, MoneyGateResult, SeedMoney
from harness.money_gate import main
from harness.stats import MoneyVerdict, gate_verdict, money_verdict

BASE_ARGV = [
    "--candidate",
    "champion",
    "--baseline",
    "champion",
    "--opponent",
    "zoo:tape-thunder-719",
    "--n-seeds",
    "10",
    "--seed-base",
    "940000",
    "--candidate-commit",
    "abc123",
]


def _fake_result(
    *, deltas: list[float], vetoes: tuple[str, ...] = (), threshold: float = 1000.0
) -> MoneyGateResult:
    seeds = list(range(940000, 940000 + len(deltas)))
    baseline_by_seed = {seed: 37167.0 + 1000.0 * (i % 5) for i, seed in enumerate(seeds)}
    candidate_by_seed = {seed: baseline_by_seed[seed] + deltas[i] for i, seed in enumerate(seeds)}

    def arm(by_seed: dict[int, float], spec: str) -> GateResult:
        rows = [
            GameRow(
                seed=seed,
                candidate_seat=seat,
                candidate_money=by_seed[seed],
                opponent_money=120000.0,
                outcome="loss",
                candidate_crashed=False,
                opponent_crashed=False,
            )
            for seed in seeds
            for seat in (0, 1)
        ]
        return GateResult(
            candidate=spec,
            opponent="zoo:tape-thunder-719",
            gate_type="money",
            n_seeds=len(seeds),
            seed_base=seeds[0],
            seeds=seeds,
            rows=rows,
            wins=0,
            losses=len(rows),
            ties=0,
            verdict=gate_verdict(wins=0, losses=len(rows), ties=0),
            any_candidate_crash=False,
            extra_config=None,
            agent_config=None,
            threshold=0.5,
        )

    verdict: MoneyVerdict = money_verdict(
        candidate_by_seed,
        baseline_by_seed,
        threshold=threshold,
        min_seeds=2,
        extra_vetoes=vetoes,
    )
    return MoneyGateResult(
        candidate="champion",
        agent_config=None,
        baseline="champion",
        baseline_agent_config=None,
        opponent="zoo:tape-thunder-719",
        opponent_digest="sha256:" + "ab" * 32,
        gate_type="money",
        n_seeds=len(seeds),
        seed_base=seeds[0],
        seeds=seeds,
        candidate_result=arm(candidate_by_seed, "champion"),
        baseline_result=arm(baseline_by_seed, "champion"),
        per_seed=[
            SeedMoney(
                seed=seed,
                candidate_money=candidate_by_seed[seed],
                baseline_money=baseline_by_seed[seed],
                delta=candidate_by_seed[seed] - baseline_by_seed[seed],
            )
            for seed in seeds
        ],
        money_verdict=verdict,
        opponent_mean_delta=-1234.5,
        min_opponent_money=110000.0,
        candidate_canary_ran=True,
        candidate_canary_crashed=False,
        baseline_canary_ran=False,
        baseline_canary_crashed=False,
        extra_config=None,
        threshold=threshold,
        alpha=0.05,
        min_seeds=2,
        catastrophic_tail_quantile=0.15,
        catastrophic_tail_floor=19000.0,
        degenerate_dispersion_ratio=0.05,
        candidate_money_floor=3000.0,
        opponent_money_floor=10000.0,
        degenerate_seed_fraction=0.25,
    )


def _patch(monkeypatch: pytest.MonkeyPatch, result: MoneyGateResult) -> list[dict[str, Any]]:
    import harness.money_gate as cli_module

    calls: list[dict[str, Any]] = []

    def fake_run_money_gate(*args: Any, **kwargs: Any) -> MoneyGateResult:
        calls.append({"args": args, "kwargs": kwargs})
        return result

    monkeypatch.setattr(cli_module, "run_money_gate", fake_run_money_gate)
    return calls


PASSING = [6000.0, 5200.0, 7100.0, 4900.0, 8000.0, 5500.0, 6400.0, 5800.0, 7300.0, 6100.0]
FAILING = [200.0, -400.0, 900.0, 1500.0, -800.0, 300.0, 1100.0, -100.0, 600.0, 250.0]
#: Bound clears the threshold; the lower tail is wiped out. At n=10 the
#: interpolation index is 0.15 * 9 = 1.35, so two seeds under the floor fire
#: it.
BLOCKED = [-30000.0] * 3 + [40000.0] * 7


class TestMoneyGateCli:
    def test_cli_prints_pass_and_exits_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch(monkeypatch, _fake_result(deltas=PASSING))

        exit_code = main([*BASE_ARGV, "--eval-dir", str(tmp_path)])

        output = capsys.readouterr().out
        assert exit_code == 0
        lines = output.splitlines()
        assert lines[0] == "candidate=champion agent_config=null"
        assert lines[1] == "baseline=champion baseline_agent_config=null"
        assert lines[2].startswith("opponent=zoo:tape-thunder-719 digest=sha256:")
        assert lines[3] == "seeds: base=940000 n=10"
        assert lines[4].startswith("canary: candidate=ran crashed=False baseline=skipped")
        assert lines[5].startswith("money: candidate_mean=")
        assert lines[6].startswith("bounds: t_lower=")
        assert lines[7].startswith("diagnostics: skew=")
        assert "n_regressed=0/10" in lines[7]
        assert lines[8] == "vetoes: none"
        assert lines[9] == "blockers: none"
        assert lines[10].startswith("ledger: ")
        assert lines[-1] == "PASS"

    def test_cli_prints_fail_and_exits_1_when_the_bound_misses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch(monkeypatch, _fake_result(deltas=FAILING))

        exit_code = main([*BASE_ARGV, "--eval-dir", str(tmp_path)])

        output = capsys.readouterr().out
        assert exit_code == 1
        assert output.splitlines()[-1] == "FAIL"
        assert "vetoes: none" in output

    def test_cli_prints_fail_and_exits_1_when_a_blocker_fires_on_a_clearing_bound(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Three of ten seeds lose $30,000 -- most of the measured bank --
        # while the mean bound clears $1,000. That is a sound measurement of
        # an unacceptable candidate, so it is FAIL (exit 1, keep tuning), NOT
        # INVALID (exit 2, rerun it).
        _patch(monkeypatch, _fake_result(deltas=BLOCKED))

        exit_code = main([*BASE_ARGV, "--eval-dir", str(tmp_path)])

        output = capsys.readouterr().out
        assert exit_code == 1
        assert output.splitlines()[-1] == "FAIL"
        assert "vetoes: none" in output
        assert "blockers: catastrophic_tail" in output
        assert "tail_quantile=-30000.0" in output
        assert "n_regressed=3/10" in output

    def test_cli_prints_invalid_and_exits_2_when_any_veto_fires(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch(monkeypatch, _fake_result(deltas=PASSING, vetoes=("candidate_crash",)))

        exit_code = main([*BASE_ARGV, "--eval-dir", str(tmp_path)])

        output = capsys.readouterr().out
        assert exit_code == 2
        assert output.splitlines()[-1] == "INVALID"
        assert "vetoes: candidate_crash" in output

    def test_cli_notes_a_large_negative_delta_as_silent_degradation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # A candidate faulting on 5-25% of turns banks money inside the
        # healthy range with every flag clean; the paired statistic is the
        # only thing that sees it, so the CLI has to name the possibility.
        _patch(monkeypatch, _fake_result(deltas=[-13240.0 + 100.0 * i for i in range(10)]))

        main([*BASE_ARGV, "--eval-dir", str(tmp_path)])

        output = capsys.readouterr().out
        assert "note: large negative delta is the signature of silent degradation" in output

    def test_cli_writes_a_ledger_entry_by_default_and_no_ledger_suppresses_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _patch(monkeypatch, _fake_result(deltas=PASSING))

        main([*BASE_ARGV, "--eval-dir", str(tmp_path)])
        written = sorted((tmp_path / "gates").glob("*-money.json"))
        assert len(written) == 1
        entry = json.loads(written[0].read_text(encoding="utf-8"))
        assert entry["identity"]["candidate_commit"] == "abc123"
        assert entry["money_verdict"]["passed"] is True
        assert f"ledger: {written[0]}" in capsys.readouterr().out

        other = tmp_path / "second"
        main([*BASE_ARGV, "--eval-dir", str(other), "--no-ledger"])
        assert not other.exists()
        assert "ledger: none" in capsys.readouterr().out

    def test_cli_forwards_parsed_config_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = _patch(monkeypatch, _fake_result(deltas=PASSING))

        main(
            [
                *BASE_ARGV,
                "--eval-dir",
                str(tmp_path),
                "--agent-config",
                '{"melon_tile_target": 16}',
                "--extra-config",
                '{"episodeSteps": 719}',
                "--workers",
                "4",
                "--threshold",
                "2500",
                "--no-canary",
                "--no-ledger",
            ]
        )

        kwargs = calls[0]["kwargs"]
        assert calls[0]["args"] == ("champion", "zoo:tape-thunder-719", 10, 940000)
        assert kwargs["agent_config"] == {"melon_tile_target": 16}
        assert kwargs["extra_config"] == {"episodeSteps": 719}
        assert kwargs["workers"] == 4
        assert kwargs["threshold"] == 2500.0
        assert kwargs["run_canary"] is False

    def test_cli_rejects_malformed_json_config_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch(monkeypatch, _fake_result(deltas=PASSING))
        for flag in ("--agent-config", "--baseline-agent-config", "--extra-config"):
            with pytest.raises(SystemExit):
                main([*BASE_ARGV, "--eval-dir", str(tmp_path), flag, "{not json"])
            with pytest.raises(SystemExit):
                main([*BASE_ARGV, "--eval-dir", str(tmp_path), flag, "[1, 2]"])
