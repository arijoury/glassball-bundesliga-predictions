# Rolling update after matchday 5 (data up to 2026-10-12)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–5 (9 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.2201 | 0.6349 | 1.0356 | 67% |
| GBM (Elo + form) | 0.2419 | 0.7245 | 1.2154 | 56% |
| Bookmakers (avg. closing odds) | 0.2369 | 0.6785 | 1.1156 | 67% |
| Base rates | 0.2349 | 0.6432 | 1.0631 | 44% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 78% | 100% → 99% | 0% → 0% | 80 → 78 |
| Dortmund | 14% → 12% | 90% → 85% | 0% → 0% | 69 → 67 |
| Leverkusen | 3% → 5% | 63% → 69% | 0% → 0% | 61 → 63 |
| RB Leipzig | 1% → 2% | 37% → 52% | 0% → 0% | 55 → 59 |
| Stuttgart | 0% → 1% | 31% → 35% | 0% → 0% | 54 → 56 |
| Freiburg | 0% → 1% | 24% → 24% | 0% → 0% | 52 → 53 |
| Mainz | 0% → 0% | 13% → 8% | 1% → 2% | 48 → 47 |
| Augsburg | 0% → 0% | 7% → 7% | 3% → 2% | 45 → 46 |
| Ein Frankfurt | 0% → 0% | 9% → 4% | 2% → 4% | 47 → 44 |
| Werder Bremen | 0% → 0% | 4% → 4% | 5% → 4% | 43 → 44 |
| Hoffenheim | 0% → 0% | 6% → 2% | 4% → 7% | 44 → 42 |
| FC Koln | 0% → 0% | 1% → 2% | 17% → 11% | 38 → 40 |
| Elversberg | 0% → 0% | 10% → 5% | 13% → 17% | 42 → 40 |
| Hamburg | 0% → 0% | 1% → 1% | 28% → 15% | 35 → 38 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 26% | 33 → 35 |
| Schalke 04 | 0% → 0% | 2% → 1% | 31% → 33% | 35 → 34 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 30% | 35 → 34 |
| Paderborn | 0% → 0% | 2% → 0% | 37% → 48% | 33 → 30 |
