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
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class Card:
    id: int
    due: int  # days from today (1 = tomorrow)
    interval: int  # current interval, in days
    note: Optional[int] = None  # cards of the same note are siblings

    @property
    def note_key(self) -> object:
        """Same value for siblings; a card without a note has no sibling."""
        return self.note if self.note is not None else ("card", self.id)


# Days on which each note already has a card that smoothing does not move
# (another deck, after the cards looked at...): note id -> days from today.
Taken = Mapping[int, Set[int]]


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


def assign(
    cards: Sequence[Card], target: Sequence[int], taken: Optional[Taken] = None
) -> Dict[int, int]:
    """New due day for each card so that daily counts match `target` exactly.

    Cards are only ever advanced. Among valid assignments, this minimises the
    total relative advance, sum((due - new_due) / interval): advancing a card
    by a few days matters little when its interval is long, a lot when it is
    short. Days are filled from the last one backwards, each taking the
    available cards with the shortest intervals (the ones that are the most
    costly to advance).

    Siblings: a card is not moved to a day where a card of the same note is
    due (before smoothing, in `taken`, or already moved there), as long as
    another available card can take its place; otherwise it is, rather than
    failing. Cards that stay on their day are never moved for that, so
    siblings already due on the same day stay so.

    Raises InfeasibleCurve if the target would require postponing cards.
    """
    taken = taken or {}
    # Days each note has a card on: before smoothing, then where moved to.
    due_days: Dict[object, Set[int]] = {}
    for card in cards:
        due_days.setdefault(card.note_key, set()).add(card.due)
    moved_days: Dict[object, Set[int]] = {}

    def has_sibling_on(card: Card, day: int) -> bool:
        key = card.note_key
        return (
            day in due_days.get(key, ())
            or day in moved_days.get(key, ())
            or (card.note is not None and day in taken.get(card.note, ()))
        )

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
            heapq.heappush(available, (card.interval, card.due, card.id, card))
        chosen: List[Card] = []
        # Cards that would join a sibling on this day, in order of priority.
        set_aside: list = []
        while len(chosen) < target[day - 1] and available:
            entry = heapq.heappop(available)
            card = entry[-1]
            if card.due != day and has_sibling_on(card, day):
                set_aside.append(entry)
            else:
                chosen.append(card)
                if card.due != day:
                    moved_days.setdefault(card.note_key, set()).add(day)
        # Not enough other cards: siblings on the same day, rather than fail.
        while len(chosen) < target[day - 1] and set_aside:
            card = set_aside.pop(0)[-1]
            chosen.append(card)
            moved_days.setdefault(card.note_key, set()).add(day)
        if len(chosen) < target[day - 1]:
            raise InfeasibleCurve(day)
        for entry in set_aside:
            heapq.heappush(available, entry)
        for card in chosen:
            new_due[card.id] = day
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


# The curve is computed over the window plus this share of it, so that the end
# of the window does not drop just because the cards due right after it are
# left out: some of them are pulled into the window.
LOOKAHEAD = 0.25


def lookahead_end(horizon: int) -> int:
    """Last day of the cards that `smooth` may pull into the window."""
    return horizon + int(horizon * LOOKAHEAD)


def smooth(
    cards: Sequence[Card],
    horizon: int,
    allow_postpone: bool = True,
    taken: Optional[Taken] = None,
) -> Tuple[List[int], Dict[int, int]]:
    """Target curve over the window and new due day of every card.

    `cards` are the cards due from day 1 to `lookahead_end(horizon)`. The curve
    is computed over that longer period and only its first `horizon` days are
    applied: the cards it puts in the window are advanced into it, the others
    after the window keep their due day. So the end of the window holds what
    smoothing a longer period would give it, instead of dropping because the
    cards due right after it are left out.

    Cards are advanced only (see `auto_curve` and `assign`), unless
    `allow_postpone`: then the peak at the start of the curve is lowered one
    card a day at a time, by postponing cards within their margin, as long as
    that postpones no more cards than the budget, creates no steeper step
    than the advance-only curve has, and leaves no top plateau more than one
    day longer than the plateau below it (see `_top_plateau_too_long`).

    Those last two rules keep postponing for isolated bumps (4, 3, 3, 3...
    becomes 3, 3, 3, 3...) and away from steady slopes: capping 18, 17, 17,
    16, 15... would turn it into a plateau ending with a cliff (16 x 7 days,
    then 13), and capping 18, 17, 16, 16, 16, 14... into a long plateau
    (16 x 6 days, then 15, 14...).

    Postponing only concerns the cards of the window, and keeps them in it;
    the rules above look at the window part of the curves only.

    Finally, plateaus of the window are evened out (see `even_out`), and the
    cards are picked by `assign`, which keeps siblings apart: `taken` gives
    the days of the siblings outside `cards`.
    """
    end = lookahead_end(horizon)
    window = [c for c in cards if c.due <= horizon]
    advance_only = auto_curve(daily_counts((c.due for c in cards), end))
    target = advance_only
    shifted: Sequence[Card] = cards
    if allow_postpone:
        budget = max(1, int(len(window) * POSTPONE_BUDGET))
        steepest = _steepest_step(advance_only[:horizon])
        while target[0] > 1:
            postponed = _postpone_to_cap(window, target[0] - 1, horizon)
            if postponed is None or len(postponed) > budget:
                break
            candidate = [replace(c, due=postponed.get(c.id, c.due)) for c in cards]
            lowered = auto_curve(daily_counts((c.due for c in candidate), end))
            # Cards due after the window can hold the peak up (a pile right
            # after it): postponing then does not lower it.
            if lowered[0] >= target[0]:
                break
            if _steepest_step(lowered[:horizon]) > steepest or _top_plateau_too_long(
                lowered[:horizon]
            ):
                break
            shifted, target = candidate, lowered
    # Evening out only moves cards earlier, so the whole curve stays reachable.
    target = even_out(target[:horizon]) + target[horizon:]
    assigned = assign(shifted, target, taken)
    # Cards left after the window keep their due day.
    new_due = {
        c.id: assigned[c.id] if assigned[c.id] <= horizon else c.due for c in cards
    }
    return target[:horizon], new_due


def _steepest_step(curve: Sequence[int]) -> int:
    """Largest drop from one day to the next."""
    return max((a - b for a, b in zip(curve, curve[1:])), default=0)


def _top_plateau_too_long(curve: Sequence[int]) -> bool:
    """Whether the first plateau of the curve, as shown (after `even_out`),
    is more than one day longer than the next one.

    `even_out` never shortens the top plateau, so a peak lowered too far would
    stay a long block of days at the same level. As in `even_out`, the plateau
    at the level of the last day is no reference (its length only reflects
    where the window ends): if it is the top or the next one, any length goes.
    """
    shown = even_out(curve)
    if not shown:
        return False
    top = shown.count(shown[0])
    if top == len(shown) or shown[top] == shown[-1]:
        return False
    return top > shown.count(shown[top]) + 1


def even_out(curve: Sequence[int]) -> List[int]:
    """Make the staircase more regular by evening out plateau lengths.

    Going down the staircase, plateaus (the days at one level) should get
    longer gradually. A block of plateaus at consecutive levels gives one day
    to the level above it and one to the level below it (its first day goes
    up by one card, its last day down by one) when:
    - its top plateau is at least 2 days longer than the one above it, so
      that jump shrinks;
    - its bottom plateau is longer than the one below it (a dip, which then
      turns into a rise), or at least 2 days longer for a single plateau,
      which loses 2 days.
    Plateaus inside the block keep their length. Jumps are handled from the
    peak down; for each, the shortest block that can absorb it is used.

    Examples: 14, 13, 12, 12, 12, 11, 10 becomes 14, 13, 13, 12, 11, 11, 10
    (single plateau); in 10 x 1, 9 x 2, 8 x 4, 7 x 5, 6 x 7, 5 x 7, 4 x 6, the
    block from 8 to 5 takes a day from the jump between 9 and 8 and gives it
    to the dip at 4.

    When the curve ends at 1 or 0 cards a day, days at 0 are a level like the
    others, and the plateau of 1s also gives them a day while it is at least
    as long: they absorb the jumps that no dip can (the author prefers more
    days at 3 and 2 and fewer at 1, even if it leaves empty days at the end of
    the window). Otherwise the plateau at the level of the last day is left
    out, as a neighbour too: its length only reflects where the window ends.

    Each change moves one card earlier, so it never requires postponing
    anything; the total and the descending order are kept. A block of several
    plateaus never gives days to the peak's plateau: repeated, that would
    lengthen the peak a lot (4 x 5, 3 x 37, 2 x 46, 1 x 2 would reach 4 x 22),
    advancing cards to the busiest days. A single plateau still may, one day
    at a time (5, 4, 4, 4, 4, 3 becomes 5, 5, 4, 4, 3, 3).
    """
    result = list(curve)
    if not result:
        return result
    # Lowest level that may give days.
    lowest = 1 if result[-1] <= 1 else result[-1] + 2
    # Each change moves a card earlier, so this ends; the cap is a safeguard.
    for _ in range(sum(result) * len(result) + 1):
        lengths: Dict[int, int] = {}
        for level in result:
            lengths[level] = lengths.get(level, 0) + 1
        block = next(
            (
                (high, low)
                for high in range(result[0] - 1, lowest - 1, -1)
                for low in range(high, lowest - 1, -1)
                if (low == high or high + 1 < result[0])
                and lengths.get(high, 0) >= lengths.get(high + 1, 0) + 2
                and lengths.get(low, 0) >= lengths.get(low - 1, 0) + _dip(high, low)
            ),
            None,
        )
        if block is None:
            break
        high, low = block
        result[result.index(high)] += 1
        result[len(result) - 1 - result[::-1].index(low)] -= 1
    return result


def _dip(high: int, low: int) -> int:
    """How much longer than the plateau below it the bottom plateau of the
    block high..low must be for `even_out` to use that block."""
    if low == high:
        return 2  # a single plateau loses 2 days
    if low == 1:
        return 0  # days at 0 absorb what no dip can
    return 1


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
