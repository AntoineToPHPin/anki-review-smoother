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


# Moves up to this share of a card's interval are accepted when that moves
# fewer cards (see `fewer_moves`); below it, as few cards as possible move.
MOVE_CEILING = 0.05


def lookahead_end(horizon: int) -> int:
    """Last day of the cards that shape the end of the window: `smooth`
    computes its curve up to there; and the last day
    a card may be taken from (or put on) when no day after the window is
    above (or below) its reference (see `_outside_target`)."""
    return horizon + int(horizon * LOOKAHEAD)


# Cards due up to this share of the window after it are looked at, to find
# the days that hold more (or fewer) cards than their reference: the cards
# the window lacks are taken from them (see `_outside_target`).
OUTSIDE = 1.0


def outside_end(horizon: int) -> int:
    """Last day of the cards to give the smoothing functions."""
    return max(lookahead_end(horizon), horizon + int(horizon * OUTSIDE))


def _outside_target(
    cards: Sequence[Card],
    horizon: int,
    window_target: Sequence[int],
    curve: Optional[Sequence[int]] = None,
) -> Tuple[List[int], int]:
    """Target over every day of `cards`, the window's then the days after it,
    and the cards the window lacks that no day could give.

    Taking a card from the day right after the window would leave a gap that
    shows in the window the next day (that day becomes its last one); putting
    one there, a peak. So the days after the window keep their cards, except
    those **above their reference**: the window's missing cards are taken from
    them, the nearest first, down to the reference; cards the window has too
    many of go to the nearest days **below** it, up to it. The reference is
    the custom curve, carried on after the window, or else the closest
    non-increasing curve to the days after the window (`levels`).

    Only if that is not enough, the rest is taken (or put) as far as possible
    within `lookahead_end`: one card a day, from that last day backwards.
    The cards then reach the window in hops (see `_few_moves`), each day on
    the way keeping its count.
    """
    end = max([lookahead_end(horizon), horizon + 1] + [c.due for c in cards])
    counts = [0] * (end - horizon)
    for card in cards:
        if card.due > horizon:
            counts[card.due - horizon - 1] += 1
    if curve is None:
        reference = levels(counts)
    else:
        reference = [curve[d - 1] if d <= len(curve) else 0 for d in range(horizon + 1, end + 1)]
    need = sum(window_target) - sum(1 for c in cards if c.due <= horizon)
    for i in range(len(counts)):
        if need > 0 and counts[i] > reference[i]:
            n = min(need, counts[i] - reference[i])
        elif need < 0 and counts[i] < reference[i]:
            n = -min(-need, reference[i] - counts[i])
        else:
            continue
        counts[i] -= n
        need -= n
    # As far as possible: from the last day of the lookahead backwards.
    farthest_first = range(max(1, min(lookahead_end(horizon) - horizon, len(counts))) - 1, -1, -1)
    while need > 0 and any(counts[i] > 0 for i in farthest_first):
        for i in farthest_first:
            if need > 0 and counts[i] > 0:
                counts[i] -= 1
                need -= 1
    while need < 0:
        for i in farthest_first:
            if need < 0:
                counts[i] += 1
                need += 1
    return list(window_target) + counts, need


def smooth(
    cards: Sequence[Card],
    horizon: int,
    allow_postpone: bool = True,
    taken: Optional[Taken] = None,
    ceiling: float = MOVE_CEILING,
) -> Tuple[List[int], Dict[int, int]]:
    """Target curve over the window and new due day of every card.

    `cards` are the cards due from day 1 to `outside_end(horizon)`. The curve
    is computed over the cards due up to `lookahead_end(horizon)` and only its
    first `horizon` days are applied, so the end of the window holds what
    smoothing a longer period would give it, instead of dropping because the
    cards due right after it are left out. The cards it pulls into the window
    come from days after it that have cards to spare (see `_outside_target`).

    The curve is the most regular staircase (see `regular_staircase`) holding
    the window's cards plus those `auto_curve` pulls into it.

    Cards are advanced only, unless `allow_postpone`: then the peak at the
    start of `auto_curve`'s curve is lowered one card a day at a time, by
    postponing cards within their margin, as long as that postpones no more
    cards than the budget and creates no steeper step than the advance-only
    curve has. That keeps postponing for isolated bumps (4, 3, 3, 3...
    becomes 3, 3, 3, 3...) and away from steady slopes: capping 18, 17, 17,
    16, 15... would turn it into a plateau ending with a cliff (16 x 7 days,
    then 13). Postponing only concerns the cards of the window, and keeps
    them in it; the regular staircase is then built on the shifted cards.

    The cards are picked by `assign_in_short_hops` (the smallest largest
    advance relative to the interval), then `fewer_moves` (as few cards as
    possible within the larger of that and `ceiling`), which keep siblings
    apart: `taken` gives the days of the siblings outside `cards`.
    """
    end = lookahead_end(horizon)
    window = [c for c in cards if c.due <= horizon]

    def curve_of(some: Sequence[Card]) -> List[int]:
        return auto_curve(daily_counts((c.due for c in some if c.due <= end), end))

    advance_only = curve_of(cards)
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
            lowered = curve_of(candidate)
            # Cards due after the window can hold the peak up (a pile right
            # after it): postponing then does not lower it.
            if lowered[0] >= target[0]:
                break
            if _steepest_step(lowered[:horizon]) > steepest:
                break
            shifted, target = candidate, lowered
    total = sum(target[:horizon])
    due = daily_counts((c.due for c in shifted if c.due <= horizon), horizon)
    target = regular_staircase(due, total)
    if shifted is not cards:
        # Postponing is only worth it if the regular staircase starts lower.
        due = daily_counts((c.due for c in window), horizon)
        unshifted = regular_staircase(due, total)
        if target[0] >= unshifted[0]:
            shifted, target = cards, unshifted
    # The cards pulled into the window come from days after it that have
    # cards to spare (see `_outside_target`).
    full, _ = _outside_target(shifted, horizon, target)
    assigned = assign_in_short_hops(shifted, full, taken)
    # Postponed cards start from their new day; their total move counts.
    few = fewer_moves(shifted, full, assigned, False, taken, ceiling)
    return target, few


def levels(counts: Sequence[int]) -> List[int]:
    """Level of each day: the closest non-increasing curve to `counts` (least
    squares, by pooling adjacent days that rise), rounded to whole cards.

    A rise is pooled with what comes before it until the curve no longer
    rises: 1, 1, 0, 3 gives 1.25 for each of those days. So an isolated empty
    day among days at 1 is at level 1, and a pile after it does not lift the
    days before it much."""
    blocks: List[List[int]] = []  # [cards, days]
    for count in counts:
        blocks.append([count, 1])
        # Pool while the previous block's average is below this one's.
        while len(blocks) >= 2 and blocks[-2][0] * blocks[-1][1] < blocks[-1][0] * blocks[-2][1]:
            cards, days = blocks.pop()
            blocks[-1][0] += cards
            blocks[-1][1] += days
    result: List[int] = []
    for cards, days in blocks:
        # Rounded half up: 1.5 cards a day is level 2.
        result += [math.floor(Fraction(cards, days) + Fraction(1, 2))] * days
    return result


def largest_share(cards: Sequence[Card], new_due: Mapping[int, int]) -> float:
    """Largest move (advance or postponement) relative to the interval."""
    return max(
        (abs(new_due[c.id] - c.due) / max(c.interval, 1) for c in cards),
        default=0.0,
    )


def _moved(cards: Sequence[Card], new_due: Mapping[int, int]) -> int:
    return sum(1 for c in cards if new_due[c.id] != c.due)


def fewer_moves(
    cards: Sequence[Card],
    window_target: Sequence[int],
    baseline: Dict[int, int],
    both_ways: bool,
    taken: Optional[Taken] = None,
    ceiling: float = MOVE_CEILING,
) -> Dict[int, int]:
    """The compromise between few cards moved and short moves.

    `window_target` covers every day of `cards`, those after the window too
    (see `_outside_target`). `baseline` makes them hold it with the smallest
    largest move (short hops, many cards: see `assign_in_short_hops`). This
    allows each card to move by up to the larger of that move and `ceiling`
    (relative to its interval) and, within that, moves as few cards as
    possible (see `_few_moves`); the baseline's own limit is tried too (often
    the same largest move with fewer, longer hops). The baseline stays if
    neither moves fewer cards.

    `both_ways`: cards may be postponed too (`follow_curve`).
    """
    shortest = largest_share(cards, baseline)
    best = baseline
    # The greedy pass is not monotonic: longer hops allowed can mean more
    # cards moved. Both limits are tried; the fewest cards moved wins.
    for share in sorted({shortest, max(shortest, ceiling)}):
        few = _few_moves(cards, window_target, share, both_ways, taken)
        if few is not None and _moved(cards, few) < _moved(cards, best):
            best = few
    return best


def _few_moves(
    cards: Sequence[Card],
    target: Sequence[int],
    share: float,
    both_ways: bool,
    taken: Optional[Taken] = None,
) -> Optional[Dict[int, int]]:
    """Days 1..len(target) holding exactly `target` cards, each card moving
    by at most `share` of its interval, with few cards moved; None if this
    greedy pass fails.

    Days are filled from the first one. Each keeps its own cards first (the
    least movable ones, if it has too many). A day short of cards then takes,
    in this order, cards that have to move anyway: left over from earlier
    days (postponed, `both_ways` only), from later days holding more than
    their target, or due after the window when the window needs some (the
    nearest first); otherwise the **farthest** card it may take from a later
    day of the window, which leaves that day short in turn, so that a gap is
    carried to the cards that have to move in as few hops as the share allows.
    Siblings are kept apart while another card can come.
    """
    taken = taken or {}
    horizon = len(target)
    reach = {c.id: math.floor(share * max(c.interval, 1) + 1e-9) for c in cards}
    farthest = max(reach.values(), default=0)
    own: List[List[Card]] = [[] for _ in range(horizon + 1)]
    outside: List[Card] = []
    for card in cards:
        (own[card.due] if card.due <= horizon else outside).append(card)
    outside.sort(key=lambda c: (c.due, c.id))
    pulls_left = max(0, sum(target) - sum(len(day) for day in own))
    note_days: Dict[object, Set[int]] = {}
    for card in cards:
        note_days.setdefault(card.note_key, set()).add(card.due)

    def free(card: Card, day: int, siblings_ok: bool) -> bool:
        if siblings_ok:
            return True
        return day not in note_days.get(card.note_key, ()) and not (
            card.note is not None and day in taken.get(card.note, ())
        )

    def from_day(source: int, day: int, siblings_ok: bool) -> Optional[Card]:
        """The most movable card of `source` that may go to `day`."""
        fits = [
            c
            for c in own[source]
            if reach[c.id] >= abs(source - day) and free(c, day, siblings_ok)
        ]
        return max(fits, key=lambda c: (reach[c.id], c.id), default=None)

    new_due: Dict[int, int] = {}
    waiting: List[Card] = []

    def pick(day: int, siblings_ok: bool) -> Optional[Card]:
        # Left over from earlier days: soonest deadline first.
        fits = [
            c
            for c in waiting
            if c.due + reach[c.id] >= day and free(c, day, siblings_ok)
        ]
        if fits:
            card = min(fits, key=lambda c: (c.due + reach[c.id], c.id))
            waiting.remove(card)
            return card
        # Cards that have to move: the nearest.
        last = min(horizon, day + farthest)
        for source in range(day + 1, last + 1):
            if len(own[source]) > target[source - 1]:
                card = from_day(source, day, siblings_ok)
                if card is not None:
                    own[source].remove(card)
                    return card
        nonlocal pulls_left
        if pulls_left > 0:
            for card in outside:
                if card.due - day > farthest:
                    break
                if card.due - reach[card.id] <= day and free(card, day, siblings_ok):
                    outside.remove(card)
                    pulls_left -= 1
                    return card
        # Otherwise the farthest card of the window this day may take, but not
        # past the first day with cards to spare: the gap left behind is
        # carried towards it, not beyond it, where nothing would fill it.
        spare_day = next(
            (s for s in range(day + 1, horizon + 1) if len(own[s]) > target[s - 1]),
            None,
        )
        if spare_day is not None:
            last = min(last, spare_day)
        for source in range(last, day, -1):
            card = from_day(source, day, siblings_ok)
            if card is not None:
                own[source].remove(card)
                return card
        return None

    for day in range(1, horizon + 1):
        need = target[day - 1]
        mine = sorted(own[day], key=lambda c: (reach[c.id], c.id))
        own[day] = []
        for card in mine[:need]:
            new_due[card.id] = day
        extra = mine[need:]
        if extra:
            if not both_ways:
                return None
            waiting.extend(extra)
        for _ in range(need - len(mine[:need])):
            card = pick(day, False) or pick(day, True)
            if card is None:
                return None
            new_due[card.id] = day
            note_days.setdefault(card.note_key, set()).add(day)
        # A card left waiting past its last allowed day would move too far.
        if any(c.due + reach[c.id] <= day for c in waiting):
            return None
    for card in waiting:
        new_due[card.id] = horizon + 1
    for card in outside:
        new_due[card.id] = card.due
    return new_due


def assign_in_short_hops(
    cards: Sequence[Card], target: Sequence[int], taken: Optional[Taken] = None
) -> Dict[int, int]:
    """New due day for each card so that daily counts match `target` exactly,
    advancing cards only, with the **smallest largest advance relative to the
    interval**.

    Rather than one card advanced far (day 90 to day 4), a chain of short
    hops: day 5 to day 4, day 6 to day 5... day 90 to day 89. More cards move,
    each by a small share of its interval. (`assign` minimises the sum of the
    relative advances instead, which favours the one long hop of the card
    with the longest interval.)

    The smallest share is searched by bisection: with a share s, each card may
    advance by at most s times its interval, and days are filled from the
    first one, each taking the cards it may take that are due the soonest
    (they have the least room left), its own cards first. A card is not moved
    to a day where a sibling is (see `assign`), even if that takes a larger
    share; only if the curve cannot be reached that way at all are siblings
    ignored.
    """
    taken = taken or {}
    if sum(target) != len(cards):
        raise ValueError(
            f"Target curve holds {sum(target)} cards, not {len(cards)}."
        )
    due_days: Dict[object, Set[int]] = {}
    for card in cards:
        due_days.setdefault(card.note_key, set()).add(card.due)

    def attempt(share: float, siblings: bool) -> Optional[Dict[int, int]]:
        opening: Dict[int, List[Card]] = {}
        for card in cards:
            earliest = max(1, card.due - math.floor(share * max(card.interval, 1) + 1e-9))
            opening.setdefault(earliest, []).append(card)
        moved_days: Dict[object, Set[int]] = {}
        available: list = []
        new_due: Dict[int, int] = {}
        for day in range(1, len(target) + 1):
            for card in opening.get(day, ()):
                # Due soonest first; then the longest interval, cheapest to move.
                heapq.heappush(available, (card.due, -card.interval, card.id, card))
            chosen: List[Card] = []
            set_aside: list = []
            while len(chosen) < target[day - 1] and available:
                entry = heapq.heappop(available)
                card = entry[-1]
                key = card.note_key
                if (
                    siblings
                    and card.due != day
                    and (
                        day in due_days.get(key, ())
                        or day in moved_days.get(key, ())
                        or (card.note is not None and day in taken.get(card.note, ()))
                    )
                ):
                    set_aside.append(entry)
                else:
                    chosen.append(card)
            # No sibling as a last resort here: a larger share is tried
            # instead, which lets other cards come.
            if len(chosen) < target[day - 1]:
                return None
            for entry in set_aside:
                heapq.heappush(available, entry)
            for card in chosen:
                new_due[card.id] = day
                if card.due != day:
                    moved_days.setdefault(card.note_key, set()).add(day)
            # A card still waiting past its due day would have to be postponed.
            if available and available[0][0] <= day:
                return None
        return new_due

    # Every card may go as far as day 1: reachable if advancing alone is.
    top = max((c.due - 1) / max(c.interval, 1) for c in cards) if cards else 0.0
    for siblings in (True, False):
        best = attempt(top, siblings)
        if best is None:
            continue
        low, high = 0.0, top
        for _ in range(40):
            middle = (low + high) / 2
            found = attempt(middle, siblings)
            if found is None:
                low = middle
            else:
                high, best = middle, found
        return best
    raise InfeasibleCurve(1)


def _steepest_step(curve: Sequence[int]) -> int:
    """Largest drop from one day to the next."""
    return max((a - b for a, b in zip(curve, curve[1:])), default=0)


def regular_staircase(due: Sequence[int], total: int) -> List[int]:
    """The most regular staircase holding `total` cards over the days of
    `due` (cards due on days 1, 2...), reachable by advancing cards only.

    Regular (the author's rule, 2026-11-16): going down, each plateau (days
    at one level) lasts **at least as long as the one above it**, and the
    curve goes down one card at a time. Two exceptions: the last plateau,
    cut by the end of the window, and the 0s, may be of any length; and
    between plateaus of one day (a steep start, 55, 51, 48...), the curve may
    go down by more than one card, by never more than the step before (6, 4,
    4 is a cliff: not allowed).
    Reachable: on every day, the cards scheduled up to it are at least the
    cards due up to it (`total` may be more: cards pulled from after the
    window).

    Among those staircases, J1 included, the one that **advances cards the
    least in total** (the sum, over the days, of the cards scheduled up to
    that day beyond those due; that is the sum of every card's advance in
    days). So the first days rise when that spares longer advances later:
    Bepo::Caracteres over 90 days, 16 x 3, 15 x 5, 14 x 4, 13 x 1, 12 x 2...
    once evened out, becomes 19, 18, 17, 16 x 2... 11 x 2, 10 x 3, 9 x 4...,
    with 149 days of advance instead of 592.

    A* search, day by day. A state is the day, the level, the days spent at
    it, the days it must still last, the largest next step and the cards
    scheduled so far. Pruned: states dominated by another one on the same
    day, level and cards (a shorter plateau, no longer to wait, no more
    advance), states that cannot keep up with the cards due without going
    above their level, and states whose fastest descent already holds too
    many cards. The bound: the cheapest curve of whole cards, never
    increasing, above what is due (the least concave majorant of the due
    counts from the state, rounded down and its daily counts sorted, as in
    `auto_curve`), shape rule left out.
    """
    days = len(due)
    if days == 0:
        return []
    if total == 0:
        return [0] * days
    due_by = [0] + list(accumulate(due))
    if total < due_by[days]:
        raise ValueError(f"{total} cards, fewer than the {due_by[days]} due.")
    points = [(day, due_by[day]) for day in range(days + 1)]
    points[days] = (days, total)

    bounds: Dict[Tuple[int, int], int] = {}

    def bound(day: int, cards: int) -> int:
        """Advance of the days after `day`, at least."""
        value = bounds.get((day, cards))
        if value is None:
            hull = _upper_hull([(day, cards)] + points[day + 1:])
            counts: List[int] = []
            for (x1, y1), (x2, y2) in zip(hull, hull[1:]):
                low, high = divmod(y2 - y1, x2 - x1)
                counts += [low + 1] * high + [low] * (x2 - x1 - high)
            counts.sort(reverse=True)
            value, scheduled = 0, cards
            for later, count in zip(range(day + 1, days + 1), counts):
                scheduled += count
                value += scheduled - due_by[later]
            bounds[(day, cards)] = value
        return value

    lowest: Dict[Tuple[int, int], int] = {}

    def keeps_up(day: int, level: int, cards: int) -> bool:
        """Whether a curve never above `level` from now can keep up with
        the cards due and reach the total."""
        need = lowest.get((day, level))
        if need is None:
            need = max(due_by[later] - level * (later - day) for later in range(day, days + 1))
            need = max(need, total - level * (days - day))
            lowest[(day, level)] = need
        return cards >= need

    def fastest(day: int, level: int, wait: int, step: int, length: int, cards: int) -> int:
        """Cards over the window if the curve goes down as fast as allowed:
        `wait` more days at `level`, then down by `step` every `length` days."""
        while day < days and level > 0:
            if wait == 0:
                level = max(0, level - step)
                wait = length
                continue
            n = min(wait, days - day)
            cards += level * n
            day += n
            wait -= n
        return cards

    unlimited = total + 1
    # Node: (day, level, run, wait, step_cap, cards).
    Node = Tuple[int, int, int, int, int, int]
    fronts: Dict[Tuple[int, int, int, int], List[Tuple[int, int, int]]] = {}
    parents: Dict[Tuple[Node, int], Optional[Tuple[Node, int]]] = {}
    heap: list = []
    order = 0

    def push(node: Node, advance: int, parent: Optional[Tuple[Node, int]]) -> None:
        nonlocal order
        day, level, run, wait, cap, cards = node
        key = (day, level, cap, cards)
        front = fronts.setdefault(key, [])
        if any(r <= run and w <= wait and a <= advance for r, w, a in front):
            return
        if not keeps_up(day, level, cards):
            return
        if level > 0:
            step = cap if run == 1 and cap > 1 else 1
            length = 1 if step > 1 else run + wait
            if fastest(day, level, wait, step, length, cards) > total:
                return
        front[:] = [
            (r, w, a) for r, w, a in front if not (run <= r and wait <= w and advance <= a)
        ]
        front.append((run, wait, advance))
        parents[(node, advance)] = parent
        order += 1
        heapq.heappush(heap, (advance + bound(day, cards), advance, order, node))

    for top in range(max(1, due_by[1]), total + 1):
        push((1, top, 1, 0, unlimited, top), top - due_by[1], None)

    while heap:
        _, advance, _, node = heapq.heappop(heap)
        day, level, run, wait, cap, cards = node
        if (run, wait, advance) not in fronts.get((day, level, cap, cards), ()):
            continue  # dominated since it was pushed
        if day == days:
            if cards != total:
                continue
            curve: List[int] = []
            entry: Optional[Tuple[Node, int]] = (node, advance)
            while entry is not None:
                curve.append(entry[0][1])
                entry = parents[entry]
            return curve[::-1]
        here = (node, advance)
        # One more day at this level (after a day, steps of one card); not
        # after a step of more than one card, which only joins one-day
        # plateaus.
        more = cards + level
        stretchable = level == 0 or cap <= 1 or cap == unlimited
        if stretchable and due_by[day + 1] <= more <= total:
            if level == 0:
                push((day + 1, 0, 0, 0, 0, more), advance + more - due_by[day + 1], here)
            else:
                push(
                    (day + 1, level, run + 1, max(0, wait - 1), 1, more),
                    advance + more - due_by[day + 1],
                    here,
                )
        # Down, once the plateau is long enough; the next one lasts at least
        # as long.
        if wait == 0 and level > 0:
            for drop in range(1, min(level, cap if run == 1 else 1) + 1):
                below = level - drop
                more = cards + below
                if not due_by[day + 1] <= more <= total:
                    continue
                if below == 0:
                    if more == total:
                        push((day + 1, 0, 0, 0, 0, more), advance + more - due_by[day + 1], here)
                else:
                    push(
                        (day + 1, below, 1, run - 1, drop, more),
                        advance + more - due_by[day + 1],
                        here,
                    )
    raise ValueError("No regular staircase reaches the total.")  # cannot happen


@dataclass(frozen=True)
class CurveSettings:
    """A custom curve, as in the author's spreadsheet: day 1 holds `tomorrow`
    cards, day 2 `drop_day2` fewer, day 3 `drop_day3` fewer again; from there
    the curve decays exponentially (Ebbinghaus's forgetting curve,
    e^(-t/strength)) towards `floor`, the long-term reviews, reached by day
    90; after day 90 it goes down in a straight line, by `slope` cards a day.
    """

    tomorrow: int
    drop_day2: int
    drop_day3: int
    floor: int
    strength: float
    slope: float = 0.0


# Last day of the exponential part; the straight line starts there.
EXPONENTIAL_DAYS = 90


def custom_curve(settings: CurveSettings, days: int) -> List[int]:
    """Cards wanted on each of days 1..`days`, with the spreadsheet's
    formulas:
    - day 1: tomorrow; day 2: tomorrow - drop_day2;
    - days 3 to 90: floor + rounded down((tomorrow - drop_day2 - drop_day3 -
      floor) x e^(-(day - 3) / strength)), so day 3 is tomorrow - drop_day2 -
      drop_day3;
    - after day 90: floor - slope x (day - 90), rounded to the nearest.
    Never below 0 cards.
    """
    s = settings
    above_floor = s.tomorrow - s.drop_day2 - s.drop_day3 - s.floor
    curve = []
    for day in range(1, days + 1):
        if day == 1:
            value = s.tomorrow
        elif day == 2:
            value = s.tomorrow - s.drop_day2
        elif day <= EXPONENTIAL_DAYS:
            value = s.floor + math.floor(
                above_floor * math.exp(-(day - 3) / max(s.strength, 1e-9))
            )
        else:
            # Half up, like the spreadsheet's ROUND on positive values.
            value = math.floor(s.floor - s.slope * (day - EXPONENTIAL_DAYS) + 0.5)
        curve.append(max(0, value))
    return curve


def follow_curve(
    cards: Sequence[Card],
    horizon: int,
    curve: Sequence[int],
    taken: Optional[Taken] = None,
    ceiling: float = MOVE_CEILING,
) -> Tuple[List[int], Dict[int, int]]:
    """Daily counts over the window and new due day of every card, following
    a given curve (see `custom_curve`) exactly: the window holds `curve[day]`
    cards on each day.

    `cards` are the cards due from day 1 to `outside_end(horizon)`, and
    `curve` should go as far, to compare the days after the window to it.
    Cards are advanced where the curve wants more than is due and postponed
    where it wants less. Cards the window lacks come from the days after it
    above the curve, the ones it has too many of go to the days below it
    (see `_outside_target`). If there are not enough cards for the whole
    curve, its last days are left short.

    Cards are picked as in `assign_in_short_hops` (the smallest largest move,
    advance or postponement, relative to the interval, in short hops), then
    `fewer_moves` with `ceiling`; siblings kept apart.
    """
    target = list(curve[:horizon]) + [0] * (horizon - len(curve))
    full, missing = _outside_target(cards, horizon, target, curve)
    # Not enough cards: the end of the window stays below the curve.
    for index in range(horizon - 1, -1, -1):
        if missing <= 0:
            break
        cut = min(missing, full[index])
        full[index] -= cut
        missing -= cut
    assigned = assign_both_ways(cards, full, taken)
    few = fewer_moves(cards, full, assigned, True, taken, ceiling)
    return full[:horizon], few


def assign_both_ways(
    cards: Sequence[Card], target: Sequence[int], taken: Optional[Taken] = None
) -> Dict[int, int]:
    """New due day for each card so that days 1..len(target) hold exactly
    `target` cards, with the smallest largest move relative to the interval;
    cards may be advanced or postponed. Cards not needed in the window stay
    where they are if due after it, or go to the day right after it.

    As in `assign_in_short_hops`, the share s is searched by bisection: each
    card may move by at most s times its interval either way; days are filled
    from the first one, each taking the cards it may take whose last allowed
    day comes first. Siblings are kept apart, unless the curve cannot be
    reached that way at all.
    """
    taken = taken or {}
    horizon = len(target)
    if sum(target) > len(cards):
        raise ValueError(f"Target holds {sum(target)} cards, only {len(cards)} given.")
    due_days: Dict[object, Set[int]] = {}
    for card in cards:
        due_days.setdefault(card.note_key, set()).add(card.due)

    def attempt(share: float, siblings: bool) -> Optional[Dict[int, int]]:
        opening: Dict[int, List[Tuple[Card, int]]] = {}
        for card in cards:
            reach = math.floor(share * max(card.interval, 1) + 1e-9)
            earliest = max(1, card.due - reach)
            if earliest <= horizon:
                opening.setdefault(earliest, []).append((card, card.due + reach))
        moved_days: Dict[object, Set[int]] = {}
        available: list = []
        new_due: Dict[int, int] = {}
        for day in range(1, horizon + 1):
            for card, latest in opening.get(day, ()):
                heapq.heappush(
                    available, (latest, card.due, -card.interval, card.id, card)
                )
            chosen: List[Card] = []
            set_aside: list = []
            while len(chosen) < target[day - 1] and available:
                entry = heapq.heappop(available)
                card = entry[-1]
                key = card.note_key
                if (
                    siblings
                    and card.due != day
                    and (
                        day in due_days.get(key, ())
                        or day in moved_days.get(key, ())
                        or (card.note is not None and day in taken.get(card.note, ()))
                    )
                ):
                    set_aside.append(entry)
                else:
                    chosen.append(card)
            if len(chosen) < target[day - 1]:
                return None
            for entry in set_aside:
                heapq.heappush(available, entry)
            for card in chosen:
                new_due[card.id] = day
                if card.due != day:
                    moved_days.setdefault(card.note_key, set()).add(day)
            # A card left waiting past its last allowed day would move too far.
            if available and available[0][0] <= day:
                return None
        # Left over: due after the window, they stay; due in it, they go to
        # the day right after it.
        for card in cards:
            if card.id not in new_due:
                new_due[card.id] = max(card.due, horizon + 1)
        return new_due

    top = max(
        (max(c.due - 1, horizon + 1 - c.due) / max(c.interval, 1) for c in cards),
        default=0.0,
    )
    for siblings in (True, False):
        best = attempt(top, siblings)
        if best is None:
            continue
        low, high = 0.0, top
        for _ in range(40):
            middle = (low + high) / 2
            found = attempt(middle, siblings)
            if found is None:
                low = middle
            else:
                high, best = middle, found
        return best
    raise InfeasibleCurve(1)


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
