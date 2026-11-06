# Rolling update after matchday 8 (data up to 2026-11-02)

Generated automatically by `analysis/update.py`: frozen code (verified against MANIFEST.sha256), new data only.

## The frozen 8 Oct forecast, graded on matchdays 5–8 (36 matches)

| | RPS | Brier | Log loss | Accuracy |
|---|---|---|---|---|
| Glass box (Dixon-Coles) | 0.2170 | 0.6235 | 1.0279 | 50% |
| GBM (Elo + form) | 0.2270 | 0.6463 | 1.0808 | 47% |
| Bookmakers (avg. closing odds) | 0.2288 | 0.6517 | 1.0748 | 56% |
| Base rates | 0.2296 | 0.6466 | 1.0693 | 44% |

Lower is better for RPS (primary metric), Brier and log loss. Small samples are noisy: with fewer than ~100 matches, differences of 0.01 RPS are not meaningful.

## How the season forecast has moved since the freeze

| Team | Title (8 Oct → now) | Top 4 | Relegation | Exp. points |
|---|---|---|---|---|
| Bayern Munich | 81% → 86% | 100% → 100% | 0% → 0% | 80 → 79 |
| Dortmund | 14% → 10% | 90% → 90% | 0% → 0% | 69 → 67 |
| RB Leipzig | 1% → 2% | 37% → 64% | 0% → 0% | 55 → 60 |
| Leverkusen | 3% → 1% | 63% → 50% | 0% → 0% | 61 → 58 |
| Stuttgart | 0% → 0% | 31% → 30% | 0% → 0% | 54 → 54 |
| Freiburg | 0% → 0% | 24% → 29% | 0% → 0% | 52 → 53 |
| Werder Bremen | 0% → 0% | 4% → 9% | 5% → 1% | 43 → 48 |
| Ein Frankfurt | 0% → 0% | 9% → 7% | 2% → 2% | 47 → 46 |
| Hoffenheim | 0% → 0% | 6% → 5% | 4% → 3% | 44 → 45 |
| Elversberg | 0% → 0% | 10% → 8% | 13% → 7% | 42 → 44 |
| Mainz | 0% → 0% | 13% → 4% | 1% → 4% | 48 → 44 |
| Augsburg | 0% → 0% | 7% → 2% | 3% → 6% | 45 → 42 |
| Hamburg | 0% → 0% | 1% → 1% | 28% → 18% | 35 → 38 |
| FC Koln | 0% → 0% | 1% → 1% | 17% → 17% | 38 → 37 |
| Union Berlin | 0% → 0% | 0% → 0% | 33% → 28% | 33 → 35 |
| Paderborn | 0% → 0% | 2% → 1% | 37% → 31% | 33 → 35 |
| M'gladbach | 0% → 0% | 1% → 0% | 25% → 31% | 35 → 34 |
| Schalke 04 | 0% → 0% | 2% → 0% | 31% → 52% | 35 → 30 |
