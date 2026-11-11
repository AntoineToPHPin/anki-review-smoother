"""Pure smoothing logic.

This module must not import anything from Anki (`anki`, `aqt`) so that it can
be unit-tested and simulated outside of Anki.

Days are expressed as offsets from today: 1 is tomorrow, `horizon` is the last
day of the smoothing window. Today and overdue cards are never touched.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import accumulate
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Card:
    id: int
    due: int  # days from today (1 = tomorrow)
    interval: int  # current interval, in days


class InfeasibleCurve(ValueError):
    """The target curve cannot be reached by advancing cards only."""

    def __init__(self, day: int) -> None:
        super().__init__(
            f"Not enough cards due on or after day {day} to fill the target "
            f"curve without postponing cards."
        )
        self.day = day


def daily_counts(dues: Iterable[int], horizon: int) -> List[int]:
    """Number of cards due on each day of the window (index 0 = day 1)."""
    counts = [0] * horizon
    for due in dues:
        if not 1 <= due <= horizon:
            raise ValueError(f"Due day {due} is outside the window 1..{horizon}.")
        counts[due - 1] += 1
    return counts


def _upper_hull(points: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Upper convex hull of points sorted by x (monotone chain)."""
    hull: List[Tuple[int, int]] = []
    for x, y in points:
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            # Drop the middle point if it lies on or below the new chord.
            if (y2 - y1) * (x - x1) <= (y - y1) * (x2 - x1):
                hull.pop()
            else:
                break
        hull.append((x, y))
    return hull


def auto_curve(counts: Sequence[int]) -> List[int]:
    """Smooth descending curve reachable by advancing cards only.

    Guarantees, for the returned curve `t`:
    - `sum(t) == sum(counts)`: every card stays in the window;
    - for every day k, cards scheduled on days 1..k >= cards currently due on
      days 1..k, so no card ever needs to be postponed;
    - it is a non-increasing staircase, down to a block of 1s then 0s for
      sparse decks (the author prefers that to spacing 1 card every n days).

    The ideal curve is the lowest concave majorant of the cumulative due
    counts: its slope is the lowest non-increasing (fractional) daily rate
    that never falls behind what is due. It is then rounded down to whole
    cards, which still never falls behind (due counts are whole numbers below
    the ideal curve) and advances cards as little as possible.
    """
    horizon = len(counts)
    points = [(0, 0)] + list(zip(range(1, horizon + 1), accumulate(counts)))
    hull = _upper_hull(points)

    # Ideal cumulative curve at each day, rounded down to whole cards: still
    # >= the integer due counts.
    planned = [0]
    for (x1, y1), (x2, y2) in zip(hull, hull[1:]):
        slope = Fraction(y2 - y1, x2 - x1)
        for x in range(x1 + 1, x2 + 1):
            planned.append(math.floor(y1 + slope * (x - x1)))
    curve = [b - a for a, b in zip(planned, planned[1:])]

    # Rounding alternates (4, 3, 4, 3, 3... or 1, 0, 1, 1, 0...): sort it into
    # a staircase. Moving cards to earlier days keeps every cumulative
    # constraint satisfied.
    return sorted(curve, reverse=True)


def assign(cards: Sequence[Card], target: Sequence[int]) -> Dict[int, int]:
    """New due day for each card so that daily counts match `target` exactly.

    Cards are only ever advanced. Among valid assignments, this minimises the
    total relative advance, sum((due - new_due) / interval): advancing a card
    by a few days matters little when its interval is long, a lot when it is
    short. Days are filled from the last one backwards, each taking the
    available cards with the shortest intervals (the ones that are the most
    costly to advance).

    Raises InfeasibleCurve if the target would require postponing cards.
    """
    horizon = len(target)
    if sum(target) != len(cards):
        raise ValueError(
            f"Target curve holds {sum(target)} cards, but {len(cards)} cards "
            f"are due in the window."
        )
    by_due: List[List[Card]] = [[] for _ in range(horizon)]
    for card in cards:
        if not 1 <= card.due <= horizon:
            raise ValueError(
                f"Card {card.id} is due on day {card.due}, outside the window "
                f"1..{horizon}."
            )
        by_due[card.due - 1].append(card)

    available: list = []
    new_due: Dict[int, int] = {}
    for day in range(horizon, 0, -1):
        for card in by_due[day - 1]:
            # Shortest interval first; then the card due soonest, to keep
            # each individual move as small as possible.
            heapq.heappush(available, (card.interval, card.due, card.id))
        for _ in range(target[day - 1]):
            if not available:
                raise InfeasibleCurve(day)
            _, _, card_id = heapq.heappop(available)
            new_due[card_id] = day
    return new_due


# Postponing is the exception: a card may be pushed back by at most this
# share of its interval...
POSTPONE_MARGIN = 0.10
# ...and at most this share of the window's cards (at least one card) may be
# postponed, only to lower the peak at the start of the curve.
POSTPONE_BUDGET = 0.01


def _postpone_to_cap(
    cards: Sequence[Card], cap: int, horizon: int
) -> Optional[Dict[int, int]]:
    """Postpone cards so that days 1..k never hold more than cap * k cards.

    Returns the new due day of each postponed card, or None if the margins do
    not allow it. Sweeps forward; on an excess, pushes one day later a card
    already postponed if possible (to postpone as few cards as possible),
    otherwise the one with the longest interval; on a tie, the one due the
    latest, so that it is pushed back by as few days as possible.
    """
    latest = {
        c.id: min(c.due + int(c.interval * POSTPONE_MARGIN), horizon) for c in cards
    }
    arriving: List[List[Tuple[Card, bool]]] = [[] for _ in range(horizon + 2)]
    for card in cards:
        arriving[card.due].append((card, False))

    candidates: list = []
    scheduled = 0
    new_due: Dict[int, int] = {}
    for day in range(1, horizon + 1):
        for card, postponed in arriving[day]:
            scheduled += 1
            heapq.heappush(
                candidates, (not postponed, -card.interval, -day, card.id, card)
            )
        while scheduled > cap * day:
            # Cards that cannot go past this day stay where they are.
            while candidates and latest[candidates[0][-1].id] <= day:
                heapq.heappop(candidates)
            if not candidates:
                return None
            card = heapq.heappop(candidates)[-1]
            scheduled -= 1
            arriving[day + 1].append((card, True))
            new_due[card.id] = day + 1
    return new_due


def smooth(
    cards: Sequence[Card], horizon: int, allow_postpone: bool = True
) -> Tuple[List[int], Dict[int, int]]:
    """Target curve and new due day of every card.

    Cards are advanced only (see `auto_curve` and `assign`), unless
    `allow_postpone`: then the peak at the start of the curve is lowered one
    card a day at a time, by postponing cards within their margin, as long as
    that postpones no more cards than the budget and creates no steeper step
    than the advance-only curve has.

    That last rule keeps postponing for isolated bumps (4, 3, 3, 3... becomes
    3, 3, 3, 3...) and away from steady slopes: capping 18, 17, 17, 16, 15...
    would turn it into a plateau ending with a cliff (16 x 7 days, then 13).

    Finally, plateaus are evened out (see `even_out`).
    """
    advance_only = auto_curve(daily_counts((c.due for c in cards), horizon))
    target = advance_only
    shifted: Sequence[Card] = cards
    if allow_postpone:
        budget = max(1, int(len(cards) * POSTPONE_BUDGET))
        steepest = _steepest_step(advance_only)
        while target[0] > 1:
            postponed = _postpone_to_cap(cards, target[0] - 1, horizon)
            if postponed is None or len(postponed) > budget:
                break
            candidate = [replace(c, due=postponed.get(c.id, c.due)) for c in cards]
            lowered = auto_curve(daily_counts((c.due for c in candidate), horizon))
            if _steepest_step(lowered) > steepest:
                break
            shifted, target = candidate, lowered
    target = even_out(target)
    return target, assign(shifted, target)


def _steepest_step(curve: Sequence[int]) -> int:
    """Largest drop from one day to the next."""
    return max((a - b for a, b in zip(curve, curve[1:])), default=0)


def even_out(curve: Sequence[int]) -> List[int]:
    """Make the staircase more regular by evening out plateau lengths.

    While a plateau (the days at one level) is at least 2 days longer than the
    plateaus of both neighbouring levels, it gives one of its days to each:
    its first day goes up by one card, its last day down by one. For example
    14, 13, 12, 12, 12, 11, 10 becomes 14, 13, 13, 12, 11, 11, 10.

    That moves one card earlier, so it never requires postponing anything;
    the total and the descending order are kept. The plateau at the level of
    the last day is left out, as a neighbour too: its length only reflects
    where the window ends.
    """
    result = list(curve)
    if not result:
        return result
    last_level = result[-1]
    # Each change moves a card earlier, so this ends; the cap is a safeguard.
    for _ in range(sum(result) * len(result) + 1):
        lengths: Dict[int, int] = {}
        for level in result:
            lengths[level] = lengths.get(level, 0) + 1
        uneven = next(
            (
                level
                for level in range(result[0] - 1, last_level + 1, -1)
                if lengths.get(level, 0) >= lengths.get(level + 1, 0) + 2
                and lengths.get(level, 0) >= lengths.get(level - 1, 0) + 2
            ),
            None,
        )
        if uneven is None:
            break
        result[result.index(uneven)] += 1
        result[len(result) - 1 - result[::-1].index(uneven)] -= 1
    return result


@dataclass(frozen=True)
class MoveStats:
    """How far the cards moved in one direction (advanced or postponed)."""

    count: int
    mean_days: float
    max_days: int
    max_share: float  # largest move relative to the card's interval


def move_stats(
    cards: Sequence[Card], new_due: Dict[int, int]
) -> Tuple[Optional[MoveStats], Optional[MoveStats]]:
    """Statistics of the advanced cards and of the postponed cards (None if
    there are none). Wording is left to `i18n`."""

    def stats(moved: List[Card]) -> Optional[MoveStats]:
        if not moved:
            return None
        days = [abs(new_due[c.id] - c.due) for c in moved]
        return MoveStats(
            count=len(moved),
            mean_days=sum(days) / len(days),
            max_days=max(days),
            max_share=max(d / c.interval for d, c in zip(days, moved)),
        )

    return (
        stats([c for c in cards if new_due[c.id] < c.due]),
        stats([c for c in cards if new_due[c.id] > c.due]),
    )
