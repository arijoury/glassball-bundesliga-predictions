# Rolling update after matchday 9 (data up to 2026-11-09)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–9 (45 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.1968 | 0.5662 | 0.9506 | 58% |
| GBM (Elo + form) | 0.2056 | 0.5854 | 0.9939 | 56% |
| Bookmakers (avg. closing odds) | 0.2040 | 0.5832 | 0.9804 | 62% |
| Base rates | 0.2287 | 0.6307 | 1.0463 | 49% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 87% | 100% → 100% | 0% → 0% | 80 → 80 |
| Dortmund | 14% → 9% | 90% → 90% | 0% → 0% | 69 → 68 |
| RB Leipzig | 1% → 2% | 37% → 68% | 0% → 0% | 55 → 62 |
| Leverkusen | 3% → 1% | 63% → 55% | 0% → 0% | 61 → 59 |
| Freiburg | 0% → 0% | 24% → 31% | 0% → 0% | 52 → 55 |
| Stuttgart | 0% → 0% | 31% → 30% | 0% → 0% | 54 → 55 |
| Werder Bremen | 0% → 0% | 4% → 6% | 5% → 1% | 43 → 47 |
| Hoffenheim | 0% → 0% | 6% → 5% | 4% → 2% | 44 → 46 |
| Ein Frankfurt | 0% → 0% | 9% → 4% | 2% → 2% | 47 → 46 |
| Elversberg | 0% → 0% | 10% → 6% | 13% → 6% | 42 → 44 |
| Mainz | 0% → 0% | 13% → 3% | 1% → 3% | 48 → 43 |
| Augsburg | 0% → 0% | 7% → 1% | 3% → 7% | 45 → 40 |
| Hamburg | 0% → 0% | 1% → 1% | 28% → 9% | 35 → 40 |
| FC Koln | 0% → 0% | 1% → 0% | 17% → 19% | 38 → 36 |
| Paderborn | 0% → 0% | 2% → 0% | 37% → 28% | 33 → 35 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 31% | 33 → 34 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 37% | 35 → 32 |
| Schalke 04 | 0% → 0% | 2% → 0% | 31% → 54% | 35 → 29 |
