"""Plots for every object the package returns. Each function takes the object and returns a Figure.

    from glassball import Bundesliga, plots
    s = Bundesliga(2026)
    plots.matchday(s.predict(contrast=True))
    plots.table(s.forecast())
    plots.explain(s.explain("Bayern Munich", "RB Leipzig"))
    plots.swing(s.forecast().swing("Dortmund", "title"))
"""
from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# ---- palette (validated: categorical slots pass CVD all-pairs; H/D/A is a diverging pair + neutral)
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8983", "#e6e5e0"
HOME, DRAW, AWAY = "#2a78d6", "#b4b2aa", "#e34948"
GLASS, GBM, BOOK = "#2a78d6", "#eb6834", "#1baf7a"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUES = LinearSegmentedColormap.from_list("seq", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])


def style():
    matplotlib.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 24, "axes.labelcolor": INK2, "axes.edgecolor": GRID, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
        "grid.linewidth": 0.6, "axes.axisbelow": True, "xtick.color": INK2, "ytick.color": INK2,
        "xtick.major.size": 0, "ytick.major.size": 0, "text.color": INK, "legend.frameon": False,
        "lines.linewidth": 2, "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
    })


style()


def _subtitle(ax, text):
    ax.text(0, 1.012, text, transform=ax.transAxes, color=INK2, fontsize=9, va="bottom")


def _pct(p):
    return f"{100 * p:.0f}%"


# ---- matches -------------------------------------------------------------------------------
def matchday(pred: pd.DataFrame, title: str | None = None):
    """Stacked home/draw/away bars for one matchday; GBM (if present) as ticks on the same scale."""
    n = len(pred)
    fig, ax = plt.subplots(figsize=(9, 0.55 * n + 1.4))
    y = np.arange(n)[::-1]
    for i, r in enumerate(pred.itertuples()):
        left = 0
        for p, c in [(r.pH, HOME), (r.pD, DRAW), (r.pA, AWAY)]:
            ax.barh(y[i], p - 0.004, left=left + 0.002, color=c, height=0.62, edgecolor=SURFACE, linewidth=0)
            if p >= 0.09:
                ax.text(left + p / 2, y[i], _pct(p), ha="center", va="center", fontsize=8.5,
                        color="white" if c != DRAW else INK, fontweight="bold")
            left += p
        if hasattr(r, "ml_pH"):
            for x in (r.ml_pH, r.ml_pH + r.ml_pD):
                ax.plot([x, x], [y[i] - 0.4, y[i] + 0.4], color=INK, lw=1.6, solid_capstyle="butt")
        if hasattr(r, "FTHG") and pd.notna(r.FTHG):
            ax.text(1.02, y[i], f"{int(r.FTHG)}–{int(r.FTAG)}", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y, [f"{h}  vs  {a}" for h, a in zip(pred.HomeTeam, pred.AwayTeam)])
    ax.set_xlim(0, 1); ax.set_xticks([0, .25, .5, .75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="y", visible=False)
    md = int(pred.Matchday.iloc[0])
    ax.set_title(title or f"Matchday {md}: who wins?")
    legend = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (HOME, DRAW, AWAY)]
    labels = ["Home win", "Draw", "Away win"]
    if "ml_pH" in pred:
        legend.append(plt.Line2D([0], [0], color=INK, lw=1.6)); labels.append("GBM's H | D | A boundaries")
    ax.legend(legend, labels, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.02 - 0.3 / n), fontsize=9)
    _subtitle(ax, "Glass-box probabilities; every bar decomposes into home advantage, attack and defence")
    return fig


def explain(ex: pd.DataFrame):
    """Waterfall of the additive drivers of one forecast, in goals."""
    home, away = ex.attrs["home"], ex.attrs["away"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharex=True)
    for ax, side, lam, name, c in [(axes[0], "home", ex.attrs["lambda_home"], home, HOME),
                                   (axes[1], "away", ex.attrs["lambda_away"], away, AWAY)]:
        rows = ex[ex.affects.isin([f"{side} goals", "both goals"])]
        cum, ys = 0.0, []
        labels = list(rows.driver) + [f"= expected {name} goals"]
        for i, r in enumerate(rows.itertuples()):
            ax.barh(len(labels) - 1 - i, r.value, left=cum, color=c if r.value >= 0 else MUTED, height=0.55)
            ax.text(cum + r.value + (0.02 if r.value >= 0 else -0.02), len(labels) - 1 - i, f"×{r.multiplier:.2f}",
                    va="center", ha="left" if r.value >= 0 else "right", fontsize=9, color=INK2)
            ax.plot([cum + r.value] * 2, [len(labels) - 1 - i - 0.28, len(labels) - 2 - i + 0.28], color=MUTED, lw=0.8)
            cum += r.value
        ax.barh(0, cum, color=INK, height=0.55)
        ax.text(cum + 0.02, 0, f"{lam:.2f} goals", va="center", fontsize=9.5, fontweight="bold")
        ax.set_yticks(range(len(labels))[::-1], labels)
        ax.axvline(0, color=INK2, lw=0.8)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("contribution to log(expected goals)")
    M = ex.attrs["matrix"]
    pH, pD, pA = np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()
    fig.suptitle(f"Why the model says {home} {_pct(pH)} · draw {_pct(pD)} · {away} {_pct(pA)}",
                 x=0.01, ha="left", fontweight="bold", fontsize=12.5)
    fig.text(0.01, 0.9, "Each driver multiplies the expected goals; positive bars push scoring up", color=INK2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return fig


def sensitivity(ex: pd.DataFrame):
    """Tornado: how much P(home win) moves if each driver is one standard error higher or lower."""
    d = ex.assign(abs=ex["p_home_win_if_+1se"].abs()).sort_values("abs")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    y = np.arange(len(d))
    v = d["p_home_win_if_+1se"].to_numpy()
    ax.barh(y, v, color=[HOME if x > 0 else AWAY for x in v], height=0.55)
    ax.barh(y, -v, color=[HOME if x < 0 else AWAY for x in v], height=0.55, alpha=0.35)
    ax.set_yticks(y, [f"{r.driver}  (±{r.std_err:.2f})" for r in d.itertuples()])
    ax.axvline(0, color=INK2, lw=0.8)
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:+.0f} pp")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"What would sway {ex.attrs['home']} vs {ex.attrs['away']}?")
    _subtitle(ax, f"Change in home-win probability ({_pct(ex.attrs['p_home'])}) if one driver moves by its "
                  "standard error (solid: +1 SE, faded: −1 SE)")
    return fig


# ---- the season ----------------------------------------------------------------------------
def table(fc, title="Where will they finish?"):
    """Heatmap of final-position probabilities."""
    t = fc.table if hasattr(fc, "table") else fc
    pos = t[[c for c in t.columns if c.startswith("pos_")]].to_numpy()
    n = len(t)
    fig, ax = plt.subplots(figsize=(11, 0.42 * n + 1.6))
    ax.imshow(pos, cmap=BLUES, vmin=0, vmax=max(0.5, pos.max()), aspect="auto")
    for i in range(n):
        for j in range(n):
            if pos[i, j] >= 0.03:
                ax.text(j, i, f"{100 * pos[i, j]:.0f}", ha="center", va="center", fontsize=8,
                        color="white" if pos[i, j] > 0.3 else INK)
    ax.set_yticks(range(n), [f"{tm}  ({e:.0f} pts)" for tm, e in zip(t.index, t.exp_points)])
    ax.set_xticks(range(n), [str(i + 1) for i in range(n)])
    ax.xaxis.tick_top()
    ax.grid(False)
    for x, lab in [(3.5, "Champions League"), (15.5, "play-off"), (16.5, "relegation")]:
        ax.axvline(x, color=INK2, lw=1, ls=(0, (2, 2)))
    ax.set_title(title, pad=46)
    ax.text(0, 1.075, "Probability (%) of each final position, 20,000 simulated seasons with rating uncertainty",
            transform=ax.transAxes, color=INK2, fontsize=9)
    ax.tick_params(axis="x", labelsize=9)
    return fig


def swing(sw: pd.DataFrame):
    """For the matches that matter most: the event probability under each result."""
    team, event, base = sw.attrs["team"], sw.attrs["event"], sw.attrs["baseline"]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(sw) + 1.5))
    y = np.arange(len(sw))[::-1]
    for i, r in enumerate(sw.itertuples()):
        vals = [r.if_home_win, r.if_draw, r.if_away_win]
        ax.plot([min(vals), max(vals)], [y[i]] * 2, color=GRID, lw=6, solid_capstyle="round", zorder=1)
        for v, c, lab in zip(vals, (HOME, DRAW, AWAY), ("H", "D", "A")):
            ax.scatter(v, y[i], s=90, color=c, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.axvline(base, color=INK2, lw=1, ls=(0, (3, 2)))
    ax.text(base, -0.75, f" today: {_pct(base)}", color=INK2, fontsize=9, va="center")
    ax.set_ylim(-1, len(sw) - 0.4)
    ax.set_yticks(y, [f"MD{r.Matchday}  {r.HomeTeam} vs {r.AwayTeam}" for r in sw.itertuples()])
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.grid(axis="y", visible=False)
    nice = {"title": "the title", "top4": "the top 4", "relegated": "relegation", "top6": "the top 6",
            "playoff16": "the relegation play-off"}[event]
    ax.set_title(f"Which matches decide whether {team} {'win' if event == 'title' else 'reach'} {nice}?"
                 if event != "relegated" else f"Which matches decide whether {team} go down?")
    _subtitle(ax, f"P({event}) given each result of that match, from the simulated seasons")
    ax.legend([plt.Line2D([0], [0], marker="o", ls="", color=c, markersize=8) for c in (HOME, DRAW, AWAY)],
              ["if home win", "if draw", "if away win"], ncol=3, loc="upper left",
              bbox_to_anchor=(0, -0.04 - 0.3 / len(sw)), fontsize=9)
    return fig


def what_if(base_fc, scenarios: dict, metric="p_title", teams=None):
    """Compare a metric across what-if scenarios (dict of label -> TableForecast)."""
    teams = teams or list(base_fc.table.index[:4])
    labels = ["As forecast"] + list(scenarios)
    data = [base_fc.table.loc[teams, metric]] + [s.table.loc[teams, metric] for s in scenarios.values()]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(labels) * len(teams) / 2 + 1.5))
    h = 0.8 / len(teams)
    for k, tm in enumerate(teams):
        vals = [d[tm] for d in data]
        yy = np.arange(len(labels))[::-1] + (len(teams) / 2 - k - 0.5) * h
        ax.barh(yy, vals, height=h * 0.85, color=SERIES[k], label=tm)
        for v, yv in zip(vals, yy):
            ax.text(v + 0.005, yv, _pct(v), va="center", fontsize=8, color=INK2)
    ax.set_yticks(np.arange(len(labels))[::-1], labels)
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=len(teams), loc="upper left", bbox_to_anchor=(0, -0.06), fontsize=9)
    return fig, ax


def race(history: pd.DataFrame, metric="p_title", title="Title race, as the season unfolded"):
    """`history`: rows = matchday, columns = teams, values = probability."""
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for k, tm in enumerate(history.columns):
        ax.plot(history.index, history[tm], color=SERIES[k], lw=2.2)
    ends = history.iloc[-1].sort_values(ascending=False)
    last_y = None
    for tm, v in ends.items():  # direct-label only where labels won't collide; the legend covers the rest
        if last_y is None or last_y - v > 0.06:
            ax.text(history.index[-1] + 0.4, v, tm, color=INK, fontsize=9, va="center")
            last_y = v
    ax.set_xlim(history.index.min(), history.index.max() + 5)
    ax.set_ylim(0, 1.02)
    ax.yaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.set_xlabel("forecast made before matchday")
    ax.set_title(title)
    ax.legend(history.columns, ncol=len(history.columns), loc="upper left", bbox_to_anchor=(0, -0.14), fontsize=9)
    return fig


# ---- grading ---------------------------------------------------------------------------------
def reliability(preds: dict[str, np.ndarray], outcomes: np.ndarray, bins=10):
    """Calibration: predicted probability vs observed frequency, all three outcomes pooled."""
    fig, ax = plt.subplots(figsize=(5.4, 5.2))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls=(0, (3, 2)))
    obs = np.eye(3)[outcomes].ravel()
    colors = [GLASS, GBM, BOOK, SERIES[3]]
    for (name, P), c in zip(preds.items(), colors):
        p = P.ravel()
        edges = np.quantile(p, np.linspace(0, 1, bins + 1))
        k = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
        xs = [p[k == b].mean() for b in range(bins)]
        ys = [obs[k == b].mean() for b in range(bins)]
        ax.plot(xs, ys, color=c, marker="o", markersize=6, markeredgecolor=SURFACE, label=name)
    ax.set_xlim(0, 0.9); ax.set_ylim(0, 0.9)
    ax.xaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.yaxis.set_major_formatter(lambda x, _: f"{100 * x:.0f}%")
    ax.set_xlabel("predicted probability"); ax.set_ylabel("observed frequency")
    ax.set_title("Does 30% mean 30%?")
    _subtitle(ax, "Calibration on the diagonal = honest probabilities")
    ax.legend(loc="upper left", fontsize=9)
    return fig
