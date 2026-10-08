# Pre-registered Bundesliga 2026/27 forecast

**Frozen:** 8 October 2026, before matchday 5 (first kick-off: Fri 9 Oct 2026, 20:30 CEST, Dortmund vs Werder Bremen)
**Author:** Ari Joury (Wangari Global)
**Purpose:** Live evaluation at Machine Learning Week Europe, Munich, 17 November 2026: *Soccer Analytics: Traceable and Honest Forecasting Across a Bundesliga Season*

The point of freezing is simple: a forecast that can be edited after the fact can't be graded honestly. Everything below was fixed before any of the matches it predicts were played. The SHA-256 fingerprint of `MANIFEST.sha256` is published separately, so anyone can verify that none of these files changed afterwards.

## What is frozen

| File | Content |
|---|---|
| `freeze/2026-10-08/match_forecasts.csv` | Home/draw/away probabilities and expected goals for all 270 remaining matches (MD5–MD34), from both models, with the additive drivers of every glass-box forecast |
| `freeze/2026-10-08/table_forecast.csv` | Distribution of final league positions for all 18 teams (20,000 simulated seasons) |
| `freeze/2026-10-08/team_ratings.csv` | Attack and defence ratings with standard errors |
| `freeze/2026-10-08/table_at_cutoff.csv` | Table after MD4 (the starting point) |
| `freeze/2026-10-08/meta.json` | Hyperparameters, seeds, training sizes, package versions |
| `src/` | The full model code that produced the above |
| `data/raw/` | Exact data snapshot used (football-data.co.uk results 2012/13–2026/27 MD4; OpenLigaDB fixture list as of 8 Oct 2026) |

## The models

**Glass box (primary): time-weighted, penalised Dixon-Coles.**
Expected goals are `exp(base + home advantage + attack + opponent defence)`, so every match probability decomposes into four named terms. Matches are down-weighted with a 270-day half-life. Ratings are shrunk toward a prior (0 for established teams; −0.3 attack / +0.3 defence for promoted teams), and a Dixon-Coles low-score correction with ρ = −0.10 is applied. Season outcomes are simulated 20,000 times. Each simulated season draws its own team ratings from the Laplace posterior, so rating uncertainty is propagated, not just match randomness.

Hyperparameters were chosen by walk-forward backtest on 2019/20–2024/25 (ranked probability score), then validated once on the held-out 2025/26 season.

**Contrast model: gradient-boosted classifier (scikit-learn HistGradientBoosting).**
Features: Elo ratings, last-5 form (points, goals for/against), season points per game. Trained on all matches since 2013/14. It predicts home/draw/away directly and has no built-in decomposition.

### Out-of-sample record before the freeze (ranked probability score, lower is better)

| | Held-out 2025/26 | 7 seasons 2019/20–2025/26 |
|---|---|---|
| Glass box (Dixon-Coles) | 0.1970 | 0.2038 |
| GBM (Elo + form) | 0.1949 | 0.2081 |
| Bookmakers (avg. closing odds) | 0.1901 | 0.1977 |
| Base rates | 0.2314 | n/a |

The 7-season comparison partly overlaps the glass box's tuning seasons, which favours it slightly. Bookmakers beat both models in every season.

## Evaluation plan (committed in advance)

**At the talk (17 Nov 2026): matchdays 5–9 (45 matches) from the frozen snapshot.**
- Primary metric: mean ranked probability score (RPS) over H/D/A.
- Secondary: Brier score, log loss, and a reliability diagram (predicted vs observed frequency).
- Benchmarks: the GBM snapshot, bookmaker average closing odds from football-data.co.uk (overround removed by proportional normalisation), and constant base rates.
- Results get reported whatever they turn out to be, including if the model loses to every benchmark.

**Rolling forecasts (drift).** After every matchday the *unchanged* code in `src/` is re-run with only the data cut-off moved:
`python src/forecast.py --as-of <date> --fixtures <snapshot> --out updates/<date>`.
Model specification and hyperparameters stay fixed for the whole season. Any change would be published as a separately named model, never as an edit to this one.

**End of season (May 2027).** The table forecast is scored by the log score of each team's actual final position, and by the Brier score for the events *title*, *top 4*, *relegation (17th–18th)*.

## Known limitations (stated in advance)

- Injuries, suspensions, transfers and manager changes aren't modelled explicitly. They only reach the model through results, with a lag. The talk will look at where that lag shows.
- Ratings are static inside a snapshot. A December match is forecast with October's ratings, and only parameter uncertainty widens it.
- Promoted teams get a generic prior. Their ratings are the least certain (standard errors about twice those of established teams).
- Data comes from public sources (football-data.co.uk, OpenLigaDB). No xG, tracking or lineup data.
