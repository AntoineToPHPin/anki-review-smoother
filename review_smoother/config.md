**horizon_days** (default `90`): number of days, starting tomorrow, over which upcoming reviews are smoothed. It is the initial value in the smoothing dialog, where it can also be changed for a single run.

**allow_postpone** (default `true`): initial state of the "Postpone a few cards" checkbox in the smoothing dialog. Cards are normally only advanced; when this is on, a few cards (at most 1% of the deck's cards in the window, at least one) may be pushed back by up to 10% of their interval, only to lower the peak at the start of the curve.
