# Review Smoother — context for agents

Anki add-on ("Review Smoother" on AnkiWeb; repo `anki-review-smoother`) that reshapes each deck's upcoming review forecast into a smooth descending curve — e.g. 4/day, then 3/day, then 2/day — instead of a jagged 5, 2, 4, 3… It only moves due dates; it never changes how many cards there are.

The author discusses in French; everything in the repo (code, comments, README, UI strings) is English because the add-on is meant for wide sharing. The UI is translated to French (see `i18n.py`).

> **Keep this file up to date** without being asked: remove open items once resolved, add durable conventions, design decisions and gotchas. Only what someone resuming cold needs — not task-by-task progress.

## Design decisions (agreed with the author)

- **Target curve**: computed automatically per deck, nothing to enter. A manual per-deck curve (e.g. `4x14, 3x28, 2x48`) was planned, then **dropped by the author on 2026-11-11**: the automatic curve suits them. Don't reintroduce it unless asked (if it ever is: a fixed curve rarely matches the day's card count, so it needs a policy such as "cap per day, filled from day 1" vs "proportional rescale").
- **Moves**: cards are almost always *advanced*. Postponing is the exception (decided 2026-11-11): margin **10% of the interval**, **longest intervals first**, budget **1% of the window's cards (at least 1)**, used **only to lower the peak at the start of the curve**. On by default (`allow_postpone` config), with a dialog checkbox to turn it off that recomputes the preview instantly.
- **Horizon**: 90 days by default, configurable. Day 1 = tomorrow; today, overdue, new, learning, suspended and buried cards, and cards due after the horizon are never touched.
- **Trigger**: manual only — a menu action opening a dialog with a before/after preview, confirmation, and undo.
- **Preview graph**: must look like Anki's Statistics "Future Due" graph (French UI: « Charge de travail », ftl key `statistics-future-due-title`). Reimplement it — do not copy Anki's code (AGPL; this repo is MIT).
- Only the due date changes; the interval is kept.

## Layout

- `review_smoother/` — the add-on folder itself (what gets installed in `addons21/`).
  - `smoothing.py` — pure logic. **Must not import `anki`/`aqt`**, so tests and tools can import it outside Anki.
  - `__init__.py` — Anki entry point. Only imports `ui` when `aqt.mw` exists, so the package (and `smoothing`) stays importable outside Anki for tests and tools.
  - `web/graph.js` + `web/graph.css` — before/after graphs (inline SVG, no library), shown in an `AnkiWebView` in the dialog: files are read and inlined into `stdHtml()`, then `render({before, after})` is called via `web.eval()` (queued by Anki until the page is ready). Look copied from Anki's Future Due graph by inspecting its bundle (`_aqt/data/web/sveltekit/.../nodes/7.*.mjs` + assets CSS): ColorBrewer Greens from 0.7 (tomorrow) to 0.3 (horizon), translucent running-total area with a right axis (`--area-*` variables, light/night), tick text opacity .5 / 10px, grid opacity .1, gray hover columns. The tooltip is `position: fixed` and kept inside the viewport (flipped above/left of the cursor when needed): positioned in the page, it extended it near the bottom and made a scrollbar appear on hover. Differences on purpose: one bar per day (Anki bins 2 days in its 3-month view) and a shared y scale for both graphs. Quick visual check outside Anki: build a page with the two files + `render(...)` and screenshot it with headless Edge (`msedge --headless --screenshot`).
  - `i18n.py` — every user-facing string, English + French, in `STRINGS` (no Anki import). `Translator(anki.lang.current_lang)` picks the language from Anki's interface (`fr_FR` → French, unknown → English); keys `x_one`/`x_other` are plurals chosen by `count` (French: 0 and 1 are singular). French follows Anki's own French wording (« Total cumulé », « Demain », « Dans 3 jours », « Paquet ») and typography (decimal comma, non-breaking space before `:` and `%`, typographic apostrophe). **Any new string goes into both languages**: `tests/test_i18n.py` fails if keys or placeholders differ. The graph gets its labels from `Translator.graph_strings()` inside the `render()` data. Qt's standard buttons (Apply/Close) are translated by Qt itself. `config.md` stays English.
  - `ui.py` — Tools menu entry + dialog: deck, horizon, before/after graphs, summary, Apply. `done()` calls `web.cleanup()`. `make_plan()` (read-only) / `apply_plan()` (sets `card.due`, wrapped in `add_custom_undo_entry` + `merge_undo_entries` so it is one undo step, run via `CollectionOp`).
  - `config.json` / `config.md` — `horizon_days` (default 90), `allow_postpone` (default true).
- `tests/` — `unittest` only (stdlib, no dependency): `python -m unittest` from the repo root.
- `tools/simulate.py` — **read-only** simulation on the real collection through AnkiConnect (`localhost:8765`, Anki must be running): `python tools/simulate.py "Deck::Name" [--horizon 90] [--no-postpone]`. On Windows, prefix with `PYTHONIOENCODING=utf-8` for accented deck names in the output.

## Algorithm (`smoothing.py`)

- `auto_curve(counts)`: upper concave hull of the cumulative due counts = the lowest non-increasing *fractional* daily rate that never falls behind what is due (so advancing alone is always enough). Rounded **down** to whole cards on the cumulative curve — still ≥ the integer due counts, and moves cards less than rounding up. The alternating rounding (4, 3, 4, 3… / 1, 0, 1, 1, 0…) is then sorted descending into a staircase; sorting only moves cards earlier, so the constraint holds. **Sparse decks (< 1 card/day) end as a block of 1s followed by 0s — the author's explicit choice** (2026-11-10), rather than spacing 1 card every n days or a density that keeps decreasing below 1/day. Downside: on such decks some cards are advanced a large share of their interval (up to ~50% seen on `Informatique::PHP`). Accepted as is: the user picks which decks to smooth, and would not smooth a deck that sparse — so no max-advance limit for now.
- `smooth(cards, horizon, allow_postpone)`: entry point used by the UI and `simulate.py`. Starts from `auto_curve`; if allowed, tries to lower the first value (the peak) one card/day at a time via `_postpone_to_cap` (forward sweep: whenever cards due on days 1..k exceed cap·k, push one card a day later — preferably one already pushed, to postpone few distinct cards; else longest interval; tie → due latest, to push it the fewest days), keeping each lowering only while the postponed count stays within budget **and the lowered curve has no steeper day-to-day step than the advance-only curve** (added 2026-11-11 after the author found `Bépo::Caractères` much better without postponing: capping its steady slope 18, 17, 17, 16, 15… gave a 16 × 7-day plateau then a cliff to 13). Postponing is for isolated bumps, not for flattening steady slopes. Then `assign` on the shifted due days.
  - **Rejected first attempt** (don't retry): the lowest curve reachable with every card allowed its full 10% margin. It reshapes the whole curve and postponed 67/160 and 296/420 cards on real decks — not an exception. With the final rules: 1 card on `Paroles de chansons (entières)` (removes an isolated 4), none on `Bépo::Caractères`, 1 on `Paroles de chansons` (53 → 52).
- `even_out(curve)`: last step of `smooth()`, always applied. While a plateau (days at one level) is ≥ 2 days longer than both neighbouring levels' plateaus, its first day gets +1 and its last day −1 (one card moved earlier, so never needs postponing). Asked by the author on `Bépo::Caractères` (2026-11-11): `14, 13, 12, 12, 12, 11, 10` → `14, 13, 13, 12, 11, 11, 10`. The plateau at the last day's level is excluded, also as a neighbour: its length only reflects where the window ends (otherwise `Pays`'s `3x37 2x46 1x2`, which the author likes, would change).
  - **Rejected attempts** (don't retry): smoothing the daily rate with a moving average then re-hulling changes nothing (a moving average of a descending curve stays at or below it, and the hull snaps back to the due counts); rounding the smoothed cumulative *up* instead inflates the curve (`18, 18, 16, 16, 16` on Bépo, a 5 on Pays).
- `move_stats()`: count / mean / max days / max share of the interval, for advanced and for postponed cards. No wording here: sentences are built by `i18n.Translator.describe_moves()`.
- `assign(cards, target)`: fills days from the last one backwards, each day taking the available cards (due on or after it) with the **shortest interval** first. This minimises the total relative advance Σ (due − new_due) / interval — proven against brute force in the tests. Raises `InfeasibleCurve` if the target would need postponing. It may **chain moves** (e.g. a long-interval card J6 → J3 and a short-interval card J7 → J6 rather than J7 → J3 directly), so it touches more cards than strictly needed. **Kept on purpose (author, 2026-11-11)** after comparing with a "fewest cards moved" variant: about a third fewer cards moved, but each moved further relative to its interval (e.g. `Dates Histoire`: 19 → 11 cards, max advance 15% → 32% of the interval). Don't switch unless asked.

## Local dev install

On the author's Windows machine, `%APPDATA%\Anki2\addons21\review_smoother` is a **junction** to this repo's `review_smoother/` folder: code changes apply after restarting Anki. Anki writes `meta.json` (user config overrides) into it — git-ignored. (`cmd /c mklink /J` fails from Git Bash; use PowerShell `New-Item -ItemType Junction`.)

## Environment gotchas

- AnkiConnect requests must be sent as UTF-8 bytes; non-ASCII deck names fail otherwise.
- AnkiConnect has no "today" action: `simulate.py` deduces Anki's day number from a card found with `prop:due=N`.
- Target Python: Anki 26.09 bundles Python 3.13, but keep the code compatible with older Anki versions' Python 3.9 (`from __future__ import annotations`, no `match`, no `X | Y` at runtime).

## Open items

- **Packaging**: `manifest.json` and `.ankiaddon` build for AnkiWeb.
- **Window edge**: cards just past the horizon are ignored, so the curve may drop at the very end (e.g. `…2211`); consider letting them be pulled into the window.
- Sibling cards (same note) may land on the same day; not handled yet.
- One deck at a time in the dialog. Smoothing several decks in one run was **dropped by the author on 2026-11-11** — don't reintroduce unless asked.
