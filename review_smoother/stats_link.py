"""Link to Review Smoother next to the Future Due graph of the Statistics window.

The Statistics window (`aqt.stats.NewDeckStats`) is a web page built by Anki
after it loads; each graph has an `<h1>` title. A script finds the Future Due
title (« Charge de travail ») and appends a link to it, again whenever the
page redraws. A click sends a bridge command, handled here.
"""

from __future__ import annotations

import json
from typing import Any, Tuple

import anki.lang
from aqt import gui_hooks, mw
from aqt.qt import QTimer
from aqt.stats import NewDeckStats

from .i18n import Translator

COMMAND = "review_smoother:open"

LINK_SCRIPT = """
(() => {
    if (window.reviewSmootherLink) {
        return;
    }
    window.reviewSmootherLink = true;
    const title = %(title)s;
    const addLink = () => {
        for (const h1 of document.querySelectorAll("h1")) {
            if (h1.querySelector(".review-smoother-link")) {
                continue;
            }
            // The title's own text, without what may have been added to it.
            const text = [...h1.childNodes]
                .filter((node) => node.nodeType === Node.TEXT_NODE)
                .map((node) => node.nodeValue)
                .join("")
                .trim();
            if (text !== title) {
                continue;
            }
            // A plain <button>: the page gives it Anki's button look, in light
            // and night mode; only its size is set here.
            const button = document.createElement("button");
            button.type = "button";
            button.className = "review-smoother-link";
            button.textContent = %(label)s;
            button.title = %(tip)s;
            button.style.cssText =
                "margin-left: 0.75em; padding: 0.15em 0.7em; font-size: 0.55em;"
                + " font-weight: normal; vertical-align: middle;";
            button.addEventListener("click", () => pycmd(%(command)s));
            h1.appendChild(button);
        }
    };
    addLink();
    // The page builds its graphs after loading and redraws them (deck,
    // period...): add the link again whenever needed.
    new MutationObserver(addLink).observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
    });
})();
"""


def link_script() -> str:
    tr = Translator(anki.lang.current_lang)
    return LINK_SCRIPT % {
        "title": json.dumps(mw.col.tr.statistics_future_due_title()),
        "label": json.dumps("Review Smoother"),
        "tip": json.dumps(tr("stats_link_tip")),
        "command": json.dumps(COMMAND),
    }


def on_stats_dialog(dialog: NewDeckStats) -> None:
    """Add the link each time the page loads (the window reloads it when the
    deck changes)."""
    web = dialog.form.web
    web.loadFinished.connect(lambda ok: ok and web.eval(link_script()))


def on_js_message(handled: Tuple[bool, Any], message: str, context: Any) -> Tuple[bool, Any]:
    if message != COMMAND or not isinstance(context, NewDeckStats):
        return handled
    from .ui import open_dialog

    deck = stats_deck_name(context)

    def reload_stats() -> None:
        try:
            context.refresh()
        except RuntimeError:  # the Statistics window was closed meanwhile
            pass

    # Opened once the bridge call has returned, not inside it: the dialog
    # runs its own event loop. The graphs are reloaded once applied.
    QTimer.singleShot(0, lambda: open_dialog(deck=deck, on_applied=reload_stats))
    return (True, None)


def stats_deck_name(stats: NewDeckStats) -> str:
    """Deck shown in the Statistics window, or the current deck."""
    chooser = getattr(stats, "deck_chooser", None)
    name = getattr(chooser, "selected_deck_name", None)
    if callable(name):  # a method in some Anki versions
        name = name()
    return name or mw.col.decks.current()["name"]


def setup_stats_link() -> None:
    gui_hooks.stats_dialog_will_show.append(on_stats_dialog)
    gui_hooks.webview_did_receive_js_message.append(on_js_message)
