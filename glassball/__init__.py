"""glassball: traceable, honestly-graded Bundesliga forecasts.

    from glassball import Bundesliga
    Bundesliga(2026).forecast().table
"""
from .model import DixonColes, Hyper
from .season import Bundesliga
from .simulate import TableForecast

__version__ = "0.1.0"
__all__ = ["Bundesliga", "DixonColes", "Hyper", "TableForecast"]
