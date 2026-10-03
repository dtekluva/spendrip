# Bulk drips: one plan, many people, different amounts

Status: **built 3 Oct 2026.** Not yet built: the day-before heads-up email, the optional "approve each payout" setting and the CSV export of a payout (see 2.6 and 6.9).

Decisions:
- Called **Group** in the app ("Send to several people" in the picker).
- **All or nothing:** a group payout waits until the balance covers everyone.
- **Flat ₦100 SpenDrip fee per payout,** however many people. Paystack's charge and stamp duty still apply to each transfer.
- **Tier-1 limits raised** to ₦500k per transfer and ₦2M balance, with a daily cap up to ₦2M. This is above the CBN's Tier-1 levels and rests on ID + live-selfie checks only, so bringing Dojah forward matters more.

## 1. Who it's for (and who it isn't, yet)

- **Household payroll:** driver, nanny, cook, gateman, cleaner. Paid monthly, different amounts, the same day for everyone. This is the strongest fit. It's a personal account paying people, which our individual ID checks already cover.
- **Family support lists:** Mum ₦30k, Dad ₦30k, two siblings ₦15k, grandma ₦10k, all on the 25th.
- **Small teams and side businesses:** 3–10 staff paid from the owner's personal money. This works, but we hit the limits quickly (see 6).
- **Not yet: registered-company payroll.** That needs business verification (CAC and directors), invoices, payslips and tax deductions. Leave it until there's a business tier.

The pitch: "Pay everyone in one go, on time, every month. Each person gets a WhatsApp message when theirs lands, and you get one receipt."

## 2. The critical UX calls

1. **The one-sentence plan can't stretch to 8 people.** The sentence stays for *when*. *Who and how much* moves into a list:
   > Send to **6 people** · **₦412,000** every **month** on the **28th** at **9:00 AM**.

   The "6 people" chip opens the list. There's no single amount chip, because each person's amount is set in the list.
2. **Don't make people choose "single or bulk" up front.** In the existing "to whom" sheet, add **"Several people"**. From an existing single plan, "Add another person" turns it into a bulk plan. People find it when they need it, and new users don't face an extra question.
3. **Entering 10 accounts by hand is the real pain.** Offer three ways in, all landing in the same list:
   - **Saved people:** a checklist of recipients you already have.
   - **New person:** bank + account number, then the name check (as today).
   - **Paste a list:** one person per line, e.g. `Musa, 0123456789, GTBank, 80000`. CSV upload works the same way. Name checks run for every row together, rows that fail are marked red, and nothing is saved until every row is fixed or removed.
4. **The total and fees are always in view.** A sticky footer reads "6 people · ₦412,000 + ₦750 fees = **₦412,750 each month**". Fees are worked out per transfer, because stamp duty and Paystack's charge apply to each transfer, not to the total.
5. **Payroll changes month to month.** This is the part most apps get wrong. Each row has a menu:
   - **Change amount:** *Just the next payout* (a bonus or deduction) or *Every payout from now on* (a raise).
   - **Skip next payout:** someone on leave, or already paid by hand.
   - **Remove from list.**

   One-off changes show as a small tag on the row, like "₦90,000 next time only", and clear themselves after that payout.
6. **A heads-up before money moves.** The day before each bulk payout, an email says "Tomorrow at 9:00 AM: 6 people, ₦412,750. Balance ₦300,000. **Short by ₦112,750.**" with **Review** and **Add money** buttons. Nothing has to be approved; it simply goes out unless you change it. Optional setting: "Ask me to approve each payout".
7. **One result, not six.** The sender gets one summary email ("Paid 6 of 6 · ₦412,000"), and Activity shows one row that opens to show each person. Each person still gets their own WhatsApp message, and recipients never see each other.

## 3. Money rules (the hard edges)

| Situation | Rule (recommended) |
|---|---|
| Balance covers everyone | Reserve the whole batch at once, then send each transfer. |
| Balance is short | **Wait for the full amount** (all or nothing), so no one is paid while others aren't. Keep retrying within the late window. Tell the sender straight away how much is short. *Alternative: pay down the list in order until the money runs out.* |
| One transfer fails (closed account, wrong bank) | The others still go. That person's money comes back to the balance, their row is flagged "Fix account", and the summary says "Paid 5 of 6". |
| Priorities | The whole bulk plan takes one priority rank, and its full monthly total is protected. |
| Daily sending cap | The batch counts as one total against the cap. A batch that would break the cap waits, and the heads-up email warns about it in advance. |
| Pause | Pauses the whole list. Skipping one person is per row (see 2.5). |
| Editing while a payout is going out | The list is locked from the moment the batch is reserved until every transfer settles. |
| Same person twice in one list | Blocked: "Musa is already on this list." |
| End dates | Same rules as single plans (months or a date). |

## 4. Limits: the blocker to decide on

These are today's limits for people verified with an ID photo and live selfies (Tier 1):

| Limit | Value | What it means for bulk |
|---|---|---|
| Per transfer | ₦50,000 | Each person can get at most ₦50k. That's fine for family support, but a ₦80k driver is blocked. |
| Balance | ₦300,000 | Caps the whole batch at about ₦300k, because the money must be in the balance at payout time. |
| Daily cap | ₦100,000 default | Blocks most batches unless the person raises it. Bulk plans need the cap to cover the batch total; the plan builder offers to raise it, up to the tier limit. |

So with Tier 1, household payroll works only for small amounts. Real payroll needs the higher tier: government ID verification through Dojah, which is already in the backlog. **Recommendation: build bulk now within Tier-1 limits, with clear messages in the list footer** (for example "Musa's ₦80,000 is over your ₦50,000 per-transfer limit"), and bring Dojah forward.

## 5. Fees

Each line is charged like a normal drip: ₦50 SpenDrip fee, plus Paystack's ₦10/₦25/₦50, plus ₦50 stamp duty on ₦10k or more. A 6-person payroll of ₦50k each costs 6 × ₦125 = ₦750.

**Decision:** keep ₦50 per person, or give bulk plans a cheaper SpenDrip fee to win payroll users (for example ₦50 for the first person and ₦25 for each one after).

## 6. Screens

1. **New plan → "to whom" sheet** gets *Several people*.
2. **List editor (full screen):**
   - Rows: initials, name, bank ••1234, the checked account name, and an amount field you can type into.
   - Add buttons: *Saved people*, *New person*, *Paste a list*.
   - Sticky footer with the total, fees and any limit warnings.
3. **Paste/CSV review:** a table of rows marked ✓ name matched or ✗ with a reason. Fix or remove, then *Add 6 people*.
4. **Plan builder:** the sentence with a "6 people · ₦412,000" chip, plus the start/end and priority chips as today.
5. **Plans tab card:** "👷 Staff pay · 6 people · ₦412,000 · next 28 Nov", which opens the list with next-payout tags.
6. **Next payout review** (from the heads-up email or the card): this payout's list with one-off changes and skips, the total, and the balance check.
7. **Activity:** one grouped row, "Staff pay · paid 6 of 6", that opens to show each person's status.
8. **Calendar and Home:** one entry per batch, not six.
9. **Statement export:** the bulk payout's lines as a CSV (a simple pay record).

## 7. Data and engine

- `Plan.kind`: `single` | `bulk`. For bulk plans, `amount_kobo` and `recipient` are empty.
- `PlanLine`:
  - plan, recipient, amount_kobo, position, active
  - `next_amount_kobo` (a one-off override)
  - `skip_next` (bool)
- `Run` gets an optional `line` and a `batch` (FK to `RunBatch`).
- `RunBatch`:
  - plan, scheduled_for, status, total_kobo, fee_kobo
  - one record per payout, so the decision is all-or-nothing on the total
- **Engine:** a plan's amount for a given date is the sum of its active lines, and its fee is the sum of each line's fee. `decide()` already takes amount and fee, so for bulk plans it gets the batch totals.
- **Worker:**
  1. Decide on the batch.
  2. Reserve every line in one database transaction.
  3. Send each transfer through the existing path, so the run id stays the reference and nothing can be paid twice.
  4. Close the batch when every line has settled.
  5. Clear one-off overrides and skips.
- **Paystack:** single transfers via the existing path (not the bulk-transfer API), so failure handling stays the same as today.
- **Ledger:** one reserve entry per line, so the statement and fee ledger stay per transfer.

## 8. Build order

1. Model, engine and worker (all-or-nothing batches, line overrides and skips) with tests.
2. List editor, adding saved and new people, and the footer with totals and limits.
3. Paste/CSV import with batch name checks.
4. Plans card, next-payout review, grouped Activity, Calendar and Home.
5. Heads-up email and summary email, and the CSV export.
6. Live check, then deploy.

## 9. Not now

- One-off "send now to several people", without a schedule (easy to add after this as a "once" frequency).
- Business payroll: CAC verification, payslips, PAYE/pension deductions, multiple approvers.
- Recipients confirming receipt, or recipients seeing each other.
