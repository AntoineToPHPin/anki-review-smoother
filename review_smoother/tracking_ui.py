"""Anki side of the tracking note: note type, note, and the dialog recording
the day (« Enregistrer le suivi du jour », opened from the Review Smoother
dialog). Format and form logic: `tracking.py`."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import anki.lang
from anki.collection import Collection, OpChanges, SearchNode
from anki.models import NotetypeDict
from anki.notes import Note
from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.utils import tooltip

from . import tracking
from .i18n import STRINGS, Translator
from .smoothing import CurveSettings


def anki_day(col: Collection) -> str:
    """Anki's today (it ends at the day's cutoff, 4 a.m. by default)."""
    return datetime.fromtimestamp(col.sched.day_cutoff - 86400).date().isoformat()


def deck_counts(col: Collection, deck: str) -> tuple:
    """The deck's (and subdecks') new cards of the day (first reviewed
    today, as Anki's `introduced:1`) and learned cards (not new); the
    spreadsheet's « Nouvelles cartes apprises » and « Total paquet »."""
    search = col.build_search_string(SearchNode(deck=deck))
    new_cards = len(col.find_cards(f"{search} introduced:1"))
    learned = len(col.find_cards(f"{search} -is:new"))
    return new_cards, learned


def find_model(col: Collection) -> Optional[NotetypeDict]:
    """The tracking note type, whatever language created it."""
    for strings in STRINGS.values():
        model = col.models.by_name(strings["tracking_note_type"])
        if model:
            return model
    return None


def _text(field: str) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", field)).strip()


def find_note(col: Collection, deck: str) -> Optional[Note]:
    """The deck's tracking note: first field = the deck's name."""
    model = find_model(col)
    if not model:
        return None
    for nid in col.find_notes(col.build_search_string(SearchNode(note=model["name"]))):
        note = col.get_note(nid)
        if _text(note.fields[0]) == deck:
            return note
    return None


def ensure_model(col: Collection, tr: Translator) -> NotetypeDict:
    """The tracking note type, created if missing; its template and CSS
    updated when the add-on's differ (new version, other language)."""
    model = find_model(col)
    css = tracking.card_css()
    if model is None:
        models = col.models
        model = models.new(tr("tracking_note_type"))
        for name in (tr("tracking_deck_field"), tr("tracking_history_field")):
            models.add_field(model, models.new_field(name))
        template = models.new_template(tr("tracking_card"))
        front = tracking.card_template(tr("tracking_history_field"), tracking.card_strings(tr))
        template["qfmt"] = template["afmt"] = front
        models.add_template(model, template)
        model["css"] = css
        models.add_dict(model)
        return models.by_name(tr("tracking_note_type"))
    front = tracking.card_template(model["flds"][1]["name"], tracking.card_strings(tr))
    template = model["tmpls"][0]
    if template["qfmt"] != front or template["afmt"] != front or model["css"] != css:
        template["qfmt"] = template["afmt"] = front
        model["css"] = css
        col.models.update_dict(model)
    return model


def save_history(
    col: Collection, deck: str, data: Dict[str, Any], tr: Translator, undo_label: str
) -> OpChanges:
    """Write the history into the deck's note (created, card suspended, in
    the « _Review Smoother » deck if missing), as one undo step."""
    undo_start = col.add_custom_undo_entry(undo_label)
    model = ensure_model(col, tr)
    note = find_note(col, deck)
    if note is None:
        note = col.new_note(model)
        note.fields[0] = html.escape(deck, quote=False)
        note.fields[1] = tracking.to_field(data)
        col.add_note(note, col.decks.id(tr("tracking_deck")))
        col.sched.suspend_cards(note.card_ids())
    else:
        note.fields[1] = tracking.to_field(data)
        col.update_note(note)
    return col.merge_undo_entries(undo_start)


class TrackingDialog(QDialog):
    def __init__(self, parent: QWidget, deck: str, settings: CurveSettings) -> None:
        super().__init__(parent)
        self.tr = tr = Translator(anki.lang.current_lang)
        self.deck = deck
        self.day = anki_day(mw.col)
        note = find_note(mw.col, deck)
        self.data = tracking.from_field(note.fields[1]) if note else tracking.new_history(tr)
        if not self.data.get("tables"):
            self.data = tracking.new_history(tr)
        computed = tracking.day_values(settings, *deck_counts(mw.col, deck))
        self.setWindowTitle(tr("tracking_title", deck=deck))

        comma = tr.lang == "fr"
        shown_day = datetime.strptime(self.day, "%Y-%m-%d").strftime(
            "%d/%m/%Y" if comma else "%Y-%m-%d"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("tracking_day", date=shown_day)))
        notes: List[str] = []
        if note is None:
            notes.append(tr("tracking_new_note", deck=tr("tracking_deck")))
        elif any(tracking.find_row(t, self.day) for t in self.data["tables"]):
            notes.append(tr("tracking_replace"))
        notes.append(tr("tracking_hint"))
        for text in notes:
            label = QLabel(text)
            label.setWordWrap(True)
            layout.addWidget(label)

        form = QFormLayout()
        self.fields: List[tuple] = []
        for field_id, label, value in tracking.form_fields(self.data, self.day, computed):
            edit = QLineEdit(tracking.show_value(value, comma))
            if field_id == "remark":
                edit.setMinimumWidth(360)
            form.addRow(label or tr("tracking_col_remark"), edit)
            self.fields.append((field_id, edit))
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(buttons.accepted, self.save)
        qconnect(buttons.rejected, self.reject)
        layout.addWidget(buttons)

    def save(self) -> None:
        tr = self.tr
        values = {field_id: tracking.parse_value(edit.text()) for field_id, edit in self.fields}
        data = tracking.record(self.data, self.day, values, tr("tracking_col_remark"))
        deck = self.deck
        undo_label = tr("tracking_undo")
        message = tr("tracking_saved")
        CollectionOp(
            self.parentWidget(), lambda col: save_history(col, deck, data, tr, undo_label)
        ).success(lambda _: tooltip(message, parent=mw)).run_in_background()
        self.accept()


def open_tracking_dialog(parent: QWidget, deck: str, settings: CurveSettings) -> None:
    TrackingDialog(parent, deck, settings).exec()
