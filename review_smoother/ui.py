"""Anki integration: Tools menu entry and the smoothing dialog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

import anki.lang
import aqt
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
    Qt,
    qconnect,
)
from aqt.utils import restoreGeom, saveGeom, tooltip
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

# Size and position of the dialog, remembered by Anki between openings.
GEOMETRY_KEY = "reviewSmoother"
# Share of the screen taken by the dialog the first time it opens.
DEFAULT_SCREEN_SHARE = 0.8


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
    ids = col.find_cards(query)
    rows = col.db.all(f"select id, nid, due, ivl from cards where id in {ids2str(ids)}")
    cards = [
        Card(id=cid, due=due - today, interval=ivl, note=nid)
        for cid, nid, due, ivl in rows
    ]
    before = daily_counts((c.due for c in cards if c.due <= horizon), horizon)
    after, new_due = smooth(cards, horizon, allow_postpone, sibling_days(col, cards))
    return Plan(horizon, cards, before, after, new_due)


def sibling_days(col: Collection, cards: List[Card]) -> Dict[int, Set[int]]:
    """Days (from today) on which the notes of `cards` have other cards due,
    which smoothing does not move: other decks, due later, etc. Only cards
    due on a given day count (review, or relearning over days; queues 2 and
    3), outside filtered decks."""
    if not cards:
        return {}
    today = col.sched.today
    notes = {c.note for c in cards}
    rows = col.db.all(
        f"select nid, due from cards where nid in {ids2str(notes)}"
        f" and id not in {ids2str(c.id for c in cards)}"
        " and queue in (2, 3) and odid = 0"
    )
    taken: Dict[int, Set[int]] = {}
    for nid, due in rows:
        taken.setdefault(nid, set()).add(due - today)
    return taken


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
    def __init__(
        self,
        deck: Optional[str] = None,
        on_applied: Optional[Callable[[], None]] = None,
    ) -> None:
        """`deck`: deck selected at first (default: the current deck).
        `on_applied`: called once the new due dates are written."""
        super().__init__(mw)
        self.on_applied = on_applied
        self.setWindowTitle("Review Smoother")
        # Dialogs have no maximize button by default; the graphs follow the size.
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.plan: Optional[Plan] = None
        # Anki's interface language, read when the dialog opens.
        self.tr = Translator(anki.lang.current_lang)
        tr = self.tr
        config = mw.addonManager.getConfig(__name__) or {}

        self.deck = QComboBox()
        self.deck.addItems(sorted(d.name for d in mw.col.decks.all_names_and_ids()))
        current = deck or mw.col.decks.current()["name"]
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
        # How to zoom the graphs (see web/graph.js), greyed out.
        hint = QLabel(tr("zoom_hint"))
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setEnabled(False)
        self.summary = QLabel()
        self.summary.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(self.buttons.rejected, self.reject)
        qconnect(
            self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked, self.apply
        )
        self.show_moved = self.buttons.addButton(
            tr("show_moved"), QDialogButtonBox.ButtonRole.ActionRole
        )
        qconnect(self.show_moved.clicked, self.browse_moved)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.web, 1)
        layout.addWidget(hint)
        layout.addWidget(self.summary)
        layout.addWidget(self.buttons)

        qconnect(self.deck.currentTextChanged, self.refresh)
        qconnect(self.horizon.valueChanged, self.refresh)
        qconnect(self.postpone.toggled, self.refresh)
        restoreGeom(self, GEOMETRY_KEY, default_size=self.default_size())
        self.refresh()

    def default_size(self) -> Tuple[int, int]:
        """Size on first opening: most of the screen the main window is on."""
        screen = (mw.screen() or self.screen()).availableGeometry()
        return (
            int(screen.width() * DEFAULT_SCREEN_SHARE),
            int(screen.height() * DEFAULT_SCREEN_SHARE),
        )

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
        self.show_moved.setEnabled(bool(moved))

    def browse_moved(self) -> None:
        """Open Anki's Browser on the cards that applying would move."""
        if not self.plan or not self.plan.moved:
            return
        ids = ",".join(str(card.id) for card in self.plan.moved)
        aqt.dialogs.open("Browser", mw, search=(f"cid:{ids}",))

    def apply(self) -> None:
        plan = self.plan
        if not plan or not plan.moved:
            return
        done_message = self.tr("applied", count=len(plan.moved))
        undo_label = self.tr("undo")
        on_applied = self.on_applied

        def success(_: OpChanges) -> None:
            # Parented to the main window: this dialog closes right away.
            tooltip(done_message, parent=mw)
            if on_applied:
                on_applied()

        CollectionOp(mw, lambda col: apply_plan(col, plan, undo_label)).success(
            success
        ).run_in_background()
        self.accept()

    def done(self, result: int) -> None:
        saveGeom(self, GEOMETRY_KEY)
        self.web.cleanup()
        super().done(result)


def open_dialog(
    deck: Optional[str] = None, on_applied: Optional[Callable[[], None]] = None
) -> None:
    dialog = SmoothDialog(deck, on_applied)
    # Blocks the main window only, so that the Browser opened by "Show cards
    # to move" can be used while the dialog is open.
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.exec()


def setup_menu() -> None:
    action = QAction("Review Smoother…", mw)
    # A lambda: `triggered` passes a `checked` argument that is not a deck.
    qconnect(action.triggered, lambda: open_dialog())
    mw.form.menuTools.addAction(action)
