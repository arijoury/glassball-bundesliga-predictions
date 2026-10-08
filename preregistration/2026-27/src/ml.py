"""Contrast model: gradient-boosted classifier on Elo + form features.

Deliberately a typical 'throw features at a GBM' baseline. It predicts H/D/A
directly; it has no notion of goals, so it can't simulate a table except by
sampling outcomes, and its forecasts have no built-in decomposition.
"""
from collections import defaultdict, deque

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ELO_K, ELO_HOME, ELO_START = 20.0, 60.0, 1500.0
FEATURES = ["elo_home", "elo_away", "elo_diff",
            "form_pts_home", "form_pts_away", "form_gf_home", "form_gf_away",
            "form_ga_home", "form_ga_away", "season_ppg_home", "season_ppg_away"]


class TeamState:
    """Chronological state machine. Records pre-match features, then updates on the result."""

    def __init__(self):
        self.elo = {}
        self.recent = defaultdict(lambda: deque(maxlen=5))  # (pts, gf, ga)
        self.season_pts = defaultdict(list)
        self.season = None
        self.prev_teams, self.cur_teams = set(), set()

    def _new_season(self, season, teams):
        if self.season is not None:
            left = self.prev_teams - teams
            arriving_elo = np.mean([self.elo[t] for t in left]) if left else ELO_START - 100
            for t in teams - self.prev_teams:
                self.elo[t] = arriving_elo  # promoted teams inherit the relegated teams' level
        self.season, self.prev_teams = season, teams
        self.season_pts = defaultdict(list)

    def features(self, home, away):
        def form(t, k):
            r = self.recent[t]
            return np.mean([x[k] for x in r]) if r else np.nan

        def ppg(t):
            p = self.season_pts[t]
            return np.mean(p) if p else np.nan

        eh, ea = self.elo.get(home, ELO_START), self.elo.get(away, ELO_START)
        return {"elo_home": eh, "elo_away": ea, "elo_diff": eh - ea + ELO_HOME,
                "form_pts_home": form(home, 0), "form_pts_away": form(away, 0),
                "form_gf_home": form(home, 1), "form_gf_away": form(away, 1),
                "form_ga_home": form(home, 2), "form_ga_away": form(away, 2),
                "season_ppg_home": ppg(home), "season_ppg_away": ppg(away)}

    def update(self, home, away, hg, ag):
        eh, ea = self.elo.get(home, ELO_START), self.elo.get(away, ELO_START)
        exp_h = 1 / (1 + 10 ** ((ea - eh - ELO_HOME) / 400))
        s_h = 1.0 if hg > ag else 0.5 if hg == ag else 0.0
        self.elo[home], self.elo[away] = eh + ELO_K * (s_h - exp_h), ea - ELO_K * (s_h - exp_h)
        ph, pa = (3, 0) if hg > ag else (1, 1) if hg == ag else (0, 3)
        self.recent[home].append((ph, hg, ag)); self.recent[away].append((pa, ag, hg))
        self.season_pts[home].append(ph); self.season_pts[away].append(pa)


def build(results: pd.DataFrame, as_of: pd.Timestamp):
    """Pre-match features for every match before `as_of`, plus the state at `as_of`."""
    st, rows = TeamState(), []
    teams_by_season = results.groupby("Season").apply(lambda d: set(d.HomeTeam) | set(d.AwayTeam))
    for g in results[results["Date"] < as_of].itertuples():
        if g.Season != st.season:
            st._new_season(g.Season, teams_by_season[g.Season])
        rows.append({"Season": g.Season, "Date": g.Date, "HomeTeam": g.HomeTeam, "AwayTeam": g.AwayTeam,
                     "FTHG": g.FTHG, "FTAG": g.FTAG, **st.features(g.HomeTeam, g.AwayTeam)})
        st.update(g.HomeTeam, g.AwayTeam, g.FTHG, g.FTAG)
    return pd.DataFrame(rows), st


def label(df):
    return np.where(df.FTHG > df.FTAG, 0, np.where(df.FTHG == df.FTAG, 1, 2))


def make_model(seed=0):
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_depth=4,
                                          l2_regularization=1.0, early_stopping=True,
                                          validation_fraction=0.15, random_state=seed)


def predict_fixtures(model, state: TeamState, fixtures: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame([state.features(f.HomeTeam, f.AwayTeam) for f in fixtures.itertuples()])[FEATURES]
    P = model.predict_proba(X)
    return fixtures.reset_index(drop=True).assign(ml_pH=P[:, 0], ml_pD=P[:, 1], ml_pA=P[:, 2])
