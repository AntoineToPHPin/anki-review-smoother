import unittest
from datetime import date

from review_smoother import tracking
from review_smoother.i18n import Translator


class FieldTest(unittest.TestCase):
    def test_round_trip(self):
        data = tracking.history([
            tracking.table("Suivi 90 j.", ["Total", "Remarque"], [["2026-11-18", 12947, "a < b & « c »"]]),
        ])
        field = tracking.to_field(data)
        self.assertNotIn("<", field)
        self.assertEqual(tracking.from_field(field), data)

    def test_what_the_editor_may_add(self):
        self.assertEqual(tracking.from_field('<div>{"v":1,&nbsp;"tables":[]}</div><br>'), {"v": 1, "tables": []})
        self.assertEqual(tracking.from_field(""), {"v": 1, "tables": []})


class SpreadsheetTest(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(tracking.number(19.010000000000002), 19.01)
        self.assertIsInstance(tracking.number(55.0), int)
        self.assertEqual(tracking.number("?"), "?")
        self.assertIsNone(tracking.number(None))

    def test_one_row_a_day_up_to_the_last_day(self):
        rows = tracking.dated_rows([[1], [2], [3]], date(2026, 3, 1))
        self.assertEqual(rows, [["2026-02-27", 1], ["2026-02-28", 2], ["2026-03-01", 3]])


class TemplateTest(unittest.TestCase):
    def test_template(self):
        tr = Translator("fr")
        template = tracking.card_template("Historique", tracking.card_strings(tr))
        self.assertIn("{{Historique}}", template)
        self.assertNotIn("/*STRINGS*/", template)
        self.assertIn('"locale": "fr-FR"', template)
        self.assertIn(".rs-root", tracking.card_css())


if __name__ == "__main__":
    unittest.main()
