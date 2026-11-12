import itertools
import random
import unittest
from itertools import accumulate

from review_smoother.smoothing import (
    POSTPONE_BUDGET,
    POSTPONE_MARGIN,
    Card,
    InfeasibleCurve,
    assign,
    auto_curve,
    daily_counts,
    even_out,
    lookahead_end,
    smooth,
)


def relative_cost(cards, new_due):
    return sum((c.due - new_due[c.id]) / c.interval for c in cards)


def random_cards(rng, count, horizon):
    return [
        Card(id=i, due=rng.randint(1, horizon), interval=rng.randint(1, 120))
        for i in range(count)
    ]


class DailyCountsTest(unittest.TestCase):
    def test_counts_per_day(self):
        self.assertEqual(daily_counts([1, 1, 3], 4), [2, 0, 1, 0])

    def test_rejects_days_outside_window(self):
        with self.assertRaises(ValueError):
            daily_counts([0], 4)
        with self.assertRaises(ValueError):
            daily_counts([5], 4)


class AutoCurveTest(unittest.TestCase):
    def assert_valid_curve(self, counts, curve):
        self.assertEqual(len(curve), len(counts))
        self.assertEqual(sum(curve), sum(counts))
        self.assertTrue(all(a >= b for a, b in zip(curve, curve[1:])), curve)
        for planned, due in zip(accumulate(curve), accumulate(counts)):
            self.assertGreaterEqual(planned, due)

    def test_already_smooth_curve_is_kept(self):
        counts = [4] * 14 + [3] * 28 + [2] * 48
        self.assertEqual(auto_curve(counts), counts)

    def test_jagged_counts_become_a_staircase(self):
        counts = [3, 4, 4, 3, 3, 3, 3, 4, 4, 4, 3, 2, 2, 2, 3, 2]
        curve = auto_curve(counts)
        self.assert_valid_curve(counts, curve)
        self.assertEqual(curve, [4] * 5 + [3] * 7 + [2] * 4)

    def test_late_pile_is_spread_from_day_one(self):
        self.assertEqual(auto_curve([0, 0, 0, 0, 7]), [2, 2, 1, 1, 1])

    def test_early_spike_cannot_be_flattened_without_postponing(self):
        self.assertEqual(auto_curve([5, 0, 0, 1]), [5, 1, 0, 0])

    def test_sparse_deck_becomes_a_block_of_ones(self):
        self.assertEqual(auto_curve([0, 0, 0, 0, 0, 3]), [1, 1, 1, 0, 0, 0])

    def test_staircase_down_to_ones_then_zeros(self):
        counts = [0, 0, 0, 0, 8] + [0, 0, 0, 1] * 3
        self.assertEqual(auto_curve(counts), [2, 2, 2] + [1] * 5 + [0] * 9)

    def test_empty_window(self):
        self.assertEqual(auto_curve([0, 0, 0]), [0, 0, 0])

    def test_random_inputs_give_valid_curves(self):
        rng = random.Random(1)
        for _ in range(300):
            horizon = rng.randint(1, 90)
            counts = [rng.choice([0, 0, 1, 2, 3, 8]) for _ in range(horizon)]
            self.assert_valid_curve(counts, auto_curve(counts))


class AssignTest(unittest.TestCase):
    def assert_valid_assignment(self, cards, target, new_due):
        self.assertEqual(set(new_due), {c.id for c in cards})
        self.assertEqual(daily_counts(new_due.values(), len(target)), list(target))
        for card in cards:
            self.assertLessEqual(new_due[card.id], card.due, "card postponed")

    def test_already_matching_cards_do_not_move(self):
        cards = [Card(1, 1, 10), Card(2, 2, 10), Card(3, 3, 10)]
        self.assertEqual(assign(cards, [1, 1, 1]), {1: 1, 2: 2, 3: 3})

    def test_longest_interval_is_the_one_advanced(self):
        cards = [Card(1, 2, 5), Card(2, 2, 60)]
        self.assertEqual(assign(cards, [1, 1]), {1: 2, 2: 1})

    def test_target_requiring_postponement_is_rejected(self):
        cards = [Card(1, 1, 10), Card(2, 1, 10)]
        with self.assertRaises(InfeasibleCurve) as raised:
            assign(cards, [1, 1])
        # Day 2 has a slot that only a postponed day-1 card could fill.
        self.assertEqual(raised.exception.day, 2)

    def test_target_total_must_match_card_count(self):
        with self.assertRaises(ValueError):
            assign([Card(1, 1, 10)], [1, 1])

    def test_auto_curve_is_always_reachable(self):
        rng = random.Random(2)
        for _ in range(200):
            horizon = rng.randint(1, 90)
            cards = random_cards(rng, rng.randint(0, 300), horizon)
            target = auto_curve(daily_counts((c.due for c in cards), horizon))
            self.assert_valid_assignment(cards, target, assign(cards, target))

    def test_cost_is_minimal_against_brute_force(self):
        rng = random.Random(3)
        for _ in range(150):
            horizon = rng.randint(1, 5)
            cards = random_cards(rng, rng.randint(1, 6), horizon)
            target = auto_curve(daily_counts((c.due for c in cards), horizon))
            best = min(
                relative_cost(cards, dict(zip((c.id for c in cards), days)))
                for days in itertools.product(range(1, horizon + 1), repeat=len(cards))
                if all(d <= c.due for d, c in zip(days, cards))
                and daily_counts(days, horizon) == target
            )
            new_due = assign(cards, target)
            self.assert_valid_assignment(cards, target, new_due)
            self.assertAlmostEqual(relative_cost(cards, new_due), best)



def plateau_lengths(curve):
    lengths = {}
    for level in curve:
        lengths[level] = lengths.get(level, 0) + 1
    return lengths


class EvenOutTest(unittest.TestCase):
    def test_long_plateau_between_short_ones_is_split(self):
        # The author's example on Bepo::Caracteres.
        self.assertEqual(
            even_out([15, 14, 13, 12, 12, 12, 11, 10, 9]),
            [15, 14, 13, 13, 12, 11, 11, 10, 9],
        )

    def test_regular_staircase_is_kept(self):
        curve = [5, 5, 4, 4, 3, 3, 2, 2, 1, 1]
        self.assertEqual(even_out(curve), curve)

    def test_plateau_at_the_end_of_the_window_is_left_out(self):
        # 2 x 46 is much longer than 3 x 37, but it only ends because the
        # window does.
        curve = [4] * 5 + [3] * 37 + [2] * 46
        self.assertEqual(even_out(curve), curve)

    def test_jump_and_dip_are_evened_out(self):
        # The author's remarks on Bepo::Caracteres: 9 x 2 then 8 x 4 is a
        # jump, 4 x 6 between 5 x 7 and 3 x 9 a dip.
        def staircase(plateaus):
            return [level for level, days in plateaus for _ in range(days)]

        curve = staircase([(11, 2), (10, 1), (9, 2), (8, 4), (7, 5), (6, 7), (5, 7), (4, 6), (3, 9)])
        self.assertEqual(
            even_out(curve),
            staircase([(11, 2), (10, 2), (9, 2), (8, 3), (7, 5), (6, 6), (5, 7), (4, 7), (3, 9)]),
        )

    def test_long_tail_of_ones_gives_days_down_to_zero(self):
        # The author's request on Bepo::Caracteres: more days at 3 and 2,
        # fewer at 1, even if days at 0 are left at the end.
        curve = [4] * 6 + [3] * 7 + [2] * 7 + [1] * 32
        self.assertEqual(
            even_out(curve), [4] * 6 + [3] * 11 + [2] * 11 + [1] * 12 + [0] * 12
        )

    def test_same_when_the_curve_already_ends_with_zeros(self):
        curve = [3] * 2 + [2] * 20 + [1] * 30 + [0] * 4
        self.assertEqual(even_out(curve), [3] * 2 + [2] * 23 + [1] * 24 + [0] * 7)

    def test_two_plateaus_never_give_days_to_the_peak(self):
        # 2 x 40 and 1 x 40 are long, but giving days to the peak's 3 x 5
        # would advance cards to the busiest days.
        curve = [3] * 5 + [2] * 40 + [1] * 40
        self.assertEqual(even_out(curve), curve)

    def test_sparse_deck_of_ones_is_kept(self):
        # Nothing above the 1s: they are the peak.
        curve = [1] * 88 + [0] * 2
        self.assertEqual(even_out(curve), curve)

    def test_random_curves_only_move_cards_earlier(self):
        rng = random.Random(5)
        for _ in range(300):
            horizon = rng.randint(1, 90)
            counts = [rng.choice([0, 1, 2, 3, 5, 12]) for _ in range(horizon)]
            curve = auto_curve(counts)
            even = even_out(curve)
            self.assertEqual(sum(even), sum(curve))
            self.assertTrue(all(a >= b for a, b in zip(even, even[1:])), even)
            for evened, original in zip(accumulate(even), accumulate(curve)):
                self.assertGreaterEqual(evened, original)
            lengths = plateau_lengths(even)
            n = lambda level: lengths.get(level, 0)
            lowest = 1 if even[-1] <= 1 else even[-1] + 2
            for high in range(even[0] - 1, lowest - 1, -1):
                for low in range(high, lowest - 1, -1):
                    if low == high or high + 1 < even[0]:
                        dip = 2 if low == high else 0 if low == 1 else 1
                        self.assertFalse(
                            n(high) >= n(high + 1) + 2 and n(low) >= n(low - 1) + dip,
                            even,
                        )

def cards_from_counts(counts, interval):
    days = [day for day, n in enumerate(counts, start=1) for _ in range(n)]
    return [Card(id=i, due=day, interval=interval) for i, day in enumerate(days)]


class SmoothTest(unittest.TestCase):
    def postponed(self, cards, new_due):
        return [c for c in cards if new_due[c.id] > c.due]

    def test_without_postponing_it_only_advances(self):
        cards = cards_from_counts([3] * 6 + [4] + [3] * 13, interval=120)
        target, new_due = smooth(cards, 20, allow_postpone=False)
        self.assertEqual(target, auto_curve(daily_counts((c.due for c in cards), 20)))
        self.assertEqual(target[0], 4)
        self.assertEqual(self.postponed(cards, new_due), [])

    def test_one_postponed_card_removes_an_isolated_bump(self):
        # A single extra card on day 7 would otherwise lift tomorrow to 4. It
        # goes to the lighter day 13: 6 days later, within its 12-day margin.
        cards = cards_from_counts([3] * 6 + [4] + [3] * 5 + [2] + [3] * 7, interval=120)
        target, new_due = smooth(cards, 20)
        self.assertEqual(target, [3] * 20)
        self.assertEqual(daily_counts(new_due.values(), 20), target)
        postponed = self.postponed(cards, new_due)
        self.assertEqual([(c.due, new_due[c.id]) for c in postponed], [(7, 13)])

    def test_short_intervals_cannot_be_postponed(self):
        # 10% of a 9-day interval rounds down to 0 days of margin.
        cards = cards_from_counts([3] * 6 + [4] + [3] * 12 + [2], interval=9)
        target, new_due = smooth(cards, 20)
        self.assertEqual(target[0], 4)
        self.assertEqual(self.postponed(cards, new_due), [])

    def test_longest_interval_is_the_one_postponed(self):
        cards = [Card(1, 1, 50), Card(2, 1, 200), Card(3, 3, 50)]
        _, new_due = smooth(cards, 3)
        self.assertEqual(new_due, {1: 1, 2: 2, 3: 3})

    def test_postponing_stops_at_the_budget(self):
        # Lowering the 4s to 3s would need 5 postponed cards; the budget for
        # 50 cards is 1.
        cards = cards_from_counts([4] * 5 + [3] * 10, interval=300)
        target, new_due = smooth(cards, 15)
        self.assertEqual(target, [4] * 5 + [3] * 10)
        self.assertEqual(self.postponed(cards, new_due), [])

    def test_steady_slope_is_not_flattened_into_a_cliff(self):
        # Postponing 1 card (within budget) would lower the peak to
        # 29, 29, 29, 27...: a 2-card step on a curve that only ever drops by
        # 1. Postponing must not do that.
        counts = [30, 29, 28, 27, 26, 25, 24, 23, 22, 21]
        cards = cards_from_counts(counts, interval=300)
        target, new_due = smooth(cards, 10)
        self.assertEqual(target, counts)
        self.assertEqual(self.postponed(cards, new_due), [])

    def test_peak_is_not_lowered_into_a_long_plateau(self):
        # Postponing 1 card (within budget, no steeper step) would give
        # 4, 4, 4, 4, 4, 3, 2...: five days at the top, then one at 3.
        counts = [5, 4, 4, 4, 4, 2, 2, 2, 2, 1, 1]
        cards = cards_from_counts(counts, interval=300)
        target, new_due = smooth(cards, 11)
        self.assertEqual(target, [5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 1])
        self.assertEqual(self.postponed(cards, new_due), [])

    def test_random_decks_respect_margin_and_budget(self):
        rng = random.Random(4)
        for _ in range(200):
            horizon = rng.randint(1, 90)
            cards = random_cards(rng, rng.randint(0, 400), horizon)
            target, new_due = smooth(cards, horizon)
            self.assertEqual(daily_counts(new_due.values(), horizon), target)
            self.assertTrue(all(a >= b for a, b in zip(target, target[1:])), target)
            postponed = self.postponed(cards, new_due)
            self.assertLessEqual(len(postponed), max(1, int(len(cards) * POSTPONE_BUDGET)))
            for card in postponed:
                self.assertLessEqual(
                    new_due[card.id] - card.due, int(card.interval * POSTPONE_MARGIN)
                )

    def test_random_decks_with_cards_after_the_window(self):
        rng = random.Random(7)
        for _ in range(200):
            horizon = rng.randint(1, 90)
            cards = random_cards(rng, rng.randint(0, 400), lookahead_end(horizon))
            target, new_due = smooth(cards, horizon)
            window = [c for c in cards if c.due <= horizon]
            self.assertEqual(len(target), horizon)
            self.assertEqual(
                daily_counts((d for d in new_due.values() if d <= horizon), horizon),
                target,
            )
            self.assertGreaterEqual(sum(target), len(window))
            self.assertTrue(all(a >= b for a, b in zip(target, target[1:])), target)
            for card in cards:
                if card.due > horizon:
                    # Pulled into the window, or left where it was.
                    self.assertTrue(new_due[card.id] == card.due or new_due[card.id] <= horizon)
                else:
                    # Postponed cards stay in the window.
                    self.assertLessEqual(new_due[card.id], horizon)
            postponed = self.postponed(cards, new_due)
            self.assertLessEqual(len(postponed), max(1, int(len(window) * POSTPONE_BUDGET)))


class WindowEdgeTest(unittest.TestCase):
    def test_last_empty_days_are_filled_from_after_the_window(self):
        # One card a day for 88 days, nothing on days 89 and 90, then cards on
        # days 93 and 96: those two fill days 89 and 90.
        cards = cards_from_counts([1] * 88 + [0] * 4 + [1, 0, 0, 1], interval=300)
        target, new_due = smooth(cards, 90)
        self.assertEqual(target, [1] * 90)
        moved = sorted((c.due, new_due[c.id]) for c in cards if new_due[c.id] != c.due)
        self.assertEqual(moved, [(93, 90), (96, 89)])

    def test_same_on_a_shorter_window(self):
        # 30 days: cards up to day 37 are looked at; days 29 and 30 are filled
        # at the level of the cards due after the window.
        cards = cards_from_counts([2] * 28 + [0] * 2 + [2] * 7, interval=300)
        target, new_due = smooth(cards, 30)
        self.assertEqual(target, [2] * 30)
        self.assertEqual(sum(1 for c in cards if new_due[c.id] != c.due), 4)

    def test_cards_after_the_window_are_not_needed(self):
        # Already smooth up to the end: the cards after the window stay put.
        cards = cards_from_counts([2] * 20 + [1] * 5, interval=300)
        target, new_due = smooth(cards, 20)
        self.assertEqual(target, [2] * 20)
        self.assertTrue(all(new_due[c.id] == c.due for c in cards))


if __name__ == "__main__":
    unittest.main()
