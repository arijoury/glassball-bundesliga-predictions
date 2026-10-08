"""Regenerate every figure in the README.

    python scripts/make_figures.py            # all figures (~6 min, the backtest dominates)
    python scripts/make_figures.py --quick    # skip the slow ones if their data is cached

Figures about the *forecast* are drawn from the frozen files in preregistration/2026-27/freeze/2026-10-08,
never from a re-fit, so they show exactly what was pre-registered.
"""
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from glassball import Bundesliga, DixonColes, Hyper, plots  # noqa: E402
from glassball.data import load_history  # noqa: E402
from glassball.model import outcome_index  # noqa: E402
from glassball.plots import BOOK, DRAW, GBM, GLASS, GRID, HOME, AWAY, INK, INK2, SERIES, _subtitle  # noqa: E402

PRE = ROOT / "preregistration" / "2026-27"
FIG, CACHE, FREEZE = ROOT / "figures", ROOT / "figures" / "data", PRE / "freeze" / "2026-10-08"
FIG.mkdir(exist_ok=True); CACHE.mkdir(parents=True, exist_ok=True)


def save(fig, name):
    fig.savefig(FIG / name)
    plt.close(fig)
    print("wrote", name)


def season_label(y):
    return f"{y % 100:02d}/{(y + 1) % 100:02d}"


# ---- 1. the dataset ---------------------------------------------------------------------------
def dataset_figures(hist):
    # 1a. what's in it: variable availability by season
    groups = {
        "Result & half-time score": ["FTHG", "HTHG"],
        "Shots / on target": ["HS", "HST"],
        "Corners, fouls, cards": ["HC", "HF", "HY"],
        "Pre-match odds (avg)": ["AvgH", "BbAvH"],
        "Closing odds (avg)": ["AvgCH"],
        "Expected goals (xG)": ["HxG"],
    }
    seasons = sorted(hist.Season.unique())
    A = np.array([[hist.loc[hist.Season == s, [c for c in cols if c in hist]].notna().any(axis=1).mean()
                   if any(c in hist for c in cols) else 0 for s in seasons] for cols in groups.values()])
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.imshow(A, cmap=plots.BLUES, vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(groups)), list(groups))
    ax.set_xticks(range(len(seasons)), [season_label(s) for s in seasons], rotation=90, fontsize=8)
    ax.grid(False)
    n = len(hist)
    ax.set_title("The dataset: what we know about each season", pad=24)
    ax.text(0, 1.04, f"{n:,} Bundesliga matches, {len(seasons)} seasons, {hist.shape[1]} columns "
            "(football-data.co.uk + OpenLigaDB). Darker = available for more matches",
            transform=ax.transAxes, color=INK2, fontsize=9)
    save(fig, "01_data_availability.png")

    # 1b. how the variables evolve: per-match averages, small multiples (one y-axis each)
    g = hist.groupby("Season")
    series = {
        "Goals per match": g.apply(lambda d: (d.FTHG + d.FTAG).mean()),
        "Shots per match": g.apply(lambda d: (d.HS + d.AS).mean() if "HS" in d and d.HS.notna().any() else np.nan),
        "Shots on target per match": g.apply(lambda d: (d.HST + d.AST).mean() if d.HST.notna().any() else np.nan),
        "Goals per shot on target": g.apply(lambda d: (d.FTHG + d.FTAG).sum() / (d.HST + d.AST).sum() if d.HST.notna().any() else np.nan),
        "Yellow cards per match": g.apply(lambda d: (d.HY + d.AY).mean() if d.HY.notna().any() else np.nan),
        "Bookmaker margin (overround)": g.apply(lambda d: ((1 / d.AvgH + 1 / d.AvgD + 1 / d.AvgA).mean() - 1)
                                                if "AvgH" in d and d.AvgH.notna().any() else
                                                ((1 / d.BbAvH + 1 / d.BbAvD + 1 / d.BbAvA).mean() - 1)
                                                if "BbAvH" in d and d.BbAvH.notna().any() else np.nan),
    }
    # 2006/07 counts ~56% of shots as on target (vs ~35% every other season): a source quirk, not football
    for k in ("Shots on target per match", "Goals per shot on target"):
        series[k].loc[2006] = np.nan
    cur = hist.Season.max()
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.4), sharex=True)
    for ax, (name, s) in zip(axes.ravel(), series.items()):
        s = s.dropna()
        full = s[s.index < cur]
        ax.plot(full.index, full.values, color=GLASS, marker="o", markersize=3.5)
        if cur in s.index:  # current season: only a few matchdays, drawn hollow and unconnected
            ax.plot([cur], [s[cur]], marker="o", markersize=5, markerfacecolor="white", markeredgecolor=GLASS, ls="")
        ax.set_title(name, fontsize=10.5, pad=8)
        if "margin" in name:
            ax.yaxis.set_major_formatter(lambda x, _: f"{100 * x:.1f}%")
        ax.axvspan(2019.5, 2020.5, color=GRID, alpha=0.6, lw=0)
    for ax in axes[1]:
        ax.set_xticks(seasons[::3], [season_label(s) for s in seasons[::3]], fontsize=8)
    axes[0, 0].text(2020, axes[0, 0].get_ylim()[1], "ghost\ngames", ha="center", va="top", fontsize=8, color=INK2)
    fig.suptitle("How the game (and the market) changed", x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.text(0.01, 0.925, f"Per-match averages by season. Hollow dot = {season_label(cur)} so far (4 matchdays). "
             "2006/07 shots-on-target omitted (inconsistent at source). Margin = average across the bookmakers football-data lists",
             color=INK2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, "02_variables_evolution.png")

    # 1c. home advantage and the outcome mix
    res = g.apply(lambda d: pd.Series({"Home win": (d.FTHG > d.FTAG).mean(), "Draw": (d.FTHG == d.FTAG).mean(),
                                       "Away win": (d.FTHG < d.FTAG).mean()}))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axes[0]
    bottom = np.zeros(len(res))
    res = res[res.index < cur]
    bottom = np.zeros(len(res))
    for col, c in zip(res.columns, (HOME, DRAW, AWAY)):
        ax.bar(res.index, res[col] - 0.003, bottom=bottom + 0.0015, color=c, width=0.8, label=col)
        bottom += res[col].to_numpy()
    for x, v in zip(res.index, res["Home win"]):
        if x in (seasons[0], 2020, cur - 1):
            ax.text(x, v / 2, f"{100 * v:.0f}", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    ax.set_ylim(0, 1); ax.yaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.set_xticks(seasons[:-1:2], [season_label(s) for s in seasons[:-1:2]], fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.set_title("Home advantage: real, noisy, and briefly gone")
    _subtitle(ax, "Share of results per completed season; 2020/21 was played without fans")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.1), fontsize=9)

    ax = axes[1]
    goals = np.concatenate([hist.FTHG, hist.FTAG])
    k = np.arange(0, 8)
    from scipy.stats import poisson
    obs = np.array([(goals == i).mean() for i in k])
    ax.bar(k, obs, color=GLASS, width=0.7, label="observed")
    ax.plot(k, poisson.pmf(k, goals.mean()), color=INK, marker="o", markersize=5, lw=1.5, label=f"Poisson({goals.mean():.2f})")
    ax.yaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("goals by one team in a match")
    ax.set_title("Why a Poisson model?")
    _subtitle(ax, "Goals per team per match vs a Poisson with the same mean")
    ax.legend(fontsize=9)
    fig.tight_layout()
    save(fig, "03_outcomes_and_goals.png")


# ---- 2. ratings over time -----------------------------------------------------------------------
def ratings_evolution(hist):
    path = CACHE / "ratings_monthly.csv"
    if not path.exists():
        rows = []
        for d in pd.date_range("2010-08-01", "2026-10-01", freq="MS"):
            if d.month in (6, 7):  # summer break
                continue
            yr = d.year if d.month >= 8 else d.year - 1
            teams = set(hist[hist.Season == yr].HomeTeam)
            prom = teams - set(hist[hist.Season == yr - 1].HomeTeam)
            dc = DixonColes(Hyper()).fit(hist, d, prom)
            r = dc.ratings()
            r = r[r.team.isin(teams)]
            rows += [{"date": d, "team": t.team, "attack": t.attack, "defence": t.defence, "net": t.net} for t in r.itertuples()]
        pd.DataFrame(rows).to_csv(path, index=False)
    r = pd.read_csv(path, parse_dates=["date"])
    focus = ["Bayern Munich", "Dortmund", "Leverkusen", "RB Leipzig"]
    fig, ax = plt.subplots(figsize=(12, 4.6))
    for t, d in r.groupby("team"):
        if t not in focus:
            d = d.set_index("date").net.asfreq("MS")
            ax.plot(d.index, d.values, color=GRID, lw=1, zorder=1)
    for k, t in enumerate(focus):
        d = r[r.team == t].set_index("date").net.asfreq("MS")
        ax.plot(d.index, d.values, color=SERIES[k], lw=2.2, zorder=3, label=t)
        ax.text(d.dropna().index[-1] + pd.Timedelta(days=40), d.dropna().iloc[-1], t, fontsize=9, va="center")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xlim(pd.Timestamp("2010-06-01"), pd.Timestamp("2028-01-01"))
    ax.set_title("Team strength over 16 seasons (attack − defence, log goals)")
    _subtitle(ax, "Glass-box ratings refit monthly; grey = every other Bundesliga club. +0.5 ≈ 65% more goals scored than conceded vs an average side")
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=9)
    save(fig, "04_ratings_evolution.png")


# ---- 3. the frozen forecast ------------------------------------------------------------------------
def forecast_figures():
    mf = pd.read_csv(FREEZE / "match_forecasts.csv")
    md5 = mf[mf.Matchday == 5].reset_index(drop=True)
    save(plots.matchday(md5, "Matchday 5 (9–11 Oct 2026), as frozen on 8 Oct"), "05_matchday5_frozen.png")

    tf = pd.read_csv(FREEZE / "table_forecast.csv", index_col=0)
    save(plots.table(tf, "Final table 2026/27, as frozen on 8 Oct (after matchday 4)"), "06_table_frozen.png")

    # glass box vs GBM on all 270 frozen matches
    fig, ax = plt.subplots(figsize=(5.6, 5.4))
    ax.plot([0, 1], [0, 1], color=GRID, lw=1)
    ax.scatter(mf.pH, mf.ml_pH, s=16, color=GBM, alpha=0.7, edgecolor="none")
    ax.set_xlabel("glass box: P(home win)"); ax.set_ylabel("GBM: P(home win)")
    for a in (ax.xaxis, ax.yaxis):
        a.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    corr = np.corrcoef(mf.pH, mf.ml_pH)[0, 1]
    ax.set_title("Two models, same 270 matches")
    bay = mf[mf.HomeTeam == "Bayern Munich"]
    ax.annotate("every Bayern home game:\nglass box 78–88%, GBM 60–72%", xy=(bay.pH.mean(), bay.ml_pH.mean()),
                xytext=(0.52, 0.12), fontsize=8.5, color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    _subtitle(ax, f"Agree on the ordering (r = {corr:.2f}), not on the confidence")
    save(fig, "07_glassbox_vs_gbm.png")


def drivers_figures(live):
    cut = dict(as_of="2026-10-08")  # the frozen information set
    ex = live.explain("Bayern Munich", "RB Leipzig", **cut)
    save(plots.explain(ex), "08_drivers_bayern_leipzig.png")
    save(plots.sensitivity(ex), "09_sensitivity_bayern_leipzig.png")

    fc = live.forecast(**cut)
    save(plots.swing(fc.swing("Dortmund", "title", top=8)), "10_swing_dortmund_title.png")
    save(plots.swing(fc.swing("Union Berlin", "relegated", top=8)), "11_swing_union_relegation.png")

    scen = {
        "Bayern lose their top scorer (attack −0.15)": live.forecast(shift={"Bayern Munich": {"attack": -0.15}}, **cut),
        "Dortmund sign a striker (attack +0.10)": live.forecast(shift={"Dortmund": {"attack": 0.10}}, **cut),
        "Both": live.forecast(shift={"Bayern Munich": {"attack": -0.15}, "Dortmund": {"attack": 0.10}}, **cut),
    }
    fig, ax = plots.what_if(fc, scen, "p_title", ["Bayern Munich", "Dortmund", "Leverkusen"])
    ax.set_title("What would it take to stop Bayern?")
    _subtitle(ax, "Title probability under what-if shifts to team ratings (as of 8 Oct)")
    save(fig, "12_what_if_title.png")


# ---- 4. honesty: grading and drift -------------------------------------------------------------------
def grading_figures(quick):
    path = CACHE / "walkforward_2019_2025.csv"
    if not path.exists() and not quick:
        frames = []
        for y in range(2019, 2026):
            ev = Bundesliga(y).evaluate()
            frames.append(ev.attrs["predictions"].assign(Season=y))
            print(y, ev.round(4).to_dict("records"))
        pd.concat(frames).to_csv(path, index=False)
    p = pd.read_csv(path)
    o = outcome_index(p.FTHG.to_numpy(), p.FTAG.to_numpy())
    preds = {"Glass box": p[["pH", "pD", "pA"]].to_numpy(), "GBM": p[["ml_pH", "ml_pD", "ml_pA"]].to_numpy(),
             "Bookmakers": p[["book_pH", "book_pD", "book_pA"]].to_numpy()}
    save(plots.reliability(preds, o), "13_calibration.png")

    from glassball.model import rps
    rows = []
    for (s, d) in p.groupby("Season"):
        oo = outcome_index(d.FTHG.to_numpy(), d.FTAG.to_numpy())
        rows.append({"Season": s, **{k: rps(d[c].to_numpy(), oo).mean() for k, c in
                     [("Glass box", ["pH", "pD", "pA"]), ("GBM", ["ml_pH", "ml_pD", "ml_pA"]),
                      ("Bookmakers", ["book_pH", "book_pD", "book_pA"])]}})
    r = pd.DataFrame(rows).set_index("Season")
    fig, ax = plt.subplots(figsize=(10, 3.8))
    w = 0.26
    for k, (col, c) in enumerate(zip(r.columns, (GLASS, GBM, BOOK))):
        ax.bar(r.index + (k - 1) * w, r[col], width=w - 0.03, color=c, label=col)
    ax.set_ylim(0.175, r.values.max() + 0.006)
    ax.set_xticks(r.index, [season_label(s) for s in r.index])
    ax.grid(axis="x", visible=False)
    ax.set_title("Seven seasons, every matchday predicted blind (lower is better)")
    _subtitle(ax, "Ranked probability score; both models refit before every matchday. GBM beat the glass box in 1 of 7 seasons; "
                  "the market beat both in all 7. Axis starts at 0.175")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.1), fontsize=9)
    save(fig, "14_rps_by_season.png")

    # drift: watching a title race unfold, 2023/24 (Leverkusen's unbeaten season)
    path = CACHE / "title_race_2023.csv"
    if not path.exists() and not quick:
        s = Bundesliga(2023)
        rows = {}
        for md in range(1, 35):
            rows[md] = s.forecast(before_matchday=md, n_sims=4000).table.p_title
        pd.DataFrame(rows).T.to_csv(path)
    tr = pd.read_csv(path, index_col=0)
    tr = tr[tr.max().sort_values(ascending=False).index[:4]]
    fig = plots.race(tr, title="Watching it drift: the 2023/24 title race, forecast before every matchday")
    _subtitle(fig.axes[0], "Bayern started as favourites (52%); Leverkusen only passed 50% before matchday 19. "
                           "Strong priors are honest, and slow")
    save(fig, "15_title_race_2023.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    hist = load_history(2004, 2026)
    dataset_figures(hist)
    ratings_evolution(hist)
    forecast_figures()
    live = Bundesliga(2026, data_dir=PRE / "data" / "raw",
                      fixtures_file=PRE / "data" / "raw" / "openligadb_bl1_2026_20261008.json")
    drivers_figures(live)
    grading_figures(a.quick)
