"""The one-line entry point: `Bundesliga(2026)` is the 2026/27 season.

Every question is asked "as of" a moment in the season, so nothing a forecast
uses can come from the future:

    before_matchday=k  ->  only matches played before matchday k kicks off
    as_of="2026-10-08" ->  only matches played before that date
    (neither)          ->  today, or the end of the season if it's over
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, ml
from .model import DixonColes, Hyper, brier, logloss, odds_to_probs, outcome_index, rps
from .simulate import TableForecast, league_table, simulate


class Bundesliga:
    """One Bundesliga season, from 2004/05 onwards (past, current, or future once fixtures exist).

    >>> from glassball import Bundesliga
    >>> s = Bundesliga(2026)                 # 2026/27
    >>> s.predict(matchday=5)                # every match of MD5, with the drivers of each forecast
    >>> s.forecast(before_matchday=5).table  # simulated final table
    """

    def __init__(self, season: int | None = None, *, hyper: Hyper | None = None, data_dir: str | Path | None = None,
                 fixtures_file: str | Path | None = None, offline: bool = False, history_seasons: int = 14):
        season = data.current_season() if season is None else int(season)
        if season < data.FIRST_SEASON:
            raise ValueError(f"Seasons from {data.FIRST_SEASON}/{data.FIRST_SEASON + 1} onwards are supported")
        self.season, self.hyper = season, hyper or Hyper()
        kw = {"data_dir": data_dir, "offline": offline}
        self.history = data.load_history(season - history_seasons, season, **kw)
        oldb = data.load_oldb(season, file=Path(fixtures_file) if fixtures_file else None, **kw)
        this = self.history[self.history.Season == season]
        names = data.reconcile_names(oldb, this)
        fx = oldb.assign(HomeTeam=oldb.HomeTeamOLDB.map(names), AwayTeam=oldb.AwayTeamOLDB.map(names))
        fx["Kickoff"] = fx.Kickoff.dt.tz_localize(None) if fx.Kickoff.dt.tz is not None else fx.Kickoff
        # attach football-data result + stats + odds where available; fall back to OpenLigaDB scores
        fd = this.drop(columns=["Season"]).rename(columns={"Date": "Date_fd"})
        fx = fx.merge(fd, on=["HomeTeam", "AwayTeam"], how="left")
        fx["FTHG"] = fx.FTHG.fillna(fx.FTHG_oldb)
        fx["FTAG"] = fx.FTAG.fillna(fx.FTAG_oldb)
        fx["Finished"] = fx.Finished | fx.Date_fd.notna()
        self.fixtures = (fx.drop(columns=["HomeTeamOLDB", "AwayTeamOLDB", "FTHG_oldb", "FTAG_oldb"])
                         .sort_values(["Matchday", "Kickoff", "HomeTeam"]).reset_index(drop=True))
        self.teams = sorted(set(self.fixtures.HomeTeam))
        prev = set(self.history.query("Season == @season - 1").HomeTeam)
        self.promoted = set(self.teams) - prev
        # matches from this season that football-data doesn't have yet (it lags a few days)
        late = self.fixtures[self.fixtures.Finished & self.fixtures.Date_fd.isna()]
        extra = late.assign(Season=season, Date=late.Kickoff.dt.normalize())[
            ["Season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"]]
        self._results = pd.concat([self.history, extra], ignore_index=True).astype({"FTHG": int, "FTAG": int})

    def __repr__(self):
        n = int(self.fixtures.Finished.sum())
        return f"Bundesliga({self.season}/{(self.season + 1) % 100:02d}: {n}/306 matches played, next matchday {self.next_matchday()})"

    # ---- time handling ---------------------------------------------------------------------
    def next_matchday(self) -> int | None:
        """The matchday of the next match to be played (ignoring old postponed fixtures)."""
        open_ = self.fixtures[~self.fixtures.Finished]
        if not len(open_):
            return None
        upcoming = open_[open_.Kickoff >= pd.Timestamp.today().normalize()]
        return int((upcoming if len(upcoming) else open_).sort_values("Kickoff").Matchday.iloc[0])

    def team(self, name: str) -> str:
        """Forgiving team lookup: 'bayern', 'BVB', 'gladbach', 'Köln' all work."""
        return data.resolve_team(name, self.teams)

    def cutoff(self, before_matchday: int | None = None, as_of=None) -> pd.Timestamp:
        if as_of is not None:
            return pd.Timestamp(as_of)
        if before_matchday is not None:
            return self.fixtures.query("Matchday == @before_matchday").Kickoff.min().normalize()
        # default: now, i.e. every match finished so far (capped at the end of the season)
        return min(pd.Timestamp.today().normalize() + pd.Timedelta(days=1),
                   self.fixtures.Kickoff.max().normalize() + pd.Timedelta(days=1))

    def played(self, before_matchday=None, as_of=None) -> pd.DataFrame:
        c = self.cutoff(before_matchday, as_of)
        return self.fixtures[self.fixtures.Finished & (self.fixtures.Kickoff < c)]

    def table(self, after_matchday: int | None = None, as_of=None) -> pd.DataFrame:
        """League table after a matchday (or at a date)."""
        if after_matchday is not None:
            nxt = after_matchday + 1
            played = (self.played(before_matchday=nxt) if nxt <= 34
                      else self.fixtures[self.fixtures.Finished])
        else:
            played = self.played(as_of=as_of)
        return league_table(played, self.teams)

    # ---- the glass box ---------------------------------------------------------------------
    @lru_cache(maxsize=64)
    def _fit(self, cutoff: pd.Timestamp) -> DixonColes:
        return DixonColes(self.hyper).fit(self._results, cutoff, self.promoted)

    def model(self, before_matchday=None, as_of=None) -> DixonColes:
        return self._fit(self.cutoff(before_matchday, as_of))

    def ratings(self, before_matchday=None, as_of=None) -> pd.DataFrame:
        """Attack (goals scored, log-scale), defence (goals conceded, log-scale, lower = better), with standard errors."""
        r = self.model(before_matchday, as_of).ratings()
        return r[r.team.isin(self.teams)].reset_index(drop=True)

    def predict(self, matchday: int | None = None, *, before_matchday=None, as_of=None,
                contrast: bool = False) -> pd.DataFrame:
        """Probabilities for one matchday (default: the next one), using only information
        available before it. Played matches also show the result and the bookmakers' view."""
        matchday = matchday or self.next_matchday() or 34
        if before_matchday is None and as_of is None:
            before_matchday = matchday
        dc = self.model(before_matchday, as_of)
        fx = self.fixtures.query("Matchday == @matchday")
        out = dc.predict(fx[["Matchday", "Kickoff", "HomeTeam", "AwayTeam"]])
        scores = []
        for r in out.itertuples():  # most likely scoreline
            M = dc.score_matrix(r.xG_home, r.xG_away)
            i, j = np.unravel_index(M.argmax(), M.shape)
            scores.append(f"{i}-{j}")
        out.insert(out.columns.get_loc("xG_away") + 1, "likely_score", scores)
        res = fx[["FTHG", "FTAG"]].reset_index(drop=True)
        out[["FTHG", "FTAG"]] = res.where(np.repeat(fx.Finished.to_numpy()[:, None], 2, axis=1))
        if {"AvgCH", "AvgCD", "AvgCA"} <= set(fx.columns) and fx.AvgCH.notna().any():
            bk = odds_to_probs(fx.AvgCH.to_numpy(), fx.AvgCD.to_numpy(), fx.AvgCA.to_numpy())
            out[["book_pH", "book_pD", "book_pA"]] = bk
        if contrast:
            gbm, state = self._gbm(self.cutoff(before_matchday, as_of))
            out = out.merge(ml.predict_fixtures(gbm, state, out)[["HomeTeam", "AwayTeam", "ml_pH", "ml_pD", "ml_pA"]],
                            on=["HomeTeam", "AwayTeam"])
        return out

    def explain(self, home: str, away: str, *, before_matchday=None, as_of=None) -> pd.DataFrame:
        """The receipt for one forecast: each additive driver, its uncertainty, and how far
        the home-win probability moves if that driver were one standard error higher."""
        home, away = self.team(home), self.team(away)
        dc = self.model(before_matchday, as_of)
        idx, T = dc._idx()
        h, a = idx[home], idx[away]
        terms = [("base scoring rate", 0, "both"), ("home advantage", 1, "home"),
                 (f"{home} attack", 2 + h, "home"), (f"{away} defence", 2 + T + a, "home"),
                 (f"{away} attack", 2 + a, "away"), (f"{home} defence", 2 + T + h, "away")]

        def p_home(theta):
            d = dc.drivers(home, away, theta)
            M = dc.score_matrix(d["lambda_home"], d["lambda_away"])
            return np.tril(M, -1).sum()

        base = p_home(dc.theta)
        rows = []
        for name, i, side in terms:
            up = dc.theta.copy(); up[i] += np.sqrt(dc.cov[i, i])
            rows.append({"driver": name, "affects": f"{side} goals", "value": dc.theta[i],
                         "std_err": np.sqrt(dc.cov[i, i]), "multiplier": np.exp(dc.theta[i]),
                         "p_home_win_if_+1se": p_home(up) - base})
        out = pd.DataFrame(rows)
        d = dc.drivers(home, away)
        out.attrs.update(home=home, away=away, lambda_home=d["lambda_home"], lambda_away=d["lambda_away"],
                         p_home=base, matrix=dc.score_matrix(d["lambda_home"], d["lambda_away"]))
        return out

    # ---- the whole season ------------------------------------------------------------------
    def forecast(self, *, before_matchday=None, as_of=None, n_sims: int = 20_000, seed: int = 20261008,
                 shift: dict | None = None) -> TableForecast:
        """Simulate the rest of the season. `shift={"Bayern Munich": {"attack": -0.1}}` runs a
        what-if (e.g. a star striker out: roughly 10% fewer goals)."""
        c = self.cutoff(before_matchday, as_of)
        dc = self._fit(c)
        if shift:
            dc = DixonColes(dc.hyper, list(dc.teams), dc.theta.copy(), dc.cov, dc.as_of, dc.n_matches)
            idx, T = dc._idx()
            for team, s in shift.items():
                team = self.team(team)
                dc.theta[2 + idx[team]] += s.get("attack", 0.0)
                dc.theta[2 + T + idx[team]] += s.get("defence", 0.0)
        played = self.fixtures[self.fixtures.Finished & (self.fixtures.Kickoff < c)]
        remaining = self.fixtures[~self.fixtures.index.isin(played.index)].reset_index(drop=True)
        return simulate(dc, league_table(played, self.teams), remaining, np.random.default_rng(seed), n_sims)

    # ---- grading -----------------------------------------------------------------------------
    def _gbm(self, cutoff):
        feats, state = ml.build(self._results, cutoff)
        train = feats[feats.Season > self.history.Season.min()]  # first season = Elo burn-in
        return ml.make_model().fit(train[ml.FEATURES], ml.label(train)), state

    def evaluate(self, matchdays=None, contrast: bool = True) -> pd.DataFrame:
        """Walk-forward grading: each matchday predicted with data from before it only."""
        mds = matchdays or sorted(self.fixtures[self.fixtures.Finished].Matchday.unique())
        preds = pd.concat([self.predict(m, contrast=contrast) for m in mds], ignore_index=True)
        preds = preds.dropna(subset=["FTHG"])
        o = outcome_index(preds.FTHG.to_numpy(), preds.FTAG.to_numpy())
        cols = {"Glass box (Dixon-Coles)": ["pH", "pD", "pA"]}
        if contrast:
            cols["GBM (Elo + form)"] = ["ml_pH", "ml_pD", "ml_pA"]
        if "book_pH" in preds and preds.book_pH.notna().all():
            cols["Bookmakers (closing)"] = ["book_pH", "book_pD", "book_pA"]
        rows = []
        for name, c in cols.items():
            P = preds[c].to_numpy(float)
            rows.append({"model": name, "matches": len(o), "rps": rps(P, o).mean(), "brier": brier(P, o).mean(),
                         "logloss": logloss(P, o).mean(), "accuracy": (P.argmax(1) == o).mean()})
        out = pd.DataFrame(rows)
        out.attrs["predictions"] = preds
        return out
