"""Smoke tests for every CLI command, offline, on the frozen data snapshot."""
import json
from pathlib import Path

import pytest

from glassball.cli import main

SNAP = Path(__file__).resolve().parents[1] / "preregistration" / "2026-27" / "data" / "raw"
BASE = ["--data-dir", str(SNAP), "--fixtures-file", str(SNAP / "openligadb_bl1_2026_20261008.json"),
        "--season", "2026", "--as-of", "2026-10-08", "--sims", "500", "-q"]


@pytest.mark.parametrize("cmd", [
    ["overview"], ["winner"], ["table"], ["table", "--full"], ["matchday"], ["matchday", "5", "-v"],
    ["matchday", "all"], ["explain", "bayern", "bvb"], ["swing", "union", "--event", "relegated"],
    ["standings"], ["ratings", "-v"], ["teams"], ["winner", "--shift", "bayern:attack=-0.15"],
])
def test_command_runs(cmd, capsys):
    assert main(cmd + BASE) == 0
    assert capsys.readouterr().out.strip()


def test_json_and_csv(tmp_path, capsys):
    assert main(["table", "--json", "--csv", str(tmp_path / "t.csv")] + BASE) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 18 and abs(sum(r["title"] for r in rows) - 1) < 1e-9
    assert (tmp_path / "t.csv").read_text().count("\n") == 19


def test_plot(tmp_path):
    assert main(["explain", "bayern", "leipzig", "--plot", str(tmp_path / "e.png")] + BASE) == 0
    assert (tmp_path / "e.png").stat().st_size > 10_000 and (tmp_path / "e_sensitivity.png").exists()


def test_friendly_errors(capsys):
    assert main(["explain", "bayern", "borussia"] + BASE) == 2
    assert "Did you mean" in capsys.readouterr().err
    assert main(["winner", "--shift", "nonsense"] + BASE) == 2


@pytest.mark.parametrize("cmd", [
    ["winner", "--model", "gbm"], ["matchday", "--model", "gbm"], ["table", "--fixed-ratings"],
    ["winner", "--half-life", "120"], ["swing", "bvb", "--model", "gbm"],
])
def test_model_flags(cmd, capsys):
    assert main(cmd + BASE) == 0
    assert capsys.readouterr().out.strip()


def test_gbm_cannot_explain_or_shift(capsys):
    assert main(["explain", "bayern", "bvb", "--model", "gbm"] + BASE) == 2
    assert main(["winner", "--model", "gbm", "--shift", "bayern:attack=-0.1"] + BASE) == 2


def test_crowd_natural_experiment(capsys):
    assert main(["crowd", "--data-dir", str(SNAP), "-q"]) == 0
    out = capsys.readouterr().out
    assert "Crowd effect" in out and "yellow cards" in out


def test_crowd_estimate_is_stable():
    from glassball import causal
    r = causal.crowd_effect(2015, 2024, data_dir=SNAP)
    assert 0.05 < r["crowd_effect"] < 0.15 and r["home_adv_with_fans"] > r["home_adv_without_fans"]
