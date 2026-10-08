# glassball ⚽🔍

**A Bundesliga forecast you can audit.** I froze a prediction for every remaining match of the 2026/27 season, plus the final table, on 8 October 2026, before matchday 5. It gets graded in public, however it turns out. Every probability traces back to the handful of numbers that produced it.

Companion code to the talk *Soccer Analytics: Traceable and Honest Forecasting Across a Bundesliga Season* (Machine Learning Week Europe, Munich, 17 Nov 2026) and to the book [*Soccer Analytics with Machine Learning*](https://learning.oreilly.com/library/view/soccer-analytics-with/9781098181109/) (O'Reilly, 2026).

```bash
pip install git+https://github.com/arijoury/bundesliga-2627-forecast
```

```python
from glassball import Bundesliga

Bundesliga(2026).predict()                         # next matchday, with the drivers of every probability
Bundesliga(2026).forecast().table                  # simulated final table
Bundesliga(2023).forecast(before_matchday=10)      # any season since 2004/05, from any point in time
```

---

## The frozen forecast

| | |
|---|---|
| **Frozen** | 8 Oct 2026, after matchday 4, before Dortmund vs Werder Bremen (9 Oct, 20:30) |
| **Fingerprint** | `e9753a97bafee5a04ce2c9229f843ed216f3e2459d97cd33a45006028530cf1a`: SHA-256 of [`MANIFEST.sha256`](MANIFEST.sha256), which hashes every frozen file (code, data, forecasts) |
| **Verify** | `./scripts/verify_freeze.sh` |
| **Rules** | [PREREGISTRATION.md](PREREGISTRATION.md): metrics, benchmarks and update protocol, all fixed in advance |
| **Files** | [`freeze/2026-10-08/`](freeze/2026-10-08/): never edited |

**Headline:** Bayern 81% to win the title, Dortmund 14%, Leverkusen 3%. Most at risk of relegation: Paderborn 37%, Union Berlin 33%, Schalke 31%, Hamburg 28%.

![Final table forecast](figures/06_table_frozen.png)

![Matchday 5 forecast](figures/05_matchday5_frozen.png)

The black ticks show what the contrast model (a gradient-boosted classifier) says for the same matches. Both forecasts are frozen and both get graded.

---

## Every forecast comes with a receipt

The model is deliberately simple. Expected goals for each side are a product of a few named factors:

```
E[home goals] = exp( base + home advantage + attack[home] + defence[away] )
E[away goals] = exp( base                  + attack[away] + defence[home] )
```

Score probabilities follow from a Poisson distribution with a [Dixon-Coles](https://doi.org/10.1111/1467-9876.00065) correction for low scores. So for any match you can ask *why*:

```python
s = Bundesliga(2026)
s.explain("Bayern Munich", "RB Leipzig")
```

![Drivers of Bayern vs Leipzig](figures/08_drivers_bayern_leipzig.png)

Bayern's attack nearly doubles their expected goals (×1.94), and that's most of the story. Leipzig's defence trims it a little (×0.89).

### What would sway it?

Every rating comes with a standard error, so you can ask how fragile a forecast is. If Leipzig's defence turned out one standard error better than estimated, Bayern's win probability would drop by about 6 percentage points:

![Sensitivity](figures/09_sensitivity_bayern_leipzig.png)

### Which matches decide the season?

The table forecast comes from 20,000 simulated seasons, so you can condition on any single result. Dortmund's title chances are 14% today. That becomes **29% if they win in Munich on matchday 8**, and 9% if they lose:

```python
fc = s.forecast()
fc.swing("Dortmund", "title")       # or "top4", "relegated", ...
```

![Title swing matches](figures/10_swing_dortmund_title.png)

![Relegation swing matches](figures/11_swing_union_relegation.png)

### What-ifs

Injuries and transfers aren't in the data, but you can play them through as shifts to a team's ratings:

```python
s.forecast(shift={"Bayern Munich": {"attack": -0.15}})   # roughly: lose a top scorer
```

![What-if](figures/12_what_if_title.png)

---

## Is it any good? Graded honestly

Hyperparameters were tuned on 2019/20–2024/25, with each matchday predicted using only data from before it. The 2025/26 season was held out and used once. The benchmark that matters is the betting market: closing odds aggregate everything the public knows, team news included.

![RPS by season](figures/14_rps_by_season.png)

- **The market wins, every season.** That's expected, and it's what makes this an honest yardstick rather than a straw man.
- **The glass box beats the gradient-boosted model in 6 of 7 seasons** (ranked probability score 0.2037 vs 0.2072 overall; market 0.1977).
- **The GBM's ranking depends on how you retrain it.** Retrained before every matchday (above), it loses 2025/26. Trained once at season start (the frozen validation in [PREREGISTRATION.md](PREREGISTRATION.md)), it *wins* 2025/26. Judge a model on one season and you can pick either.

![Calibration](figures/13_calibration.png)

All three are well calibrated: when they say 30%, it happens about 30% of the time. The market's edge is *sharpness*. It's confident more often, and right when it is.

The two models agree on which team is better. They disagree on how sure to be. The biggest disagreement is every Bayern home game: the glass box says 78–88%, while the GBM, whose trees can't extrapolate past what they've seen, says 60–72%. The frozen forecast will settle who's right.

![Glass box vs GBM](figures/07_glassbox_vs_gbm.png)

### Watching it drift

Honest models update slowly. Here is the model replaying Leverkusen's unbeaten 2023/24 season, re-forecasting before every matchday:

![Title race 2023/24](figures/15_title_race_2023.png)

```python
s = Bundesliga(2023)
{md: s.forecast(before_matchday=md).table.p_title for md in range(1, 35)}
```

---

## The data

Two free public sources, reconciled automatically. Team names differ between them and across seasons, so they're matched on (date, score).

- [football-data.co.uk](https://www.football-data.co.uk): results, shots, cards and bookmaker odds since the 1990s (xG from 2026/27)
- [OpenLigaDB](https://www.openligadb.de): official matchday structure and future fixtures

![Data availability](figures/01_data_availability.png)

![How the variables evolved](figures/02_variables_evolution.png)

![Outcomes and goals](figures/03_outcomes_and_goals.png)

Over 16 seasons of refitted ratings, Bayern's dominance, Dortmund's peak years, RB Leipzig's arrival (and the promoted-team prior they had to climb out of) and Leverkusen's 2024 surge are all visible:

![Ratings over time](figures/04_ratings_evolution.png)

---

## Package reference

```python
from glassball import Bundesliga, plots

s = Bundesliga(2026)              # season starting in 2026; data is downloaded and cached in ~/.cache/glassball
s.fixtures                        # all 306 matches: matchday, kickoff, result, shots, odds (where played)
s.table(after_matchday=4)         # league table at any point
s.ratings(before_matchday=5)      # attack / defence ratings with standard errors
s.predict(5, contrast=True)       # matchday 5: H/D/A, expected goals, drivers (+ GBM, + bookmakers if played)
s.explain("Dortmund", "Werder Bremen")
fc = s.forecast(before_matchday=5, n_sims=20_000)
fc.table                          # expected points/position, P(title/top4/top6/play-off/relegation), full position distribution
fc.swing("Union Berlin", "relegated")
s.evaluate()                      # walk-forward grading of every played matchday vs GBM and bookmakers

plots.matchday(s.predict(contrast=True)); plots.table(fc); plots.explain(s.explain("Bayern Munich", "RB Leipzig"))
```

Time travel is built in: every method takes `before_matchday=` or `as_of=`. Forecasts only ever use matches played before that point, so any historical forecast is a genuine out-of-sample forecast. Seasons from 2004/05 onwards are supported, and future seasons work as soon as OpenLigaDB publishes their fixtures.

## Repository layout

```
glassball/              the importable package
src/                    the exact code that produced the freeze (kept byte-identical; see below)
freeze/2026-10-08/      the pre-registered forecast
data/raw/               the data snapshot used for the freeze
updates/                rolling re-forecasts after each matchday (same frozen code)
figures/                everything above;  python scripts/make_figures.py  regenerates it
tests/                  includes a test that glassball reproduces the freeze from the snapshot
```

`glassball` is a packaged version of `src/`. The pre-registration promises that the rolling forecasts use the frozen code unchanged, so `src/` is never edited. `tests/test_reproduces_freeze.py` checks that the package regenerates the frozen match probabilities, GBM predictions and all 20,000 simulated seasons from the data snapshot.

## Limitations, stated up front

- No lineups, injuries or transfers. They only reach the model through results, with a lag. That's the point of the "drift" section of the talk.
- Ratings are fixed within a forecast. A match in March is forecast with October's ratings, and only parameter uncertainty widens it.
- Promoted teams start from a generic prior, so their ratings are the least certain.
- Goals are noisy. xG-based ratings would likely be sharper, but public Bundesliga xG only starts in 2026/27.

---

Built by Ari Joury at Wangari Global, where we build reliable, traceable AI and analytics. In football, that discipline keeps a forecast honest; in production, it keeps a model trustworthy.
