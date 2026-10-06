# Auto-fill: top up from your card automatically

Status: **built 6 Oct 2026, not deployed yet.** Code: `backend/drips/autofill.py`, `frontend/src/screens/AutoFill.tsx`. Kill switch: `AUTOFILL_ENABLED` in `/etc/spendrip.env`.

Decisions: name **Auto-fill**; default window end of month; payday fill covers until the next window; heads-up the same morning; **just-in-time gets one try**, then the usual low-balance reminder (it says the card was declined).

## 0. The idea in one line

Turn on **Auto-fill** once, and SpenDrip charges your saved card so your drips never wait for money: a top-up on **payday**, and a safety net **just before** any drip your balance can't cover.

## 1. Name

| Option | For | Against |
|---|---|---|
| **Auto-fill** (recommended) | Matches the drip/fill language and Kobo's *fill* mood ("Kobo fills up"). Short enough for a switch label. | Less literal than "auto top-up". |
| Auto top-up | Instantly clear; what banks and telcos call it. | Generic. |
| Payday fill | Describes the main use. | Doesn't cover the "before a drip" safety net. |
| Refill | Friendly. | Sounds like a one-off. |

Use **Auto-fill** as the name, with "automatic top-up from your card" as the subtitle everywhere it first appears. Search pages can say "auto top-up".

## 2. What it is, and what it isn't

- It **tops up your SpenDrip balance** from your card. Drips still go out from the balance exactly as today, with the same priorities, limits and fees.
- It is **not** a card payment per drip. Charging the card per transfer would mean a card fee per drip and a failed transfer every time a card is declined.
- Money that lands stays yours: it shows in the balance and can be used or withdrawn like any top-up.

## 3. Two parts, each with its own switch

### 3.1 Payday fill (the main one)

Most people are paid at the end or start of the month. On a payday window, SpenDrip adds what your drips need **until the next window**, in one charge.

- **Windows:** *End of month* (the last 5 days: 27th–31st in a 31-day month, 24th–28th in February) and *Start of month* (1st–5th). The person picks one or both. Default: **End of month**, the most common salary timing.
- **Amount:** what the forecast says you'll need until the next window, fees included, minus what's already in your balance. The same number as the "Add ₦X" in the month outlook email. If the balance already covers it, nothing is charged.
- **When:** at 10:00 AM local on the **first day of the window**, after a heads-up that morning at 7:00 AM ("Auto-fill will add ₦184,300 at 10 AM. Skip this time?").
- **Declined (no money yet, salary not in):** try again at 10:00 AM each following day of the window, **at most 3 tries per window**. Most people are paid somewhere in the window, so a later try usually works.
- **Payday before the window:** a "Fill now" button in the heads-up and on the Auto-fill screen charges immediately.

### 3.2 Just-in-time fill (the safety net)

If a drip is due within 24 hours and the balance can't cover it (the same check as the day-ahead reminder), SpenDrip charges the **shortfall** for that drip, at the time the reminder would go out.

- **Amount:** the shortfall, rounded up to the nearest ₦500 so rounding doesn't cause a second charge for small drips the same week. Minimum ₦1,000 (below that the card fee is a large share).
- **Declined:** no second try. The normal day-ahead email goes out and says the card was declined.
- **Group payouts:** the shortfall for the whole payout, since they're all or nothing.
- If both parts are on, payday fill runs first; just-in-time only catches what's left (a new drip added mid-month, an amount raised, a declined payday fill).

## 4. Limits the person sets (and we enforce)

- **Maximum per charge** (default: the month's need rounded up, at most ₦500,000).
- **Maximum per month** across all Auto-fill charges (default: 1.5 × the month's need).
- Never fills past the balance limit (₦2,000,000) or charges more than a top-up allows (₦100 to ₦10,000,000).
- **One card.** If the card is removed or expires, Auto-fill switches off and says so.
- **Two failed windows in a row** (or three failed just-in-time fills in a month): Auto-fill pauses itself and asks the person to check the card. No endless retries on a declined card.

## 5. Fees (be upfront)

Card top-ups cost Paystack's fee, passed on and shown as today: 1.5%, plus ₦100 from ₦2,500, **capped at ₦2,000 per charge**.

- Payday fill puts the month in one charge, so a big month costs at most ₦2,000. A ₦300,000 month: ₦2,000 once, against about ₦4,900 for four weekly ₦75,000 top-ups (₦1,225 each).
- Just-in-time fills for small drips are cheap (₦1,000 costs ₦15) but add up if they happen often. The settings screen shows "Auto-fill cost you ₦X in card fees last month".
- No SpenDrip fee for Auto-fill itself.

## 6. Flow

### 6.1 Turning it on

Where: **Fund** screen ("Never top up by hand again → Set up Auto-fill"), **Profile → Auto-fill**, and as a suggestion after the second time a drip waits for money.

1. **Explainer** (Kobo *fill* pose): "Auto-fill tops up your balance from your card so drips never wait. You choose when and how much."
2. **Card:** pick a saved card. No saved card: "Top up once with **Save this card** on, then come back" (or a ₦100 verification top-up). Cards that need OTP on every charge can't be used; we find out on the first charge and say so.
3. **When:** two switches with plain descriptions.
   - *Payday fill*: End of month (26th–31st) / Start of month (1st–5th) / both.
   - *Before a drip if I'm short*.
4. **Limits:** max per charge and per month, pre-filled from the forecast, editable.
5. **Preview:** "Next: **Mon 26 Oct, 10 AM**, about **₦184,300** + ₦2,000 card fee, on Visa ••4081. We'll message you that morning." Then the list of what it covers (from the forecast).
6. **Confirm with PIN or passkey.** The confirmation states the authority in one sentence: "I allow SpenDrip to charge Visa ••4081 up to ₦250,000 per charge and ₦400,000 per month, on the days above, until I turn this off."
7. **Email receipt** of the consent (same sentence, limits, how to turn off). Store the consent record.

### 6.2 Each payday fill

| When | What happens | Message |
|---|---|---|
| Window day 1, 7:00 AM | Work out the amount. Nothing needed: stop quietly. | Push + in-app: "Auto-fill will add ₦184,300 at 10 AM. [Skip this time]" |
| 10:00 AM | Charge the saved card (`charge_saved_card`). | Success: push + email receipt "₦184,300 added. Everything until 1 Nov is covered." |
| Declined | Retry tomorrow 10 AM (max 3 tries in the window). | "Your card was declined (insufficient funds). We'll try again tomorrow at 10 AM. [Fill now] [Use another card]" |
| Window ends, all tries failed | Stop. Just-in-time still runs if on. | Email: "Auto-fill couldn't add money this payday. Top up by hand so your drips go out." |

### 6.3 Each just-in-time fill

| When | What happens | Message |
|---|---|---|
| 24 h before a short drip | Charge the shortfall. | Success: in-app only ("₦3,000 added so Upkeep goes out tomorrow"), to avoid noise. |
| Declined | No second try. | Day-ahead email, saying the card was declined. |

### 6.4 Managing it

- **Profile → Auto-fill:** on/off, the next fill date and estimate, card, windows, limits, "Skip next payday fill", history (each charge, fee, result).
- **Activity:** each fill appears as a top-up, labelled "Auto-fill · Visa ••4081".
- **Turning off** is one tap with no PIN (stopping charges must always be easy); turning on or raising a limit needs the PIN.
- **Plans screen:** a small "Auto-fill on" chip next to the balance, so it's clear why "Top up" banners don't appear.

## 7. Edge cases

- **Drips on the 1st–4th** with a start-of-month window: the window charge runs on the 1st at 10 AM; a drip before 10 AM on the 1st is covered by the end-of-month window or by just-in-time.
- **February / short months:** the end window is the last 5 days of the actual month.
- **Card needs OTP/3DS** for a merchant-initiated charge: the charge comes back as `send_otp`/`open_url`; treat as declined, switch Auto-fill off, and ask the person to use another card.
- **Two devices / double runs:** one Auto-fill charge in flight per person; idempotency key per (person, window or drip, attempt).
- **Kill switch:** `AUTOFILL_ENABLED=false` stops every automatic charge without touching anything else (like `PAYOUTS_ENABLED`).
- **Paused account, all plans paused, or verification lapsed:** no charges.
- **Chargebacks/disputes:** a disputed Auto-fill charge switches Auto-fill off for that person and freezes the disputed amount, using the same ledger reversal as a card refund.
- **Time zones:** windows and 10 AM use the person's time zone (default Lagos).

## 8. What we build

Backend:
- `AutoFill` (person, card, payday_end, payday_start, just_in_time, max_per_charge, max_per_month, active, paused_reason, consent_text, consented_at).
- `AutoFillAttempt` (person, kind payday/jit, window_key or run/batch, attempt, amount, CardCharge, status, reason).
- `drips/autofill.py`: `due_payday_fills(now)`, `due_jit_fills(now)`, amount from `user_forecast()` up to the next window, limit checks. Called from the worker's `remind()` loop (every 5 minutes), before reminders, so a successful fill stops the low-balance email.
- Reuse `ledger.cards.charge_saved_card()`; add a `source="autofill"` on CardCharge for Activity and fee reporting.
- Messages: heads-up, success, declined, window failed, auto-paused, card removed/expired, consent receipt.
- API: GET/PUT `/api/autofill`, POST `/api/autofill/fill-now`, POST `/api/autofill/skip`.

Frontend:
- Set-up flow (6.1), Profile → Auto-fill screen, Fund screen entry, Activity label, Plans chip, suggestion card.

Tests: amount maths (forecast to next window, rounding, minimums, limits), window dates (Feb, 30/31-day months, time zones), retry caps and auto-pause, idempotency, decline handling, OTP-required response, kill switch.

## 9. Later

- **Bank direct debit** (Paystack Direct Debit mandates) instead of a card: no card expiry, and Paystack's direct-debit pricing may beat card fees for big months. Needs a mandate flow with the bank.
- **Payday detection:** learn the person's payday from when they usually top up, and suggest a window.
- **Liberty bank-transfer funding** (on the backlog) gives the same "money arrives on payday" result for people who'd rather send a transfer from their salary account.

## 10. Decisions needed

1. Name: **Auto-fill**?
2. Default window: **end of month only** (recommended), or both?
3. Payday fill amount: **until the next window** (recommended) or the whole calendar month?
4. Heads-up: **the same morning** (recommended) or the day before?

## 11. Paystack Direct Debit (checked 6 Oct 2026)

Paystack offers bank-account direct debit in Nigeria (https://paystack.com/docs/payments/direct-debit/):
- The customer gives consent on a Paystack page (`/customer/authorization/initialize` with `channel: direct_debit`), then makes a one-time ₦50 transfer to a NIBSS account to activate the mandate. Activation can take up to 24 hours.
- 24 banks are supported (Access, GTBank, Zenith, UBA, First Bank, FCMB, Fidelity, Sterling, Wema, Stanbic, Union, Polaris, Keystone, Providus and others). Not the fintech wallets (OPay, PalmPay, Kuda, Moniepoint).
- The result is a reusable authorization, like a saved card, so Auto-fill could charge it the same way. Pricing isn't on the docs page; ask Paystack.
