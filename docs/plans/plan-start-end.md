# Plans with a start and an end

Status: **built 2 Oct 2026.** Calendar shows "First drip" / "🏁 Last drip" tags in a day's list.

Decisions: end by months or by date (no "N drips" yet); pausing doesn't move the end; when a priority plan finishes, the priorities below move up; the only end-of-plan notice is the "last drip" line in the delivery email (no 3-day warning, no "finished" note).

## 1. Why

Many drips aren't forever: a cousin's school-term upkeep, three months of rent support, fuel while a car is in use, an allowance until NYSC ends. Today every plan starts the moment it's saved and runs until someone deletes it. That makes people do the maths themselves and remember to stop it.

## 2. What already exists

- The engine's `Schedule` already has `starts_at` and `ends_at` and only produces drips between them (`engine/schedule.py`).
- `Plan` already stores both (`drips/models.py`). The API accepts them, but the app never sends them, so `starts_at = now` and `ends_at = null`.
- Forecast, priority protection and run creation all go through `occurrences()`, so they would respect an end date without changes.

So the gaps are: how people set the dates, what happens when a plan finishes, and how the app shows progress and the total cost.

## 3. How it should feel

The plan stays one sentence. Two new chips go at the end:

> Send **₦40,000** for **⛽ Fuel** to **Me** every **Friday** at **2:00 PM**, **starting today**, **for 3 months**.

- **Starting chip.** Default "starting today". If today's slot has already passed, it reads "starting Fri 9 Oct" (the first real drip). Tapping it opens a sheet with *Today* · *Next Friday* · *Pick a date*.
- **Ending chip.** Default "and keeps going". Tapping it opens a sheet with three options:
  - **Keeps going** (today's behaviour).
  - **For a number of months:** quick picks 1 · 3 · 6 · 12, plus a stepper from 1 to 36.
  - **Until a date:** a date picker.
- **Live summary in the sheet**, so the choice is never abstract:
  > Last drip **Fri 29 Jan 2027** · **17 drips** · **₦680,000** plus **₦2,125** fees in total
- The preview card gains a "Whole plan" row, shown only for plans with an end: `17 drips · ₦682,125 in total`.

### Plan cards (Plans tab)
- **Progress line:** "Drip 4 of 17 · ends 29 Jan", with a thin progress bar.
- **Pills:** `Starts 1 Nov` (not started yet), `Ending soon` (last drip within 7 days), `Finished`.
- A new **Finished** section, collapsed by default, below active plans. Each finished plan has **Run it again** (prefills a new plan with the same sentence) and **Extend** (pick a new end).

### Elsewhere
- **Calendar:** a small "Starts" or "Last drip" marker on those days. Months after the end show nothing for that plan.
- **Home:** unchanged, except that the "next drip" card shows "Last one 🎉" on a plan's final drip.
- **Delivery email:** adds "Drip 4 of 17" for plans with an end, and "That was the last one. The plan is finished." on the final drip.
- **Add money:** unchanged. It already covers this month only, and the forecast leaves out drips after a plan's end.

## 4. Rules (the edge cases)

| Situation | Rule |
|---|---|
| "For N months" | Ends just before the same date N months after the start. Start 1 Nov, 3 months → drips 1 Nov, 1 Dec, 1 Jan. Weekly from Fri 2 Oct, 3 months → last Friday before 2 Jan. |
| "Until a date" | Inclusive: a drip on the end date still goes out. Stored as 23:59:59 Lagos time on that date. |
| Start date in the future | The plan is "Scheduled" and creates no drips until then. A priority rank is allowed, but protects nothing until the first drip falls in the current month. |
| An end that would give zero drips | Blocked: "This ends before its first drip. Pick a later end date." |
| Longest plan | 36 months, or "keeps going". |
| Paused plan | The end date doesn't move: pausing skips drips, it doesn't push the end out. The sheet says so: "Paused drips aren't added on at the end." |
| A drip that waited for money | Counts as that drip's slot. It isn't added on after the end. |
| Editing the end of a running plan | Allowed (extend or shorten). It can't end before the last drip that already went out. Future drips are rebuilt (the existing `reschedule`). |
| Editing the start | Only before the first drip has gone out. |
| Plan reaches its end | It moves to **Finished** after its last drip settles, fails or is missed. Its priority rank is released and lower priorities move up (the ranked list already compacts). |
| "Months" mode and a later start change | The end is recalculated from the new start, so "for 3 months" keeps meaning 3 months. |

## 5. Data and API

- `Plan`: add
  - `end_mode`: `ongoing` | `months` | `date`. Keeps what the person chose, so the sentence reads back exactly.
  - `duration_months`
  - `finished_at`
  - status `finished` (alongside active, paused, deleted)
- Engine: new pure helpers.
  - `months_later(start, n, tz)`: works for 31st-of-month starts and leap years.
  - `count_occurrences(schedule)`, `last_occurrence(schedule)`
- API, create/update/preview:
  - Accepts `start_date` (local date or "today"), `end_mode`, `duration_months`, `end_date`.
  - Returns `total_drips`, `drips_done`, `first_drip_at`, `last_drip_at`, `total_cost_kobo` (amounts + fees), and the status `scheduled` | `active` | `paused` | `finished`.
- Worker, each tick: mark plans finished once `ends_at` has passed and none of their drips are still in flight. Release the priority rank (lower priorities move up).
- Migration: existing plans become `end_mode = ongoing`. Nothing else changes for them.

## 6. Notifications

- **Last drip delivered:** the delivery email gets the "last one" line. (Decided: no 3-day warning and no separate "finished" note for now.)

## 7. Build order

1. **Engine + model + API.** Date maths, counts, `end_mode`, finished state, worker step, priority release. Tests: month-end starts (31 Jan + 1 month), leap year, inclusive end dates, weekly across months, pause, edits, finishing, rank compaction.
2. **Plan builder.** The two chips, the two sheets with the live summary, preview "Whole plan" row, validation messages.
3. **Plan cards and the Finished section.** Progress, pills, Run it again, Extend.
4. **Calendar markers, notifications, delivery-email lines.**
5. **Check end to end on the local app and the live app**, then deploy.

Steps 1–3 are the core. Step 4 can follow in the same pass or right after.

## 8. Not doing now

- **"For N drips"** (e.g. "pay school fees 3 times"). It's easy to add later as a fourth end mode, but it's ambiguous for daily plans and plans that wait for money.
- **Pausing until a date** ("resume on 1 Dec").
- **Changing the amount part-way** ("₦30k for 3 months, then ₦20k").
