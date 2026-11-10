"""Read-only simulation of the smoothing on a real collection, via AnkiConnect.

Usage (Anki running with AnkiConnect on localhost:8765):
    python tools/simulate.py "Deck name" ["Other deck" ...] [--horizon 90]

Nothing is written to the collection.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_smoother.smoothing import Card, assign, auto_curve, daily_counts  # noqa: E402

ANKICONNECT_URL = "http://localhost:8765"


def anki(action: str, **params):
    # Explicit UTF-8: non-ASCII deck names break AnkiConnect otherwise.
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(ANKICONNECT_URL, body)) as response:
        reply = json.load(response)
    if reply["error"]:
        raise RuntimeError(f"AnkiConnect {action}: {reply['error']}")
    return reply["result"]


def today_day_number(horizon: int) -> int:
    """Anki's day number for today, deduced from any card due in the window."""
    for offset in range(1, horizon + 1):
        ids = anki("findCards", query=f"is:review prop:due={offset}")
        if ids:
            return anki("cardsInfo", cards=ids[:1])[0]["due"] - offset
    raise RuntimeError("No review card due in the window.")


def deck_cards(deck: str, horizon: int, today: int):
    query = f'deck:"{deck}" is:review -is:suspended -is:buried prop:due>=1 prop:due<={horizon}'
    infos = anki("cardsInfo", cards=anki("findCards", query=query))
    return [Card(id=i["cardId"], due=i["due"] - today, interval=i["interval"]) for i in infos]


def digits(counts) -> str:
    return "".join(str(n) if n < 10 else "+" for n in counts)


def simulate(deck: str, horizon: int, today: int) -> None:
    cards = deck_cards(deck, horizon, today)
    before = daily_counts((c.due for c in cards), horizon)
    target = auto_curve(before)
    new_due = assign(cards, target)

    moved = [c for c in cards if new_due[c.id] != c.due]
    print(f"\n{deck}: {len(cards)} cards over {horizon} days")
    print(f"  before {digits(before)}")
    print(f"  after  {digits(target)}")
    if not moved:
        print("  nothing to move")
        return
    advances = [c.due - new_due[c.id] for c in moved]
    relative = [(c.due - new_due[c.id]) / c.interval for c in moved]
    print(
        f"  {len(moved)} cards advanced, by {sum(advances) / len(moved):.1f} days on average "
        f"(max {max(advances)}); max advance relative to interval: {max(relative):.0%}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("decks", nargs="+")
    parser.add_argument("--horizon", type=int, default=90)
    args = parser.parse_args()
    today = today_day_number(args.horizon)
    for deck in args.decks:
        simulate(deck, args.horizon, today)


if __name__ == "__main__":
    main()
