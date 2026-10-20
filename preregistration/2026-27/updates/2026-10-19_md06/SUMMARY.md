# Rolling update after matchday 6 (data up to 2026-10-19)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–6 (18 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.2066 | 0.5946 | 0.9817 | 61% |
| GBM (Elo + form) | 0.2141 | 0.6408 | 1.0760 | 50% |
| Bookmakers (avg. closing odds) | 0.2202 | 0.6305 | 1.0413 | 67% |
| Base rates | 0.2271 | 0.6276 | 1.0421 | 50% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 85% | 100% → 100% | 0% → 0% | 80 → 80 |
| Dortmund | 14% → 8% | 90% → 84% | 0% → 0% | 69 → 66 |
| Leverkusen | 3% → 5% | 63% → 76% | 0% → 0% | 61 → 64 |
| RB Leipzig | 1% → 1% | 37% → 45% | 0% → 0% | 55 → 57 |
| Stuttgart | 0% → 0% | 31% → 28% | 0% → 0% | 54 → 53 |
| Freiburg | 0% → 0% | 24% → 24% | 0% → 0% | 52 → 52 |
| Mainz | 0% → 0% | 13% → 12% | 1% → 1% | 48 → 49 |
| Ein Frankfurt | 0% → 0% | 9% → 6% | 2% → 3% | 47 → 45 |
| Augsburg | 0% → 0% | 7% → 5% | 3% → 3% | 45 → 45 |
| Hoffenheim | 0% → 0% | 6% → 4% | 4% → 4% | 44 → 44 |
| Elversberg | 0% → 0% | 10% → 8% | 13% → 10% | 42 → 43 |
| Werder Bremen | 0% → 0% | 4% → 3% | 5% → 5% | 43 → 43 |
| Hamburg | 0% → 0% | 1% → 2% | 28% → 10% | 35 → 41 |
| FC Koln | 0% → 0% | 1% → 1% | 17% → 14% | 38 → 39 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 25% | 33 → 35 |
| Schalke 04 | 0% → 0% | 2% → 1% | 31% → 42% | 35 → 32 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 39% | 35 → 32 |
| Paderborn | 0% → 0% | 2% → 1% | 37% → 44% | 33 → 32 |
