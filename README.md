# Review Smoother

An Anki add-on that reshapes a deck's upcoming review forecast into a smooth, descending curve. You get 4 reviews a day, then 3, then 2, instead of a jagged 5, 2, 4, 3…

It only changes when cards are due: the number of cards stays the same, intervals are kept, and nothing is rescheduled until you confirm. The interface is in English and French, following Anki's language.

## Smoothing a deck

Open **Tools › Review Smoother…**, or click the **Review Smoother** button next to the *Future Due* graph in the Statistics window. Then pick a deck and a period: 1 month, 3 months, 1 year, 2 years, or any number of days from 7 to 730. Day 1 is tomorrow.

The dialog shows two graphs, styled like Anki's *Future Due* graph:

- **Before**: the forecast as it is now.
- **After**: the forecast once smoothed. Days that gain cards are marked in blue, and days that lose cards are outlined in orange.

You can zoom with the mouse wheel, drag to move around, and double-click to see the whole period again. Under the graphs, a summary says how many cards will move and how far. **Show cards to move** opens them in the Browser. **Apply** makes the change as a single step that **Edit › Undo** reverts.

Today's cards, overdue, new, learning, suspended and buried cards are never touched.

### Methods

The method is remembered for each deck.

- **Smooth into a regular staircase** (default). The lowest curve reachable by **advancing** cards only. Each level lasts at least as long as the one above it, and the curve steps down one card at a time. Among those curves, it picks the one that advances cards the least. Optionally, **postpone a few cards** (at most 1% of the deck's cards in the period, by up to 10% of their interval) to lower a peak at the start of the curve.
- **Follow a custom curve**. You set the curve and cards are advanced or postponed to match it exactly. The curve has six settings:
  - the cards for tomorrow;
  - the drop from day 1 to day 2, and from day 2 to day 3;
  - the cards on day 90;
  - the memory strength: from day 3 to day 90, the curve follows a forgetting curve, e^(−t / strength), down to the day-90 value;
  - the slope after day 90.

  The dialog compares the curve's total with the cards actually due, so you can tune it.

### How cards are chosen

- Cards due just after the period may be pulled into it, so that its last days are not emptier than the days that follow. The cards are taken from days that have cards to spare, so a gap does not appear right after the period.
- Moves are kept short relative to each card's interval. Then as few cards as possible are moved, each by at most 5% of its interval (setting `move_ceiling_percent`).
- Sibling cards (cards of the same note) are not moved onto the same day when another card can take the slot.

## Repositioning new cards

**Tools › Reposition new cards…** also opens from the **Reposition** button in the Statistics window. It numbers a deck's new cards with a preview of the new positions. The settings are remembered for each deck.

- **In a row**: positions from a start value with a step. The cards are taken in their current order, or shuffled. Unlike Anki's own Reposition:
  - every card gets its own position, siblings included;
  - the shuffle mixes cards rather than notes;
  - sibling cards are kept at least as many positions apart as the deck's new cards per day, so they are not introduced on the same day.
- **By blocks**: for decks organised in blocks of positions, for example 100 per block from position 11. Each block's cards are moved up to the start of their block, in the same order. A group of cards that runs into the next block moves as a whole.

## Tracking the custom curve

With the custom curve, the dialog's **Record today's tracking…** button saves the day's values in a tracking note for the deck:

- the curve's settings;
- the deck's new cards of the day;
- its learned cards;
- an optional remark.

The values are prefilled and can be edited. Recording the same day again replaces that day's row.

The note is an ordinary note, so it syncs and can be read on AnkiDroid too. Open it from the Browser's preview. It has its own note type, *Review Smoother – Suivi* in French, and lives in the **_Review Smoother** deck. Its card is suspended, so it is never studied and never counted in the tracked deck. The card shows:

- a graph of any column, over 1 month, 3 months, 1 year or everything; click a day to jump to its row;
- a table of every day, newest first, with the curve's totals over a month, three months and a year computed from each row's settings.

The add-on rewrites the card's template and style when they differ from its own, so changes made to them in Anki do not last.

`tools/import_tracking.py` imports an earlier history kept in a spreadsheet: one sheet per table, one row per day.

## Settings

The settings are in **Tools › Add-ons › Review Smoother › Config**, described in [config.md](review_smoother/config.md). Most of them are set from the dialogs: the default period, the default method, postponing, the move ceiling, and each deck's method, curve and reposition settings.

## Development

- `review_smoother/` is the add-on folder, the one installed in Anki's `addons21`. `smoothing.py`, `reposition.py`, `tracking.py` and `i18n.py` do not import Anki, so they can be tested on their own.
- Tests use the standard library only. Run `python -m unittest` from the repository root.
- `tools/simulate.py` shows what smoothing would do on your real collection, without changing it. It needs Anki to be running with [AnkiConnect](https://ankiweb.net/shared/info/2055492159). Run `python tools/simulate.py "Deck::Name" --horizon 90`.
- The code targets Anki 26.09 (Python 3.13) and stays compatible with Python 3.9.

## License

MIT, see [LICENSE](LICENSE).
