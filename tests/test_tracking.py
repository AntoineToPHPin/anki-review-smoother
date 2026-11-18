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


class RecordTest(unittest.TestCase):
    """The author's tracking tab once reduced to the settings (2026-11-18)."""

    def setUp(self):
        from review_smoother.smoothing import CurveSettings

        self.data = tracking.history([
            tracking.table(
                "Suivi",
                ["Cartes demain (J1)", "Écart entre J1 et J2", "Écart entre J2 et J3",
                 "Cartes à J90", "Force de la mémoire", "Pente après J90 (× 10 000)",
                 "Remarque"],
                [["2026-11-17", 55, 4, 3, 13, 19.01, 194, None]],
            ),
        ])
        self.computed = tracking.day_values(CurveSettings(55, 4, 3, 13, 19.01, 0.0194))

    def test_spreadsheet_and_earlier_labels(self):
        self.assertEqual(
            tracking.column_keys([
                "Nombre révision lendemain", "Écart entre le jour 1 et le jour 2",
                "Écart entre le jour 2 et le jour 3", "Nombre révisions à long terme",
                "Force de la mémoire", "Coefficient a × 10 000", "Coefficient b",
                "Remarque", "Total paquet",
            ]),
            ["tomorrow", "drop_day2", "drop_day3", "floor", "strength", "slope_x10000",
             "floor", "remark", None],
        )

    def test_the_settings(self):
        values = dict((k, v) for k, _, v in tracking.form_fields(self.data, "2026-11-18", self.computed))
        new = tracking.record(self.data, "2026-11-18", values, "Remarque")
        self.assertEqual(new["tables"][0]["rows"][-1], ["2026-11-18", 55, 4, 3, 13, 19.01, 194, None])

    def test_same_day_replaced_and_remark_kept(self):
        values = {"remark": "Correction", "floor": 12}
        once = tracking.record(self.data, "2026-11-17", values, "Remarque")
        self.assertEqual(len(once["tables"][0]["rows"]), 1)
        self.assertEqual(once["tables"][0]["rows"][0][-1], "Correction")
        fields = tracking.form_fields(once, "2026-11-17", {"floor": 13})
        self.assertIn(("remark", "Remarque", "Correction"), fields)

    def test_rows_stay_in_date_order(self):
        new = tracking.record(self.data, "2026-11-10", {}, "Remarque")
        self.assertEqual([r[0] for r in new["tables"][0]["rows"]], ["2026-11-10", "2026-11-17"])

    def test_a_remark_without_remark_column(self):
        data = tracking.history([tracking.table("T", ["Cartes à J90"], [["2026-11-17", 1]])])
        new = tracking.record(data, "2026-11-18", {"floor": 2, "remark": "x"}, "Remarque")
        self.assertEqual(new["tables"][0]["columns"], ["Cartes à J90", "Remarque"])
        self.assertEqual(new["tables"][0]["rows"], [["2026-11-17", 1, None], ["2026-11-18", 2, "x"]])

    def test_unknown_columns_are_asked(self):
        data = tracking.history([tracking.table("T", ["Humeur"], [["2026-11-18", "bonne"]])])
        fields = tracking.form_fields(data, "2026-11-18", {})
        self.assertIn(((0, 0), "Humeur (T)", "bonne"), fields)
        new = tracking.record(data, "2026-11-18", {(0, 0): "super"}, "Remarque")
        self.assertEqual(new["tables"][0]["rows"], [["2026-11-18", "super"]])

    def test_typed_values(self):
        self.assertEqual(tracking.parse_value(" 19,01 "), 19.01)
        self.assertEqual(tracking.parse_value("12 947"), 12947)
        self.assertIsNone(tracking.parse_value(""))
        self.assertEqual(tracking.parse_value("?"), "?")
        self.assertEqual(tracking.show_value(19.01, True), "19,01")
        self.assertEqual(tracking.show_value(0.0194, False), "0.0194")

    def test_new_history(self):
        data = tracking.new_history(Translator("fr"))
        self.assertEqual(data["tables"][0]["columns"][-1], "Remarque")
        self.assertNotIn(None, tracking.column_keys(data["tables"][0]["columns"]))


if __name__ == "__main__":
    unittest.main()
