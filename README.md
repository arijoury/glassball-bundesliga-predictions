# glassball ⚽🔍

**Bundesliga predictions you can audit.** Who wins the league, who goes down, and what happens in every match, for the current season or any season since 2004/05. Every probability traces back to a few numbers you can inspect: home advantage, each team's attack, each team's defence.

No API keys, no accounts, no data wrangling. glassball downloads free public data and caches it on your machine.

## Install

Requires Python 3.10 or newer.

```bash
pip install git+https://github.com/arijoury/glassball-bundesliga-predictions
```

## Quick start

```bash
glassball
```

```
Bundesliga 2026/27: 36/306 matches played, next up: matchday 5
Top of the table: 1. Dortmund 12 pts, 2. Bayern Munich 10 pts, 3. Freiburg 10 pts

Bayern Munich are favourites to win the 2026/27 Bundesliga: 80%  (then Dortmund 15%, Leverkusen 3%, RB Leipzig 1%)

        kick-off         home          away home win draw away win          pick top score
Fri 09 Oct 20:30     Dortmund Werder Bremen      69%  19%      12%      Dortmund       2-0
Sat 10 Oct 15:30     Augsburg Bayern Munich      14%  17%      69% Bayern Munich       1-2
Sat 10 Oct 15:30   Hoffenheim       Hamburg      58%  22%      20%    Hoffenheim       1-1
...
```

The first run takes a minute while it downloads about 15 seasons of history. After that, most commands answer in a few seconds.

## What do you want to know?

| Question | Command |
|---|---|
| Who wins the league? | `glassball winner` |
| What will the final table look like? | `glassball table` |
| Every probability for every final position | `glassball table --full` |
| Who wins this weekend's games? | `glassball matchday` |
| A specific matchday | `glassball matchday 12` |
| Every remaining match of the season | `glassball matchday all` |
| How did the model do on a past matchday? | `glassball matchday 4` (shows results, ✓/✗, and the bookmakers' view) |
| Why does it favour one team? | `glassball explain bayern dortmund` |
| Which games decide my team's season? | `glassball swing bvb` or `glassball swing union --event relegated` |
| What if our striker gets injured? | `glassball winner --shift "bayern:attack=-0.15"` |
| How strong is each team? | `glassball ratings` |
| The real table right now | `glassball standings` |
| How good is the model, honestly? | `glassball evaluate --season 2025` |
| Which team names can I type? | `glassball teams` |

Team names are forgiving: `bayern`, `BVB`, `gladbach`, `köln`, `hsv` and `s04` all work.

## Options that work everywhere

| Option | What it does |
|---|---|
| `--season 2023` | Any season since 2004/05, by its starting year (`2023`, `2023/24` and `23/24` all work). Default: the current season |
| `-b 10`, `--before-matchday 10` | **Time travel:** only use matches played before matchday 10. Great for testing the model on past seasons |
| `--as-of 2026-10-08` | The same, by date |
| `-v`, `--verbose` | More detail: expected goals, the drivers of each match, uncertainty, data info |
| `-q`, `--quiet` | Just the answer, e.g. `glassball winner -q` → `Bayern Munich 80%` |
| `--plot chart.png` | Also save a chart (`.png`, `.svg`, `.pdf`) |
| `--csv file.csv` | Also save the result as a spreadsheet |
| `--json` | Print the result as JSON, for scripts |
| `--shift "TEAM:attack=X"` | What-if scenarios. `attack +0.1` means about 10% more goals scored; `defence -0.1` about 10% fewer conceded. Repeatable |
| `--sims 50000` | More simulated seasons for smoother table probabilities (default 10,000) |
| `--offline`, `--refresh` | Use cached data only / re-download the current season now |

`glassball --help` and `glassball <command> --help` list everything.

### A few recipes

```bash
glassball table --season 2023 -b 10            # 2023/24 as it looked in November: was Leverkusen's title visible?
glassball matchday all --csv rest_of_season.csv
glassball explain leipzig bayern -v --plot why.png
glassball swing hsv --event relegated --plot hsv.png
glassball winner --shift "bayern:attack=-0.15" --shift "bvb:attack=0.1"
```

## Use it from Python

```python
from glassball import Bundesliga, plots

s = Bundesliga()                         # current season; Bundesliga(2023) for 2023/24
s.predict()                              # next matchday: probabilities, expected goals, most likely score, drivers
s.predict(12, contrast=True)             # matchday 12, next to a gradient-boosted comparison model
s.explain("bayern", "dortmund")          # the receipt for one match
fc = s.forecast(n_sims=20_000)           # simulate the rest of the season
fc.table                                 # expected points, P(title / top 4 / relegation), full position distribution
fc.swing("bvb", "title")                 # which matches move Dortmund's title chances most
s.forecast(shift={"bayern": {"attack": -0.15}})
s.table(after_matchday=10)               # the real table at any point
s.ratings()                              # attack / defence ratings with standard errors
s.evaluate()                             # grade every played matchday against bookmakers

plots.table(fc).savefig("table.png")     # plots: matchday, table, explain, sensitivity, swing, ratings, reliability
```

Every method takes `before_matchday=` or `as_of=`, so any forecast for a past season uses only what was known at the time.

## How it works, in one minute

1. **Each team gets two numbers:** an attack rating (how much it scores) and a defence rating (how much it concedes), plus one league-wide home advantage.
2. **Expected goals for a match** = base rate × home advantage × home attack × away defence, and likewise for the away side. That's the whole model, and `glassball explain` shows each factor.
3. **Ratings are learned from results.** Recent matches count more (half-life of 270 days). Newly promoted teams start with a cautious prior.
4. **Goals follow a Poisson distribution** with a small correction for low scores ([Dixon & Coles, 1997](https://doi.org/10.1111/1467-9876.00065)). That gives home/draw/away probabilities and the likeliest scores.
5. **The table forecast simulates the rest of the season** thousands of times. Each run also varies the ratings within their uncertainty, so the probabilities reflect how much the model *doesn't* know.

**Reading the output:** *pick* is the most likely result; *top score* is the single most likely exact score. They can disagree: 1–1 is often the likeliest score even when one side is a clear favourite, because a favourite's wins are spread over 1–0, 2–0, 2–1 and so on.

### How good is it?

Over seven seasons (2019/20–2025/26), predicting every matchday blind, it beat a typical machine-learning baseline (gradient boosting on Elo and form) in six of them. It lost to the bookmakers every time, which is normal: betting odds include team news this model never sees. Its probabilities are well calibrated: when it says 30%, it happens about 30% of the time. Check any season yourself with `glassball evaluate --season YEAR`.

### What it doesn't know

- Lineups, injuries, suspensions, transfers and new managers. These only reach it through results, with a lag. Use `--shift` to play them through yourself.
- Anything beyond goals (no xG, shots or tracking data in the ratings).
- Within one forecast, ratings stay fixed. A match in March is predicted with today's ratings, just with wider uncertainty.

## Data

- [football-data.co.uk](https://www.football-data.co.uk): results, match statistics and bookmaker odds
- [OpenLigaDB](https://www.openligadb.de): official fixtures and matchdays, including future ones

Data is cached in `~/.cache/glassball` (set `GLASSBALL_CACHE` to change it). Finished seasons are downloaded once, and the current season refreshes every 6 hours. A new season works as soon as OpenLigaDB publishes its fixtures, usually in early summer.

## Live test: 2026/27

Backtests can be tuned until they look good, so this model is also being tested in public. Its forecast for the rest of the 2026/27 season was frozen and fingerprinted on 8 October 2026, before matchday 5, together with the rules for grading it. Everything is in [`preregistration/2026-27/`](preregistration/2026-27/), starting with the [results summary](preregistration/2026-27/RESULTS_2026-10-08.md). The first public grading is at Machine Learning Week Europe, Munich, 17 November 2026.

## Development

```bash
git clone https://github.com/arijoury/glassball-bundesliga-predictions && cd glassball-bundesliga-predictions
pip install -e ".[dev]" && pytest
```

The tests include an offline run of every CLI command, and a check that the package reproduces the frozen 2026/27 forecast exactly.

Background on the methods: [*Soccer Analytics with Machine Learning*](https://learning.oreilly.com/library/view/soccer-analytics-with/9781098181109/) (O'Reilly, 2026). MIT licensed.

---

Built by [Ari Joury](https://www.linkedin.com/in/arijoury) at [Wangari Global](https://wangari.global), where we build reliable, traceable AI and analytics.
