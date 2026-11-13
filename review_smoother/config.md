**horizon_days** (default `90`): number of days, starting tomorrow, over which upcoming reviews are smoothed. It is the initial value in the smoothing dialog, where it can also be changed for a single run. Cards due in the following quarter of that period (up to day 112 for 90 days) may be advanced into it, so that its last days are not left emptier than the days after them.

**method** (default `"auto"`): smoothing method for a deck that has none saved in `decks`:
- `"auto"`: reshape the curve into a regular staircase;
- `"gaps"`: keep the current shape and only fill its gaps (for example 2, 2, 2, 1, 1… 1, 0, 3 becomes 2, 2, 2, 2, 1… 1, 1, 1);
- `"custom"`: follow a custom curve (see `decks`), postponing cards where it wants fewer than are due.

**allow_postpone** (default `false`): initial state of the "Postpone a few cards" checkbox, shown for the `"auto"` method. Cards are normally only advanced; when this is on, a few cards (at most 1% of the deck's cards in the window, at least one) may be pushed back by up to 10% of their interval, only to lower the peak at the start of the curve.

**move_ceiling_percent** (default `5`): how far a card may move, as a share of its interval, so that fewer cards move. With every method, the cards that make the new curve are chosen in two steps: first the smallest possible largest move (many cards, each moved a little), then, allowing moves up to the larger of that and this ceiling, as few cards as possible. `0` keeps the smallest largest move; a higher value moves fewer cards, each further.

**decks** (default `{}`): the method and custom curve chosen for each deck in the smoothing dialog, saved there as soon as they change: `{"Deck name": {"method": "custom", "curve": {...}}}`. A curve holds `tomorrow` (cards on day 1), `drop_day2` and `drop_day3` (drops from day 1 to day 2 and from day 2 to day 3), `floor` (long-term reviews, reached by day 90), `strength` (memory strength: from day 3 to day 90 the curve follows e^(−t / strength) down to `floor`) and `slope_x10000` (after day 90 the curve goes down by `slope_x10000` / 10,000 cards a day).
