import unittest
from string import Formatter

from review_smoother.i18n import NBSP, STRINGS, Translator
from review_smoother.smoothing import MoveStats


def placeholders(text):
    return {name for _, name, _, _ in Formatter().parse(text) if name}


class StringsTest(unittest.TestCase):
    def test_every_language_has_the_same_keys_and_placeholders(self):
        english = STRINGS["en"]
        for lang, strings in STRINGS.items():
            self.assertEqual(set(strings), set(english), lang)
            for key, text in strings.items():
                self.assertEqual(placeholders(text), placeholders(english[key]), (lang, key))


class TranslatorTest(unittest.TestCase):
    def test_language_comes_from_anki(self):
        self.assertEqual(Translator("fr_FR").lang, "fr")
        self.assertEqual(Translator("fr").lang, "fr")
        self.assertEqual(Translator("en_US").lang, "en")

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(Translator("de_DE").lang, "en")

    def test_plurals(self):
        fr, en = Translator("fr"), Translator("en")
        self.assertEqual(fr("card", count=0), "0 carte")
        self.assertEqual(fr("card", count=1), "1 carte")
        self.assertEqual(fr("card", count=2), "2 cartes")
        self.assertEqual(en("card", count=0), "0 cards")
        self.assertEqual(en("card", count=1), "1 card")

    def test_french_number_and_percent_typography(self):
        fr = Translator("fr")
        self.assertEqual(fr.number(14.25, 1), "14,2")
        self.assertEqual(fr.percent(0.07), f"7{NBSP}%")
        self.assertEqual(fr.percent(0.001), f"<{NBSP}1{NBSP}%")
        self.assertEqual(Translator("en").percent(0.001), "<1%")

    def test_describe_moves(self):
        advanced = MoveStats(count=41, mean_days=14.2, max_days=61, max_share=0.07)
        postponed = MoveStats(count=1, mean_days=5, max_days=5, max_share=0.04)
        self.assertEqual(
            Translator("fr").describe_moves(advanced, postponed),
            [
                "41 cartes avancées de 14,2 jours en moyenne "
                f"(au plus 61, soit au maximum 7{NBSP}% de l’intervalle).",
                f"1 carte reportée de 5 jours (4{NBSP}% de son intervalle).",
            ],
        )
        self.assertEqual(
            Translator("en").describe_moves(advanced, None),
            [
                "41 cards advanced by 14.2 days on average "
                "(max 61, at most 7% of the interval)."
            ],
        )

    def test_single_card_moved_by_one_day(self):
        one = MoveStats(count=1, mean_days=1, max_days=1, max_share=0.02)
        self.assertEqual(
            Translator("en").describe_moves(None, one),
            ["1 card postponed by 1 day (2% of its interval)."],
        )


if __name__ == "__main__":
    unittest.main()
