import itertools
import random
import unittest

from review_smoother.reposition import (
    NewCard,
    block_positions,
    block_start,
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


class BlockTest(unittest.TestCase):
    def test_block_starts(self):
        self.assertEqual(block_start(11, 100, 11), 11)
        self.assertEqual(block_start(100, 100, 11), 11)
        self.assertEqual(block_start(101, 100, 11), 101)
        self.assertEqual(block_start(259, 100, 11), 201)
        self.assertEqual(block_start(1122, 100, 11), 1101)

    def test_each_block_moves_up_to_its_start(self):
        # Paroles de chansons: songs at 14..16, 103..104, 201..202 and two
        # cards put at 1 and 2 to be learned next.
        cards = [
            NewCard(id=1, note=1, ord=0, position=14),
            NewCard(id=2, note=2, ord=0, position=15),
            NewCard(id=3, note=3, ord=0, position=16),
            NewCard(id=4, note=4, ord=0, position=104),
            NewCard(id=5, note=5, ord=0, position=103),
            NewCard(id=6, note=6, ord=0, position=201),
            NewCard(id=7, note=7, ord=0, position=202),
            NewCard(id=8, note=8, ord=0, position=1),
            NewCard(id=9, note=9, ord=0, position=2),
        ]
        self.assertEqual(
            block_positions(cards, 100, 11),
            {1: 11, 2: 12, 3: 13, 5: 101, 4: 102, 6: 201, 7: 202, 8: 1, 9: 2},
        )

    def test_a_song_longer_than_a_block_moves_as_a_whole(self):
        # Rap God: 122 cards from 1001; 5 learned, 117 left from 1006.
        cards = [NewCard(id=p, note=p, ord=0, position=p) for p in range(1006, 1123)]
        new = block_positions(cards, 100, 11)
        self.assertEqual([new[c.id] for c in cards], list(range(1001, 1118)))

    def test_a_long_song_among_the_first_blocks(self):
        # 150 cards from 101 (3 learned: 104..250), the next song at 301,
        # a song of 17 at 14 before it: nothing mixes.
        first = [NewCard(id=p, note=p, ord=0, position=p) for p in range(14, 31)]
        long = [NewCard(id=p, note=p, ord=0, position=p) for p in range(104, 251)]
        after = [NewCard(id=p, note=p, ord=0, position=p) for p in range(303, 330)]
        new = block_positions(first + long + after, 100, 11)
        self.assertEqual([new[c.id] for c in first], list(range(11, 28)))
        self.assertEqual([new[c.id] for c in long], list(range(101, 248)))
        self.assertEqual([new[c.id] for c in after], list(range(301, 328)))

    def test_a_long_song_from_the_first_block(self):
        # 120 cards from 11 spill to 130; learned 2: 13..130.
        cards = [NewCard(id=p, note=p, ord=0, position=p) for p in range(13, 131)]
        new = block_positions(cards, 100, 11)
        self.assertEqual([new[c.id] for c in cards], list(range(11, 129)))

    def test_a_gap_at_the_block_end_starts_a_new_song(self):
        cards = [
            NewCard(id=1, note=1, ord=0, position=198),
            NewCard(id=2, note=2, ord=0, position=203),
        ]
        self.assertEqual(block_positions(cards, 100, 11), {1: 101, 2: 201})

    def test_siblings_on_one_position_get_their_own(self):
        cards = [
            NewCard(id=1, note=1, ord=0, position=105),
            NewCard(id=2, note=1, ord=1, position=105),
        ]
        self.assertEqual(block_positions(cards, 100, 11), {1: 101, 2: 102})


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
