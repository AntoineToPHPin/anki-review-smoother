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
from typing import Any, Dict, List, Mapping, Optional, Sequence

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
