"""Dialog repositioning a deck's new cards, one position per card."""

from __future__ import annotations

import random
from typing import Dict, List, Optional

import anki.lang
from anki.collection import Collection, OpChanges, SearchNode
from anki.utils import ids2str
from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import (
    QAbstractItemView,
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    Qt,
    qconnect,
)
from aqt.utils import restoreGeom, saveGeom, tooltip

from .i18n import Translator
from .reposition import NewCard, current_order, positions, sibling_gap, shuffled

GEOMETRY_KEY = "reviewSmootherReposition"
# Longest card text shown in the preview.
TEXT_LENGTH = 80


def new_cards(col: Collection, deck: str) -> List[NewCard]:
    """New cards of `deck` and its subdecks (suspended and buried ones
    included, like Anki's Reposition)."""
    ids = col.find_cards(col.build_search_string(SearchNode(deck=deck), "is:new"))
    rows = col.db.all(f"select id, nid, ord, due from cards where id in {ids2str(ids)}")
    return [NewCard(id=cid, note=nid, ord=ord_, position=due) for cid, nid, ord_, due in rows]


def card_texts(col: Collection, cards: List[NewCard]) -> Dict[int, str]:
    """Sort field and card template name of each card, for the preview."""
    rows = col.db.all(
        "select c.id, c.ord, n.mid, n.sfld from cards c join notes n on n.id = c.nid "
        f"where c.id in {ids2str(c.id for c in cards)}"
    )
    texts = {}
    for cid, ord_, mid, sfld in rows:
        text = " ".join(str(sfld).split())
        if len(text) > TEXT_LENGTH:
            text = text[: TEXT_LENGTH - 1] + "…"
        model = col.models.get(mid) or {}
        templates = model.get("tmpls", [])
        if len(templates) > 1 and ord_ < len(templates):
            text += f" — {templates[ord_]['name']}"
        texts[cid] = text
    return texts


def new_per_day(col: Collection, deck: str) -> int:
    """New cards a day in the deck's options."""
    deck_id = col.decks.id_for_name(deck)
    if deck_id is None:
        return 0
    return int(col.decks.config_dict_for_deck_id(deck_id)["new"]["perDay"])


def apply_positions(col: Collection, new_position: Dict[int, int], undo_label: str) -> OpChanges:
    undo_start = col.add_custom_undo_entry(undo_label)
    cards = []
    for cid, position in new_position.items():
        card = col.get_card(cid)
        card.due = position
        cards.append(card)
    col.update_cards(cards)
    return col.merge_undo_entries(undo_start)


class RepositionDialog(QDialog):
    def __init__(self, deck: Optional[str] = None) -> None:
        """`deck`: deck selected at first (default: the current deck)."""
        super().__init__(mw)
        self.tr = Translator(anki.lang.current_lang)
        tr = self.tr
        self.setWindowTitle(tr("reposition_title"))
        self.cards: List[NewCard] = []
        self.order: List[NewCard] = []
        self.texts: Dict[int, str] = {}
        self.spacing = 0

        self.deck = QComboBox()
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        current = deck or mw.col.decks.current()["name"]
        if self.deck.findText(current) >= 0:
            self.deck.setCurrentText(current)
        self.start = QSpinBox()
        self.start.setRange(0, 10_000_000)
        self.step = QSpinBox()
        self.step.setRange(1, 10_000)
        self.shuffle = QCheckBox(tr("reposition_shuffle"))
        self.reshuffle = QPushButton(tr("reposition_reshuffle"))
        shuffle_row = QHBoxLayout()
        shuffle_row.addWidget(self.shuffle)
        shuffle_row.addWidget(self.reshuffle)
        shuffle_row.addStretch()
        self.spacing_hint = QLabel()
        self.spacing_hint.setWordWrap(True)
        self.spacing_hint.setEnabled(False)

        form = QFormLayout()
        form.addRow(tr("deck"), self.deck)
        form.addRow(tr("reposition_start"), self.start)
        form.addRow(tr("reposition_step"), self.step)
        form.addRow(shuffle_row)
        form.addRow(self.spacing_hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            [tr("reposition_new"), tr("reposition_current"), tr("reposition_card")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.summary = QLabel()
        self.summary.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(self.buttons.rejected, self.reject)
        qconnect(
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked, self.apply
        )

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary)
        layout.addWidget(self.buttons)

        self.load_deck()
        qconnect(self.deck.currentTextChanged, lambda _: self.load_deck())
        qconnect(self.start.valueChanged, lambda _: self.on_settings_changed())
        qconnect(self.step.valueChanged, lambda _: self.on_settings_changed())
        qconnect(self.shuffle.toggled, lambda _: self.on_shuffle_changed())
        qconnect(self.reshuffle.clicked, lambda: self.on_shuffle_changed(save=False))
        restoreGeom(self, GEOMETRY_KEY, default_size=(800, 600))

    # Settings per deck, in the add-on's config: {"reposition": {name:
    # {"start": 1, "step": 1, "shuffle": false}}}.

    def saved(self) -> Dict[str, object]:
        config = mw.addonManager.getConfig(__name__) or {}
        return dict(config.get("reposition", {}).get(self.deck.currentText(), {}))

    def save(self) -> None:
        config = mw.addonManager.getConfig(__name__) or {}
        decks = dict(config.get("reposition", {}))
        decks[self.deck.currentText()] = {
            "start": self.start.value(),
            "step": self.step.value(),
            "shuffle": self.shuffle.isChecked(),
        }
        config["reposition"] = decks
        mw.addonManager.writeConfig(__name__, config)

    def load_deck(self) -> None:
        deck = self.deck.currentText()
        saved = self.saved()
        for widget in (self.start, self.step, self.shuffle):
            widget.blockSignals(True)
        self.start.setValue(int(saved.get("start", 1)))  # type: ignore[arg-type]
        self.step.setValue(int(saved.get("step", 1)))  # type: ignore[arg-type]
        self.shuffle.setChecked(bool(saved.get("shuffle", False)))
        for widget in (self.start, self.step, self.shuffle):
            widget.blockSignals(False)
        self.cards = new_cards(mw.col, deck)
        self.texts = card_texts(mw.col, self.cards) if self.cards else {}
        self.spacing = new_per_day(mw.col, deck)
        self.make_order()
        self.refresh()

    def on_settings_changed(self) -> None:
        self.save()
        self.refresh()

    def on_shuffle_changed(self, save: bool = True) -> None:
        if save:
            self.save()
        self.make_order()
        self.refresh()

    def make_order(self) -> None:
        """Drawn again only when asked (deck, shuffle box, "Shuffle again"),
        not when the start or step changes."""
        if self.shuffle.isChecked():
            self.order = shuffled(self.cards, self.spacing, random.Random())
        else:
            self.order = current_order(self.cards)

    def new_positions(self) -> Dict[int, int]:
        return positions(self.order, self.start.value(), self.step.value())

    def refresh(self) -> None:
        tr = self.tr
        shuffle = self.shuffle.isChecked()
        self.reshuffle.setVisible(shuffle)
        has_siblings = len({c.note for c in self.cards}) < len(self.cards)
        self.spacing_hint.setVisible(shuffle and has_siblings and self.spacing > 1)
        self.spacing_hint.setText(tr("reposition_spacing", count=self.spacing))

        new_position = self.new_positions()
        self.table.setRowCount(len(self.order))
        for row, card in enumerate(self.order):
            values = (new_position[card.id], card.position, self.texts.get(card.id, ""))
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column < 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)

        changed = sum(1 for c in self.cards if new_position[c.id] != c.position)
        if not self.cards:
            sentences = [tr("reposition_none")]
        elif not changed:
            sentences = [tr("reposition_in_place", count=len(self.cards))]
        else:
            sentences = [tr("reposition_will_change", count=changed, total=len(self.cards))]
        gap = sibling_gap(self.order)
        if shuffle and gap is not None and gap < self.spacing:
            sentences.append(tr("reposition_close_siblings", count=gap))
        self.summary.setText(" ".join(sentences))
        apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setEnabled(bool(changed))

    def apply(self) -> None:
        before = {c.id: c.position for c in self.cards}
        new_position = {
            cid: position
            for cid, position in self.new_positions().items()
            if position != before[cid]
        }
        if not new_position:
            return
        done_message = self.tr("reposition_applied", count=len(new_position))
        undo_label = self.tr("reposition_title")

        def success(_: OpChanges) -> None:
            tooltip(done_message, parent=mw)

        CollectionOp(mw, lambda col: apply_positions(col, new_position, undo_label)).success(
            success
        ).run_in_background()
        self.accept()

    def done(self, result: int) -> None:
        saveGeom(self, GEOMETRY_KEY)
        super().done(result)


def open_reposition_dialog(deck: Optional[str] = None) -> None:
    dialog = RepositionDialog(deck)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.exec()


def setup_reposition_menu() -> None:
    action = QAction(Translator(anki.lang.current_lang)("reposition_menu"), mw)
    qconnect(action.triggered, lambda: open_reposition_dialog())
    mw.form.menuTools.addAction(action)
