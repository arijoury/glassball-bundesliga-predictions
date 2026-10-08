"""Walk-forward backtest: refit before every match week, predict only that week.

Hyperparameters are tuned on TUNE seasons; VALIDATION is touched once, at the end.
"""
import itertools
import sys

import numpy as np
import pandas as pd

from data import SEASONS, load_results
from model import DixonColes, Hyper, logloss, odds_to_probs, outcome_index, rps, brier

TUNE = ["1920", "2021", "2122", "2223", "2324", "2425"]
VALIDATION = ["2526"]


def promoted_in(results, season):
    prev = SEASONS[SEASONS.index(season) - 1]
    return set(results.query("Season == @season").HomeTeam) - set(results.query("Season == @prev").HomeTeam)


def walk_forward(results, seasons, hyper):
    """Returns one row per match with predicted Poisson rates (rho applied later)."""
    out = []
    for s in seasons:
        prom = promoted_in(results, s)
        season = results.query("Season == @s")
        weeks = season["Date"].dt.to_period("W-MON")  # weeks run Tue..Mon
        for wk, games in season.groupby(weeks):
            as_of = games["Date"].min().normalize()
            dc = DixonColes(hyper).fit(results, as_of, prom)
            for g in games.itertuples():
                d = dc.drivers(g.HomeTeam, g.AwayTeam)
                out.append({"Season": s, "Date": g.Date, "HomeTeam": g.HomeTeam, "AwayTeam": g.AwayTeam,
                            "FTHG": g.FTHG, "FTAG": g.FTAG, "lam_h": d["lambda_home"], "lam_a": d["lambda_away"],
                            "AvgCH": g.AvgCH, "AvgCD": g.AvgCD, "AvgCA": g.AvgCA})
    return pd.DataFrame(out)


def probs_from_rates(bt, rho):
    dc = DixonColes(Hyper(rho=rho))
    P = np.array([[np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()]
                  for M in (dc.score_matrix(h, a) for h, a in zip(bt.lam_h, bt.lam_a))])
    return P


def score(P, bt):
    o = outcome_index(bt.FTHG.to_numpy(), bt.FTAG.to_numpy())
    return {"rps": rps(P, o).mean(), "brier": brier(P, o).mean(), "logloss": logloss(P, o).mean(), "n": len(o)}


if __name__ == "__main__":
    results = load_results()
    grid = list(itertools.product([120, 180, 270, 365, 540, 730], [2, 5, 10, 20, 40], [0.0, 0.15, 0.3]))
    rows = []
    for i, (hl, pp, po) in enumerate(grid):
        bt = walk_forward(results, TUNE, Hyper(half_life_days=hl, prior_precision=pp,
                                               promoted_attack=-po, promoted_defence=po))
        for rho in [0.0, -0.05, -0.1]:
            rows.append({"half_life_days": hl, "prior_precision": pp, "promoted_offset": po, "rho": rho,
                         **score(probs_from_rates(bt, rho), bt)})
        print(f"{i + 1}/{len(grid)}", hl, pp, po, round(rows[-2]["rps"], 5), file=sys.stderr)
    res = pd.DataFrame(rows).sort_values("rps")
    res.to_csv("../outputs/backtest/tuning_grid.csv", index=False)
    print(res.head(15).to_string())
