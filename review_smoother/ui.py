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
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
    Qt,
    qconnect,
)
from aqt.utils import restoreGeom, saveGeom, tooltip
from aqt.webview import AnkiWebView

from .i18n import Translator
from .smoothing import (
    MOVE_CEILING,
    POSTPONE_MARGIN,
    Card,
    CurveSettings,
    custom_curve,
    daily_counts,
    fill_gaps,
    follow_curve,
    outside_end,
    move_stats,
    smooth,
)

WEB_DIR = Path(__file__).parent / "web"

# Shortcuts for the horizon, in days: the periods of the Future Due graph in
# Anki's Statistics window, except 30 days for a month (Anki uses 31).
RANGES = (("range_month", 30), ("range_three_months", 90), ("range_year", 365),
          ("range_two_years", 730))

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
    # Custom curve over the window, when following one.
    curve: Optional[List[int]] = None

    @property
    def postponed_out(self) -> int:
        """Cards of the window sent after it."""
        return sum(
            1
            for c in self.cards
            if c.due <= self.horizon < self.new_due[c.id]
        )

    @property
    def moved(self) -> List[Card]:
        return [c for c in self.cards if self.new_due[c.id] != c.due]

    @property
    def total(self) -> int:
        """Cards in the window after smoothing, those pulled into it included."""
        return sum(self.after)


def make_plan(
    col: Collection,
    deck: str,
    horizon: int,
    method: str,
    allow_postpone: bool = False,
    settings: Optional[CurveSettings] = None,
) -> Plan:
    """Smoothing of one deck (subdecks included), without changing anything.

    `cards` also holds the cards due after the window, up to `outside_end`:
    smoothing takes the cards the window lacks from the days there that have
    some to spare. `method`: see `METHODS`;
    `allow_postpone` only applies to "auto", `settings` to "custom"."""
    today = col.sched.today
    query = col.build_search_string(
        SearchNode(deck=deck),
        "is:review -is:learn -is:suspended -is:buried -deck:filtered",
        f"prop:due>=1 prop:due<={outside_end(horizon)}",
    )
    ids = col.find_cards(query)
    rows = col.db.all(f"select id, nid, due, ivl from cards where id in {ids2str(ids)}")
    cards = [
        Card(id=cid, due=due - today, interval=ivl, note=nid)
        for cid, nid, due, ivl in rows
    ]
    before = daily_counts((c.due for c in cards if c.due <= horizon), horizon)
    taken = sibling_days(col, cards)
    config = mw.addonManager.getConfig(__name__) or {}
    ceiling = float(config.get("move_ceiling_percent", MOVE_CEILING * 100)) / 100
    if method == "custom" and settings is not None:
        # Carried on after the window: the days there are compared to it.
        curve = custom_curve(settings, outside_end(horizon))
        after, new_due = follow_curve(cards, horizon, curve, taken, ceiling)
        return Plan(horizon, cards, before, after, new_due, curve[:horizon])
    if method == "gaps":
        after, new_due = fill_gaps(cards, horizon, taken, ceiling)
    else:
        after, new_due = smooth(cards, horizon, allow_postpone, taken, ceiling)
    return Plan(horizon, cards, before, after, new_due)


# Smoothing methods, in the order of the dialog's list: a regular staircase
# (`smooth`), only the gaps (`fill_gaps`), a custom curve (`follow_curve`).
METHODS = ("auto", "gaps", "custom")


def default_settings(before: List[int]) -> CurveSettings:
    """Starting point of a deck's custom curve: tomorrow's cards as they are,
    no drop, towards the average of the window."""
    tomorrow = before[0] if before else 0
    average = round(sum(before) / len(before)) if before else 0
    return CurveSettings(
        tomorrow=tomorrow,
        drop_day2=0,
        drop_day3=0,
        floor=min(tomorrow, average),
        strength=20.0,
    )


def settings_to_config(settings: CurveSettings) -> Dict[str, object]:
    return {
        "tomorrow": settings.tomorrow,
        "drop_day2": settings.drop_day2,
        "drop_day3": settings.drop_day3,
        "floor": settings.floor,
        "strength": settings.strength,
        # As in the spreadsheet: a x 10,000, a whole number.
        "slope_x10000": round(settings.slope * 10000),
    }


def settings_from_config(values: Dict[str, object]) -> CurveSettings:
    return CurveSettings(
        tomorrow=int(values.get("tomorrow", 0)),  # type: ignore[arg-type]
        drop_day2=int(values.get("drop_day2", 0)),  # type: ignore[arg-type]
        drop_day3=int(values.get("drop_day3", 0)),  # type: ignore[arg-type]
        floor=int(values.get("floor", 0)),  # type: ignore[arg-type]
        strength=float(values.get("strength", 20.0)),  # type: ignore[arg-type]
        slope=int(values.get("slope_x10000", 0)) / 10000,  # type: ignore[arg-type]
    )


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
        self.horizon.setRange(7, RANGES[-1][1])
        self.horizon.setSuffix(tr("days_suffix"))
        self.horizon.setValue(int(config.get("horizon_days", 90)))

        self.postpone = QCheckBox(tr("postpone", margin=tr.percent(POSTPONE_MARGIN)))
        self.postpone.setChecked(bool(config.get("allow_postpone", False)))

        # How to smooth (see METHODS), remembered per deck.
        self.method = QComboBox()
        for method in METHODS:
            self.method.addItem(tr(f"method_{method}"), method)

        # The custom curve's settings, as in the author's spreadsheet,
        # remembered per deck; shown for the "custom" method only. Its title
        # folds the fields away; they unfold whenever that method is chosen.
        self.curve_box = QGroupBox()
        box_layout = QVBoxLayout(self.curve_box)
        self.curve_toggle = QToolButton()
        self.curve_toggle.setText(tr("curve_title"))
        self.curve_toggle.setToolTip(tr("curve_toggle"))
        self.curve_toggle.setCheckable(True)
        self.curve_toggle.setAutoRaise(True)
        self.curve_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        title_font = self.curve_toggle.font()
        title_font.setBold(True)
        self.curve_toggle.setFont(title_font)
        qconnect(self.curve_toggle.toggled, self.show_curve_fields)
        self.curve_panel = QWidget()
        curve_form = QFormLayout(self.curve_panel)
        curve_form.setContentsMargins(0, 0, 0, 0)
        self.curve_fields: Dict[str, QSpinBox] = {}
        for key in ("tomorrow", "drop_day2", "drop_day3", "floor", "slope_x10000"):
            field = QSpinBox()
            field.setRange(0, 100000)
            self.curve_fields[key] = field
        self.strength = QDoubleSpinBox()
        self.strength.setDecimals(2)
        self.strength.setRange(0.01, 10000)
        self.strength.setSingleStep(0.1)
        curve_form.addRow(tr("curve_tomorrow"), self.curve_fields["tomorrow"])
        curve_form.addRow(tr("curve_drop_day2"), self.curve_fields["drop_day2"])
        curve_form.addRow(tr("curve_drop_day3"), self.curve_fields["drop_day3"])
        curve_form.addRow(tr("curve_floor"), self.curve_fields["floor"])
        curve_form.addRow(tr("curve_strength"), self.strength)
        curve_form.addRow(tr("curve_slope"), self.curve_fields["slope_x10000"])
        curve_hint = QLabel(tr("curve_hint"))
        curve_hint.setWordWrap(True)
        curve_hint.setEnabled(False)
        curve_form.addRow(curve_hint)
        # The curve's total against the cards due stays shown when folded.
        self.curve_total = QLabel()
        self.curve_total.setWordWrap(True)
        box_layout.addWidget(self.curve_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        box_layout.addWidget(self.curve_panel)
        box_layout.addWidget(self.curve_total)
        self.shown_method: Optional[str] = None

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
        form.addRow(tr("method"), self.method)
        form.addRow("", self.postpone)
        form.addRow(self.curve_box)

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

        self.load_deck_settings()
        qconnect(self.deck.currentTextChanged, self.on_deck_changed)
        qconnect(self.horizon.valueChanged, self.refresh)
        qconnect(self.postpone.toggled, self.refresh)
        qconnect(self.method.currentIndexChanged, self.on_settings_changed)
        for field in self.curve_fields.values():
            qconnect(field.valueChanged, self.on_settings_changed)
        qconnect(self.strength.valueChanged, self.on_settings_changed)
        restoreGeom(self, GEOMETRY_KEY, default_size=self.default_size())
        self.refresh()

    # Per-deck settings, in the add-on's config: {"decks": {name: {"method":
    # ..., "curve": {...}}}}.

    def deck_config(self) -> Dict[str, object]:
        config = mw.addonManager.getConfig(__name__) or {}
        return dict(config.get("decks", {}).get(self.deck.currentText(), {}))

    def load_deck_settings(self) -> None:
        """Show the method and curve saved for the selected deck, or the
        defaults, without triggering refreshes or saves."""
        config = mw.addonManager.getConfig(__name__) or {}
        saved = self.deck_config()
        method = str(saved.get("method", config.get("method", "auto")))
        curve = saved.get("curve")
        if isinstance(curve, dict):
            settings = settings_from_config(curve)
        else:
            before = make_plan(
                mw.col, self.deck.currentText(), self.horizon.value(), "auto"
            ).before
            settings = default_settings(before)
        widgets = [self.method, self.strength, *self.curve_fields.values()]
        for widget in widgets:
            widget.blockSignals(True)
        self.method.setCurrentIndex(max(0, self.method.findData(method)))
        for key, value in settings_to_config(settings).items():
            if key in self.curve_fields:
                self.curve_fields[key].setValue(int(value))  # type: ignore[arg-type]
        self.strength.setValue(settings.strength)
        for widget in widgets:
            widget.blockSignals(False)
        self.update_method_widgets()

    def curve_settings(self) -> CurveSettings:
        values: Dict[str, object] = {k: f.value() for k, f in self.curve_fields.items()}
        values["strength"] = self.strength.value()
        return settings_from_config(values)

    def save_deck_settings(self) -> None:
        config = mw.addonManager.getConfig(__name__) or {}
        decks = dict(config.get("decks", {}))
        entry: Dict[str, object] = {"method": self.method.currentData()}
        # The curve is kept once it has been shown, even with another method.
        saved_curve = self.deck_config().get("curve")
        if self.method.currentData() == "custom" or saved_curve is not None:
            entry["curve"] = settings_to_config(self.curve_settings())
        decks[self.deck.currentText()] = entry
        config["decks"] = decks
        mw.addonManager.writeConfig(__name__, config)

    def on_deck_changed(self) -> None:
        self.load_deck_settings()
        self.refresh()

    def on_settings_changed(self) -> None:
        self.update_method_widgets()
        self.save_deck_settings()
        self.refresh()

    def update_method_widgets(self) -> None:
        method = self.method.currentData()
        # Postponing is the "auto" method's option; the custom curve
        # postpones whatever it needs to.
        self.postpone.setVisible(method == "auto")
        self.curve_box.setVisible(method == "custom")
        # Unfolded each time the custom method is chosen (or opened with).
        if method == "custom" and self.shown_method != "custom":
            self.curve_toggle.setChecked(True)
            self.show_curve_fields(True)
        self.shown_method = method

    def show_curve_fields(self, shown: bool) -> None:
        self.curve_panel.setVisible(shown)
        self.curve_toggle.setArrowType(
            Qt.ArrowType.DownArrow if shown else Qt.ArrowType.RightArrow
        )

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
            self.method.currentData(),
            self.postpone.isChecked(),
            self.curve_settings(),
        )
        plan = self.plan
        tr = self.tr
        if plan.curve is not None:
            self.curve_total.setText(self.describe_curve(plan))
        data = {
            "before": plan.before,
            "after": plan.after,
            # Drawn on the "after" graph (custom curve only).
            "curve": plan.curve,
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

    def describe_curve(self, plan: Plan) -> str:
        """The custom curve's total against the cards due, as in the
        spreadsheet's totals, and what that implies."""
        tr = self.tr
        curve = plan.curve or []
        pulled = sum(
            1 for c in plan.cards if c.due > plan.horizon >= plan.new_due[c.id]
        )
        short = sum(curve) - sum(plan.after)
        sentences = [
            tr("curve_total", curve=sum(curve), days=plan.horizon, due=sum(plan.before))
        ]
        if plan.postponed_out:
            sentences.append(tr("curve_postponed", count=plan.postponed_out))
        if pulled:
            sentences.append(tr("curve_pulled", count=pulled))
        if short:
            sentences.append(tr("curve_short", count=short))
        return " ".join(sentences)

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
