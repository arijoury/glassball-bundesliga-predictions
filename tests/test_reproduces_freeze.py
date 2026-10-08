"""The package must regenerate the frozen 8 Oct 2026 forecast from the frozen data snapshot."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import sklearn

from glassball import Bundesliga

ROOT = Path(__file__).resolve().parents[1] / "preregistration" / "2026-27"
FREEZE = ROOT / "freeze" / "2026-10-08"
TOL = 1e-4  # frozen CSVs are rounded to 4 decimals


def season():
    return Bundesliga(2026, data_dir=ROOT / "data" / "raw",
                      fixtures_file=ROOT / "data" / "raw" / "openligadb_bl1_2026_20261008.json")


def test_match_forecasts_identical():
    s = season()
    frozen = pd.read_csv(FREEZE / "match_forecasts.csv")
    fc = s.forecast(as_of="2026-10-08", n_sims=10)  # only need `remaining`
    new = s.model(as_of="2026-10-08").predict(fc.remaining)
    assert len(new) == len(frozen) == 270
    for c in ["pH", "pD", "pA", "xG_home", "xG_away"]:
        np.testing.assert_allclose(new[c].to_numpy(), frozen[c].to_numpy(), atol=TOL)


def test_table_forecast_identical():
    frozen = pd.read_csv(FREEZE / "table_forecast.csv", index_col=0)
    new = season().forecast(as_of="2026-10-08").table
    pd.testing.assert_frame_equal(new.loc[frozen.index, frozen.columns], frozen, atol=TOL, check_dtype=False)


FROZEN_SKLEARN = json.loads((FREEZE / "meta.json").read_text())["versions"]["sklearn"]


@pytest.mark.skipif(sklearn.__version__ != FROZEN_SKLEARN,
                    reason=f"the GBM only reproduces under scikit-learn {FROZEN_SKLEARN} (the glass box reproduces everywhere)")
def test_gbm_identical():
    s = season()
    frozen = pd.read_csv(FREEZE / "match_forecasts.csv")
    md5 = s.predict(5, as_of="2026-10-08", contrast=True)
    f5 = frozen[frozen.Matchday == 5].reset_index(drop=True)
    np.testing.assert_allclose(md5[["ml_pH", "ml_pD", "ml_pA"]].to_numpy(), f5[["ml_pH", "ml_pD", "ml_pA"]].to_numpy(), atol=TOL)
