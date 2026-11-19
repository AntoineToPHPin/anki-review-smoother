"""Tracking history kept in an Anki note, without Anki imports.

Asked 2026-11-18: the author recorded, every day, their custom curve's
settings and totals in the sheets « Suivi 90 j. » and « Suivi 365 j. » of
their spreadsheet. Kept in a note, the history syncs like any note and shows
in AnkiDroid too (add-on config, meta.json, does not sync). One note per
tracked deck, of a dedicated note type, in its own deck with its card
suspended (never studied: it is opened from the Browser's preview). Its card
template draws a graph and a table from the note's history field with plain
JavaScript (web/tracking.js, web/tracking.css), so nothing else is needed on
the phone.

History field: JSON, HTML-escaped (Anki fields are HTML):
    {"v": 1, "tables": [{"title": "Suivi 90 j.",
                         "columns": ["Total paquet", "Remarque"...],
                         "rows": [["2026-11-18", 12947, null...]...]}]}
Rows are oldest first, one per day, the date first (YYYY-MM-DD); values are
numbers, text (remarks) or null.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

FORMAT_VERSION = 1
WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
# Locale given to the card's Intl formatters, per interface language.
LOCALES = {"en": "en-GB", "fr": "fr-FR"}


def table(title: str, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> Dict[str, Any]:
    return {"title": title, "columns": list(columns), "rows": [list(r) for r in rows]}


def history(tables: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {"v": FORMAT_VERSION, "tables": [dict(t) for t in tables]}


def to_field(data: Mapping[str, Any]) -> str:
    """The history as stored in the note's field."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return html.escape(text, quote=False)


def from_field(field: str) -> Dict[str, Any]:
    """The history read back from the field; tolerates what Anki's editor
    may add if the field was opened (tags, entities)."""
    text = html.unescape(re.sub(r"<[^>]*>", "", field)).strip()
    if not text:
        return history([])
    try:
        return json.loads(text)
    except ValueError:
        # &nbsp; between values (not valid JSON whitespace)
        return json.loads(text.replace(" ", " "))


def _read(name: str) -> str:
    with open(os.path.join(WEB, name), encoding="utf-8") as file:
        return file.read()


def card_strings(tr) -> Dict[str, Any]:
    """Labels used by the card, from an `i18n.Translator`."""
    return {
        "locale": LOCALES.get(tr.lang, "en-GB"),
        "date": tr("tracking_date"),
        "column": tr("tracking_column"),
        "ranges": [
            [31, tr("tracking_month")],
            [92, tr("tracking_quarter")],
            [366, tr("tracking_year")],
            [0, tr("tracking_all")],
        ],
        # Normalised column label -> key: totals, remark shown last.
        "keys": known_labels(),
        "totals": [
            [31, tr("tracking_total_month")],
            [90, tr("tracking_total_quarter")],
            [365, tr("tracking_total_year")],
        ],
        "empty": tr("tracking_empty"),
        "invalid": tr("tracking_invalid"),
    }


def card_template(history_field: str, strings: Mapping[str, Any]) -> str:
    """Front (and back) template of the tracking card."""
    script = _read("tracking.js").replace(
        "/*STRINGS*/null", json.dumps(strings, ensure_ascii=False)
    )
    return (
        f'<div id="rs-history" hidden>{{{{{history_field}}}}}</div>\n'
        '<div id="rs-tracking" class="rs-root"></div>\n'
        f"<script>\n{script}</script>\n"
    )


def card_css() -> str:
    return _read("tracking.css")


def number(value: Any) -> Any:
    """A spreadsheet number as stored: whole numbers as ints, others without
    float noise (19.010000000000002 -> 19.01)."""
    if value is None or isinstance(value, str):
        return value  # "?" for an unknown value stays as typed
    if float(value).is_integer():
        return int(value)
    return round(float(value), 6)


def dated_rows(values: Sequence[Sequence[Any]], last_day) -> List[List[Any]]:
    """Rows one per day, the last one on `last_day` (a datetime.date), each
    earlier one a day before (spreadsheet rows carry no date)."""
    from datetime import timedelta

    count = len(values)
    return [
        [(last_day - timedelta(days=count - 1 - i)).isoformat()] + list(row)
        for i, row in enumerate(values)
    ]


# Recording a day (asked 2026-11-18: a button in the Review Smoother dialog,
# values prefilled and editable, plus a remark; not automatic).
#
# The custom curve's settings, by key (asked 2026-11-18: only what is set
# is kept; totals are computed by the card), plus the deck's new cards of
# the day and learned cards (asked back 2026-11-19), the remark last. A
# table's columns are matched to keys by their label (any language, spaces
# and case ignored; `i18n` keys `tracking_col_<key>`, the names of the
# Review Smoother dialog, plus ALIASES: the author's spreadsheet headers and
# earlier names).
COLUMN_KEYS = (
    "tomorrow",
    "drop_day2",
    "drop_day3",
    "floor",
    "strength",
    "slope_x10000",
    "new_cards",
    "learned",
    "remark",
)
ALIASES = {
    "tomorrow": ("Nombre révision lendemain", "Reviews tomorrow"),
    "drop_day2": ("Écart entre le jour 1 et le jour 2",),
    "drop_day3": ("Écart entre le jour 2 et le jour 3",),
    "floor": (
        "Nombre révisions à long terme",
        "Long-term reviews",
        "Révisions à long terme",
        # The spreadsheet's « Coefficient b » is the same setting.
        "Coefficient b",
    ),
    "slope_x10000": ("Coefficient a × 10 000", "Coefficient a × 10,000"),
    "new_cards": ("Nouvelles cartes apprises",),
    "learned": ("Total paquet",),
}
# Columns of the table of a deck tracked for the first time.
DEFAULT_COLUMNS = COLUMN_KEYS


def _normal(label: str) -> str:
    return "".join(label.split()).casefold()


def known_labels() -> Dict[str, str]:
    """Normalised label -> key, every language."""
    from .i18n import STRINGS

    labels: Dict[str, str] = {}
    for key in COLUMN_KEYS:
        names = [strings[f"tracking_col_{key}"] for strings in STRINGS.values()]
        for name in names + list(ALIASES.get(key, ())):
            labels[_normal(name)] = key
    return labels


def column_keys(columns: Sequence[str]) -> List[Optional[str]]:
    labels = known_labels()
    return [labels.get(_normal(c)) for c in columns]


def new_history(tr) -> Dict[str, Any]:
    columns = [tr(f"tracking_col_{key}") for key in DEFAULT_COLUMNS]
    return history([table(tr("tracking_default_table"), columns, [])])


def day_values(settings, new_cards: Any = None, learned: Any = None) -> Dict[str, Any]:
    """The day's values: the custom curve's settings, the deck's new cards
    of the day (first reviewed today) and learned cards (not new)."""
    return {
        "new_cards": new_cards,
        "learned": learned,
        "tomorrow": settings.tomorrow,
        "drop_day2": settings.drop_day2,
        "drop_day3": settings.drop_day3,
        "floor": settings.floor,
        "strength": number(settings.strength),
        "slope_x10000": number(round(settings.slope * 10000, 4)),
    }


def find_row(t: Mapping[str, Any], day: str) -> Optional[List[Any]]:
    return next((r for r in t["rows"] if r and r[0] == day), None)


def form_fields(
    data: Mapping[str, Any], day: str, computed: Mapping[str, Any]
) -> List[Tuple[Any, str, Any]]:
    """Fields of the recording form, as (id, label, value): one per key,
    labelled as its first column (shared by the tables that have it), then
    one per column the add-on does not know, id (table, column) labelled
    "column (table)". Values: computed, else what the day's row already
    holds (remark, unknown columns)."""
    fields: List[Tuple[Any, str, Any]] = []
    seen = set()
    unknown = []
    for t_index, t in enumerate(data["tables"]):
        row = find_row(t, day)
        for c_index, (column, key) in enumerate(zip(t["columns"], column_keys(t["columns"]))):
            existing = row[c_index + 1] if row and c_index + 1 < len(row) else None
            if key is None:
                unknown.append(((t_index, c_index), f"{column} ({t['title']})", existing))
            elif key not in seen:
                seen.add(key)
                value = computed.get(key)
                fields.append((key, column, existing if value is None else value))
    if "remark" not in seen:
        fields.append(("remark", None, None))  # labelled by the dialog
    return fields + unknown


def record(data: Mapping[str, Any], day: str, values: Mapping[Any, Any], remark_label: str) -> Dict[str, Any]:
    """The history with the day's row of every table set from `values`
    (form field id -> value), replacing that day's row if any. A remark goes
    into the tables with a remark column; with none, the first table gets
    one (titled `remark_label`)."""
    tables = json.loads(json.dumps(data["tables"]))
    remark = values.get("remark")
    if remark and tables and not any("remark" in column_keys(t["columns"]) for t in tables):
        tables[0]["columns"].append(remark_label)
        for row in tables[0]["rows"]:
            row.append(None)
    for t_index, t in enumerate(tables):
        keys = column_keys(t["columns"])
        row = [day] + [
            values.get(key if key is not None else (t_index, c_index))
            for c_index, key in enumerate(keys)
        ]
        rows = [r for r in t["rows"] if r[0] != day]
        rows.append(row)
        rows.sort(key=lambda r: r[0])
        t["rows"] = rows
    return {"v": FORMAT_VERSION, "tables": tables}


def parse_value(text: str) -> Any:
    """A form field's text: a number (decimal comma or point), None when
    empty, else the text as typed ("?")."""
    text = text.strip()
    if not text:
        return None
    try:
        return number(float(text.replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", ".")))
    except ValueError:
        return text


def show_value(value: Any, decimal_comma: bool) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        text = repr(value)
        return text.replace(".", ",") if decimal_comma else text
    return str(value)
