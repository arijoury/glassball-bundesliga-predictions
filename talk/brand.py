"""Wangari brand theme for the talk's charts (brand colours adapted to pass colour-blindness checks)."""
from glassball import plots

# Brand: terracotta #C97A59, burned terracotta #B56746, brown #85523E, sage #9BA992, cream #FADCCF.
# The pure brand hues are too muted for data series, so the series use saturated neighbours
# (terracotta, steel blue, olive-sage, plum), validated together for CVD separation.
WANGARI = dict(
    SURFACE="#FDF3EE", INK="#2E1D16", INK2="#6B4A3C", MUTED="#9C7F72", GRID="#EFDCD2",
    HOME="#B4532F", DRAW="#C9B6AB", AWAY="#2F6F9F",
    GLASS="#B4532F", GBM="#2F6F9F", BOOK="#8A9A3A",
    SERIES=["#B4532F", "#2F6F9F", "#8A9A3A", "#8E4F7E", "#C99A2E", "#5E8C82", "#6D5BA8", "#85523E"],
    SEQ=["#FDF3EE", "#F6D3C2", "#E8A487", "#C97A59", "#9A4A2C", "#5E2A17"],
)


def apply():
    plots.use_palette(**WANGARI)
