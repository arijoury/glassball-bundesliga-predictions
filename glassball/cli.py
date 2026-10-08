"""Command-line interface: `glassball <command> [options]`. Run `glassball --help`."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__

EXAMPLES = """\
examples:
  glassball                              overview of the current season
  glassball winner                       who wins the league?
  glassball table                        predicted final table
  glassball table --full --plot table.png
  glassball matchday                     next matchday, match by match
  glassball matchday 12 -v               matchday 12, with expected goals and the drivers
  glassball matchday all --csv rest.csv  every remaining match, to a spreadsheet
  glassball explain bayern dortmund      why the model predicts what it does
  glassball swing bvb                    which matches decide Dortmund's title chances
  glassball swing union --event relegated
  glassball winner --shift "bayern:attack=-0.15"     what if Bayern lose their top scorer?
  glassball table --season 2023 -b 10    2023/24 as it looked before matchday 10
  glassball evaluate --season 2025       how good was the model last season?
  glassball winner --model gbm           the same question, asked to the machine-learning model
  glassball crowd                        how much of home advantage is the crowd? (ghost-game natural experiment)
  glassball form                         is "form" real, or just team strength in disguise?

team names are forgiving: bayern, BVB, gladbach, köln, hsv, s04 ... (see `glassball teams`)
"""


# ---- argument parsing ------------------------------------------------------------------------
def season_arg(s: str) -> int:
    s = s.strip().replace("-", "/")
    head = s.split("/")[0]
    y = int(head)
    return y + 2000 if y < 100 else y


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("season and time")
    g.add_argument("-s", "--season", type=season_arg, default=None, metavar="YEAR",
                   help="season by its starting year: 2026, 2026/27 or 26/27 (default: current season)")
    g.add_argument("-b", "--before-matchday", type=int, metavar="N",
                   help="only use matches played before matchday N (time travel)")
    g.add_argument("--as-of", metavar="DATE", help="only use matches played before DATE (YYYY-MM-DD)")
    o = common.add_argument_group("output")
    o.add_argument("-v", "--verbose", action="store_true", help="more detail: expected goals, drivers, uncertainty, data info")
    o.add_argument("-q", "--quiet", action="store_true", help="just the answer, no progress messages or notes")
    o.add_argument("--plot", metavar="FILE", help="also save a chart (.png, .svg or .pdf)")
    o.add_argument("--csv", metavar="FILE", help="also save the result as CSV")
    o.add_argument("--json", action="store_true", help="print the result as JSON instead of a table")
    mo = common.add_argument_group("model")
    mo.add_argument("--model", choices=["glassbox", "gbm"], default="glassbox",
                    help="glassbox (default): explainable goals model; gbm: gradient-boosted classifier on Elo + form")
    mo.add_argument("--half-life", type=float, metavar="DAYS",
                    help="glass box memory: how fast old results fade (default 270; lower = reacts faster to form)")
    mo.add_argument("--fixed-ratings", action="store_true",
                    help="simulate as if team ratings were known exactly (shows how overconfident that is)")
    m = common.add_argument_group("simulation and data")
    m.add_argument("--sims", type=int, default=10_000, metavar="N", help="simulated seasons (default 10000)")
    m.add_argument("--seed", type=int, default=20261008, help="random seed (default 20261008)")
    m.add_argument("--shift", action="append", default=[], metavar="TEAM:FIELD=X",
                   help='what-if: shift a rating, e.g. "bayern:attack=-0.15" or "hsv:defence=-0.1" '
                        "(repeatable; attack +0.1 = about 10%% more goals; defence -0.1 = about 10%% fewer conceded)")
    m.add_argument("--offline", action="store_true", help="use cached data only, no downloads")
    m.add_argument("--refresh", action="store_true", help="re-download this season's data now")
    m.add_argument("--data-dir", help=argparse.SUPPRESS)
    m.add_argument("--fixtures-file", help=argparse.SUPPRESS)

    p = argparse.ArgumentParser(
        prog="glassball", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EXAMPLES,
        description="Bundesliga predictions you can audit: every probability traces back to its drivers.")
    p.add_argument("--version", action="version", version=f"glassball {__version__}")
    sub = p.add_subparsers(dest="command", metavar="command")

    def add(name, help_, **kw):
        return sub.add_parser(name, parents=[common], help=help_, description=help_,
                              formatter_class=argparse.RawDescriptionHelpFormatter, **kw)

    add("overview", "season status, title odds and the next matchday (default)")
    add("winner", "who wins the league?")
    t = add("table", "predicted final table")
    t.add_argument("--full", action="store_true", help="show the probability of every final position")
    md = add("matchday", "match-by-match predictions")
    md.add_argument("matchday", nargs="?", default="next", help="a matchday number, 'next' (default) or 'all' remaining")
    md.add_argument("--contrast", action="store_true", help="also show the gradient-boosted contrast model")
    ex = add("explain", "why the model predicts what it does for one match")
    ex.add_argument("home"); ex.add_argument("away")
    sw = add("swing", "which remaining matches decide a team's season")
    sw.add_argument("team")
    sw.add_argument("--event", default="title", choices=["title", "top4", "top6", "playoff16", "relegated"])
    sw.add_argument("--top", type=int, default=8, help="how many matches to show (default 8)")
    add("standings", "the actual league table so far")
    add("ratings", "attack and defence strength of every team")
    ev = add("evaluate", "grade the model on the matchdays already played (vs bookmakers and a GBM)")
    ev.add_argument("--no-contrast", action="store_true", help="skip the GBM (faster)")
    add("teams", "list team names and accepted nicknames")
    cr = add("crowd", "causal: how much of home advantage is the crowd? (2020-21 ghost games as a natural experiment)")
    cr.add_argument("--seasons", default="2015-2024", metavar="A-B", help="seasons to compare (default 2015-2024)")
    cr.add_argument("--exclude-autumn-2020", action="store_true",
                    help="robustness: drop Sep-Oct 2020, when a few stadiums briefly admitted small crowds")
    fo = add("form", "causal: does recent form predict results beyond team strength?")
    fo.add_argument("--seasons", default="2012-2025", metavar="A-B", help="seasons to analyse (default 2012-2025)")
    fo.add_argument("--window", type=int, default=3, help="form = last N matches (default 3)")
    return p


# ---- helpers ---------------------------------------------------------------------------------
class Out:
    def __init__(self, a):
        self.a, self.t0 = a, time.time()

    def info(self, msg):
        if not self.a.quiet and not self.a.json:
            print(msg, file=sys.stderr, flush=True)

    def note(self, msg):
        if not self.a.quiet and not self.a.json:
            print(f"\n{msg}")


def pct(x, digits=0):
    if pd.isna(x):
        return ""
    v = 100 * x
    if 0 < v < 0.5 and digits == 0:
        return "<1%"
    if v >= 99.5 and digits == 0:  # a simulation never proves certainty
        return ">99%"
    return f"{v:.{digits}f}%"


def season_name(y):
    return f"{y}/{(y + 1) % 100:02d}"


def parse_shifts(items, s):
    shifts = {}
    for it in items:
        try:
            team, rest = it.split(":", 1)
            field, val = rest.split("=", 1)
            field = {"att": "attack", "attack": "attack", "def": "defence", "defence": "defence",
                     "defense": "defence"}[field.strip().lower()]
            shifts.setdefault(s.team(team.strip()), {})[field] = float(val)
        except (ValueError, KeyError) as e:
            if isinstance(e, KeyError) and "Unknown team" in str(e):
                raise
            raise ValueError(f'could not read --shift "{it}"; use e.g. "bayern:attack=-0.15"') from None
    return shifts


def emit(df: pd.DataFrame, a, pretty: pd.DataFrame | None = None):
    """Print a table (or JSON) and optionally save CSV."""
    if a.csv:
        df.to_csv(a.csv, index=False)
    if a.json:
        print(df.to_json(orient="records", indent=2, force_ascii=False, date_format="iso"))
    else:
        print((pretty if pretty is not None else df).to_string(index=False))


def save_plot(fig, path, out):
    import matplotlib
    matplotlib.use("Agg", force=True)
    fig.savefig(path)
    out.info(f"chart saved to {path}")


def when(a):
    return {"before_matchday": a.before_matchday, "as_of": a.as_of}


def describe_cutoff(s, a):
    c = s.cutoff(a.before_matchday, a.as_of)
    n = len(s.played(a.before_matchday, a.as_of))
    return f"using {n} matches played before {c.date()}"


# ---- commands --------------------------------------------------------------------------------
def cmd_winner(s, a, out):
    fc = forecast(s, a, out)
    t = fc.table.sort_values("p_title", ascending=False)
    top = t.index[0]
    if a.json or a.csv:
        emit(t[["p_title"]].reset_index(names="team"), a)
        if a.json:
            return
    if len(fc.remaining) == 0:  # nothing left to play: report what happened
        pts = int(fc.table.exp_points.max())
        print(f"{top}" if a.quiet else f"{top} won the {season_name(s.season)} Bundesliga with {pts} points.")
    elif a.quiet:
        print(f"{top} {pct(t.p_title.iloc[0])}")
    else:
        others = ", ".join(f"{tm} {pct(p)}" for tm, p in t.p_title.iloc[1:4].items() if p >= 0.005)
        print(f"{top} are favourites to win the {season_name(s.season)} Bundesliga: {pct(t.p_title.iloc[0])}"
              + (f"  (then {others})" if others else ""))
        if a.verbose:
            print()
            print(t[t.p_title > 0][["p_title", "exp_points"]].rename(columns={"p_title": "title", "exp_points": "exp. points"})
                  .to_string(formatters={"title": pct, "exp. points": "{:.1f}".format}))
    if a.plot:
        from . import plots
        fig, ax = plots.what_if(fc, {}, "p_title", list(t.index[:5]))
        ax.set_title(f"Who wins the {season_name(s.season)} Bundesliga?")
        save_plot(fig, a.plot, out)


def forecast(s, a, out):
    shifts = parse_shifts(a.shift, s)
    out.info(f"simulating {a.sims:,} seasons ({describe_cutoff(s, a)})" + (f", what-if: {shifts}" if shifts else "") + " ...")
    if a.model == "gbm":
        out.info("model: gradient-boosted classifier (no goal model: ties on points broken by current goal difference)")
    return s.forecast(**when(a), n_sims=a.sims, seed=a.seed, shift=shifts or None, model=a.model,
                      rating_uncertainty=not a.fixed_ratings)


def cmd_table(s, a, out):
    fc = forecast(s, a, out)
    t = fc.table
    now = s.table(as_of=s.cutoff(a.before_matchday, a.as_of))
    df = pd.DataFrame({
        "pos": range(1, len(t) + 1), "team": t.index, "now": now.loc[t.index, "Pts"].to_numpy(),
        "exp_points": t.exp_points.to_numpy(), "title": t.p_title.to_numpy(), "top4": t.p_top4.to_numpy(),
        "relegated": t.p_relegated.to_numpy()})
    if a.verbose:
        df.insert(4, "exp_position", t.exp_position.to_numpy())
        df.insert(7, "top6", t.p_top6.to_numpy())
        df.insert(9, "playoff16", t.p_playoff16.to_numpy())
    if a.full:
        pos = t[[c for c in t.columns if c.startswith("pos_")]]
        df = pd.concat([df[["pos", "team", "exp_points"]], pos.reset_index(drop=True)], axis=1)
    pretty = df.copy()
    for c in pretty.columns:
        if c in ("title", "top4", "top6", "playoff16", "relegated") or c.startswith("pos_"):
            pretty[c] = pretty[c].map(pct)
    for c in ("exp_points", "exp_position"):
        if c in pretty:
            pretty[c] = pretty[c].map("{:.1f}".format)
    pretty = pretty.rename(columns={"now": "pts now", "exp_points": "exp. pts", "exp_position": "exp. pos",
                                    "relegated": "relegation", "playoff16": "play-off"})
    if not a.quiet and not a.json:
        print(f"Predicted final table, {season_name(s.season)}\n")
    emit(df, a, pretty)
    out.note("exp. pts = average final points over the simulated seasons; columns are probabilities. "
             "Relegation = 17th or 18th; play-off = 16th.")
    if a.plot:
        from . import plots
        save_plot(plots.table(fc, f"Final table {season_name(s.season)}: where will they finish?"), a.plot, out)


def cmd_matchday(s, a, out):
    if a.matchday == "all":
        open_mds = sorted(s.fixtures[~s.fixtures.Finished].Matchday.unique())
        mds = [int(m) for m in open_mds]
    elif a.matchday == "next":
        mds = [s.next_matchday() or 34]
    else:
        mds = [int(a.matchday)]
    if a.matchday == "all":  # every remaining match, all forecast from the same information set
        kw = {"as_of": s.cutoff(a.before_matchday, a.as_of)}
        mds = [m for m in mds if m >= (a.before_matchday or 0)]
    else:
        kw = {k: v for k, v in when(a).items() if v is not None}
    gbm = a.model == "gbm"
    frames = []
    for md in mds:
        p = s.predict(md, contrast=a.contrast or gbm, **kw)
        if gbm:  # the GBM's probabilities take the main columns; it has no goal model
            p[["pH", "pD", "pA"]] = p[["ml_pH", "ml_pD", "ml_pA"]].to_numpy()
            p["likely_score"] = "–"
        if a.matchday == "all":
            p = p[p.FTHG.isna()]
        frames.append(p)
    df = pd.concat(frames, ignore_index=True)

    def pick(r):
        k = int(np.argmax([r.pH, r.pD, r.pA]))
        return [r.HomeTeam, "draw", r.AwayTeam][k]

    df["pick"] = [pick(r) for r in df.itertuples()]
    played = df.FTHG.notna()
    cols = ["Matchday", "Kickoff", "HomeTeam", "AwayTeam", "pH", "pD", "pA", "pick"] + ([] if gbm else ["likely_score"])
    if a.verbose and not gbm:
        cols += ["xG_home", "xG_away"]
    if a.contrast and not gbm:
        cols += ["ml_pH", "ml_pD", "ml_pA"]
    if played.any():
        df["result"] = [f"{int(h)}-{int(g)}" if pd.notna(h) else "" for h, g in zip(df.FTHG, df.FTAG)]
        actual = [("" if pd.isna(h) else r.HomeTeam if h > g else r.AwayTeam if h < g else "draw")
                  for h, g, r in zip(df.FTHG, df.FTAG, df.itertuples())]
        df["pick_right"] = ["" if not x else ("✓" if x == p else "✗") for x, p in zip(actual, df.pick)]
        cols += ["result", "pick_right"]
        if "book_pH" in df:
            cols += ["book_pH", "book_pD", "book_pA"]
    out_df = df[cols].copy()
    pretty = out_df.copy()
    pretty["Kickoff"] = pd.to_datetime(pretty.Kickoff).dt.strftime("%a %d %b %H:%M")
    for c in [c for c in pretty.columns if c.endswith(("_pH", "_pD", "_pA")) or c in ("pH", "pD", "pA")]:
        pretty[c] = pretty[c].map(pct)
    for c in ("xG_home", "xG_away"):
        if c in pretty:
            pretty[c] = pretty[c].map("{:.2f}".format)
    pretty = pretty.rename(columns={"Matchday": "md", "Kickoff": "kick-off", "HomeTeam": "home", "AwayTeam": "away",
                                    "pH": "home win", "pD": "draw", "pA": "away win", "likely_score": "top score",
                                    "xG_home": "xG home", "xG_away": "xG away", "ml_pH": "GBM H", "ml_pD": "GBM D",
                                    "ml_pA": "GBM A", "book_pH": "book H", "book_pD": "book D", "book_pA": "book A",
                                    "pick_right": ""})
    if len(mds) == 1:
        pretty = pretty.drop(columns="md")
        if not a.quiet and not a.json:
            print(f"Matchday {mds[0]}, {season_name(s.season)}\n")
    emit(out_df, a, pretty)
    out.note("pick = most likely result; top score = most likely exact score. These can differ: "
             "a 1-1 is often the single likeliest score even when one side is favourite.")
    if gbm:
        out.note("model: gradient-boosted classifier. It gives win/draw/loss odds only: no expected goals, "
                 "no scores, and no breakdown of why. Try the same matchday without --model gbm.")
    if a.verbose and not a.json and not gbm:
        print()
        for r in df.itertuples():
            print(f"  {r.HomeTeam} vs {r.AwayTeam}: home goals ×{np.exp(r.drv_base):.2f} base ×{np.exp(r.drv_home_adv):.2f} "
                  f"home adv ×{np.exp(r.drv_home_attack):.2f} attack ×{np.exp(r.drv_away_defence):.2f} opp. defence"
                  f" = {r.xG_home:.2f};  away goals ×{np.exp(r.drv_base):.2f} ×{np.exp(r.drv_away_attack):.2f}"
                  f" ×{np.exp(r.drv_home_defence):.2f} = {r.xG_away:.2f}")
    if a.plot:
        from . import plots
        for i, md in enumerate(mds):
            path = Path(a.plot)
            if len(mds) > 1:
                path = path.with_name(f"{path.stem}_md{md:02d}{path.suffix}")
            save_plot(plots.matchday(df[df.Matchday == md].reset_index(drop=True)), path, out)


def cmd_explain(s, a, out):
    if a.model == "gbm":
        raise ValueError("the GBM can't explain a single forecast; that's the point of the glass box. "
                         "Drop --model gbm (or compare them with: glassball matchday --contrast)")
    ex = s.explain(a.home, a.away, **when(a))
    at = ex.attrs
    M = at["matrix"]
    pH, pD, pA = np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()
    if a.json or a.csv:
        emit(ex, a)
        if a.json:
            return
    home, away = at["home"], at["away"]
    print(f"{home} vs {away}:  {home} {pct(pH)} · draw {pct(pD)} · {away} {pct(pA)}\n")
    print(f"Expected goals  {home}: {at['lambda_home']:.2f}   {away}: {at['lambda_away']:.2f}\n")
    for side, label, lam in (("home", home, at["lambda_home"]), ("away", away, at["lambda_away"])):
        rows = ex[ex.affects.isin([f"{side} goals", "both goals"])]
        parts = "  ×  ".join(f"{r.multiplier:.2f} ({r.driver})" for r in rows.itertuples())
        print(f"  {label} goals = {parts}  =  {lam:.2f}")
    if a.verbose or not a.quiet:
        print("\nWhat would sway it (home-win probability if one driver is one standard error higher):")
        for _, r in ex.reindex(ex["p_home_win_if_+1se"].abs().sort_values(ascending=False).index).iterrows():
            print(f"  {r.driver:<28} {100 * r['p_home_win_if_+1se']:+5.1f} pp   (rating {r.value:+.2f} ± {r.std_err:.2f})")
    if a.verbose:
        i, j = np.unravel_index(np.argsort(M, axis=None)[::-1][:5], M.shape)
        print("\nMost likely scores: " + ", ".join(f"{x}-{y} ({pct(M[x, y])})" for x, y in zip(i, j)))
    out.note("Ratings are on a log scale: attack +0.1 ≈ 10% more goals scored; defence −0.1 ≈ 10% fewer conceded.")
    if a.plot:
        from . import plots
        save_plot(plots.explain(ex), a.plot, out)
        p = Path(a.plot)
        save_plot(plots.sensitivity(ex), p.with_name(f"{p.stem}_sensitivity{p.suffix}"), out)


def cmd_swing(s, a, out):
    fc = forecast(s, a, out)
    sw = fc.swing(a.team, a.event, top=a.top)
    team, base = sw.attrs["team"], sw.attrs["baseline"]
    pretty = sw.copy()
    for c in ("if_home_win", "if_draw", "if_away_win", "swing"):
        pretty[c] = pretty[c].map(pct)
    pretty = pretty.rename(columns={"Matchday": "md", "HomeTeam": "home", "AwayTeam": "away",
                                    "if_home_win": "if home win", "if_draw": "if draw", "if_away_win": "if away win"})
    if not a.quiet and not a.json:
        print(f"P({team}: {a.event}) today: {pct(base)}. The matches that move it most:\n")
    emit(sw, a, pretty)
    if a.plot:
        from . import plots
        save_plot(plots.swing(sw), a.plot, out)


def cmd_standings(s, a, out):
    c = s.cutoff(a.before_matchday, a.as_of)
    t = s.table(as_of=c).reset_index(names="team")
    t = t[["Pos", "team"] + [x for x in t.columns if x not in ("Pos", "team")]].rename(columns={"Pos": "pos"})
    if not a.quiet and not a.json:
        print(f"Bundesliga {season_name(s.season)}, matches played before {c.date()}\n")
    emit(t, a)


def cmd_ratings(s, a, out):
    r = s.ratings(**when(a))
    df = r.assign(goals_for_x=np.exp(r.attack), goals_against_x=np.exp(r.defence))
    cols = ["team", "net", "attack", "defence"] + (["attack_sd", "defence_sd", "goals_for_x", "goals_against_x"] if a.verbose else [])
    pretty = df[cols].copy()
    for c in cols[1:]:
        pretty[c] = pretty[c].map("{:+.2f}".format if c in ("net", "attack", "defence") else "{:.2f}".format)
    if not a.quiet and not a.json:
        print(f"Team strength, {season_name(s.season)} ({describe_cutoff(s, a)})\n")
    emit(df[cols], a, pretty)
    out.note("net = attack − defence. Log scale relative to an average side: attack +0.3 ≈ 35% more goals scored, "
             "defence −0.3 ≈ 26% fewer conceded.")
    if a.plot:
        from . import plots
        save_plot(plots.ratings(r), a.plot, out)


def cmd_evaluate(s, a, out):
    out.info("predicting every played matchday with data from before it (this takes a while with the GBM) ...")
    ev = s.evaluate(contrast=not a.no_contrast)
    pretty = ev.copy()
    for c in ("rps", "brier", "logloss"):
        pretty[c] = pretty[c].map("{:.4f}".format)
    pretty["accuracy"] = pretty.accuracy.map(pct)
    if not a.quiet and not a.json:
        print(f"Walk-forward grading, {season_name(s.season)} (lower rps/brier/logloss is better)\n")
    emit(ev, a, pretty)
    out.note("rps = ranked probability score, the standard for football forecasts. "
             "Bookmakers' closing odds are the benchmark to beat.")
    if a.plot:
        from . import plots
        from .model import outcome_index
        p = ev.attrs["predictions"]
        o = outcome_index(p.FTHG.to_numpy(), p.FTAG.to_numpy())
        preds = {"Glass box": p[["pH", "pD", "pA"]].to_numpy()}
        if "ml_pH" in p:
            preds["GBM"] = p[["ml_pH", "ml_pD", "ml_pA"]].to_numpy()
        if "book_pH" in p and p.book_pH.notna().all():
            preds["Bookmakers"] = p[["book_pH", "book_pD", "book_pA"]].to_numpy()
        save_plot(plots.reliability(preds, o, bins=5), a.plot, out)


def cmd_teams(s, a, out):
    from .data import ALIASES
    rows = [{"team": t, "nicknames": ", ".join(sorted(k for k, v in ALIASES.items() if v == t))} for t in s.teams]
    emit(pd.DataFrame(rows), a)


def cmd_overview(s, a, out):
    played = s.played(a.before_matchday, a.as_of)
    nxt = a.before_matchday or s.next_matchday()
    print(f"Bundesliga {season_name(s.season)}: {len(played)}/306 matches played"
          + (f", next up: matchday {nxt}" if nxt else ", season complete"))
    if len(played):
        st = s.table(as_of=s.cutoff(a.before_matchday, a.as_of))
        print("Top of the table: " + ", ".join(f"{i}. {t} {p} pts" for i, (t, p) in enumerate(st.Pts.head(3).items(), 1)))
    if nxt:
        print()
        cmd_winner(s, a, out)
        print()
        a.matchday, a.contrast = str(nxt), False
        q = a.quiet
        a.quiet = True
        cmd_matchday(s, a, out)
        a.quiet = q
        out.note("More: glassball table | glassball matchday all | glassball explain HOME AWAY | glassball --help")


def seasons_arg(txt):
    a_, b_ = (txt.split("-") + [txt])[:2]
    return season_arg(a_), season_arg(b_)


def cmd_crowd(a, out):
    from . import causal
    first, last = seasons_arg(a.seasons)
    out.info(f"fitting home advantage {season_name(first)}–{season_name(last)} with team-season strengths held fixed ...")
    r = causal.crowd_effect(first, last, exclude_early_2020_21=a.exclude_autumn_2020,
                            offline=a.offline, data_dir=a.data_dir)
    lo, hi = r["crowd_effect_ci95"]
    if a.json:
        print(json.dumps({k: (v.to_dict("records") if isinstance(v, pd.DataFrame) else v) for k, v in r.items()},
                         indent=2, default=float))
        return
    if a.csv:
        r["by_era"].to_csv(a.csv, index=False)
    print(f"Home advantage with fans:     home teams score {pct(r['home_goals_boost_with_fans'])} more goals "
          f"(log-rate {r['home_adv_with_fans']:.3f})")
    print(f"Home advantage without fans:  {pct(r['home_goals_boost_without_fans'])} more "
          f"(log-rate {r['home_adv_without_fans']:.3f}; ghost games, May 2020 – May 2021)")
    print(f"\nCrowd effect: {r['crowd_effect']:+.3f} log-rate  (95% CI {lo:+.3f} to {hi:+.3f}),"
          f" about {pct(r['crowd_share'])} of home advantage")
    print(f"Worth about {r['points_per_season_from_crowd']:.1f} points per team per season "
          f"({r['home_points_with_fans']:.2f} vs {r['home_points_without_fans']:.2f} points per home game, two average teams)")
    if lo < 0 < hi:
        print("The interval includes zero: one ghost season is ~390 matches, so this is suggestive rather than conclusive.")
    mech = r["mechanisms"]
    if len(mech):
        print("\nHow? Home teams' edge per match, with vs without fans:")
        for m_, d in mech.groupby("measure", sort=False):
            d = d.set_index("condition")
            if {"with fans", "without fans"} <= set(d.index):
                f_, g_ = d.loc["with fans"], d.loc["without fans"]
                lab = {"yellow cards": "fewer yellow cards", "fouls": "fewer fouls called", "shots": "more shots"}[m_]
                print(f"  {lab:<22} {f_.home_edge_per_match:5.2f} ± {f_.se:.2f}   →   {g_.home_edge_per_match:5.2f} ± {g_.se:.2f}")
    if a.verbose:
        print("\nHome advantage (log-rate) by season, team strength held fixed:")
        print(r["by_era"].to_string(index=False, formatters={"home_adv": "{:+.3f}".format, "se": "{:.3f}".format}))
    out.note("Design: home vs away for the same team, with vs without fans (difference-in-differences), in a Poisson "
             "model with separate team strengths for every season. Assumes nothing else that favours home teams "
             "changed in 2020-21. 2021/22 (partial crowds) is reported separately.")
    if a.plot:
        from . import plots
        save_plot(plots.crowd(r), a.plot, out)


def cmd_form(a, out):
    from . import causal
    first, last = seasons_arg(a.seasons)
    out.info(f"predicting every match {season_name(first)}–{season_name(last)} blind, then testing form ...")
    r = causal.momentum(first, last, window=a.window, offline=a.offline, data_dir=a.data_dir)
    if a.json:
        print(json.dumps({k: v for k, v in r.items() if k != "data"}, indent=2, default=float))
        return
    if a.csv:
        r["data"].to_csv(a.csv, index=False)
    n = a.window
    print(f"{r['matches']:,} team-matches, {season_name(first)}–{season_name(last)}, form = last {n} matches\n")
    print(f"Naive:    each extra point in the last {n} games → {r['naive_slope']:+.3f} points next game "
          f"(± {r['naive_se']:.3f}). Looks like momentum.")
    print(f"Adjusted: each point *above expectation* in the last {n} → {r['adjusted_slope']:+.3f} points above "
          f"expectation next game (± {r['adjusted_se']:.3f}).")
    print(f"\n'Hot' teams (≥3 points above expectation over the last {n}): next game {r['hot_next_points']:.2f} points "
          f"vs {r['hot_next_expected']:.2f} expected  (n={r['hot_n']})")
    print(f"'Cold' teams (≥3 points below):                       next game {r['cold_next_points']:.2f} points "
          f"vs {r['cold_next_expected']:.2f} expected  (n={r['cold_n']})")
    out.note("Form mostly reflects strength, which the ratings already track. Once strength is accounted for, "
             "recent results add little or nothing. 'Expected' comes from the glass box, fitted only on matches "
             "before each game.")
    if a.plot:
        from . import plots
        save_plot(plots.form(r), a.plot, out)


CAUSAL = {"crowd": cmd_crowd, "form": cmd_form}

COMMANDS = {"overview": cmd_overview, "winner": cmd_winner, "table": cmd_table, "matchday": cmd_matchday,
            "explain": cmd_explain, "swing": cmd_swing, "standings": cmd_standings, "ratings": cmd_ratings,
            "evaluate": cmd_evaluate, "teams": cmd_teams}


def main(argv=None):
    import warnings
    warnings.filterwarnings("ignore")
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["overview"] + argv
    a = parser.parse_args(argv)
    out = Out(a)
    try:
        from . import data
        from .season import Bundesliga
        season = a.season or data.current_season()
        if a.refresh:
            for f in (data.cache_dir() / f"D1_{data.season_code(season)}.csv", data.cache_dir() / f"oldb_bl1_{season}.json"):
                f.unlink(missing_ok=True)
        data.progress = out.info
        if a.command in ("crowd", "form"):  # multi-season analyses load their own data
            CAUSAL[a.command](a, out)
            return 0
        from .model import Hyper
        hyper = Hyper(half_life_days=a.half_life) if a.half_life else None
        out.info(f"loading Bundesliga {season_name(season)} ...")
        s = Bundesliga(season, offline=a.offline, data_dir=a.data_dir, fixtures_file=a.fixtures_file, hyper=hyper)
        if a.verbose:
            out.info(f"{s!r}; data cached in {a.data_dir or data.cache_dir()}")
        COMMANDS[a.command](s, a, out)
        if a.verbose:
            out.info(f"done in {time.time() - out.t0:.1f}s")
    except (KeyError, ValueError, FileNotFoundError) as e:
        msg = e.args[0] if e.args else str(e)
        print(f"glassball: error: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
