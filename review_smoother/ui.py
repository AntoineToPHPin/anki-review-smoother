"""Anki integration: Tools menu entry and the smoothing dialog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import anki.lang
from anki.collection import Collection, OpChanges, SearchNode
from anki.utils import ids2str
from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import (
    QAction,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    qconnect,
)
from aqt.utils import tooltip
from aqt.webview import AnkiWebView

from .i18n import Translator
from .smoothing import (
    POSTPONE_MARGIN,
    Card,
    daily_counts,
    lookahead_end,
    move_stats,
    smooth,
)

WEB_DIR = Path(__file__).parent / "web"

# Shortcuts for the horizon, in days: the periods of the Future Due graph in
# Anki's Statistics window, except 30 days for a month (Anki uses 31).
RANGES = (("range_month", 30), ("range_three_months", 90), ("range_year", 365))


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

    @property
    def total(self) -> int:
        """Cards in the window after smoothing, those pulled into it included."""
        return sum(self.after)


def make_plan(col: Collection, deck: str, horizon: int, allow_postpone: bool) -> Plan:
    """Smoothing of one deck (subdecks included), without changing anything.

    `cards` also holds the cards due shortly after the window, which smoothing
    may pull into it (see `lookahead_end`)."""
    today = col.sched.today
    query = col.build_search_string(
        SearchNode(deck=deck),
        "is:review -is:learn -is:suspended -is:buried -deck:filtered",
        f"prop:due>=1 prop:due<={lookahead_end(horizon)}",
    )
    rows = col.db.all(
        f"select id, due, ivl from cards where id in {ids2str(col.find_cards(query))}"
    )
    cards = [Card(id=cid, due=due - today, interval=ivl) for cid, due, ivl in rows]
    before = daily_counts((c.due for c in cards if c.due <= horizon), horizon)
    after, new_due = smooth(cards, horizon, allow_postpone)
    return Plan(horizon, cards, before, after, new_due)


def apply_plan(col: Collection, plan: Plan, undo_label: str) -> OpChanges:
    """Write the new due dates as a single undoable step."""
    undo_start = col.add_custom_undo_entry(undo_label)
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
        # Anki's interface language, read when the dialog opens.
        self.tr = Translator(anki.lang.current_lang)
        tr = self.tr
        config = mw.addonManager.getConfig(__name__) or {}

        self.deck = QComboBox()
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        current = mw.col.decks.current()["name"]
        if self.deck.findText(current) >= 0:
            self.deck.setCurrentText(current)

        self.horizon = QSpinBox()
        self.horizon.setRange(7, 365)
        self.horizon.setSuffix(tr("days_suffix"))
        self.horizon.setValue(int(config.get("horizon_days", 90)))

        self.postpone = QCheckBox(tr("postpone", margin=tr.percent(POSTPONE_MARGIN)))
        self.postpone.setChecked(bool(config.get("allow_postpone", False)))

        # A shortcut sets the number of days, which can still be typed in.
        self.ranges = QButtonGroup(self)
        horizon_row = QHBoxLayout()
        for key, days in RANGES:
            button = QRadioButton(tr(key))
            self.ranges.addButton(button, days)
            horizon_row.addWidget(button)
        horizon_row.addWidget(self.horizon)
        horizon_row.addStretch()
        qconnect(self.ranges.idClicked, self.horizon.setValue)
        qconnect(self.horizon.valueChanged, self.sync_range)
        self.sync_range()

        form = QFormLayout()
        form.addRow(tr("deck"), self.deck)
        form.addRow(tr("horizon"), horizon_row)
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

    def sync_range(self) -> None:
        """Check the shortcut matching the number of days, or none."""
        button = self.ranges.button(self.horizon.value())
        if button is not None:
            button.setChecked(True)
            return
        checked = self.ranges.checkedButton()
        if checked is not None:
            # An exclusive group cannot be left with nothing checked otherwise.
            self.ranges.setExclusive(False)
            checked.setChecked(False)
            self.ranges.setExclusive(True)

    def refresh(self) -> None:
        self.plan = make_plan(
            mw.col,
            self.deck.currentText(),
            self.horizon.value(),
            self.postpone.isChecked(),
        )
        plan = self.plan
        tr = self.tr
        data = {
            "before": plan.before,
            "after": plan.after,
            "strings": tr.graph_strings(),
        }
        self.web.eval(f"render({json.dumps(data)});")
        moved = plan.moved
        if not plan.total:
            text = tr("no_cards", days=plan.horizon)
        elif not moved:
            text = tr("already_smooth", count=plan.total)
        else:
            sentences = tr.describe_moves(*move_stats(plan.cards, plan.new_due))
            text = " ".join(
                [tr("will_move", count=len(moved), total=plan.total)] + sentences
            )
        self.summary.setText(text)
        apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setEnabled(bool(moved))

    def apply(self) -> None:
        plan = self.plan
        if not plan or not plan.moved:
            return
        done_message = self.tr("applied", count=len(plan.moved))
        undo_label = self.tr("undo")
        # Parented to the main window: this dialog closes right away.
        CollectionOp(mw, lambda col: apply_plan(col, plan, undo_label)).success(
            lambda _: tooltip(done_message, parent=mw)
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
