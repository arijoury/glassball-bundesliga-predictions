"""Monte Carlo season simulation (same algorithm and RNG sequence as the frozen src/forecast.py)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson

from .model import MAX_GOALS, DixonColes


def league_table(played: pd.DataFrame, teams) -> pd.DataFrame:
    t = pd.DataFrame(0, index=sorted(teams), columns=["P", "W", "D", "L", "GF", "GA", "Pts"])
    for g in played.itertuples():
        hg, ag = int(g.FTHG), int(g.FTAG)
        for team, gf, ga in [(g.HomeTeam, hg, ag), (g.AwayTeam, ag, hg)]:
            t.loc[team, ["P", "GF", "GA"]] += [1, gf, ga]
            res = "W" if gf > ga else "D" if gf == ga else "L"
            t.loc[team, res] += 1
            t.loc[team, "Pts"] += {"W": 3, "D": 1, "L": 0}[res]
    t["GD"] = t.GF - t.GA
    t = t.sort_values(["Pts", "GD", "GF"], ascending=False)
    t.insert(0, "Pos", range(1, len(t) + 1))
    return t


@dataclass
class TableForecast:
    """Result of a season simulation. `table` is the summary; the raw arrays allow
    conditional questions ("what if Bayern lose on Saturday?")."""
    table: pd.DataFrame          # per team: expected points/position, event and position probabilities
    teams: list                  # order of columns in `ranks`
    remaining: pd.DataFrame      # fixtures that were simulated (row order = columns of `outcomes`)
    ranks: np.ndarray            # (n_sims, n_teams) final position, 0-based
    points: np.ndarray           # (n_sims, n_teams) final points
    outcomes: np.ndarray         # (n_sims, n_fixtures) 0 = home win, 1 = draw, 2 = away win

    EVENTS = {"title": (0, 1), "top4": (0, 4), "top6": (0, 6), "playoff16": (15, 16), "relegated": (16, 18)}

    def event(self, team: str, event: str = "title") -> np.ndarray:
        lo, hi = self.EVENTS[event]
        r = self.ranks[:, self.teams.index(team)]
        return (r >= lo) & (r < hi)

    def swing(self, team: str, event: str = "title", top: int = 10) -> pd.DataFrame:
        """Which remaining matches move P(event) the most? Conditional probability of the
        event given each match result, straight from the simulated seasons."""
        hit = self.event(team, event)
        rows = []
        for j, f in enumerate(self.remaining.itertuples()):
            o = self.outcomes[:, j]
            cond = [hit[o == k].mean() if (o == k).any() else np.nan for k in range(3)]
            rows.append({"Matchday": f.Matchday, "HomeTeam": f.HomeTeam, "AwayTeam": f.AwayTeam,
                         "if_home_win": cond[0], "if_draw": cond[1], "if_away_win": cond[2],
                         "swing": np.nanmax(cond) - np.nanmin(cond)})
        out = pd.DataFrame(rows).sort_values("swing", ascending=False).head(top)
        out.attrs.update(team=team, event=event, baseline=hit.mean())
        return out.reset_index(drop=True)


def simulate(dc: DixonColes, table: pd.DataFrame, remaining: pd.DataFrame, rng,
             n_sims: int = 20_000, chunk: int = 1000) -> TableForecast:
    """Each simulated season draws its own team ratings from the Laplace posterior, so
    rating uncertainty (not just match randomness) is propagated into the table."""
    teams = list(table.drop(columns="Pos", errors="ignore").index)
    table = table.loc[teams]
    ti = {t: i for i, t in enumerate(teams)}
    idx, T = dc._idx()
    hi = np.array([idx[t] for t in remaining.HomeTeam], dtype=int)
    ai = np.array([idx[t] for t in remaining.AwayTeam], dtype=int)
    hs = np.array([ti[t] for t in remaining.HomeTeam], dtype=int)
    as_ = np.array([ti[t] for t in remaining.AwayTeam], dtype=int)
    n_fx, G = len(remaining), MAX_GOALS + 1
    g = np.arange(G)
    rho = dc.hyper.rho

    all_ranks = np.zeros((n_sims, len(teams)), dtype=np.int8)
    all_pts = np.zeros((n_sims, len(teams)), dtype=np.int16)
    all_out = np.zeros((n_sims, n_fx), dtype=np.int8)
    for start in range(0, n_sims, chunk):
        m = min(chunk, n_sims - start)
        th = rng.multivariate_normal(dc.theta, dc.cov, size=m)
        lh = np.exp(th[:, [0]] + th[:, [1]] + th[:, 2 + hi] + th[:, 2 + T + ai])
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
        all_ranks[start:start + m], all_pts[start:start + m] = rank, pts
        all_out[start:start + m] = np.where(hg > ag, 0, np.where(hg == ag, 1, 2))

    n = len(teams)
    pos = np.stack([(all_ranks == p).mean(0) for p in range(n)], axis=1)
    out = pd.DataFrame(pos, index=teams, columns=[f"pos_{i + 1}" for i in range(n)])
    out.insert(0, "exp_points", all_pts.mean(0))
    out.insert(1, "exp_position", (pos * np.arange(1, n + 1)).sum(1))
    out.insert(2, "p_title", pos[:, 0])
    out.insert(3, "p_top4", pos[:, :4].sum(1))
    out.insert(4, "p_top6", pos[:, :6].sum(1))
    out.insert(5, "p_playoff16", pos[:, 15] if n > 15 else 0.0)
    out.insert(6, "p_relegated", pos[:, 16:].sum(1))
    out = out.sort_values("exp_points", ascending=False)
    return TableForecast(out, teams, remaining.reset_index(drop=True), all_ranks, all_pts, all_out)
