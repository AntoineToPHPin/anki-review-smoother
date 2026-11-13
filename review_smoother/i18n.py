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
        "method": "Method:",
        "method_auto": "Smooth into a regular staircase",
        "method_gaps": "Only fill the gaps, keeping the current shape of the curve",
        "method_custom": "Follow a custom curve",
        "curve_title": "Custom curve (remembered for this deck)",
        "curve_tomorrow": "Cards tomorrow (day 1):",
        "curve_drop_day2": "Drop from day 1 to day 2:",
        "curve_drop_day3": "Drop from day 2 to day 3:",
        "curve_floor": "Long-term reviews:",
        "curve_strength": "Memory strength:",
        "curve_slope": "Slope after day 90 (× 10,000):",
        "curve_hint": (
            "From day 3 to day 90, the curve goes down towards the long-term "
            "reviews following Ebbinghaus's forgetting curve, e^(−t / strength); "
            "after day 90, it goes down in a straight line, by slope / 10,000 "
            "cards a day."
        ),
        "curve_total": "The curve plans {curve} cards over {days} days, for {due} cards due.",
        "curve_postponed_one": "{count} card will be postponed to right after the period.",
        "curve_postponed_other": (
            "{count} cards will be postponed to right after the period."
        ),
        "curve_pulled_one": "{count} card due after the period will be advanced into it.",
        "curve_pulled_other": (
            "{count} cards due after the period will be advanced into it."
        ),
        "curve_short_one": "{count} card is missing: the end of the period stays below the curve.",
        "curve_short_other": (
            "{count} cards are missing: the end of the period stays below the curve."
        ),
        "zoom_hint": "Mouse wheel: zoom · Drag: move · Double click: show all days",
        "show_moved": "Show cards to move",
        "stats_link_tip": "Smooth this workload",
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
        "added_cards": "Cards added",
        "removed_cards": "Cards removed",
        "target_curve": "Target curve",
        "vs_before": "{diff} compared with before",
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
        "method": f"Méthode{NBSP}:",
        "method_auto": "Lisser en escalier régulier",
        "method_gaps": "Combler seulement les creux, en gardant la forme actuelle de la courbe",
        "method_custom": "Suivre une courbe personnalisée",
        "curve_title": "Courbe personnalisée (mémorisée pour ce paquet)",
        "curve_tomorrow": f"Cartes demain (J1){NBSP}:",
        "curve_drop_day2": f"Écart entre J1 et J2{NBSP}:",
        "curve_drop_day3": f"Écart entre J2 et J3{NBSP}:",
        "curve_floor": f"Révisions à long terme{NBSP}:",
        "curve_strength": f"Force de la mémoire{NBSP}:",
        "curve_slope": f"Pente après J90 (× 10{NBSP}000){NBSP}:",
        "curve_hint": (
            "De J3 à J90, la courbe descend vers les révisions à long terme "
            "selon la courbe de l’oubli d’Ebbinghaus, e^(−t / force)"
            f"{NBSP}; après J90, elle descend en ligne droite, de pente / "
            f"10{NBSP}000 carte par jour."
        ),
        "curve_total": (
            "La courbe prévoit {curve} cartes sur {days} jours, pour {due} cartes dues."
        ),
        "curve_postponed_one": "{count} carte sera reportée juste après la période.",
        "curve_postponed_other": (
            "{count} cartes seront reportées juste après la période."
        ),
        "curve_pulled_one": (
            "{count} carte due après la période sera avancée dans celle-ci."
        ),
        "curve_pulled_other": (
            "{count} cartes dues après la période seront avancées dans celle-ci."
        ),
        "curve_short_one": (
            f"Il manque {{count}} carte{NBSP}: la fin de la période restera sous la courbe."
        ),
        "curve_short_other": (
            f"Il manque {{count}} cartes{NBSP}: la fin de la période restera sous "
            "la courbe."
        ),
        "zoom_hint": (
            f"Molette{NBSP}: zoomer · Glisser{NBSP}: déplacer · "
            f"Double-clic{NBSP}: afficher tous les jours"
        ),
        "show_moved": "Voir les cartes à déplacer",
        "stats_link_tip": "Lisser cette charge de travail",
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
        "added_cards": "Cartes ajoutées",
        "removed_cards": "Cartes retirées",
        "target_curve": "Courbe visée",
        "vs_before": "{diff} par rapport à avant",
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
            "addedCards": self("added_cards"),
            "removedCards": self("removed_cards"),
            "targetCurve": self("target_curve"),
            "vsBefore": STRINGS[self.lang]["vs_before"],
            "colon": self("colon"),
            "zeroIsSingular": self.is_singular(0),
        }
