import itertools
import random
import unittest
from itertools import accumulate

from review_smoother.smoothing import (
    Card,
    InfeasibleCurve,
    assign,
    auto_curve,
    daily_counts,
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


if __name__ == "__main__":
    unittest.main()
