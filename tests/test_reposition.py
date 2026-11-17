import itertools
import random
import unittest

from review_smoother.reposition import (
    NewCard,
    current_order,
    positions,
    sibling_gap,
    shuffled,
)


def deck(notes):
    """One card per entry of `notes` (its note id), positions 1, 2..."""
    seen = {}
    cards = []
    for index, note in enumerate(notes):
        cards.append(NewCard(id=index + 1, note=note, ord=seen.get(note, 0), position=index + 1))
        seen[note] = seen.get(note, 0) + 1
    return cards


class SequentialTest(unittest.TestCase):
    def test_current_order_from_start_with_step(self):
        cards = [
            NewCard(id=1, note=1, ord=0, position=40),
            NewCard(id=2, note=2, ord=0, position=12),
            NewCard(id=3, note=3, ord=0, position=25),
        ]
        self.assertEqual(positions(current_order(cards), 1, 1), {2: 1, 3: 2, 1: 3})
        self.assertEqual(positions(current_order(cards), 11, 5), {2: 11, 3: 16, 1: 21})

    def test_siblings_get_their_own_position(self):
        # Anki's Reposition gives both cards of a note the same number.
        cards = [
            NewCard(id=1, note=1, ord=1, position=5),
            NewCard(id=2, note=1, ord=0, position=5),
            NewCard(id=3, note=2, ord=0, position=6),
        ]
        self.assertEqual(positions(current_order(cards)), {2: 1, 1: 2, 3: 3})


class ShuffleTest(unittest.TestCase):
    def test_a_permutation_of_the_cards(self):
        cards = deck([1, 1, 2, 3, 4, 4, 5])
        order = shuffled(cards, 3, random.Random(1))
        self.assertEqual(sorted(c.id for c in order), [c.id for c in cards])

    def test_bepo_siblings_are_introduced_on_different_days(self):
        # Bepo::Caracteres (2026-11-17): 16 new cards, 2 notes with two of
        # them, 6 new cards a day.
        cards = deck([1, 1, 2, 2] + list(range(3, 15)))
        for seed in range(50):
            order = shuffled(cards, 6, random.Random(seed))
            self.assertGreaterEqual(sibling_gap(order), 6)

    def test_really_shuffled(self):
        cards = deck([1, 1, 2, 2] + list(range(3, 15)))
        orders = {tuple(c.id for c in shuffled(cards, 6, random.Random(s))) for s in range(20)}
        self.assertEqual(len(orders), 20)
        # Siblings are not always put first.
        firsts = {shuffled(cards, 6, random.Random(s))[0].note for s in range(20)}
        self.assertGreater(len(firsts), 3)

    def test_as_far_apart_as_possible(self):
        # 3 cards of one note among 5: 2 positions apart at most.
        cards = deck([1, 1, 1, 2, 3])
        order = shuffled(cards, 6, random.Random(2))
        self.assertEqual(sibling_gap(order), 2)

    def test_best_gap_on_small_decks(self):
        rng = random.Random(7)
        for _ in range(300):
            size = rng.randint(2, 7)
            notes = [rng.randint(1, 4) for _ in range(size)]
            spacing = rng.randint(2, 5)
            cards = deck(notes)
            best = max(
                min(sibling_gap(p) or spacing, spacing)
                for p in itertools.permutations(cards)
            )
            got = sibling_gap(shuffled(cards, spacing, rng))
            self.assertEqual(min(got or spacing, spacing), best, notes)

    def test_without_siblings_a_plain_shuffle(self):
        cards = deck(list(range(1, 400)))
        order = shuffled(cards, 10, random.Random(3))
        self.assertIsNone(sibling_gap(order))
        self.assertEqual(len(order), len(cards))


if __name__ == "__main__":
    unittest.main()
