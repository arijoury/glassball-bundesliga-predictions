"""Numbers and charts for the reveal section, straight from the rolling updates.

    python reveal.py            # print every number of the scoreboard, write figures/reveal_*.png

Reads the latest rolling update in preregistration/2026-27/updates: `git pull` first to get the newest one.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from glassball import plots  # also sets the chart style

_HERE = Path(__file__).resolve().parent
REPO = next((p for p in (_HERE.parent, _HERE.parent / "forecast") if (p / "preregistration").is_dir()), _HERE.parent)
PRE = REPO / "preregistration" / "2026-27"
FREEZE = PRE / "freeze" / "2026-10-08"
UPDATES = PRE / "updates"
OUT = Path(__file__).resolve().parent / "figures"


def updates() -> list[Path]:
    return sorted(UPDATES.glob("*_md*"))


def latest() -> Path | None:
    u = updates()
    return u[-1] if u else None


def scoreboard() -> pd.DataFrame | None:
    d = latest()
    return pd.read_csv(d / "grading.csv") if d else None


def title_path(top: int = 4, event: str = "p_title") -> pd.DataFrame:
    """Probability of `event` per team: the freeze (after MD4), then after every update."""
    frames = {4: pd.read_csv(FREEZE / "table_forecast.csv", index_col=0)[event]}
    for d in updates():
        md = int(d.name.split("_md")[1])
        frames[md] = pd.read_csv(d / "forecast" / "table_forecast.csv", index_col=0)[event]
    df = pd.DataFrame(frames).T.sort_index()
    keep = df.max().sort_values(ascending=False).index[:top]
    return df[keep]


def misses_and_hits() -> tuple[pd.Series, pd.Series] | None:
    """The frozen forecast's worst and best calls so far (by RPS)."""
    d = latest()
    if not d:
        return None
    m = pd.read_csv(d / "graded_matches.csv")
    return m.loc[m.rps_glass.idxmax()], m.loc[m.rps_glass.idxmin()]


def drift_figure(event="p_title", title="Title race since the freeze"):
    path = title_path(event=event)
    fig = plots.race(path, metric=event, title=title)
    ax = fig.axes[0]
    ax.set_xlim(path.index.min(), path.index.max() + 1.6)   # race() leaves room for 5 more matchdays; we have none
    ax.set_xticks(list(path.index))
    ax.set_xlabel("after matchday (4 = the frozen forecast)")
    return fig


# ---- cards for the live notebook: the scoreboard slide, filled in ------------------------------------
# The submitted deck keeps its [__] blanks; these show the same rows next to it, straight from the
# latest rolling update. Inline styles only, so they render the same in JupyterLab, VS Code and the
# HTML backup (and stay readable in a dark Jupyter theme).
NOISE = 0.01   # stated on the slide: on ~45 matches, RPS gaps under this are noise
HOME, DRAW, AWAY = "#B4532F", "#C9B6AB", "#2F6F9F"
_FONT = "font-family:Inter,-apple-system,'Helvetica Neue',Arial,sans-serif"
_CARD = f"background:#FADCCF;color:#2E1D16;{_FONT};padding:22px 26px 18px;border-radius:14px;max-width:1040px;line-height:1.35;margin:6px 0"
_TITLE = "font-size:28px;font-weight:700;line-height:1.15;margin:0 0 4px;color:#2E1D16"
_SUB = "font-size:15px;color:#6B4A3C;margin:0 0 14px"
_KICK = "font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#6B4A3C;font-weight:600"
_TABLE = "border-collapse:collapse;width:100%;margin:0;font-size:19px;table-layout:auto;color:#2E1D16;background:transparent"
_TH = f"{_KICK};padding:6px 10px;border:none;border-bottom:2px solid #2E1D16;background:transparent;text-align:right"
_TD = "padding:9px 10px;border:none;border-bottom:1px solid #EDC5B3;color:#2E1D16;background:transparent;text-align:right;font-variant-numeric:tabular-nums"
_CHIP = "flex:1 1 220px;background:#FDF3EE;border-radius:10px;padding:12px 14px;font-size:16px;color:#2E1D16"
_NOTE = "font-size:15px;color:#5C3D30;margin:10px 0 0"
_SRC = "font-size:13px;color:#6B4A3C;margin:14px 0 0"


def _show(title: str, sub: str, body: str, d: Path):
    from IPython.display import HTML, display
    src = (f"Source: preregistration/2026-27/updates/{d.name} in the public repo. "
           "Graded automatically after each matchday; frozen code verified against its fingerprint.")
    display(HTML(f'<div style="{_CARD}"><div style="{_TITLE}">{title}</div><div style="{_SUB}">{sub}</div>'
                 f'{body}<div style="{_SRC}">{src}</div></div>'))


def _table(head: list[str], rows: list, text_cols: int = 1) -> str:
    """rows: (cells, extra td style) tuples, or a plain string for a section line. The first `text_cols` align left."""
    left = ";text-align:left"
    th = "".join(f'<th style="{_TH}{left if i < text_cols else ""}">{h}</th>' for i, h in enumerate(head))
    trs = []
    for r in rows:
        if isinstance(r, str):
            trs.append(f'<tr style="background:transparent"><td colspan="{len(head)}" style="{_TD};{_KICK};'
                       f'text-align:left;padding-top:18px;border-bottom:2px solid #2E1D16">{r}</td></tr>')
            continue
        cells, extra = r
        trs.append('<tr style="background:transparent">' + "".join(
            f'<td style="{_TD}{left if i < text_cols else ""};{extra}">{c}</td>' for i, c in enumerate(cells)) + "</tr>")
    return (f'<table style="{_TABLE}"><thead><tr style="background:transparent">{th}</tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table>')


def _chips(chips: list[str]) -> str:
    return ('<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:16px">'
            + "".join(f'<div style="{_CHIP}">{c}</div>' for c in chips) + "</div>")


def _room_line(key: str) -> str:
    """How the room voted on `key` earlier in the notebook, as a short line ('' if nobody entered hands)."""
    import room
    r = room.ROOM.get(key, {})
    hands = {k: v for k, v in r.get("hands", {}).items() if v}
    if not hands:
        return ""
    total = sum(hands.values())
    mark = {True: " ✓", False: " ✗"}.get(r.get("right"), "")
    return "Room voted: " + " · ".join(f"{room.pretty(k)} {v / total:.0%}" for k, v in hands.items()) + mark


def _md(d: Path) -> int:
    return int(d.name.split("_md")[1])


def _row(sb: pd.DataFrame, prefix: str) -> pd.Series:
    return sb[sb.index.str.startswith(prefix)].iloc[0]


def show_scoreboard(bets: dict | None = None, room_size: int | None = None):
    """The scoreboard slide's left half, filled in, plus the room's three bets resolved (recorded for the scorecard)."""
    import room
    d = latest()
    if d is None:
        print("No rolling updates yet.")
        return
    sb = scoreboard().set_index("model")
    gm = pd.read_csv(d / "graded_matches.csv")
    glass = _row(sb, "Glass box")
    rows = []
    for label in ["Glass box", "GBM", "Bookmakers", "Base rates"]:   # same rows, same order as the slide
        r = _row(sb, label)
        gap = r.rps - glass.rps
        gap_txt = "" if label == "Glass box" else f"{gap:+.3f}" + (" · noise" if abs(gap) < NOISE else "")
        acc = f"<b>{r.accuracy:.0%}</b>" if r.accuracy == sb.accuracy.max() else f"{r.accuracy:.0%}"
        style = "background:#FDF3EE;font-weight:700" if label == "Glass box" else ""
        rows.append(([label, f"{r.rps:.3f}", acc, gap_txt], style))
    table = _table(["Forecaster", "RPS", "Accuracy", "RPS gap"], rows)
    note = f'<div style="{_NOTE}">RPS: lower is better. On {int(glass.matches)} matches, differences under ~{NOISE} are noise.</div>'

    bets = bets or {}
    chips = []
    for n, (key, label, who, short) in enumerate([("beat_gbm", "GBM", "the GBM", "the GBM"),
                                                  ("beat_bookies", "Bookmakers", "the bookmakers", "the bookmakers"),
                                                  ("beat_base", "Base rates", "plain league averages", "league averages")], 1):
        gap = _row(sb, label).rps - glass.rps
        won = gap > 0
        hands = bets.get(key)
        if room_size and hands is not None:
            room.guess(key, "yes" if hands > room_size / 2 else "no", f"Glass box beat {who}?", quiet=True)
        room.truth(key, "yes" if won else "no", quiet=True)
        detail = f"by {abs(gap):.3f}" + (" · inside the noise" if abs(gap) < NOISE else "")
        hands_txt = "" if hands is None else f"Room: {hands}{f' of {room_size}' if room_size else ''} hands"
        chips.append(f'<div style="{_KICK}">Bet {n} · glass box beat</div><div style="margin-top:2px">{short}?</div>'
                     f'<div style="font-size:26px;font-weight:700;color:{HOME if won else AWAY}">{"Yes" if won else "No"}</div>'
                     f'<div style="font-size:15px;color:#5C3D30">{detail}</div>'
                     f'<div style="font-size:15px;color:#5C3D30">{hands_txt}</div>')
    when = pd.Timestamp(d.name[:10])
    _show(f"The frozen forecast, graded: matchdays {gm.Matchday.min()}–{gm.Matchday.max()}",
          f"{int(glass.matches)} matches · metrics pre-registered on 8 Oct · update of {when.day} {when:%b}",
          table + note + _chips(chips), d)


def show_calls():
    """The frozen forecast's biggest miss and best call (by RPS), as probability bars."""
    d = latest()
    worst, best = misses_and_hits()
    boxes = []
    for kind, m in [("Biggest miss", worst), ("Best call", best)]:
        h, a = int(m.FTHG), int(m.FTAG)
        res = "H" if h > a else "D" if h == a else "A"
        segs = [("H", m.pH, HOME, "#FFFFFF", "left"), ("D", m.pD, DRAW, "#2E1D16", "center"), ("A", m.pA, AWAY, "#FFFFFF", "right")]
        bar = "".join(f'<div style="width:{p * 100:.1f}%;background:{bg};color:{fg};display:flex;align-items:center;'
                      f'justify-content:center;font-size:16px;font-weight:600;white-space:nowrap;overflow:hidden">{p:.0%}</div>'
                      for _, p, bg, fg, _ in segs)
        word = {"H": "home win", "D": "draw", "A": "away win"}[res]
        marks = "".join(f'<div style="width:{p * 100:.1f}%;text-align:{al};white-space:nowrap;font-size:15px;font-weight:700">'
                        f'{"▲ " + word if k == res else ""}</div>' for k, p, _, _, al in segs)
        boxes.append(f'<div style="{_KICK}">{kind} · matchday {int(m.Matchday)}</div>'
                     f'<div style="font-size:24px;font-weight:700;margin:4px 0 10px">{m.HomeTeam} {h}–{a} {m.AwayTeam}</div>'
                     f'<div style="display:flex;height:40px;border-radius:8px;overflow:hidden">{bar}</div>'
                     f'<div style="display:flex;margin-top:6px;color:#2E1D16">{marks}</div>')
    legend = (f'<span style="color:{HOME};font-weight:700">■</span> home win &nbsp; '
              f'<span style="color:#9C8579;font-weight:700">■</span> draw &nbsp; '
              f'<span style="color:{AWAY};font-weight:700">■</span> away win')
    body = ('<div style="display:flex;flex-wrap:wrap;gap:12px">'
            + "".join(f'<div style="flex:1 1 400px;background:#FDF3EE;border-radius:10px;padding:14px 16px">{b}</div>' for b in boxes)
            + "</div>")
    _show("Biggest miss and best call", f"What the frozen forecast said before kick-off. {legend}", body, d)


def show_bayern():
    """Bayern's home games since the freeze, glass box vs GBM: resolves the black-box vote (recorded for the scorecard)."""
    import room
    d = latest()
    gm = pd.read_csv(d / "graded_matches.csv")
    bay = gm[gm.HomeTeam == "Bayern Munich"]
    if bay.empty:
        print("No Bayern home games since the freeze yet.")
        return
    won = (bay.FTHG > bay.FTAG).astype(float)
    se_glass, se_gbm = (bay.pH - won) ** 2, (bay.ml_pH - won) ** 2
    rows = []
    for (_, m), g, b in zip(bay.iterrows(), se_glass, se_gbm):
        pg, pb = f"{m.pH:.0%}", f"{m.ml_pH:.0%}"
        pg, pb = (f"<b>{pg}</b>", pb) if g < b else (pg, f"<b>{pb}</b>")
        rows.append(([f"MD{int(m.Matchday)}", f"Bayern – {m.AwayTeam}", f"{int(m.FTHG)}–{int(m.FTAG)}", pg, pb,
                      "glass box" if g < b else "GBM"], ""))
    table = _table(["", "Match", "Score", "Glass box", "GBM", "Closer"], rows, text_cols=2)
    b_glass, b_gbm = se_glass.mean(), se_gbm.mean()
    winner = "glass_box" if b_glass < b_gbm else "gbm"
    room.truth("bayern_home", winner, quiet=True)
    n = len(bay)
    chips = [f'<div style="{_KICK}">Verdict on {n} game{"s" if n > 1 else ""}</div>'
             f'<div style="font-size:26px;font-weight:700;color:{HOME if winner == "glass_box" else AWAY}">'
             f'{"Glass box" if winner == "glass_box" else "GBM"}</div>'
             f'<div style="font-size:15px;color:#5C3D30">Brier: glass box {b_glass:.3f}, GBM {b_gbm:.3f} (lower is better)</div>'
             f'<div style="font-size:15px;color:#5C3D30">{_room_line("bayern_home")}</div>',
             f'<div style="{_KICK}">How much this tells you</div>'
             f'<div style="font-size:20px;font-weight:700;margin-top:4px">Almost nothing</div>'
             f'<div style="font-size:15px;color:#5C3D30">{n} matches. Ask again in May.</div>']
    _show("Bayern at home since the freeze: who was closer?",
          "Probability of a Bayern win, as frozen on 8 Oct. Bold = closer to what happened.", table + _chips(chips), d)


def show_season():
    """The scoreboard slide's right half, filled in, plus the 81% question resolved (recorded for the scorecard)."""
    import room
    d = latest()
    drift = pd.read_csv(d / "drift_vs_freeze.csv", index_col=0)

    def line(team, col):
        f, n = round(100 * drift.loc[team, f"{col}_frozen"]), round(100 * drift.loc[team, f"{col}_now"])
        ch = n - f
        arrow = (f'<span style="color:{HOME}">▲ {ch}</span>' if ch > 0 else
                 f'<span style="color:{AWAY}">▼ {-ch}</span>' if ch < 0 else "–")
        return [team, f"{f}%", f"<b>{n}%</b>", arrow], ""

    now_col = f"After MD{_md(d)}"
    head = ["Title", "8 Oct", now_col, "Change"]
    left = _table(head, [line(t, "title") for t in ["Bayern Munich", "Dortmund", "Leverkusen"]])
    releg = drift.sort_values("relegated_now", ascending=False).index[:4]
    top4 = (drift.top4_now - drift.top4_frozen).abs().idxmax()
    right = _table(["Relegation", "8 Oct", now_col, "Change"],
                   [line(t, "relegated") for t in releg] + ["Top four: biggest mover", line(top4, "top4")])

    now = drift.loc["Bayern Munich", "title_now"]
    ans = "too_low" if now > 0.86 else "too_high" if now < 0.76 else "about_right"
    room.truth("bayern_81", ans, quiet=True)
    verdict = (f'<div style="{_KICK}">Is 81% too confident?</div>'
               f'<div style="font-size:26px;font-weight:700;color:{HOME}">{room.pretty(ans).capitalize()}</div>'
               f'<div style="font-size:15px;color:#5C3D30">By the model\'s own reckoning: it now says {now:.0%}. The season decides.</div>'
               f'<div style="font-size:15px;color:#5C3D30">{_room_line("bayern_81")}</div>')
    body = ('<div style="display:flex;flex-wrap:wrap;gap:12px 32px">'
            f'<div style="flex:1 1 380px">{left}{_chips([verdict])}</div>'
            f'<div style="flex:1 1 380px">{right}</div></div>')
    import json
    sims = json.loads((d / "forecast" / "meta.json").read_text()).get("n_sims")
    sims_txt = f"{sims:,} simulated seasons, " if sims else ""
    _show("How the season forecast moved", f"{sims_txt}frozen on 8 Oct vs after matchday {_md(d)}", body, d)


def main():
    d = latest()
    if d is None:
        print("No rolling updates yet. The first one appears after matchday 5 is complete in both data sources.")
        return
    print(f"Latest update: {d.name}\n")
    sb = scoreboard()
    print(sb.to_string(index=False, formatters={"rps": "{:.4f}".format, "brier": "{:.4f}".format,
                                                "logloss": "{:.4f}".format, "accuracy": "{:.0%}".format}))
    worst, best = misses_and_hits()
    print(f"\nBiggest miss: MD{worst.Matchday} {worst.HomeTeam} {int(worst.FTHG)}-{int(worst.FTAG)} {worst.AwayTeam} "
          f"(model said H {worst.pH:.0%} / D {worst.pD:.0%} / A {worst.pA:.0%})")
    print(f"Best call:    MD{best.Matchday} {best.HomeTeam} {int(best.FTHG)}-{int(best.FTAG)} {best.AwayTeam} "
          f"(model said H {best.pH:.0%} / D {best.pD:.0%} / A {best.pA:.0%})")
    drift = pd.read_csv(d / "drift_vs_freeze.csv", index_col=0)
    print("\nTitle (8 Oct -> now):")
    for t in ["Bayern Munich", "Dortmund", "Leverkusen"]:
        print(f"  {t:<15} {drift.loc[t, 'title_frozen']:.0%} -> {drift.loc[t, 'title_now']:.0%}")
    print("Relegation (8 Oct -> now):")
    for t in drift.sort_values("relegated_now", ascending=False).index[:4]:
        print(f"  {t:<15} {drift.loc[t, 'relegated_frozen']:.0%} -> {drift.loc[t, 'relegated_now']:.0%}")
    OUT.mkdir(exist_ok=True)
    drift_figure().savefig(OUT / "reveal_title_drift.png")
    drift_figure("p_relegated", "Relegation race since the freeze").savefig(OUT / "reveal_relegation_drift.png")
    print(f"\nWrote {OUT / 'reveal_title_drift.png'} and reveal_relegation_drift.png")


if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import brand
    brand.apply()
    main()
