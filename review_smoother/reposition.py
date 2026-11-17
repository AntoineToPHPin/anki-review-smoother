"""New card positions, without Anki imports (testable outside Anki).

Anki's own Reposition gives every card of a note the same position, and its
"Randomize order" shuffles notes, not cards. Here each card gets its own
position; shuffled, sibling cards are kept apart, so that they are not
introduced on the same day.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

# Random attempts per sibling gap tried before the deterministic one.
SHUFFLE_TRIES = 100


@dataclass(frozen=True)
class NewCard:
    id: int
    note: int
    # Card template's index in its note.
    ord: int
    # Current position in the new card queue (Anki's `due` for new cards).
    position: int


def current_order(cards: Sequence[NewCard]) -> List[NewCard]:
    """The order Anki introduces them in (within a deck): by position, then
    note and template."""
    return sorted(cards, key=lambda c: (c.position, c.note, c.ord, c.id))


def sibling_gap(order: Sequence[NewCard]) -> Optional[int]:
    """Smallest distance, in positions of `order`, between two cards of the
    same note; None without siblings."""
    last: Dict[int, int] = {}
    gap: Optional[int] = None
    for index, card in enumerate(order):
        if card.note in last:
            distance = index - last[card.note]
            gap = distance if gap is None else min(gap, distance)
        last[card.note] = index
    return gap


def _random_attempt(cards: Sequence[NewCard], gap: int, rng: random.Random) -> Optional[List[NewCard]]:
    """A random order with siblings at least `gap` apart, built slot by slot
    (each slot takes a random card whose note is far enough), or None if it
    gets stuck."""
    remaining = list(cards)
    rng.shuffle(remaining)
    last: Dict[int, int] = {}
    order: List[NewCard] = []
    for index in range(len(cards)):
        pick = next(
            (i for i, c in enumerate(remaining) if index - last.get(c.note, -gap) >= gap),
            None,
        )
        if pick is None:
            return None
        card = remaining.pop(pick)
        last[card.note] = index
        order.append(card)
    return order


def _greedy_attempt(cards: Sequence[NewCard], gap: int, rng: random.Random) -> Optional[List[NewCard]]:
    """Like `_random_attempt`, but each slot takes a card of the note with
    the most cards left (ties at random): the order that keeps siblings
    apart whenever it can be done, used when random attempts fail."""
    left: Dict[int, List[NewCard]] = {}
    for card in rng.sample(list(cards), len(cards)):
        left.setdefault(card.note, []).append(card)
    last: Dict[int, int] = {}
    order: List[NewCard] = []
    for index in range(len(cards)):
        allowed = [n for n, c in left.items() if c and index - last.get(n, -gap) >= gap]
        if not allowed:
            return None
        most = max(len(left[n]) for n in allowed)
        note = rng.choice([n for n in allowed if len(left[n]) == most])
        order.append(left[note].pop())
        last[note] = index
    return order


def shuffled(
    cards: Sequence[NewCard], spacing: int, rng: Optional[random.Random] = None
) -> List[NewCard]:
    """The cards in a random order, card by card, siblings at least
    `spacing` positions apart (the deck's new cards per day, so that they
    are introduced on different days); when that cannot be done, as far
    apart as possible."""
    rng = rng or random.Random()
    order = list(cards)
    rng.shuffle(order)
    notes = {c.note for c in cards}
    if len(notes) == len(cards) or spacing <= 1:
        return order
    for gap in range(min(spacing, len(cards)), 1, -1):
        for _ in range(SHUFFLE_TRIES):
            attempt = _random_attempt(cards, gap, rng)
            if attempt is not None:
                return attempt
        attempt = _greedy_attempt(cards, gap, rng)
        if attempt is not None:
            return attempt
    return order


def positions(
    order: Sequence[NewCard], start: int = 1, step: int = 1
) -> Dict[int, int]:
    """New position of every card: `start`, `start + step`... in `order`,
    one per card (siblings included)."""
    return {card.id: start + index * step for index, card in enumerate(order)}
