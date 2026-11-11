"""Anki integration: Tools menu entry and the smoothing dialog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from anki.collection import Collection, OpChanges, SearchNode
from anki.utils import ids2str
from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import tooltip
from aqt.webview import AnkiWebView

from .smoothing import POSTPONE_MARGIN, Card, daily_counts, describe_moves, smooth

UNDO_LABEL = "Smooth reviews"
WEB_DIR = Path(__file__).parent / "web"


@dataclass
class Plan:
    horizon: int
    cards: List[Card]
    before: List[int]
    after: List[int]
    new_due: Dict[int, int]

    @property
    def moved(self) -> List[Card]:
        return [c for c in self.cards if self.new_due[c.id] != c.due]


def make_plan(col: Collection, deck: str, horizon: int, allow_postpone: bool) -> Plan:
    """Smoothing of one deck (subdecks included), without changing anything."""
    today = col.sched.today
    query = col.build_search_string(
        SearchNode(deck=deck),
        "is:review -is:learn -is:suspended -is:buried -deck:filtered",
        f"prop:due>=1 prop:due<={horizon}",
    )
    rows = col.db.all(
        f"select id, due, ivl from cards where id in {ids2str(col.find_cards(query))}"
    )
    cards = [Card(id=cid, due=due - today, interval=ivl) for cid, due, ivl in rows]
    before = daily_counts((c.due for c in cards), horizon)
    after, new_due = smooth(cards, horizon, allow_postpone)
    return Plan(horizon, cards, before, after, new_due)


def apply_plan(col: Collection, plan: Plan) -> OpChanges:
    """Write the new due dates as a single undoable step."""
    undo_start = col.add_custom_undo_entry(UNDO_LABEL)
    today = col.sched.today
    cards = []
    for moved in plan.moved:
        card = col.get_card(moved.id)
        card.due = today + plan.new_due[moved.id]
        cards.append(card)
    col.update_cards(cards)
    return col.merge_undo_entries(undo_start)


def graph_html() -> str:
    """Page hosting the before/after graphs; filled by `render(...)` in JS."""
    css = (WEB_DIR / "graph.css").read_text(encoding="utf-8")
    js = (WEB_DIR / "graph.js").read_text(encoding="utf-8")
    return (
        f"<style>{css}</style>"
        '<div id="charts"></div><div id="tooltip"></div>'
        f"<script>{js}</script>"
    )


class SmoothDialog(QDialog):
    def __init__(self) -> None:
        super().__init__(mw)
        self.setWindowTitle("Review Smoother")
        self.plan: Optional[Plan] = None
        config = mw.addonManager.getConfig(__name__) or {}

        self.deck = QComboBox()
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        current = mw.col.decks.current()["name"]
        if self.deck.findText(current) >= 0:
            self.deck.setCurrentText(current)

        self.horizon = QSpinBox()
        self.horizon.setRange(7, 365)
        self.horizon.setSuffix(" days")
        self.horizon.setValue(int(config.get("horizon_days", 90)))

        self.postpone = QCheckBox(
            "Postpone a few cards when it lowers the start of the curve "
            f"(by at most {POSTPONE_MARGIN:.0%} of their interval)"
        )
        self.postpone.setChecked(bool(config.get("allow_postpone", True)))

        form = QFormLayout()
        form.addRow("Deck:", self.deck)
        form.addRow("Smooth over:", self.horizon)
        form.addRow("", self.postpone)

        self.web = AnkiWebView(self, title="review smoother")
        self.web.setMinimumSize(760, 560)
        self.web.stdHtml(graph_html(), js=[], context=self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        qconnect(self.buttons.rejected, self.reject)
        qconnect(
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked, self.apply
        )

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.web, 1)
        layout.addWidget(self.summary)
        layout.addWidget(self.buttons)

        qconnect(self.deck.currentTextChanged, self.refresh)
        qconnect(self.horizon.valueChanged, self.refresh)
        qconnect(self.postpone.toggled, self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.plan = make_plan(
            mw.col,
            self.deck.currentText(),
            self.horizon.value(),
            self.postpone.isChecked(),
        )
        plan = self.plan
        data = {"before": plan.before, "after": plan.after}
        self.web.eval(f"render({json.dumps(data)});")
        moved = plan.moved
        if not plan.cards:
            text = f"No review card due in the next {plan.horizon} days."
        elif not moved:
            text = f"{len(plan.cards)} cards, already smooth: nothing to move."
        else:
            text = f"{len(moved)} of {len(plan.cards)} cards will move. " + " ".join(
                describe_moves(plan.cards, plan.new_due)
            )
        self.summary.setText(text)
        apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setEnabled(bool(moved))

    def apply(self) -> None:
        plan = self.plan
        if not plan or not plan.moved:
            return
        count = len(plan.moved)
        # Parented to the main window: this dialog closes right away.
        CollectionOp(mw, lambda col: apply_plan(col, plan)).success(
            lambda _: tooltip(f"{count} cards moved. Undo with Edit > Undo.", parent=mw)
        ).run_in_background()
        self.accept()

    def done(self, result: int) -> None:
        self.web.cleanup()
        super().done(result)


def open_dialog() -> None:
    SmoothDialog().exec()


def setup_menu() -> None:
    action = QAction("Review Smoother…", mw)
    qconnect(action.triggered, open_dialog)
    mw.form.menuTools.addAction(action)
