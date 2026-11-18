"""Import tracking sheets of a spreadsheet into the deck's tracking note.

Usage (Anki running with AnkiConnect on localhost:8765):
    python tools/import_tracking.py book.xlsx "Deck::Name" "Sheet 1" ["Sheet 2"...]
        [--last-day 2026-11-18] [--lang fr] [--preview page.html]

Each sheet must hold one table: a header row, then one row per day, the
first column being a day number (dropped), down to a "Total" row or the end.
Rows carry no date: the last one is `--last-day` (today by default), each
earlier one a day before. Cell comments become a « Remarque » column
(author prefix "Name:" removed). Written to Anki: the note type (created, or
its template and CSS updated), the deck, the note (created with its card
suspended, or its history replaced). `--preview` writes a page showing the
card instead, without touching Anki.

Only the standard library: the .xlsx is read with zipfile + ElementTree.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from review_smoother import tracking  # noqa: E402
from review_smoother.i18n import Translator  # noqa: E402

ANKICONNECT_URL = "http://localhost:8765"
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def anki(action: str, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    with urllib.request.urlopen(ANKICONNECT_URL, body) as response:
        reply = json.load(response)
    if reply.get("error"):
        raise RuntimeError(f"{action}: {reply['error']}")
    return reply["result"]


def _rels(book: zipfile.ZipFile, part: str):
    folder, name = posixpath.split(part)
    path = posixpath.join(folder, "_rels", name + ".rels")
    if path not in book.namelist():
        return {}
    root = ET.fromstring(book.read(path))
    return {
        rel.get("Type").rsplit("/", 1)[-1]: posixpath.normpath(posixpath.join(folder, rel.get("Target")))
        for rel in root.iter(PR + "Relationship")
    }


def _column(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - 64
    return index


def read_sheet(book: zipfile.ZipFile, name: str):
    """(columns, rows) of the sheet's table, rows as lists of values, the
    remark (cell comments) last."""
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(PR + "Relationship")}
    sheet = next((s for s in workbook.iter(M + "sheet") if s.get("name") == name), None)
    if sheet is None:
        raise SystemExit(f"No sheet named {name!r}.")
    part = posixpath.normpath(posixpath.join("xl", targets[sheet.get(R + "id")]))
    strings = []
    if "xl/sharedStrings.xml" in book.namelist():
        shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.iter(M + "t")) for si in shared.findall(M + "si")]
    comments = {}
    comments_part = _rels(book, part).get("comments")
    if comments_part:
        for comment in ET.fromstring(book.read(comments_part)).iter(M + "comment"):
            text = "".join(t.text or "" for t in comment.iter(M + "t")).strip()
            # "Antoine:\nCorrection de..." -> "Correction de..."
            text = re.sub(r"^[^\n:]{1,40}\s?:\s*\n", "", text).strip()
            comments[comment.get("ref")] = text

    grid = []
    for row in ET.fromstring(book.read(part)).iter(M + "row"):
        cells = {}
        notes = []
        for cell in row.findall(M + "c"):
            ref = cell.get("r")
            if ref in comments:
                notes.append(comments[ref])
            value = cell.find(M + "v")
            if value is None:
                continue
            text = value.text
            if cell.get("t") == "s":
                cells[_column(ref)] = strings[int(text)]
            elif cell.get("t") in ("str", "inlineStr"):
                cells[_column(ref)] = text
            else:
                cells[_column(ref)] = float(text)
        grid.append((cells, notes))

    start = next(i for i, (cells, _) in enumerate(grid) if cells and all(isinstance(v, str) for v in cells.values()))
    header = grid[start][0]
    keys = sorted(header)[1:]  # first column: the day number
    columns = [header[k].strip() for k in keys]
    rows = []
    for cells, notes in grid[start + 1:]:
        if any(isinstance(v, str) and v.strip().lower() == "total" for v in cells.values()):
            break
        if not any(k in cells for k in keys):
            continue
        rows.append([tracking.number(cells.get(k)) for k in keys] + ["\n".join(notes) or None])
    return columns, rows


def build(path: str, sheets, last_day: date, remark: str):
    with zipfile.ZipFile(path) as book:
        tables = []
        for name in sheets:
            columns, rows = read_sheet(book, name)
            if not any(row[-1] for row in rows):
                rows = [row[:-1] for row in rows]
            else:
                columns = columns + [remark]
            tables.append(tracking.table(name, columns, tracking.dated_rows(rows, last_day)))
    return tracking.history(tables)


def preview(path: str, data, tr) -> None:
    fields = tr("tracking_history_field")
    template = tracking.card_template(fields, tracking.card_strings(tr))
    body = template.replace("{{%s}}" % fields, tracking.to_field(data))
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{tracking.card_css()}</style></head>"
        f"<body class='card'>{body}</body></html>"
    )
    with open(path, "w", encoding="utf-8") as file:
        file.write(page)


def write_to_anki(deck: str, data, tr) -> str:
    model = tr("tracking_note_type")
    deck_field = tr("tracking_deck_field")
    history_field = tr("tracking_history_field")
    template = tracking.card_template(history_field, tracking.card_strings(tr))
    css = tracking.card_css()
    card = tr("tracking_card")
    if model in anki("modelNames"):
        anki("updateModelTemplates", model={"name": model, "templates": {card: {"Front": template, "Back": template}}})
        anki("updateModelStyling", model={"name": model, "css": css})
    else:
        anki(
            "createModel",
            modelName=model,
            inOrderFields=[deck_field, history_field],
            css=css,
            isCloze=False,
            cardTemplates=[{"Name": card, "Front": template, "Back": template}],
        )
    home = tr("tracking_deck")
    anki("createDeck", deck=home)
    field = tracking.to_field(data)
    query = '"note:%s" "%s:%s"' % (model, deck_field, deck.replace('"', '\\"'))
    notes = anki("findNotes", query=query)
    if notes:
        anki("updateNoteFields", note={"id": notes[0], "fields": {history_field: field}})
        return f"Updated note {notes[0]}."
    note = anki(
        "addNote",
        note={
            "deckName": home,
            "modelName": model,
            "fields": {deck_field: deck, history_field: field},
            "options": {"allowDuplicate": True},
            "tags": [],
        },
    )
    anki("suspend", cards=anki("findCards", query=f"nid:{note}"))
    return f"Created note {note} in deck {home!r}, card suspended."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("book")
    parser.add_argument("deck")
    parser.add_argument("sheets", nargs="+")
    parser.add_argument("--last-day", type=date.fromisoformat, default=date.today())
    parser.add_argument("--lang", default="fr")
    parser.add_argument("--remark", default=None, help="Title of the comments column.")
    parser.add_argument("--preview", help="Write this page instead of writing to Anki.")
    args = parser.parse_args()
    tr = Translator(args.lang)
    remark = args.remark or ("Remarque" if tr.lang == "fr" else "Remark")
    data = build(args.book, args.sheets, args.last_day, remark)
    for t in data["tables"]:
        rows = t["rows"]
        print(f"{t['title']}: {len(rows)} days, {rows[0][0]} to {rows[-1][0]}, columns: {', '.join(t['columns'])}")
    if args.preview:
        preview(args.preview, data, tr)
        print(f"Preview written to {args.preview}.")
    else:
        print(write_to_anki(args.deck, data, tr))


if __name__ == "__main__":
    main()
