# What Platinum 2 is asking

Platinum 1 asked: *how many months will this project’s in-service date move?* Almost every model was as bad as guessing zero.

Platinum 2 asks a different question: **next year, how many delayed megawatts are sitting in the planned (GIA-ish) pile?**

## Where the numbers come from

Every March / June / September / December, EIA publishes a generator spreadsheet. For plants that are still **planned** (not already running), we look at the planned in-service date.

If that date has already been pushed out **a year or more** compared with the first time we saw that generator, we count its megawatts as **delayed**. Add those up. That total is `delayed_mw` for that quarter.

GIA is extra: we try to match those generators to the MISO queue and keep only ones already in GIA / interconnection agreement. That match is fuzzy, so the GIA line can be a lot smaller. If it is too thin, we still forecast the EIA delayed-MW total and treat GIA as a slice.

## How we score

We do **not** use “average months off.”

We hide the last year of data, guess the delayed-MW total **12 months later**, and see how far off we were (RMSE, in MW). We also check a **3-month** guess as a sanity check.

The dumb comparison is **seasonal naive**: same quarter last year. If a fancy model cannot beat that, it is not helping.

**2024 is sealed.** A 12-month guess made at the end of 2023 lands in 2024, so that fold is not used to pick a winner.

## What we should not say

- This is not “we can predict each COD to the month.”
- This is not proof of a MISO Step-Up process failing. EIA planned dates moved; that is all.
- If the GIA overlay is tiny, do not pretend we measured the whole GIA pile.

## What this run found

We have **18 quarters** (2022-03 through 2026-06). Delayed planned MW in the EIA file goes from about **0** up to about **45,000 MW**.

The GIA-matched slice is tiny (median share about **0.6%** of delayed MW). So the forecast is really **EIA delayed planned MW**, with GIA as a thin overlay.

On 2023 validation (four 12-month folds; 2024 still sealed):

| Model | 12-month RMSE (MW) | Beat last-year same quarter? | 3-month RMSE |
|---|---|---|---|
| TimesFM | **10,715** | yes | **3,358** |
| Holt (damped trend) | 12,684 | yes | 5,140 |
| Last value / seasonal naive (same at 12m) | 14,864 | no | last-value 5,272 is better at 3m |
| Moving average of 3 | 16,559 | no | 8,501 |
| ARIMA | skipped (would not fit) | — | — |

TimesFM and Holt are the first models in this repo that clearly beat a dumb calendar guess **on delayed megawatts**. That is a system stock, not a project calendar. 2024 is still sealed.

