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
        "range_two_years": "2 years",
        "postpone": (
            "Postpone a few cards when it lowers the start of the curve "
            "(by at most {margin} of their interval)"
        ),
        "method": "Method:",
        "method_auto": "Smooth into a regular staircase",
        "method_custom": "Follow a custom curve",
        "curve_title": "Custom curve (remembered for this deck)",
        "curve_toggle": "Show or hide the curve's settings",
        "curve_tomorrow": "Cards tomorrow (day 1):",
        "curve_drop_day2": "Drop from day 1 to day 2:",
        "curve_drop_day3": "Drop from day 2 to day 3:",
        "curve_floor": "Cards on day 90:",
        "curve_strength": "Memory strength:",
        "curve_slope": "Slope after day 90 (× 10,000):",
        "curve_hint": (
            "From day 3 to day 90, the curve goes down towards the cards on day 90 "
            "following Ebbinghaus's forgetting curve, e^(−t / strength); "
            "after day 90, it goes down in a straight line from there, by "
            "slope / 10,000 cards a day."
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
        "reposition_menu": "Reposition new cards…",
        "reposition_button": "Reposition",
        "reposition_title": "Reposition new cards",
        "reposition_mode": "Mode:",
        "reposition_sequential": "In a row",
        "reposition_blocks": "By blocks",
        "reposition_block_size": "Block size:",
        "reposition_first_block": "First block from:",
        "reposition_blocks_hint": (
            "The cards of each block (positions {first}–{first_end}, then {next}–{next_end}…) "
            "move up to the start of their block, in the same order. Cards that run on into "
            "the next block without a gap move up with it, as a whole. Cards placed before "
            "{first} stay where they are."
        ),
        "reposition_start": "Start position:",
        "reposition_step": "Step:",
        "reposition_shuffle": "Shuffle the cards (card by card, not note by note)",
        "reposition_reshuffle": "Shuffle again",
        "reposition_spacing_one": (
            "Sibling cards are kept at least {count} position apart, so that they are "
            "not introduced on the same day ({count} new card a day)."
        ),
        "reposition_spacing_other": (
            "Sibling cards are kept at least {count} positions apart, so that they are "
            "not introduced on the same day ({count} new cards a day)."
        ),
        "reposition_new": "New position",
        "reposition_current": "Current position",
        "reposition_card": "Card",
        "reposition_none": "No new card in this deck.",
        "reposition_in_place_one": "{count} new card, already in place.",
        "reposition_in_place_other": "{count} new cards, already in place.",
        "reposition_will_change_one": "{count} of {total} new cards will change position.",
        "reposition_will_change_other": "{count} of {total} new cards will change position.",
        "reposition_close_siblings_one": (
            "Some sibling cards could not be kept apart: they follow each other."
        ),
        "reposition_close_siblings_other": (
            "Some sibling cards could only be kept {count} positions apart."
        ),
        "reposition_applied_one": "{count} card repositioned. Undo with Edit > Undo.",
        "reposition_applied_other": "{count} cards repositioned. Undo with Edit > Undo.",
        "tracking_note_type": "Review Smoother tracking",
        "tracking_deck_field": "Deck",
        "tracking_history_field": "History",
        "tracking_card": "Tracking",
        "tracking_deck": "_Review Smoother",
        "tracking_date": "Date",
        "tracking_column": "Shown",
        "tracking_month": "1 month",
        "tracking_quarter": "3 months",
        "tracking_year": "1 year",
        "tracking_all": "All",
        "tracking_empty": "No data yet.",
        "tracking_invalid": "The history cannot be read.",
        "tracking_col_tomorrow": "Cards tomorrow (day 1)",
        "tracking_col_drop_day2": "Drop from day 1 to day 2",
        "tracking_col_drop_day3": "Drop from day 2 to day 3",
        "tracking_col_floor": "Cards on day 90",
        "tracking_col_strength": "Memory strength",
        "tracking_col_slope_x10000": "Slope after day 90 (× 10,000)",
        "tracking_col_new_cards": "New cards today",
        "tracking_col_learned": "Cards learned in the deck",
        "tracking_col_remark": "Remark",
        "tracking_default_table": "Tracking",
        "tracking_total_month": "Total over a month",
        "tracking_total_quarter": "Total over three months",
        "tracking_total_year": "Total over a year",
        "tracking_button": "Record today’s tracking…",
        "tracking_button_tip": "For the custom curve: records its settings in the deck’s tracking note (synced, shown in AnkiDroid).",
        "tracking_button_disabled": "Only with the custom curve.",
        "tracking_title": "Today’s tracking — {deck}",
        "tracking_day": "Day: {date}",
        "tracking_hint": "The settings of the custom curve shown; you can change them.",
        "tracking_replace": "This day is already recorded: its row will be replaced.",
        "tracking_new_note": "First record for this deck: its tracking note will be created in the deck “{deck}”.",
        "tracking_saved": "Today’s tracking recorded.",
        "tracking_undo": "Record tracking",
    },
    "fr": {
        "deck": f"Paquet{NBSP}:",
        "horizon": f"Lisser sur{NBSP}:",
        "days_suffix": " jours",
        "range_month": "1 mois",
        "range_three_months": "3 mois",
        "range_year": "1 an",
        "range_two_years": "2 ans",
        "postpone": (
            "Reporter quelques cartes quand cela abaisse le début de la courbe "
            "(d’au plus {margin} de leur intervalle)"
        ),
        "method": f"Méthode{NBSP}:",
        "method_auto": "Lisser en escalier régulier",
        "method_custom": "Suivre une courbe personnalisée",
        "curve_title": "Courbe personnalisée (mémorisée pour ce paquet)",
        "curve_toggle": "Afficher ou masquer les réglages de la courbe",
        "curve_tomorrow": f"Cartes demain (J1){NBSP}:",
        "curve_drop_day2": f"Écart entre J1 et J2{NBSP}:",
        "curve_drop_day3": f"Écart entre J2 et J3{NBSP}:",
        "curve_floor": f"Cartes à J90{NBSP}:",
        "curve_strength": f"Force de la mémoire{NBSP}:",
        "curve_slope": f"Pente après J90 (× 10{NBSP}000){NBSP}:",
        "curve_hint": (
            "De J3 à J90, la courbe descend vers les cartes à J90 "
            "selon la courbe de l’oubli d’Ebbinghaus, e^(−t / force)"
            f"{NBSP}; après J90, elle descend de là en ligne droite, de pente / "
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
        "reposition_menu": "Repositionner les nouvelles cartes…",
        "reposition_button": "Repositionner",
        "reposition_title": "Repositionner les nouvelles cartes",
        "reposition_mode": f"Mode{NBSP}:",
        "reposition_sequential": "À la suite",
        "reposition_blocks": "Par blocs",
        "reposition_block_size": f"Taille des blocs{NBSP}:",
        "reposition_first_block": f"Premier bloc à partir de{NBSP}:",
        "reposition_blocks_hint": (
            "Les cartes de chaque bloc (positions {first} à {first_end}, puis {next} à "
            "{next_end}…) remontent au début de leur bloc, dans le même ordre. Les cartes "
            "qui débordent sur le bloc suivant sans trou remontent avec lui, d’un seul tenant. "
            "Les cartes placées avant {first} ne bougent pas."
        ),
        "reposition_start": f"Position de départ{NBSP}:",
        "reposition_step": f"Pas{NBSP}:",
        "reposition_shuffle": "Mélanger les cartes (carte par carte, pas note par note)",
        "reposition_reshuffle": "Mélanger à nouveau",
        "reposition_spacing_one": (
            "Les cartes sœurs sont écartées d’au moins {count} position, pour ne pas "
            "être introduites le même jour ({count} nouvelle carte par jour)."
        ),
        "reposition_spacing_other": (
            "Les cartes sœurs sont écartées d’au moins {count} positions, pour ne pas "
            "être introduites le même jour ({count} nouvelles cartes par jour)."
        ),
        "reposition_new": "Nouvelle position",
        "reposition_current": "Position actuelle",
        "reposition_card": "Carte",
        "reposition_none": "Aucune nouvelle carte dans ce paquet.",
        "reposition_in_place_one": "{count} nouvelle carte, déjà en place.",
        "reposition_in_place_other": "{count} nouvelles cartes, déjà en place.",
        "reposition_will_change_one": (
            "{count} nouvelle carte sur {total} changera de position."
        ),
        "reposition_will_change_other": (
            "{count} nouvelles cartes sur {total} changeront de position."
        ),
        "reposition_close_siblings_one": (
            f"Certaines cartes sœurs n’ont pas pu être écartées{NBSP}: elles se suivent."
        ),
        "reposition_close_siblings_other": (
            "Certaines cartes sœurs n’ont pu être écartées que de {count} positions."
        ),
        "reposition_applied_one": (
            f"{{count}} carte repositionnée. Pour annuler{NBSP}: Édition > Annuler."
        ),
        "reposition_applied_other": (
            f"{{count}} cartes repositionnées. Pour annuler{NBSP}: Édition > Annuler."
        ),
        "tracking_note_type": "Review Smoother – Suivi",
        "tracking_deck_field": "Paquet",
        "tracking_history_field": "Historique",
        "tracking_card": "Suivi",
        "tracking_deck": "_Review Smoother",
        "tracking_date": "Date",
        "tracking_column": "Affiché",
        "tracking_month": "1 mois",
        "tracking_quarter": "3 mois",
        "tracking_year": "1 an",
        "tracking_all": "Tout",
        "tracking_empty": "Aucune donnée pour l’instant.",
        "tracking_invalid": "L’historique est illisible.",
        "tracking_col_tomorrow": "Cartes demain (J1)",
        "tracking_col_drop_day2": "Écart entre J1 et J2",
        "tracking_col_drop_day3": "Écart entre J2 et J3",
        "tracking_col_floor": "Cartes à J90",
        "tracking_col_strength": "Force de la mémoire",
        "tracking_col_slope_x10000": f"Pente après J90 (× 10{NBSP}000)",
        "tracking_col_new_cards": "Nouvelles cartes du jour",
        "tracking_col_learned": "Cartes apprises du paquet",
        "tracking_col_remark": "Remarque",
        "tracking_default_table": "Suivi",
        "tracking_total_month": "Total à un mois",
        "tracking_total_quarter": "Total à trois mois",
        "tracking_total_year": "Total à un an",
        "tracking_button": "Enregistrer le suivi du jour…",
        "tracking_button_tip": f"Pour la courbe personnalisée{NBSP}: enregistre ses réglages dans la note de suivi du paquet (synchronisée, visible dans AnkiDroid).",
        "tracking_button_disabled": "Seulement avec la courbe personnalisée.",
        "tracking_title": "Suivi du jour — {deck}",
        "tracking_day": f"Jour{NBSP}: {{date}}",
        "tracking_hint": "Réglages de la courbe personnalisée affichée, modifiables.",
        "tracking_replace": f"Ce jour est déjà enregistré{NBSP}: sa ligne sera remplacée.",
        "tracking_new_note": f"Premier enregistrement pour ce paquet{NBSP}: sa note de suivi sera créée dans le paquet «{NBSP}{{deck}}{NBSP}».",
        "tracking_saved": "Suivi du jour enregistré.",
        "tracking_undo": "Enregistrer le suivi",
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
