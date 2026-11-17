# Live notebook: MLW Europe 2026

The notebook from the talk *Traceable and honest forecasting across a Bundesliga season* at Machine Learning Week Europe, Munich, 17 November 2026. It grades the forecast frozen on 8 October 2026 against the season so far, with the audience prompts from the talk built in, so you can play along.

## Run it

```bash
git clone https://github.com/arijoury/glassball-bundesliga-predictions && cd glassball-bundesliga-predictions
pip install -e . jupyterlab
jupyter lab talk/live_demo.ipynb
```

Then run all cells. The first run downloads about 11 MB of free public data (every Bundesliga season since 2000/01) and takes a few minutes. The data is cached in `~/.cache/glassball`, so later runs take under a minute, and `OFFLINE = True` in the first cell works without a network.

The reveal (section 6) reads the newest rolling update in [`preregistration/2026-27/updates/`](../preregistration/2026-27/updates/), so it grades more matches as the season goes on: `git pull` to get the latest. The saved outputs are from 17 November 2026, after matchday 9.

## Files

| File | What |
|---|---|
| `live_demo.ipynb` | The notebook. 🙋 cells are the audience prompts: fill in your own answers, or leave them at `None` |
| `reveal.py` | The scoreboard, the biggest miss and best call, Bayern's home games and the season forecast, read from the rolling updates. `python talk/reveal.py` prints every number |
| `room.py` | Keeps score of the answers in the 🙋 cells |
| `brand.py` | The chart colours used in the talk |
| `mystery_matches.csv` | The five matches of the game in section 4, drawn at random (seed 2026), with answers |
