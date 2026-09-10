# What the Platinum numbers actually mean

This is a plain-English read of the delay-model run. You do not need the notebooks to follow it.

## Two separate questions

This repo has two modeling tracks. They are easy to mix up.

**Electrum** asks: *will this project drop out of the queue in the next year?* That work is frozen. These Platinum numbers do not change it.

**Platinum** asks a different question: *if the project stays in the queue, how many months will its planned in-service date slip?* That is the “approved megawatts vs actually deliverable megawatts” idea. We are **not** claiming MISO already has a working “Step-Up” failure log. We are measuring whether generator schedules move after we first see them.

## What we asked the computer to guess

For each project in a given year, we look at the in-service date on file **at that moment**. Then we look ahead (up to two years, because the 2024 public snapshot is missing those dates) and see how far that date moved.

- If the date did not move: slip = **0 months**.
- If it moved out by a year: slip = **12 months**.
- If the project withdrew in that window, we **do not** score it. Withdrawal is Electrum’s job, not this one.

We trained on **2020–2022**. We scored on **2023** only. **2024 was not used** to pick a winner. That is on purpose, so we cannot cheat by peeking at later years.

## How we scored guesses

The headline number is: **on average, how many months off was the guess?**

If a model’s score is **12.04**, it was wrong by about **12 months** on a typical project. That is not “12 months of delay predicted.” It is **12 months of error**.

A useful comparison is a brain-dead guess: **always say 0 months of slip.** That scores **12.05**. If a fancy model cannot beat “always zero,” it is not helping.

## The one-sentence result

**We cannot yet forecast how many months a COD will slip.** Almost every model is as bad as guessing zero. CatBoost is a hair better (12.04 vs 12.05). That is not a real win.

## Why the table looks confusing

| What you saw | What it means |
|---|---|
| MAE around 12 | Average error, in months. Lower is better. 12 is poor. |
| “Beats persist: True” only for CatBoost | Only CatBoost beat the always-zero guess, and only by 0.01 months. |
| Median error near 0 | For **most** projects the guess of 0 is fine. The pain is in a **smaller group** that slips a lot. Average error stays high because those misses are huge. |
| CatBoost “companion” 0.55 | A side task: “will it slip by a year or more, yes/no?” CatBoost is somewhat better than a coin flip at ranking the risky ones. It is still not a months calendar. |
| Survival ~21 | That model is answering a different shape of question (when does something happen). It is worse at the months-of-slip score. |
| TimesFM | Not a per-project model. It looks at the whole system’s delay over time. Ignore its “0.0” score; it is not comparable. |
| TabPFN skipped | That library wants a license key we do not have. Nothing to read there. |
| TabICL “not competitive” | It lost to the always-zero guess. We labeled it so nobody treats it as a win. |

## Why the models all hug zero

This is the important part.

In **2020–2022** (what the models learned from), big slips were rare. In **2023** (what we tested on), they were common. About **38%** of the 2023 projects we could score slipped by a year or more. Average slip on that 2023 set is about **11 months**, but the **middle** project is still 0 — a few large slips pull the average up.

So the models mostly learned “dates usually do not move.” Then 2023 hit them with a lot of movement they had barely seen. Fancy networks (NASNet, the 1-D CNN, TabM, FT-Transformer) did **not** magically solve that. They also guessed near zero.

Among projects already in a **GIA / advanced study** stage, delay is the real story: about **half** slipped ≥12 months, and that slice is about **66,000 MW**. CatBoost’s error on that slice is about **22 months**, because it still barely predicts any delay. The overall 12.04 looks “better” only because many earlier-stage rows are still 0.

## What we should say out loud

- Electrum (will they withdraw?) is the stronger, frozen result. Do not replace it with these delay scores.
- Platinum shows that **COD slip is lumpy and regime-shifting**, not a smooth number we can currently predict from the queue snapshot.
- A future “delivery check” could still use a **simple flag** (GIA + already-slipped + large MW) better than these month-count models. The models did not earn a months forecast.
- We still have **not** opened 2024 to pick a champion. Nothing here is a production delay calendar.

## Where the files are

| File | What it is |
|---|---|
| `platinum/results/leaderboard.csv` | The scoreboard |
| `platinum/results/platinum_performance.ipynb` | Charts for the same numbers |
| `platinum/results/<model>/metrics.json` | One model’s full score |
| `platinum/results/<model>/models/` | The saved trained model |
| `data/gold/delay/README.md` | Why we used a 24-month look-ahead |

If someone asks “which delay model should we ship?” the honest answer is: **none of them, not for months of slip.** CatBoost is the least-bad of a set that all fail the “better than always zero” test in any meaningful way.
