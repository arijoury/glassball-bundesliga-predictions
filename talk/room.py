"""Keeps score of the room during the session: hands-up votes, shouted guesses, and the truth.

    room.vote("bayern_home", glass_box=12, gbm=20)     # hands per option
    room.guess("bayern_goals", 2.5)                     # a shouted number (or the room's consensus)
    room.truth("bayern_home", "glass_box", "Bayern won 3 of 3 at home")
    room.scorecard()                                    # the closing slide of the notebook
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from glassball import plots

ROOM: dict[str, dict] = {}
LABELS = {"q25": "~25%", "q40": "~40%", "q75": "~75%", "zero": "0", "one_to_three": "1–3", "four_to_six": "4–6",
          "seven": "7", "glass_box": "glass box", "gbm": "GBM", "too_high": "too high", "too_low": "too low",
          "about_right": "about right"}


def pretty(x):
    return LABELS.get(x, str(x).replace("_", " ")) if x is not None else None


def vote(key: str, question: str = "", **hands: int):
    """Record hands per option and draw the split."""
    total = sum(v for v in hands.values() if v) or 1
    ROOM[key] = {"question": question or key, "kind": "vote", "hands": hands,
                 "room_answer": max(hands, key=lambda k: hands[k] or 0) if any(hands.values()) else None}
    if not any(hands.values()):
        print(f"[{key}] no hands entered yet: fill in the counts and re-run")
        return
    fig, ax = plt.subplots(figsize=(7, 0.55 * len(hands) + 0.8))
    names = [pretty(n) for n in list(hands)[::-1]]
    shares = [(hands[n] or 0) / total for n in list(hands)[::-1]]
    ax.barh(names, shares, color=plots.GLASS, height=0.6)
    for y, s in enumerate(shares):
        ax.text(s + 0.01, y, f"{s:.0%}", va="center", fontsize=11, color=plots.INK)
    ax.set_xlim(0, 1.1); ax.set_xticks([]); ax.grid(False)
    ax.set_title(question or key, fontsize=12)
    plt.show()


def guess(key: str, value, question: str = "", quiet: bool = False):
    ROOM[key] = {"question": question or key, "kind": "guess", "room_answer": value}
    if not quiet:
        print(f"[{key}] the room says: {value}")


def truth(key: str, answer, explanation: str = "", tolerance: float | None = None, quiet: bool = False):
    """Reveal the answer and mark whether the room got it. `quiet`: record only (a card shows the result)."""
    r = ROOM.setdefault(key, {"question": key, "kind": "guess", "room_answer": None})
    r["truth"] = answer
    ra = r.get("room_answer")
    if ra is None:
        right = None
    elif tolerance is not None:
        right = abs(float(ra) - float(answer)) <= tolerance
    else:
        right = str(ra).lower() == str(answer).lower()
    r["right"] = right
    if quiet:
        return
    verdict ={True: "The room got it ✓", False: "The room missed it", None: "(no room answer recorded)"}[right]
    print(f"Answer: {pretty(answer)}. Room said: {pretty(ra)}. {verdict}")
    if explanation:
        print(explanation)


def scorecard() -> pd.DataFrame:
    rows = [{"question": r["question"], "room said": pretty(r.get("room_answer")), "answer": pretty(r.get("truth", "—")),
             "right?": {True: "✓", False: "✗", None: ""}.get(r.get("right"), "")}
            for r in ROOM.values() if "truth" in r]
    df = pd.DataFrame(rows)
    hits = sum(1 for r in ROOM.values() if r.get("right") is True)
    graded = sum(1 for r in ROOM.values() if r.get("right") is not None)
    print(f"The room: {hits} of {graded} right." if graded else "No graded answers yet.")
    return df
