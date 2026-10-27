# Rolling update after matchday 7 (data up to 2026-10-26)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–7 (27 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.2159 | 0.6065 | 1.0038 | 56% |
| GBM (Elo + form) | 0.2315 | 0.6576 | 1.1008 | 48% |
| Bookmakers (avg. closing odds) | 0.2271 | 0.6343 | 1.0515 | 59% |
| Base rates | 0.2297 | 0.6328 | 1.0491 | 48% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 89% | 100% → 100% | 0% → 0% | 80 → 81 |
| Dortmund | 14% → 8% | 90% → 88% | 0% → 0% | 69 → 67 |
| Leverkusen | 3% → 2% | 63% → 68% | 0% → 0% | 61 → 61 |
| RB Leipzig | 1% → 1% | 37% → 58% | 0% → 0% | 55 → 59 |
| Freiburg | 0% → 0% | 24% → 23% | 0% → 0% | 52 → 51 |
| Stuttgart | 0% → 0% | 31% → 21% | 0% → 1% | 54 → 51 |
| Hoffenheim | 0% → 0% | 6% → 10% | 4% → 2% | 44 → 47 |
| Mainz | 0% → 0% | 13% → 8% | 1% → 2% | 48 → 46 |
| Werder Bremen | 0% → 0% | 4% → 7% | 5% → 3% | 43 → 46 |
| Ein Frankfurt | 0% → 0% | 9% → 5% | 2% → 4% | 47 → 45 |
| Augsburg | 0% → 0% | 7% → 4% | 3% → 4% | 45 → 44 |
| Hamburg | 0% → 0% | 1% → 2% | 28% → 14% | 35 → 39 |
| Elversberg | 0% → 0% | 10% → 4% | 13% → 20% | 42 → 39 |
| FC Koln | 0% → 0% | 1% → 1% | 17% → 18% | 38 → 38 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 26% | 33 → 35 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 28% | 35 → 35 |
| Paderborn | 0% → 0% | 2% → 1% | 37% → 35% | 33 → 34 |
| Schalke 04 | 0% → 0% | 2% → 1% | 31% → 43% | 35 → 32 |
