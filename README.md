# Bundesliga 2026/27: a traceable, pre-registered forecast

Companion code for *Soccer Analytics: Traceable and Honest Forecasting Across a Bundesliga Season* (Machine Learning Week Europe, Munich, 17 Nov 2026), building on *Soccer Analytics with Machine Learning* (O'Reilly, 2026).

See [PREREGISTRATION.md](PREREGISTRATION.md) for what was frozen, when, and how it will be graded.

```
src/data.py       load results (football-data.co.uk) and fixtures (OpenLigaDB)
src/model.py      glass-box Dixon-Coles model + scoring rules
src/ml.py         contrast model: gradient boosting on Elo + form
src/backtest.py   walk-forward hyperparameter tuning (2019/20-2024/25)
src/validate.py   one-shot validation on 2025/26
src/forecast.py   full snapshot: every remaining match + simulated final table
freeze/           the frozen forecast (never edited)
updates/          rolling re-runs after each matchday, same code
```

Verify the freeze:

```
shasum -a 256 -c MANIFEST.sha256
shasum -a 256 MANIFEST.sha256
```
