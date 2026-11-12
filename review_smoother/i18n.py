"""User-facing strings, in English and French.

No Anki imports: the UI passes Anki's current language, tools pass "en".
French wording follows Anki's own French translation where it has an
equivalent ("Total cumulé", "Demain", "Dans 3 jours", "Paquet").

Keys ending in `_one` / `_other` are plural forms, picked by `count`.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .smoothing import MoveStats

NBSP = " "  # French puts a non-breaking space before ":" and "%"

STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "deck": "Deck:",
        "horizon": "Smooth over:",
        "days_suffix": " days",
        "range_month": "1 month",
        "range_three_months": "3 months",
        "range_year": "1 year",
        "postpone": (
            "Postpone a few cards when it lowers the start of the curve "
            "(by at most {margin} of their interval)"
        ),
        "no_cards": "No review card due in the next {days} days.",
        "already_smooth_one": "{count} card, already smooth: nothing to move.",
        "already_smooth_other": "{count} cards, already smooth: nothing to move.",
        "will_move_one": "{count} of {total} cards will move.",
        "will_move_other": "{count} of {total} cards will move.",
        "advanced_one": "1 card advanced by {days} ({share} of its interval).",
        "advanced_other": (
            "{count} cards advanced by {mean} days on average "
            "(max {max}, at most {share} of the interval)."
        ),
        "postponed_one": "1 card postponed by {days} ({share} of its interval).",
        "postponed_other": (
            "{count} cards postponed by {mean} days on average "
            "(max {max}, at most {share} of the interval)."
        ),
        "day_one": "{count} day",
        "day_other": "{count} days",
        "applied_one": "{count} card moved. Undo with Edit > Undo.",
        "applied_other": "{count} cards moved. Undo with Edit > Undo.",
        "undo": "Smooth reviews",
        "before": "Before",
        "after": "After",
        "tomorrow": "Tomorrow",
        "in_days": "In {days} days",
        "card_one": "{count} card",
        "card_other": "{count} cards",
        "running_total": "Running total",
        "colon": ":",
    },
    "fr": {
        "deck": f"Paquet{NBSP}:",
        "horizon": f"Lisser sur{NBSP}:",
        "days_suffix": " jours",
        "range_month": "1 mois",
        "range_three_months": "3 mois",
        "range_year": "1 an",
        "postpone": (
            "Reporter quelques cartes quand cela abaisse le début de la courbe "
            "(d’au plus {margin} de leur intervalle)"
        ),
        "no_cards": "Aucune carte à réviser dans les {days} prochains jours.",
        "already_smooth_one": f"{{count}} carte, déjà lissée{NBSP}: rien à déplacer.",
        "already_smooth_other": f"{{count}} cartes, déjà lissées{NBSP}: rien à déplacer.",
        "will_move_one": "{count} carte sur {total} sera déplacée.",
        "will_move_other": "{count} cartes sur {total} seront déplacées.",
        "advanced_one": "1 carte avancée de {days} ({share} de son intervalle).",
        "advanced_other": (
            "{count} cartes avancées de {mean} jours en moyenne "
            "(au plus {max}, soit au maximum {share} de l’intervalle)."
        ),
        "postponed_one": "1 carte reportée de {days} ({share} de son intervalle).",
        "postponed_other": (
            "{count} cartes reportées de {mean} jours en moyenne "
            "(au plus {max}, soit au maximum {share} de l’intervalle)."
        ),
        "day_one": "{count} jour",
        "day_other": "{count} jours",
        "applied_one": f"{{count}} carte déplacée. Pour annuler{NBSP}: Édition > Annuler.",
        "applied_other": f"{{count}} cartes déplacées. Pour annuler{NBSP}: Édition > Annuler.",
        "undo": "Lisser les révisions",
        "before": "Avant",
        "after": "Après",
        "tomorrow": "Demain",
        "in_days": "Dans {days} jours",
        "card_one": "{count} carte",
        "card_other": "{count} cartes",
        "running_total": "Total cumulé",
        "colon": f"{NBSP}:",
    },
}


class Translator:
    def __init__(self, lang: str) -> None:
        """`lang` as Anki gives it, e.g. "fr_FR" or "fr"; unknown → English."""
        code = lang.replace("-", "_").split("_")[0].lower()
        self.lang = code if code in STRINGS else "en"

    def __call__(self, key: str, count: Optional[int] = None, **values: object) -> str:
        if count is not None:
            key += "_one" if self.is_singular(count) else "_other"
            values["count"] = count
        return STRINGS[self.lang][key].format(**values)

    def is_singular(self, count: float) -> bool:
        # French uses the singular for 0 and 1, English only for 1.
        return count < 2 if self.lang == "fr" else count == 1

    def number(self, value: float, decimals: int = 0) -> str:
        text = f"{value:.{decimals}f}"
        return text.replace(".", ",") if self.lang == "fr" else text

    def percent(self, ratio: float) -> str:
        text = "<1" if 0 < ratio < 0.005 else f"{ratio * 100:.0f}"
        if self.lang == "fr":
            return text.replace("<", f"<{NBSP}") + f"{NBSP}%"
        return text + "%"

    def describe_moves(
        self, advanced: Optional[MoveStats], postponed: Optional[MoveStats]
    ) -> List[str]:
        """One sentence for the advanced cards, one for the postponed ones."""
        sentences = []
        for key, stats in (("advanced", advanced), ("postponed", postponed)):
            if stats is None:
                continue
            values: Dict[str, object] = {"share": self.percent(stats.max_share)}
            if stats.count == 1:
                values["days"] = self("day", count=stats.max_days)
            else:
                values["mean"] = self.number(stats.mean_days, 1)
                values["max"] = stats.max_days
            sentences.append(self(key, count=stats.count, **values))
        return sentences

    def graph_strings(self) -> Dict[str, object]:
        """Labels for web/graph.js; `{days}` / `{count}` are filled in JS."""
        return {
            "before": self("before"),
            "after": self("after"),
            "tomorrow": self("tomorrow"),
            "inDays": STRINGS[self.lang]["in_days"],
            "cardOne": STRINGS[self.lang]["card_one"],
            "cardOther": STRINGS[self.lang]["card_other"],
            "runningTotal": self("running_total"),
            "colon": self("colon"),
            "zeroIsSingular": self.is_singular(0),
        }
