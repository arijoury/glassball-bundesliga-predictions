# Rolling update after matchday 10 (data up to 2026-11-23)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–10 (54 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.1952 | 0.5673 | 0.9538 | 61% |
| GBM (Elo + form) | 0.2001 | 0.5743 | 0.9719 | 59% |
| Bookmakers (avg. closing odds) | 0.2003 | 0.5794 | 0.9768 | 63% |
| Base rates | 0.2297 | 0.6328 | 1.0491 | 48% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 78% | 100% → 100% | 0% → 0% | 80 → 78 |
| Dortmund | 14% → 14% | 90% → 90% | 0% → 0% | 69 → 69 |
| RB Leipzig | 1% → 5% | 37% → 76% | 0% → 0% | 55 → 64 |
| Leverkusen | 3% → 2% | 63% → 59% | 0% → 0% | 61 → 61 |
| Freiburg | 0% → 1% | 24% → 34% | 0% → 0% | 52 → 57 |
| Stuttgart | 0% → 0% | 31% → 21% | 0% → 0% | 54 → 53 |
| Werder Bremen | 0% → 0% | 4% → 9% | 5% → 0% | 43 → 50 |
| Ein Frankfurt | 0% → 0% | 9% → 5% | 2% → 1% | 47 → 47 |
| Hoffenheim | 0% → 0% | 6% → 2% | 4% → 2% | 44 → 45 |
| Augsburg | 0% → 0% | 7% → 2% | 3% → 3% | 45 → 43 |
| Mainz | 0% → 0% | 13% → 1% | 1% → 5% | 48 → 41 |
| Elversberg | 0% → 0% | 10% → 2% | 13% → 8% | 42 → 41 |
| FC Koln | 0% → 0% | 1% → 0% | 17% → 10% | 38 → 38 |
| Hamburg | 0% → 0% | 1% → 0% | 28% → 13% | 35 → 38 |
| Paderborn | 0% → 0% | 2% → 0% | 37% → 37% | 33 → 32 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 36% | 33 → 32 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 39% | 35 → 31 |
| Schalke 04 | 0% → 0% | 2% → 0% | 31% → 47% | 35 → 30 |
