"""Two causal questions the data can actually answer, and how.

1. crowd_effect(): how much of home advantage is caused by the crowd?
   Natural experiment: from 16 May 2020 to the end of 2020/21 the Bundesliga played
   without fans ("ghost games"). Same teams, same stadiums, same referees, crowd removed.
   We estimate home advantage with and without fans in one Poisson model that holds
   each team's strength fixed *per season* (team-season attack and defence effects), so
   a change in who was good that year can't masquerade as a change in home advantage.
   Comparing home vs away for the same team, with vs without fans, is a
   difference-in-differences design.

   Identifying assumption: nothing else that favours home teams changed at the same time.
   Candidates, stated rather than hidden: five substitutions (introduced May 2020, but
   symmetric home/away), no travelling fans (part of the treatment), schedule congestion
   (symmetric). 2021/22 had partial, changing crowds and is reported separately.

2. momentum(): is "form" real, once you account for team strength?
   Winning teams keep winning, but mostly because they're good. The question is whether
   recent results carry information *beyond* strength. We take each team's surprise over
   its last 3 matches (actual points minus what the model expected before each match) and
   ask whether it predicts the surprise in the next match. The naive version (last-3
   points vs next-match points) is confounded by strength; the adjusted version isn't.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import poisson

from . import data

GHOST_START, GHOST_END = pd.Timestamp("2020-05-16"), pd.Timestamp("2021-06-30")
PARTIAL = 2021  # 2021/22: crowds capped and changing week to week


def _era(df: pd.DataFrame) -> pd.Series:
    ghost = (df.Date >= GHOST_START) & (df.Date <= GHOST_END)
    lab = df.Season.map(lambda y: f"{y}/{(y + 1) % 100:02d}")
    lab = lab.where(~ghost, "ghost")
    lab = lab.where(df.Season != PARTIAL, f"{PARTIAL}/{(PARTIAL + 1) % 100:02d} (partial)")
    return lab


def _poisson_fit(X, y, prior_prec, iters=60):
    theta = np.zeros(X.shape[1]); theta[0] = np.log(y.mean())
    for _ in range(iters):
        mu = np.exp(X @ theta)
        grad = X.T @ (y - mu) - prior_prec * theta
        H = (X * mu[:, None]).T @ X + np.diag(prior_prec)
        step = np.linalg.solve(H, grad)
        theta += step
        if np.abs(step).max() < 1e-9:
            break
    mu = np.exp(X @ theta)
    H = (X * mu[:, None]).T @ X + np.diag(prior_prec)
    return theta, np.linalg.inv(H)


def home_advantage_by_era(results: pd.DataFrame, group: pd.Series):
    """Poisson model: log E[goals] = base + HA[group] * is_home + attack[team, season] + defence[opp, season].
    Returns (estimates per group, full parameter vector, covariance, group names)."""
    df = results.reset_index(drop=True)
    g = pd.Categorical(group.reset_index(drop=True))
    groups = list(g.categories)
    ts_h = (df.HomeTeam + "|" + df.Season.astype(str))
    ts_a = (df.AwayTeam + "|" + df.Season.astype(str))
    ts = sorted(set(ts_h) | set(ts_a))
    ti = {t: i for i, t in enumerate(ts)}
    n, G, T = len(df), len(groups), len(ts)
    P = 1 + G + 2 * T
    X = np.zeros((2 * n, P))
    r = np.arange(n)
    hi, ai, gi = ts_h.map(ti).to_numpy(), ts_a.map(ti).to_numpy(), g.codes
    X[r, 0] = 1; X[r, 1 + gi] = 1; X[r, 1 + G + hi] = 1; X[r, 1 + G + T + ai] = 1
    X[n + r, 0] = 1; X[n + r, 1 + G + ai] = 1; X[n + r, 1 + G + T + hi] = 1
    y = np.concatenate([df.FTHG.to_numpy(), df.FTAG.to_numpy()]).astype(float)
    prior = np.full(P, 1e-2); prior[: 1 + G] = 1e-8  # tiny ridge only to pin down team effects
    theta, cov = _poisson_fit(X, y, prior)
    est = pd.DataFrame({"era": groups, "home_adv": theta[1:1 + G], "se": np.sqrt(np.diag(cov)[1:1 + G]),
                        "matches": np.bincount(gi, minlength=G)})
    return est, theta, cov, groups


def _home_points(ha: float, rho: float = -0.10, base: float = 0.30) -> float:
    """Expected home points between two average teams, given a home-advantage value."""
    lh, la = np.exp(base + ha), np.exp(base)
    gg = np.arange(11)
    M = np.outer(poisson.pmf(gg, lh), poisson.pmf(gg, la))
    M[0, 0] *= 1 - lh * la * rho; M[0, 1] *= 1 + lh * rho; M[1, 0] *= 1 + la * rho; M[1, 1] *= 1 - rho
    M /= M.sum()
    return 3 * np.tril(M, -1).sum() + np.trace(M)


def crowd_effect(first: int = 2015, last: int = 2024, *, exclude_early_2020_21: bool = False, **kw) -> dict:
    """Natural-experiment estimate of the crowd's share of home advantage."""
    res = data.load_history(first, last, **kw)
    res = res[(res.Season >= first) & (res.Season <= last)]
    if exclude_early_2020_21:  # Sep-Oct 2020: some stadiums briefly admitted up to 20% capacity
        res = res[~((res.Date >= "2020-09-01") & (res.Date < "2020-11-01"))]
    era = _era(res)
    by_era, *_ = home_advantage_by_era(res, era)

    treat = np.where(era == "ghost", "without fans", np.where(era.str.contains("partial"), "partial crowds", "with fans"))
    pooled, theta, cov, groups = home_advantage_by_era(res, pd.Series(treat, index=res.index))
    i, j = groups.index("with fans"), groups.index("without fans")
    ha_f, ha_g = theta[1 + i], theta[1 + j]
    diff = ha_f - ha_g
    se = np.sqrt(cov[1 + i, 1 + i] + cov[1 + j, 1 + j] - 2 * cov[1 + i, 1 + j])

    # mechanism: discipline. Cards are decided by referees, who can hear crowds.
    mech = res.assign(treat=treat)
    rows = []
    for col_h, col_a, name in [("HY", "AY", "yellow cards"), ("HF", "AF", "fouls"), ("HS", "AS", "shots")]:
        if col_h in mech and mech[col_h].notna().any():
            for t, d in mech.dropna(subset=[col_h, col_a]).groupby("treat"):
                gap = (d[col_a] - d[col_h]) if name != "shots" else (d[col_h] - d[col_a])
                rows.append({"measure": name, "condition": t, "home_edge_per_match": gap.mean(),
                             "se": gap.std(ddof=1) / np.sqrt(len(gap)), "matches": len(gap)})
    mechanisms = pd.DataFrame(rows)

    pts_f, pts_g = _home_points(ha_f), _home_points(ha_g)
    return {
        "by_era": by_era, "pooled": pooled,
        "home_adv_with_fans": ha_f, "home_adv_without_fans": ha_g,
        "crowd_effect": diff, "crowd_effect_se": se,
        "crowd_effect_ci95": (diff - 1.96 * se, diff + 1.96 * se),
        "crowd_share": diff / ha_f if ha_f > 0 else np.nan,
        "home_goals_boost_with_fans": np.exp(ha_f) - 1, "home_goals_boost_without_fans": np.exp(ha_g) - 1,
        "home_points_with_fans": pts_f, "home_points_without_fans": pts_g,
        "points_per_season_from_crowd": 17 * (pts_f - pts_g),
        "mechanisms": mechanisms, "seasons": (first, last),
    }


def momentum(first: int = 2012, last: int | None = None, window: int = 3, **kw) -> dict:
    """Does recent form predict the next result beyond what team strength already explains?"""
    from .season import Bundesliga
    last = last if last is not None else data.current_season() - 1
    rows = []
    for y in range(first, last + 1):
        s = Bundesliga(y, **kw)
        for md in range(1, 35):
            p = s.predict(md)
            p = p.dropna(subset=["FTHG"])
            for r in p.itertuples():
                hp = 3 if r.FTHG > r.FTAG else 1 if r.FTHG == r.FTAG else 0
                ap = 3 if r.FTAG > r.FTHG else 1 if r.FTHG == r.FTAG else 0
                rows.append({"Season": y, "Kickoff": r.Kickoff, "team": r.HomeTeam, "points": hp,
                             "expected": 3 * r.pH + r.pD})
                rows.append({"Season": y, "Kickoff": r.Kickoff, "team": r.AwayTeam, "points": ap,
                             "expected": 3 * r.pA + r.pD})
    tm = pd.DataFrame(rows).sort_values(["Season", "team", "Kickoff"])
    tm["surprise"] = tm.points - tm.expected
    g = tm.groupby(["Season", "team"])
    tm["form_points"] = g.points.transform(lambda x: x.shift(1).rolling(window).sum())
    tm["form_surprise"] = g.surprise.transform(lambda x: x.shift(1).rolling(window).sum())
    d = tm.dropna(subset=["form_points", "form_surprise"])

    def ols(x, y):
        X = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        s2 = resid @ resid / (len(y) - 2)
        se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
        return beta[1], se

    naive_b, naive_se = ols(d.form_points.to_numpy(), d.points.to_numpy())
    adj_b, adj_se = ols(d.form_surprise.to_numpy(), d.surprise.to_numpy())
    hot, cold = d[d.form_surprise >= 3], d[d.form_surprise <= -3]
    return {
        "matches": len(d), "window": window, "seasons": (first, last),
        "naive_slope": naive_b, "naive_se": naive_se,          # next points ~ last-k points
        "adjusted_slope": adj_b, "adjusted_se": adj_se,        # next surprise ~ last-k surprise
        "hot_next_surprise": hot.surprise.mean(), "hot_se": hot.surprise.std() / np.sqrt(len(hot)), "hot_n": len(hot),
        "cold_next_surprise": cold.surprise.mean(), "cold_se": cold.surprise.std() / np.sqrt(len(cold)), "cold_n": len(cold),
        "hot_next_points": hot.points.mean(), "hot_next_expected": hot.expected.mean(),
        "cold_next_points": cold.points.mean(), "cold_next_expected": cold.expected.mean(),
        "data": d,
    }
