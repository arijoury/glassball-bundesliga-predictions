"""Glass-box match model: time-weighted, penalised Dixon-Coles.

    log E[home goals] = base + home_adv + attack[home] + defence[away]
    log E[away goals] = base            + attack[away] + defence[home]

Every forecast decomposes into these four or three additive terms, so each
prediction can be traced back to the team strengths that drive it.

Fitting is a weighted Poisson GLM solved with Newton's method:
  * matches are down-weighted exponentially with age (half-life `half_life_days`),
  * every team rating is shrunk toward a prior mean with precision `prior_precision`
    (0 for established Bundesliga teams, `promoted_attack` / `promoted_defence`
    for teams that were not in the Bundesliga the previous season),
  * the Dixon-Coles low-score correction `rho` is applied at prediction time.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import poisson

MAX_GOALS = 10


@dataclass
class Hyper:
    half_life_days: float = 270.0
    prior_precision: float = 10.0
    promoted_attack: float = -0.3
    promoted_defence: float = 0.3
    rho: float = -0.10
    window_days: int = 4 * 365  # ignore matches older than this (weight is tiny anyway)


@dataclass
class DixonColes:
    hyper: Hyper = field(default_factory=Hyper)
    teams: list = field(default_factory=list)
    theta: np.ndarray | None = None
    cov: np.ndarray | None = None
    as_of: pd.Timestamp | None = None
    n_matches: int = 0

    # ---- parameter layout: [base, home_adv, attack_0..T-1, defence_0..T-1]
    def _idx(self):
        T = len(self.teams)
        return {t: i for i, t in enumerate(self.teams)}, T

    def fit(self, results: pd.DataFrame, as_of: pd.Timestamp, promoted: set[str]):
        h = self.hyper
        df = results[(results["Date"] < as_of) &
                     (results["Date"] >= as_of - pd.Timedelta(days=h.window_days))]
        self.as_of, self.n_matches = as_of, len(df)
        self.teams = sorted(set(df["HomeTeam"]) | set(df["AwayTeam"]) | set(promoted))
        idx, T = self._idx()
        P = 2 + 2 * T
        n = len(df)

        age = (as_of - df["Date"]).dt.days.to_numpy()
        w = 0.5 ** (age / h.half_life_days)
        hi = df["HomeTeam"].map(idx).to_numpy()
        ai = df["AwayTeam"].map(idx).to_numpy()

        # Design matrix: one row per (match, side)
        X = np.zeros((2 * n, P))
        r = np.arange(n)
        X[r, 0] = 1; X[r, 1] = 1; X[r, 2 + hi] = 1; X[r, 2 + T + ai] = 1          # home goals
        X[n + r, 0] = 1; X[n + r, 2 + ai] = 1; X[n + r, 2 + T + hi] = 1           # away goals
        y = np.concatenate([df["FTHG"].to_numpy(), df["FTAG"].to_numpy()]).astype(float)
        ww = np.concatenate([w, w])

        prior_mean = np.zeros(P)
        prior_prec = np.full(P, h.prior_precision)
        prior_prec[:2] = 1e-6  # base and home advantage are essentially unpenalised
        for t in promoted:
            prior_mean[2 + idx[t]] = h.promoted_attack
            prior_mean[2 + T + idx[t]] = h.promoted_defence

        theta = prior_mean.copy()
        theta[0] = np.log(max(y.mean(), 0.5))
        for _ in range(50):
            mu = np.exp(X @ theta)
            grad = X.T @ (ww * (y - mu)) - prior_prec * (theta - prior_mean)
            H = (X * (ww * mu)[:, None]).T @ X + np.diag(prior_prec)
            step = np.linalg.solve(H, grad)
            theta += step
            if np.abs(step).max() < 1e-8:
                break
        mu = np.exp(X @ theta)
        H = (X * (ww * mu)[:, None]).T @ X + np.diag(prior_prec)
        self.theta, self.cov = theta, np.linalg.inv(H)
        return self

    # ---- interpretable pieces
    def ratings(self) -> pd.DataFrame:
        idx, T = self._idx()
        sd = np.sqrt(np.diag(self.cov))
        return pd.DataFrame({
            "team": self.teams,
            "attack": self.theta[2:2 + T], "attack_sd": sd[2:2 + T],
            "defence": self.theta[2 + T:], "defence_sd": sd[2 + T:],
        }).assign(net=lambda d: d.attack - d.defence).sort_values("net", ascending=False)

    def drivers(self, home: str, away: str, theta: np.ndarray | None = None) -> dict:
        """Additive log-rate decomposition of one match (the 'receipt' for a forecast)."""
        th = self.theta if theta is None else theta
        idx, T = self._idx()
        h, a = idx[home], idx[away]
        d = {
            "base": th[0], "home_adv": th[1],
            "home_attack": th[2 + h], "away_defence": th[2 + T + a],
            "away_attack": th[2 + a], "home_defence": th[2 + T + h],
        }
        d["log_lambda_home"] = d["base"] + d["home_adv"] + d["home_attack"] + d["away_defence"]
        d["log_lambda_away"] = d["base"] + d["away_attack"] + d["home_defence"]
        d["lambda_home"], d["lambda_away"] = np.exp(d["log_lambda_home"]), np.exp(d["log_lambda_away"])
        return d

    def score_matrix(self, lam_h: float, lam_a: float) -> np.ndarray:
        g = np.arange(MAX_GOALS + 1)
        M = np.outer(poisson.pmf(g, lam_h), poisson.pmf(g, lam_a))
        rho = self.hyper.rho
        M[0, 0] *= 1 - lam_h * lam_a * rho
        M[0, 1] *= 1 + lam_h * rho
        M[1, 0] *= 1 + lam_a * rho
        M[1, 1] *= 1 - rho
        return M / M.sum()

    def predict(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for f in fixtures.itertuples():
            d = self.drivers(f.HomeTeam, f.AwayTeam)
            M = self.score_matrix(d["lambda_home"], d["lambda_away"])
            rows.append({
                "pH": np.tril(M, -1).sum(), "pD": np.trace(M), "pA": np.triu(M, 1).sum(),
                "xG_home": d["lambda_home"], "xG_away": d["lambda_away"],
                **{f"drv_{k}": v for k, v in d.items() if not k.startswith(("log_", "lambda"))},
            })
        return pd.concat([fixtures.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# ---- scoring rules ------------------------------------------------------------
def outcome_index(hg, ag):
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def rps(p: np.ndarray, o: np.ndarray) -> np.ndarray:
    """Ranked probability score for ordered outcomes (H, D, A). Lower is better."""
    obs = np.eye(3)[o]
    cp, co = np.cumsum(p, 1)[:, :2], np.cumsum(obs, 1)[:, :2]
    return ((cp - co) ** 2).sum(1) / 2


def brier(p, o):
    return ((p - np.eye(3)[o]) ** 2).sum(1)


def logloss(p, o):
    return -np.log(np.clip(p[np.arange(len(o)), o], 1e-12, 1))


def odds_to_probs(h, d, a):
    inv = np.column_stack([1 / h, 1 / d, 1 / a])
    return inv / inv.sum(1, keepdims=True)
