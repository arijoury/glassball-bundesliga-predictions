"""One-shot validation on the held-out 2025/26 season: glass box vs GBM vs bookmakers vs base rates."""
import numpy as np
import pandas as pd

import ml
from backtest import VALIDATION, TUNE, probs_from_rates, walk_forward
from data import load_results
from model import Hyper, brier, logloss, odds_to_probs, outcome_index, rps

if __name__ == "__main__":
    results = load_results()
    hyper = Hyper()
    bt = walk_forward(results, VALIDATION, hyper)
    o = outcome_index(bt.FTHG.to_numpy(), bt.FTAG.to_numpy())

    feats, _ = ml.build(results, pd.Timestamp("2026-07-01"))
    train = feats[(feats.Season < VALIDATION[0]) & (feats.Season > "1213")]  # 12/13 = Elo burn-in
    val = feats[feats.Season == VALIDATION[0]]
    gbm = ml.make_model().fit(train[ml.FEATURES], ml.label(train))
    val = val.merge(bt[["Date", "HomeTeam", "AwayTeam"]], on=["Date", "HomeTeam", "AwayTeam"])

    train_rates = np.bincount(ml.label(train), minlength=3) / len(train)
    preds = {
        "Glass box (Dixon-Coles)": probs_from_rates(bt, hyper.rho),
        "GBM (Elo + form)": gbm.predict_proba(val[ml.FEATURES]),
        "Bookmakers (closing, avg)": odds_to_probs(bt.AvgCH, bt.AvgCD, bt.AvgCA),
        "Base rates (H/D/A)": np.tile(train_rates, (len(bt), 1)),
    }
    rows = [{"model": k, "rps": rps(P, o).mean(), "brier": brier(P, o).mean(),
             "logloss": logloss(P, o).mean(), "accuracy": (P.argmax(1) == o).mean()}
            for k, P in preds.items()]
    table = pd.DataFrame(rows)
    print(table.round(4).to_string(index=False))
    table.to_csv("../outputs/backtest/validation_2526.csv", index=False)

    out = bt.assign(**{f"dc_{c}": preds["Glass box (Dixon-Coles)"][:, i] for i, c in enumerate("HDA")},
                    **{f"ml_{c}": preds["GBM (Elo + form)"][:, i] for i, c in enumerate("HDA")},
                    **{f"bk_{c}": preds["Bookmakers (closing, avg)"][:, i] for i, c in enumerate("HDA")})
    out.to_csv("../outputs/backtest/validation_2526_predictions.csv", index=False)
