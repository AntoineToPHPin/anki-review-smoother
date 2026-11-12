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

from review_smoother.i18n import Translator  # noqa: E402
from review_smoother.smoothing import (  # noqa: E402
    Card,
    daily_counts,
    lookahead_end,
    move_stats,
    smooth,
)

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


REVIEW_CARDS = "is:review -is:suspended -is:buried -deck:filtered"


def deck_cards(deck: str, horizon: int, today: int):
    query = f'deck:"{deck}" {REVIEW_CARDS} prop:due>=1 prop:due<={horizon}'
    infos = anki("cardsInfo", cards=anki("findCards", query=query))
    return [
        Card(id=i["cardId"], due=i["due"] - today, interval=i["interval"], note=i["note"])
        for i in infos
    ]


def sibling_days(cards, today: int):
    """Days on which the notes of `cards` have other review cards due (like
    ui.sibling_days, without relearning cards)."""
    if not cards:
        return {}
    notes = ",".join(str(n) for n in {c.note for c in cards})
    ids = set(anki("findCards", query=f"nid:{notes} {REVIEW_CARDS}")) - {c.id for c in cards}
    taken = {}
    for info in anki("cardsInfo", cards=sorted(ids)) if ids else []:
        taken.setdefault(info["note"], set()).add(info["due"] - today)
    return taken


def same_day_siblings(due_by_card, notes, taken, horizon: int) -> int:
    """Cards in the window sharing their day with a sibling."""
    days = {}
    for card_id, day in due_by_card.items():
        if 1 <= day <= horizon:
            days.setdefault((notes[card_id], day), []).append(card_id)
    count = 0
    for (note, day), ids in days.items():
        if len(ids) > 1 or day in taken.get(note, ()):
            count += len(ids)
    return count


def digits(counts) -> str:
    return "".join(str(n) if n < 10 else "+" for n in counts)


def simulate(deck: str, horizon: int, today: int, allow_postpone: bool) -> None:
    cards = deck_cards(deck, lookahead_end(horizon), today)
    taken = sibling_days(cards, today)
    before = daily_counts((c.due for c in cards if c.due <= horizon), horizon)
    target, new_due = smooth(cards, horizon, allow_postpone, taken)

    moved = [c for c in cards if new_due[c.id] != c.due]
    pulled = sum(target) - sum(before)
    notes = {c.id: c.note for c in cards}
    print(f"\n{deck}: {sum(before)} cards over {horizon} days, {pulled} pulled in")
    print(f"  before {digits(before)}")
    print(f"  after  {digits(target)}")
    print(
        "  cards sharing their day with a sibling: "
        f"{same_day_siblings({c.id: c.due for c in cards}, notes, taken, horizon)} before, "
        f"{same_day_siblings(new_due, notes, taken, horizon)} after"
    )
    if not moved:
        print("  nothing to move")
        return
    for sentence in Translator("en").describe_moves(*move_stats(cards, new_due)):
        print(f"  {sentence}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("decks", nargs="+")
    parser.add_argument("--horizon", type=int, default=90)
    parser.add_argument(
        "--postpone", action="store_true", help="allow postponing a few cards"
    )
    args = parser.parse_args()
    today = today_day_number(args.horizon)
    for deck in args.decks:
        simulate(deck, args.horizon, today, args.postpone)


if __name__ == "__main__":
    main()
