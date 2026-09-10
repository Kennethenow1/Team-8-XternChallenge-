# Platinum 2 gold — delayed MW sitting in GIA

This is **not** “how many months will this one project slip.”

Each quarter we look at EIA-860M planned generators in MISO states and add up
megawatts whose **planned in-service date has already moved out by a year or
more** compared with the first time we saw that generator.

- `delayed_mw` is the series we can actually forecast (dense EIA quarters).
- `gia_delayed_mw` is the same stock, but only generators we can match to a
  GIQ project that was already in GIA / IA as of that quarter. The match is
  fuzzy, so this overlay can be thin. If it is too thin, we still forecast
  `delayed_mw` and report GIA as a slice.

GIQ snapshots are year-end. Between Decembers we **carry forward** the last
GIA flag. We never use a later queue snapshot as a feature.

2024 is sealed for picking a model. A 12-month-ahead guess made in late 2023
lands in 2024 — that fold is test, not validation.
