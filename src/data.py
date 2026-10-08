"""Load Bundesliga results (football-data.co.uk) and fixtures (OpenLigaDB)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
SEASONS = ["1213", "1314", "1415", "1516", "1617", "1718", "1819", "1920",
           "2021", "2122", "2223", "2324", "2425", "2526", "2627"]

# OpenLigaDB team name -> football-data.co.uk team name
OLDB_TO_FD = {
    "FC Bayern München": "Bayern Munich",
    "Borussia Dortmund": "Dortmund",
    "Bayer 04 Leverkusen": "Leverkusen",
    "RB Leipzig": "RB Leipzig",
    "VfB Stuttgart": "Stuttgart",
    "Eintracht Frankfurt": "Ein Frankfurt",
    "SC Freiburg": "Freiburg",
    "TSG Hoffenheim": "Hoffenheim",
    "SV Werder Bremen": "Werder Bremen",
    "FC Augsburg": "Augsburg",
    "1. FSV Mainz 05": "Mainz",
    "1. FC Union Berlin": "Union Berlin",
    "Borussia Mönchengladbach": "M'gladbach",
    "Hamburger SV": "Hamburg",
    "1. FC Köln": "FC Koln",
    "FC Schalke 04": "Schalke 04",
    "SC Paderborn 07": "Paderborn",
    "SV 07 Elversberg": "Elversberg",
}


def load_results() -> pd.DataFrame:
    """All finished Bundesliga matches, one row per match, with closing odds where available."""
    frames = []
    for s in SEASONS:
        df = pd.read_csv(RAW / f"D1_{s}.csv", encoding="utf-8-sig")
        df = df.dropna(subset=["HomeTeam", "FTHG"])
        df["Season"] = s
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    keep = ["Season", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
            "HxG", "AxG", "AvgH", "AvgD", "AvgA", "AvgCH", "AvgCD", "AvgCA"]
    df = df[[c for c in keep if c in df.columns]].copy()
    df[["FTHG", "FTAG"]] = df[["FTHG", "FTAG"]].astype(int)
    # Matchday index within each season (by date order, 9 matches per round is not
    # guaranteed historically, so we use calendar rounds only where needed).
    return df.sort_values(["Date", "HomeTeam"]).reset_index(drop=True)


def load_fixtures(path: Path | None = None) -> pd.DataFrame:
    """Full 2026/27 schedule from an OpenLigaDB snapshot, team names mapped to football-data."""
    path = path or RAW / "openligadb_bl1_2026_20261008.json"
    rows = []
    for m in json.loads(Path(path).read_text()):
        final = [r for r in m["matchResults"] if r["resultTypeID"] == 2]
        rows.append({
            "MatchID": m["matchID"],
            "Matchday": m["group"]["groupOrderID"],
            "Kickoff": pd.Timestamp(m["matchDateTime"]),
            "HomeTeam": OLDB_TO_FD[m["team1"]["teamName"]],
            "AwayTeam": OLDB_TO_FD[m["team2"]["teamName"]],
            "Finished": m["matchIsFinished"],
            "FTHG": final[0]["pointsTeam1"] if final else np.nan,
            "FTAG": final[0]["pointsTeam2"] if final else np.nan,
        })
    return pd.DataFrame(rows).sort_values(["Matchday", "Kickoff", "HomeTeam"]).reset_index(drop=True)


def season_start(season: str) -> pd.Timestamp:
    return load_results().query("Season == @season")["Date"].min()
