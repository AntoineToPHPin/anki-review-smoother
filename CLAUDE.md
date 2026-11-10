# Review Smoother — context for agents

Anki add-on ("Review Smoother" on AnkiWeb; repo `anki-review-smoother`) that reshapes each deck's upcoming review forecast into a smooth descending curve — e.g. 4/day, then 3/day, then 2/day — instead of a jagged 5, 2, 4, 3… It only moves due dates; it never changes how many cards there are.

The author discusses in French; everything in the repo (code, comments, README, UI strings) is English because the add-on is meant for wide sharing. A French UI translation is planned.

> **Keep this file up to date** without being asked: remove open items once resolved, add durable conventions, design decisions and gotchas. Only what someone resuming cold needs — not task-by-task progress.

## Design decisions (agreed with the author)

- **Target curve**: computed automatically per deck, then adjustable by the user per deck.
- **Moves**: cards are almost always *advanced*. Postponing is a rare exception (not implemented yet).
- **Horizon**: 90 days by default, configurable. Day 1 = tomorrow; today, overdue, new, learning, suspended and buried cards, and cards due after the horizon are never touched.
- **Trigger**: manual only — a menu action opening a dialog with a before/after preview, confirmation, and undo.
- **Preview graph**: must look like Anki's Statistics "Future Due" graph (French UI: « Charge de travail », ftl key `statistics-future-due-title`). Reimplement it — do not copy Anki's code (AGPL; this repo is MIT).
- Only the due date changes; the interval is kept.

## Layout

- `review_smoother/` — the add-on folder itself (what gets installed in `addons21/`).
  - `smoothing.py` — pure logic. **Must not import `anki`/`aqt`**, so tests and tools can import it outside Anki.
  - `__init__.py` — Anki entry point (integration not written yet). When adding Anki imports there, keep `review_smoother.smoothing` importable outside Anki (tests import the package).
- `tests/` — `unittest` only (stdlib, no dependency): `python -m unittest` from the repo root.
- `tools/simulate.py` — **read-only** simulation on the real collection through AnkiConnect (`localhost:8765`, Anki must be running): `python tools/simulate.py "Deck::Name" [--horizon 90]`. On Windows, prefix with `PYTHONIOENCODING=utf-8` for accented deck names in the output.

## Algorithm (`smoothing.py`)

- `auto_curve(counts)`: upper concave hull of the cumulative due counts = the lowest non-increasing *fractional* daily rate that never falls behind what is due (so advancing alone is always enough). Rounded **down** to whole cards on the cumulative curve — still ≥ the integer due counts, and moves cards less than rounding up. The alternating rounding (4, 3, 4, 3… / 1, 0, 1, 1, 0…) is then sorted descending into a staircase; sorting only moves cards earlier, so the constraint holds. **Sparse decks (< 1 card/day) end as a block of 1s followed by 0s — the author's explicit choice** (2026-11-10), rather than spacing 1 card every n days or a density that keeps decreasing below 1/day. Downside: on such decks some cards are advanced a large share of their interval (up to ~50% seen on `Informatique::PHP`). Accepted as is: the user picks which decks to smooth, and would not smooth a deck that sparse — so no max-advance limit for now.
- `assign(cards, target)`: fills days from the last one backwards, each day taking the available cards (due on or after it) with the **shortest interval** first. This minimises the total relative advance Σ (due − new_due) / interval — proven against brute force in the tests. Raises `InfeasibleCurve` if the target would need postponing.

## Environment gotchas

- AnkiConnect requests must be sent as UTF-8 bytes; non-ASCII deck names fail otherwise.
- AnkiConnect has no "today" action: `simulate.py` deduces Anki's day number from a card found with `prop:due=N`.
- Target Python: Anki 26.09 bundles Python 3.13, but keep the code compatible with older Anki versions' Python 3.9 (`from __future__ import annotations`, no `match`, no `X | Y` at runtime).

## Open items

- **Anki integration**: menu entry, deck selection dialog, Future-Due-style before/after graph, apply with undo (`CollectionOp`), config (`config.json` + `config.md`, horizon default 90), `manifest.json`.
- **User-adjusted curves**: input format (e.g. `4x14, 3x28, 2x48`), and what to do when its total differs from the number of cards in the window.
- **Postponing as an exception**: needed when a user curve, or an early spike, cannot be met by advancing alone.
- **Window edge**: cards just past the horizon are ignored, so the curve may drop at the very end (e.g. `…2211`); consider letting them be pulled into the window.
- Sibling cards (same note) may land on the same day; not handled yet.
- Local dev install: link `review_smoother/` into `%APPDATA%\Anki2\addons21\`.
