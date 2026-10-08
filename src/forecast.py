"""Produce a full forecast snapshot: every remaining match + the final table.

    python forecast.py --as-of 2026-10-08 --fixtures ../data/raw/openligadb_bl1_2026_20261008.json --out ../freeze/2026-10-08

The same script is re-run after every matchday (rolling forecasts) with the
model specification unchanged; only the data cut-off moves.
"""
import argparse
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import sklearn

import ml
from data import SEASONS, load_fixtures, load_results
from model import MAX_GOALS, DixonColes, Hyper

N_SIMS, SEED = 20_000, 20261008
SEASON = "2627"


def current_table(played: pd.DataFrame, teams) -> pd.DataFrame:
    t = pd.DataFrame(0, index=sorted(teams), columns=["P", "W", "D", "L", "GF", "GA", "Pts"])
    for g in played.itertuples():
        hg, ag = int(g.FTHG), int(g.FTAG)
        for team, gf, ga in [(g.HomeTeam, hg, ag), (g.AwayTeam, ag, hg)]:
            t.loc[team, ["P", "GF", "GA"]] += [1, gf, ga]
            res = "W" if gf > ga else "D" if gf == ga else "L"
            t.loc[team, res] += 1
            t.loc[team, "Pts"] += {"W": 3, "D": 1, "L": 0}[res]
    t["GD"] = t.GF - t.GA
    return t.sort_values(["Pts", "GD", "GF"], ascending=False)


def simulate_table(dc: DixonColes, table: pd.DataFrame, remaining: pd.DataFrame, rng) -> pd.DataFrame:
    """Monte Carlo seasons. Each simulated season draws its own team ratings from the
    Laplace posterior, so rating uncertainty (not just match randomness) is propagated."""
    teams = list(table.index)
    ti = {t: i for i, t in enumerate(teams)}
    idx, T = dc._idx()
    hi = np.array([idx[t] for t in remaining.HomeTeam]); ai = np.array([idx[t] for t in remaining.AwayTeam])
    hs = np.array([ti[t] for t in remaining.HomeTeam]); as_ = np.array([ti[t] for t in remaining.AwayTeam])
    n_fx, G = len(remaining), MAX_GOALS + 1
    g = np.arange(G)
    from scipy.stats import poisson
    rho = dc.hyper.rho

    positions = np.zeros((len(teams), len(teams)), dtype=np.int64)
    pts_sum = np.zeros(len(teams))
    chunk = 1000
    for start in range(0, N_SIMS, chunk):
        m = min(chunk, N_SIMS - start)
        th = rng.multivariate_normal(dc.theta, dc.cov, size=m)                     # (m, P)
        lh = np.exp(th[:, [0]] + th[:, [1]] + th[:, 2 + hi] + th[:, 2 + T + ai])   # (m, n_fx)
        la = np.exp(th[:, [0]] + th[:, 2 + ai] + th[:, 2 + T + hi])
        M = poisson.pmf(g, lh[..., None])[..., :, None] * poisson.pmf(g, la[..., None])[..., None, :]
        M[..., 0, 0] *= 1 - lh * la * rho; M[..., 0, 1] *= 1 + lh * rho
        M[..., 1, 0] *= 1 + la * rho;      M[..., 1, 1] *= 1 - rho
        M = M.reshape(m, n_fx, G * G); M /= M.sum(-1, keepdims=True)
        u = rng.random((m, n_fx, 1))
        k = (M.cumsum(-1) < u).sum(-1).clip(max=G * G - 1)
        hg, ag = k // G, k % G

        pts = np.tile(table.Pts.to_numpy(float), (m, 1)); gd = np.tile(table.GD.to_numpy(float), (m, 1))
        gf = np.tile(table.GF.to_numpy(float), (m, 1))
        ph = np.where(hg > ag, 3, np.where(hg == ag, 1, 0)); pa = np.where(ag > hg, 3, np.where(hg == ag, 1, 0))
        rows = np.arange(m)[:, None]
        np.add.at(pts, (rows, hs), ph); np.add.at(pts, (rows, as_), pa)
        np.add.at(gd, (rows, hs), hg - ag); np.add.at(gd, (rows, as_), ag - hg)
        np.add.at(gf, (rows, hs), hg); np.add.at(gf, (rows, as_), ag)
        key = pts * 1e6 + (gd + 500) * 1e3 + gf + rng.random(pts.shape) * 1e-3  # Pts > GD > GF > coin
        rank = (-key).argsort(1).argsort(1)
        for p in range(len(teams)):
            positions[:, p] += (rank == p).sum(0)
        pts_sum += pts.sum(0)

    pos = positions / N_SIMS
    out = pd.DataFrame(pos, index=teams, columns=[f"pos_{i + 1}" for i in range(len(teams))])
    out.insert(0, "exp_points", pts_sum / N_SIMS)
    out.insert(1, "exp_position", (pos * np.arange(1, len(teams) + 1)).sum(1))
    out.insert(2, "p_title", pos[:, 0])
    out.insert(3, "p_top4", pos[:, :4].sum(1))
    out.insert(4, "p_top6", pos[:, :6].sum(1))
    out.insert(5, "p_playoff16", pos[:, 15])
    out.insert(6, "p_relegated", pos[:, 16:].sum(1))
    return out.sort_values("exp_points", ascending=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    as_of, out = pd.Timestamp(a.as_of), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    results = load_results()
    fixtures = load_fixtures(Path(a.fixtures))
    played = fixtures[fixtures.Finished & (fixtures.Kickoff.dt.tz_localize(None) < as_of)]
    remaining = fixtures[~fixtures.index.isin(played.index)].reset_index(drop=True)
    teams = set(fixtures.HomeTeam)
    promoted = teams - set(results.query("Season == @SEASONS[-2]").HomeTeam)

    # Glass box
    dc = DixonColes(Hyper()).fit(results, as_of, promoted)
    match = dc.predict(remaining)

    # Contrast GBM: trained on every completed match since 2013/14 (2012/13 = Elo burn-in)
    feats, state = ml.build(results, as_of)
    train = feats[feats.Season > "1213"]
    gbm = ml.make_model().fit(train[ml.FEATURES], ml.label(train))
    match = match.merge(ml.predict_fixtures(gbm, state, remaining)[["MatchID", "ml_pH", "ml_pD", "ml_pA"]], on="MatchID")
    match.drop(columns=["Finished", "FTHG", "FTAG"]).to_csv(out / "match_forecasts.csv", index=False, float_format="%.4f")

    dc.ratings().query("team in @teams").to_csv(out / "team_ratings.csv", index=False, float_format="%.4f")
    table = current_table(played, teams)
    table.to_csv(out / "table_at_cutoff.csv")
    sim = simulate_table(dc, table, remaining, np.random.default_rng(SEED))
    sim.to_csv(out / "table_forecast.csv", float_format="%.4f")

    meta = {"as_of": str(as_of.date()), "matches_played": int(len(played)), "matches_forecast": int(len(remaining)),
            "training_matches_glass_box": dc.n_matches, "training_matches_gbm": int(len(train)),
            "hyper": vars(dc.hyper), "base": float(dc.theta[0]), "home_adv": float(dc.theta[1]),
            "n_sims": N_SIMS, "seed": SEED, "promoted": sorted(promoted),
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                         "scipy": scipy.__version__, "sklearn": sklearn.__version__}}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(sim[["exp_points", "exp_position", "p_title", "p_top4", "p_relegated"]].round(3).to_string())


if __name__ == "__main__":
    main()
