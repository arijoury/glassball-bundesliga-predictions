"""Data layer: download, cache and reconcile two free public sources.

* football-data.co.uk: results since 1993/94, bookmaker odds, shots, cards, (recently) xG.
* OpenLigaDB: the official matchday structure and future fixtures.

Team names differ between the two sources (and across seasons). They are reconciled
with a shipped name table, and any team the table doesn't know is matched
automatically by pairing finished games on (date, score).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

FIRST_SEASON = 2004  # first season OpenLigaDB covers completely
FD_URL = "https://www.football-data.co.uk/mmz4281/{code}/D1.csv"
OLDB_URL = "https://api.openligadb.de/getmatchdata/bl1/{year}"
NAMES = json.loads((Path(__file__).parent / "team_names.json").read_text())
FD_COLS = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG",
           "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR",
           "HxG", "AxG", "AvgH", "AvgD", "AvgA", "AvgCH", "AvgCD", "AvgCA",
           "B365H", "B365D", "B365A", "BbAvH", "BbAvD", "BbAvA"]


def season_code(year: int) -> str:
    """2026 -> '2627' (football-data's naming)."""
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def cache_dir() -> Path:
    d = Path(os.environ.get("GLASSBALL_CACHE", Path.home() / ".cache" / "glassball"))
    d.mkdir(parents=True, exist_ok=True)
    return d


progress = None  # optional callback(str) for download messages (the CLI sets it)


def _fetch(url: str, path: Path, max_age_hours: float | None, offline: bool) -> Path | None:
    fresh = path.exists() and path.stat().st_size > 0 and (
        max_age_hours is None or time.time() - path.stat().st_mtime < max_age_hours * 3600)
    if fresh or offline:
        return path if path.exists() and path.stat().st_size > 0 else None
    if progress:
        progress(f"  downloading {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "glassball (github.com/arijoury)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        if len(body) < 50:
            return path if path.exists() else None
        path.write_bytes(body)
    except Exception:
        if not path.exists():
            return None
    return path


def _max_age(year: int) -> float | None:
    """Finished seasons never change; the current one is refreshed every 6 hours."""
    today = pd.Timestamp.today()
    season_over = today > pd.Timestamp(year + 1, 7, 1)
    return None if season_over else 6.0


def load_fd(year: int, *, data_dir: Path | None = None, offline: bool = False) -> pd.DataFrame:
    """football-data.co.uk results for one season (empty frame if not available)."""
    code = season_code(year)
    d = Path(data_dir) if data_dir else cache_dir()
    path = _fetch(FD_URL.format(code=code), d / f"D1_{code}.csv",
                  _max_age(year) if not data_dir else None, offline or bool(data_dir))
    if path is None:
        return pd.DataFrame(columns=["Season", "Date"] + FD_COLS)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc, on_bad_lines="skip")
            break
        except UnicodeDecodeError:
            continue
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")].dropna(subset=["HomeTeam", "FTHG"])
    df = df[[c for c in FD_COLS if c in df.columns]].copy()
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    df[["FTHG", "FTAG"]] = df[["FTHG", "FTAG"]].astype(int)
    df.insert(0, "Season", year)
    return df.reset_index(drop=True)


def load_oldb(year: int, *, data_dir: Path | None = None, offline: bool = False,
              file: Path | None = None) -> pd.DataFrame:
    """OpenLigaDB fixture list (all 306 matches with matchday numbers)."""
    if file is None:
        d = Path(data_dir) if data_dir else cache_dir()
        file = _fetch(OLDB_URL.format(year=year), d / f"oldb_bl1_{year}.json",
                      _max_age(year) if not data_dir else None, offline or bool(data_dir))
    if file is None:
        raise FileNotFoundError(f"No OpenLigaDB fixtures for {year}/{year + 1} (offline or not yet published)")
    rows = []
    for m in json.loads(Path(file).read_text()):
        # final score: type 2 in recent seasons, "Endergebnis" with type 0 in older ones
        final = [r for r in m["matchResults"] if r["resultTypeID"] == 2 or r.get("resultName") == "Endergebnis"]
        rows.append({
            "MatchID": m["matchID"], "Matchday": m["group"]["groupOrderID"],
            "Kickoff": pd.Timestamp(m["matchDateTime"]),
            "HomeTeamOLDB": m["team1"]["teamName"], "AwayTeamOLDB": m["team2"]["teamName"],
            "Finished": bool(m["matchIsFinished"] and final),
            "FTHG_oldb": final[0]["pointsTeam1"] if final else np.nan,
            "FTAG_oldb": final[0]["pointsTeam2"] if final else np.nan,
        })
    df = pd.DataFrame(rows)
    df = df[df.Matchday <= 34]  # some old seasons store relegation play-offs as matchdays 35-36
    return df.sort_values(["Matchday", "Kickoff", "HomeTeamOLDB"]).reset_index(drop=True)


def reconcile_names(oldb: pd.DataFrame, fd: pd.DataFrame) -> dict[str, str]:
    """OpenLigaDB name -> football-data name. Shipped table first, then (date, score) votes."""
    mapping = {n: NAMES[n] for n in set(oldb.HomeTeamOLDB) | set(oldb.AwayTeamOLDB) if n in NAMES}
    unknown = (set(oldb.HomeTeamOLDB) | set(oldb.AwayTeamOLDB)) - set(mapping)
    if unknown and len(fd):
        votes = Counter()
        a = oldb[oldb.Finished].assign(D=lambda x: x.Kickoff.dt.tz_localize(None).dt.normalize())
        m = a.merge(fd.assign(D=fd.Date.dt.normalize()), left_on=["D", "FTHG_oldb", "FTAG_oldb"],
                    right_on=["D", "FTHG", "FTAG"])
        for r in m.itertuples():
            votes[(r.HomeTeamOLDB, r.HomeTeam)] += 1
            votes[(r.AwayTeamOLDB, r.AwayTeam)] += 1
        for name in unknown:
            cands = {fdn: v for (o, fdn), v in votes.items() if o == name}
            if cands:
                mapping[name] = max(cands, key=cands.get)
    for name in (set(oldb.HomeTeamOLDB) | set(oldb.AwayTeamOLDB)) - set(mapping):
        mapping[name] = name  # brand-new team with no games yet: keep its own name
    return mapping


def load_history(first: int, last: int, **kw) -> pd.DataFrame:
    """Concatenated football-data results for seasons first..last (inclusive)."""
    frames = [load_fd(y, **kw) for y in range(first, last + 1)]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True).sort_values(["Date", "HomeTeam"]).reset_index(drop=True)


def current_season(today: pd.Timestamp | None = None) -> int:
    """The season being played (or about to start): from July onwards it's this year's."""
    t = today or pd.Timestamp.today()
    return t.year if t.month >= 7 else t.year - 1


# Nicknames and spellings people actually type
ALIASES = {
    "bayern": "Bayern Munich", "fcb": "Bayern Munich", "fc bayern": "Bayern Munich", "munich": "Bayern Munich",
    "bvb": "Dortmund", "borussia dortmund": "Dortmund",
    "gladbach": "M'gladbach", "mönchengladbach": "M'gladbach", "monchengladbach": "M'gladbach", "bmg": "M'gladbach",
    "köln": "FC Koln", "koln": "FC Koln", "koeln": "FC Koln", "cologne": "FC Koln", "effzeh": "FC Koln",
    "frankfurt": "Ein Frankfurt", "eintracht": "Ein Frankfurt", "sge": "Ein Frankfurt",
    "leipzig": "RB Leipzig", "rbl": "RB Leipzig", "hsv": "Hamburg", "hamburger sv": "Hamburg",
    "werder": "Werder Bremen", "bremen": "Werder Bremen", "union": "Union Berlin", "fcu": "Union Berlin",
    "s04": "Schalke 04", "schalke": "Schalke 04", "vfb": "Stuttgart", "b04": "Leverkusen", "bayer": "Leverkusen",
    "tsg": "Hoffenheim", "scf": "Freiburg", "fca": "Augsburg", "m05": "Mainz", "05": "Mainz",
    "fürth": "Greuther Furth", "furth": "Greuther Furth", "düsseldorf": "Fortuna Dusseldorf",
    "dusseldorf": "Fortuna Dusseldorf", "fortuna": "Fortuna Dusseldorf", "pauli": "St Pauli", "st. pauli": "St Pauli",
    "kiel": "Holstein Kiel", "hertha": "Hertha", "wolfsburg": "Wolfsburg", "vfl": "Wolfsburg", "bochum": "Bochum",
}


def _fold(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c)).strip()


def resolve_team(name: str, teams) -> str:
    """Map whatever the user typed to one of `teams` (case-, accent- and nickname-insensitive)."""
    teams = list(teams)
    if name in teams:
        return name
    key = _fold(name)
    by_fold = {_fold(t): t for t in teams}
    long_names = {_fold(o): f for o, f in NAMES.items() if f in teams}  # official names, e.g. "1. FC Köln"
    for cand in (by_fold.get(key), ALIASES.get(name.lower()), ALIASES.get(key), long_names.get(key)):
        if cand in teams:
            return cand
    hits = {t for f, t in {**by_fold, **long_names}.items() if key and key in f}
    if len(hits) == 1:
        return hits.pop()
    msg = f"Unknown team {name!r}." + (f" Did you mean one of: {', '.join(sorted(hits))}?" if hits else
                                        f" Teams this season: {', '.join(sorted(teams))}")
    raise KeyError(msg)
