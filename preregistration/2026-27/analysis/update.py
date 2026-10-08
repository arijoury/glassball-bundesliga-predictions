"""Rolling update after each completed matchday, exactly as pre-registered.

    python preregistration/2026-27/analysis/update.py            # do the next update if a matchday has completed
    python preregistration/2026-27/analysis/update.py --dry-run  # only report what would happen

What it does, in order:
  1. Downloads fresh results (football-data.co.uk) and fixtures (OpenLigaDB).
  2. Finds the latest matchday that is complete in BOTH sources (football-data lags a day or two).
     If that matchday already has an update, it stops: the script is safe to run daily.
  3. Re-runs the frozen code in src/ unchanged. It first checks every file against MANIFEST.sha256
     and refuses to run if anything differs. Only the data cut-off moves.
  4. Grades the frozen 8 Oct forecast on every match played since, with the pre-registered metrics
     and benchmarks.
  5. Writes everything to updates/<date>_md<NN>/, including the exact data snapshot used, so anyone
     can reproduce it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

PRE = Path(__file__).resolve().parents[1]
FREEZE = PRE / "freeze" / "2026-10-08"
UPDATES = PRE / "updates"
FD_URL = "https://www.football-data.co.uk/mmz4281/2627/D1.csv"
OLDB_URL = "https://api.openligadb.de/getmatchdata/bl1/2026"
FROZEN_MD = 4  # the freeze used matchdays 1-4


def fetch(url: str, dest: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "glassball-rolling-update"})
    with urllib.request.urlopen(req, timeout=60) as r:
        dest.write_bytes(r.read())


def verify_frozen_code():
    """Every frozen file listed in the manifest must be byte-identical."""
    bad = []
    for line in (PRE / "MANIFEST.sha256").read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        if hashlib.sha256((PRE / path).read_bytes()).hexdigest() != digest:
            bad.append(path)
    if bad:
        sys.exit(f"Frozen files changed, refusing to run: {bad}")


def load_sources(tmp: Path):
    sys.path.insert(0, str(PRE / "src"))
    import data as frozen_data  # the frozen loader: same team-name mapping as the freeze
    fd = pd.read_csv(tmp / "D1_2627.csv", encoding="utf-8-sig").dropna(subset=["HomeTeam", "FTHG"])
    fd["Date"] = pd.to_datetime(fd["Date"], dayfirst=True, format="mixed")
    fx = frozen_data.load_fixtures(tmp / "oldb.json")
    return fd, fx


def latest_complete_matchday(fd: pd.DataFrame, fx: pd.DataFrame) -> int | None:
    """Highest matchday whose every match is finished in OpenLigaDB *and* present in football-data.
    A match still unplayed a week after its matchday counts as postponed and doesn't block."""
    have = set(zip(fd.HomeTeam, fd.AwayTeam))
    best = None
    for md, g in fx.groupby("Matchday"):
        played = g[g.Finished]
        if played.empty:
            break
        last = played.Kickoff.max().tz_localize(None)
        postponed = g[~g.Finished & (pd.Timestamp.now() > last + pd.Timedelta(days=7))]
        pending = g[~g.Finished & ~g.index.isin(postponed.index)]
        in_fd = all((h, a) in have for h, a in zip(played.HomeTeam, played.AwayTeam))
        if len(pending) or not in_fd:
            break
        best = int(md)
    return best


def rps(P, o):
    obs = np.eye(3)[o]
    return (((np.cumsum(P, 1) - np.cumsum(obs, 1))[:, :2]) ** 2).sum(1) / 2


def grade(fd: pd.DataFrame, fx: pd.DataFrame, upto_md: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score the frozen snapshot on matchdays 5..upto_md, per the pre-registered plan."""
    frozen = pd.read_csv(FREEZE / "match_forecasts.csv")
    frozen = frozen[(frozen.Matchday > FROZEN_MD) & (frozen.Matchday <= upto_md)]
    m = frozen.merge(fd[["HomeTeam", "AwayTeam", "FTHG", "FTAG", "AvgCH", "AvgCD", "AvgCA"]],
                     on=["HomeTeam", "AwayTeam"], how="inner")
    o = np.where(m.FTHG > m.FTAG, 0, np.where(m.FTHG == m.FTAG, 1, 2))
    # base rates: H/D/A frequencies in the training data available at the freeze (2013/14 - MD4 2026/27)
    hist = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in sorted((PRE / "data" / "raw").glob("D1_*.csv"))
                      if p.stem[-4:] >= "1314"]).dropna(subset=["FTR"])
    base = hist.FTR.value_counts(normalize=True).reindex(["H", "D", "A"]).to_numpy()
    book = 1 / m[["AvgCH", "AvgCD", "AvgCA"]].to_numpy()
    preds = {
        "Glass box (Dixon-Coles)": m[["pH", "pD", "pA"]].to_numpy(),
        "GBM (Elo + form)": m[["ml_pH", "ml_pD", "ml_pA"]].to_numpy(),
        "Bookmakers (avg. closing odds)": book / book.sum(1, keepdims=True),
        "Base rates": np.tile(base, (len(m), 1)),
    }
    rows = []
    for name, P in preds.items():
        ok = ~np.isnan(P).any(1)
        rows.append({"model": name, "matches": int(ok.sum()), "rps": rps(P[ok], o[ok]).mean(),
                     "brier": ((P[ok] - np.eye(3)[o[ok]]) ** 2).sum(1).mean(),
                     "logloss": -np.log(np.clip(P[ok][np.arange(ok.sum()), o[ok]], 1e-12, 1)).mean(),
                     "accuracy": (P[ok].argmax(1) == o[ok]).mean()})
    per_match = m.assign(outcome=np.array(["H", "D", "A"])[o], rps_glass=rps(preds["Glass box (Dixon-Coles)"], o),
                         rps_gbm=rps(preds["GBM (Elo + form)"], o),
                         rps_book=rps(preds["Bookmakers (avg. closing odds)"], o))
    return pd.DataFrame(rows), per_match


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo the latest update even if it exists")
    ap.add_argument("--matchday", type=int, help=argparse.SUPPRESS)   # testing: pretend this is the latest
    ap.add_argument("--as-of", help=argparse.SUPPRESS)                # testing: override the cut-off
    ap.add_argument("--out", help=argparse.SUPPRESS)                  # testing: write elsewhere
    a = ap.parse_args()
    verify_frozen_code()

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        fetch(FD_URL, tmp / "D1_2627.csv")
        fetch(OLDB_URL, tmp / "oldb.json")
        fd, fx = load_sources(tmp)
        md = a.matchday or latest_complete_matchday(fd, fx)
        if md is None or (md <= FROZEN_MD and not a.matchday):
            print(f"No completed matchday after the freeze yet (latest complete: {md}).")
            return
        last_kick = fx[(fx.Matchday == md) & fx.Finished].Kickoff.max().tz_localize(None)
        as_of = pd.Timestamp(a.as_of).date() if a.as_of else (last_kick.normalize() + pd.Timedelta(days=1)).date()
        out = Path(a.out) if a.out else UPDATES / f"{as_of}_md{md:02d}"
        if out.exists() and not a.force:
            print(f"Matchday {md} already has an update ({out.name}). Nothing to do.")
            return
        print(f"Matchday {md} complete in both sources -> update as of {as_of}")
        if a.dry_run:
            return

        # run the frozen code, byte-identical, in a sandbox where only the current-season data is new
        sandbox = tmp / "run"
        shutil.copytree(PRE / "src", sandbox / "src")
        shutil.copytree(PRE / "data" / "raw", sandbox / "data" / "raw")
        shutil.copy(tmp / "D1_2627.csv", sandbox / "data" / "raw" / "D1_2627.csv")
        snap = sandbox / "data" / "raw" / f"openligadb_bl1_2026_{as_of:%Y%m%d}.json"
        shutil.copy(tmp / "oldb.json", snap)
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        subprocess.run([sys.executable, "-W", "ignore", "forecast.py", "--as-of", str(as_of),
                        "--fixtures", str(snap), "--out", str(out / "forecast")],
                       cwd=sandbox / "src", check=True, stdout=subprocess.DEVNULL)

        (out / "data").mkdir()
        shutil.copy(tmp / "D1_2627.csv", out / "data" / "D1_2627.csv")
        shutil.copy(snap, out / "data" / snap.name)

        scores, per_match = grade(fd[fd.Date < pd.Timestamp(as_of)], fx, md)
        scores.to_csv(out / "grading.csv", index=False, float_format="%.5f")
        per_match.to_csv(out / "graded_matches.csv", index=False, float_format="%.4f")

        frozen_t = pd.read_csv(FREEZE / "table_forecast.csv", index_col=0)
        now_t = pd.read_csv(out / "forecast" / "table_forecast.csv", index_col=0)
        drift = pd.DataFrame({
            "title_frozen": frozen_t.p_title, "title_now": now_t.p_title,
            "top4_frozen": frozen_t.p_top4, "top4_now": now_t.p_top4,
            "relegated_frozen": frozen_t.p_relegated, "relegated_now": now_t.p_relegated,
            "exp_points_frozen": frozen_t.exp_points, "exp_points_now": now_t.exp_points,
        }).loc[now_t.index]
        drift.to_csv(out / "drift_vs_freeze.csv", float_format="%.4f")

        files = sorted(p for p in out.rglob("*") if p.is_file())
        (out / "MANIFEST.sha256").write_text("".join(
            f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n" for p in files))
        meta = {"matchday": md, "as_of": str(as_of), "graded_matches": int(scores.matches.iloc[0]),
                "frozen_code_verified": True, "platform": platform.platform(), "python": platform.python_version()}
        (out / "update_meta.json").write_text(json.dumps(meta, indent=2))
        write_summary(out, md, as_of, scores, drift)
        if not a.out:
            write_index()
        print(f"Wrote {out}")


def write_index():
    """updates/README.md: one line per update, newest first."""
    rows = []
    for d in sorted(UPDATES.glob("*_md*"), reverse=True):
        g = pd.read_csv(d / "grading.csv").set_index("model")
        meta = json.loads((d / "update_meta.json").read_text())
        rows.append(f"| [{d.name}]({d.name}/SUMMARY.md) | {meta['matchday']} | {meta['graded_matches']} | "
                    + " | ".join(f"{g.loc[m, 'rps']:.4f}" for m in g.index) + " |")
    models = list(pd.read_csv(next(UPDATES.glob("*_md*")) / "grading.csv").model) if rows else []
    head = ["# Rolling updates", "",
            "Each folder: the frozen code re-run with data up to that date, plus the frozen 8 Oct forecast graded "
            "on every match since. Generated by `analysis/update.py` (daily GitHub Action).", "",
            "Ranked probability score of the **frozen** forecast so far (lower is better):", "",
            "| Update | Matchday | Matches graded | " + " | ".join(models) + " |",
            "|---|---|---|" + "---|" * len(models)]
    (UPDATES / "README.md").write_text("\n".join(head + rows) + "\n")


def write_summary(out: Path, md: int, as_of, scores: pd.DataFrame, drift: pd.DataFrame):
    pct = lambda x: f"{100 * x:.0f}%"
    s = scores.copy()
    lines = [f"# Rolling update after matchday {md} (data up to {as_of})", "",
             "Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), "
             "new data only.", "",
             f"## The frozen 8 Oct forecast, graded on matchdays 5–{md} ({int(s.matches.iloc[0])} matches)", "",
             "| | RPS | Brier | Log loss | Accuracy |", "|---|---|---|---|---|"]
    for r in s.itertuples():
        lines.append(f"| {r.model} | {r.rps:.4f} | {r.brier:.4f} | {r.logloss:.4f} | {pct(r.accuracy)} |")
    lines += ["", "Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: "
              "with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.", "",
              "## How the season forecast has moved since the freeze", "",
              "| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |", "|---|---|---|---|---|"]
    for t, r in drift.iterrows():
        lines.append(f"| {t} | {pct(r.title_frozen)} → {pct(r.title_now)} | {pct(r.top4_frozen)} → {pct(r.top4_now)} | "
                     f"{pct(r.relegated_frozen)} → {pct(r.relegated_now)} | {r.exp_points_frozen:.0f} → {r.exp_points_now:.0f} |")
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
