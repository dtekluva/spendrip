# SpenDrip — scheduled money drops (build plan)

> Name: **SpenDrip** (spendrip.com). Each scheduled payment is a "drip".

## 1. What it does

You create **Plans**: recurring payouts. Each one has these fields:

| Field | Example |
|---|---|
| Label + emoji | ⛽ Fuel |
| Amount | ₦40,000 |
| Recipient | Me (my GTB account) / Mum / Cousin |
| Frequency | Daily · Weekly · Monthly (later: every N days, custom) |
| When | Friday · 14:00 (Africa/Lagos) |
| Notify | WhatsApp to recipient, push to me |
| Start / end | Starts now, runs until paused or until an end date |

**Funding:** the app works out what your schedule needs over a period, compares it with what you have and gives you one account number to top up.

Example for October 2026 (the month has 5 Fridays and 31 days):

| Plan | Runs | Total |
|---|---|---|
| ⛽ Fuel ₦40k every Friday 2pm | 5 | ₦200,000 |
| 🍲 Upkeep ₦3k daily 6am | 31 | ₦93,000 |
| 💛 Mum ₦30k monthly | 1 | ₦30,000 |
| 🤝 Cousin ₦25k monthly | 1 | ₦25,000 |
| Transfer fees | 38 × ₦50 | ₦1,900 |
| **Needed** | | **₦349,900** |
| Already funded (your ledger balance) | | − ₦120,000 |
| **Top up** | | **₦229,900** |

Each transfer goes out on time. Then:
- **The recipient** gets a WhatsApp message. Example: "Hi Mum 💛, ₦30,000 has just been sent to your Opay account from Ete."
- **You** get a push notification and an in-app activity entry. Example: "⛽ Fuel ₦40,000 sent to GTB ••2018 ✅".

## 2. Providers

### Liberty Pay Core Banking (main money rail)
From the Postman collection:

| Need | Endpoint |
|---|---|
| Auth (JWT) | `POST /api/v1/companies/auth/login/` (access + refresh); `GET …/verify_token` |
| Funding account(s) | `POST /api/v1/wema/virtual_accounts/` (Wema NUBAN); `GET` to list |
| Inflow confirmation | Company `callback_url` webhook, then `GET /api/v1/wema/verify_event?session_id=` to verify |
| Validate a recipient | `POST /api/v1/core/account_name_enquiry/` `{bank_code, account_number}` (Api_key auth) |
| Send money | `POST /accounts/transfer_money/` `{source_account, account_name, account_number, bank_code, amount, narration, request_reference, mode, service_provider:"WEMA_BANK"}`. It returns `PENDING`. |
| Transfer status (TSQ) | `GET /accounts/verify_transfer?search={request_reference}`, which returns `SUCCESSFUL`/`FAILED`… |
| Balance | **None.** Liberty holds one **pool account**, and there are no per-user accounts or balances. **Our ledger is the source of truth** for each user's balance (see §6). |
| Alt send | `POST /api/v1/core/central_send_money/` (keep as a fallback adapter) |

Bank codes are **NIP codes** (`000013` GTB, `000017` Wema, `100004` Opay).

**Mocked for now:** Liberty sandbox, webhook payloads, and transfer callbacks. We define our own normalised event shapes (`InflowEvent`, `TransferStatusEvent`). The mock emits them, and the real adapter will map Liberty's payloads onto them once we have samples.

**Fee:** a flat **₦50 per outward transfer**. It's held in config per provider, so it's easy to change.

### Paystack (optional, both directions)
- **Funding by card debit:** Paystack checkout or charge, confirmed by its webhook, then credited to your ledger. Paystack's card fee is either shown to you or absorbed (configurable).
- **Outward transfers (alternative rail):** a second `PaymentProvider` you can pick per plan, or use as a fallback when Liberty is down. Paystack needs a "transfer recipient" created once per recipient. It uses **CBN bank codes** rather than NIP codes, so `recipient` stores both and we keep a NIP↔CBN mapping table.
- Both are **off by default** behind feature flags. Phase 1 builds the interface with mocks only.

### WhatsApp
**Mock for now.** Every message is written to an `outbox` table and shown on an in-app "Messages" screen with a "would have sent" badge. Later we swap in Meta Cloud API, Termii or Twilio behind the same `Messenger` interface. Business-initiated WhatsApp messages need **pre-approved templates**, so we'll write the copy as templates from day one.

## 3. Architecture

```
┌──── React app (Vite + TypeScript, installable PWA) ────┐   frontend/
│  Screens from docs/mock · talks only to the API        │
└───────────────┬────────────────────────────────────────┘
                │ JSON over /api
┌───────────────┴────────────────────────────────────────┐   backend/
│  Django 5 + Django REST Framework                      │
│  /api/...  ·  /admin  ·  /api/webhooks/liberty (later) │
└───────────────┬────────────────────────────────────────┘
                │ PostgreSQL (Django ORM)
┌───────────────┴────────────────────────────────────────┐
│  Worker: `python manage.py run_worker`                 │
│   • every 30s: create upcoming runs from plans         │
│   • due runs: protection check → set money aside → send│
│   • in-flight: status check (TSQ) → settle or release  │
│   • notifications: WhatsApp (mock) + push + in-app     │
└───────────────┬────────────────────────────────────────┘
        PaymentProvider             Messenger / KycProvider
        ├─ MockPaymentProvider      ├─ MockMessenger (outbox)
        ├─ LibertyProvider          └─ MockKycProvider
        └─ (later) Paystack
```

- **Backend (`backend/`):** Django apps `accounts` (user, PIN, KYC), `drips` (recipients, plans, runs, worker), `ledger` (double-entry ledger, funding accounts, inflows) and `notifications` (outbox).
- **Engine (`backend/engine/`):** plain Python with no Django imports. It holds the schedule maths, the priority protection and the month forecast, and the worker and the API both use it.
- **Worker:** a Django management command running a simple loop. A Postgres advisory lock makes sure only one worker ticks at a time. There's no Redis or Celery.
- **Frontend (`frontend/`):** React + TypeScript (Vite). It talks only to the Django API, so a native app can reuse the same API later.
- **Hosting:** Railway, Render or Fly, running the API, the worker, Postgres and the static frontend. Liberty needs a public HTTPS URL for its webhook.
- **Everything runs in Docker** (`docker compose up`): `db` (Postgres 16 on localhost:5434), `migrate`, `backend` (localhost:8010), `worker` and `frontend` (localhost:5173).

## 4. Data model (core tables)

- `user`: you, for now. The model is multi-user-ready for later.
- `recipient`: name, phone (WhatsApp), nip_bank_code, cbn_bank_code (for Paystack), account_number, verified_account_name, is_self, verified_at, paystack_recipient_code (nullable).
- `plan`: label, emoji, colour, amount_kobo, recipient_id, frequency, weekday/monthday, time_local, tz, start/end, status (active/paused), **protection** (`none` | `priority` | `allocation`), priority_rank (1–3, unique per user), allocation_kobo (when protection = allocation), provider (liberty/paystack), notify flags, message_template. Plans have no provider accounts of their own. Protection is enforced purely in our ledger and payout rules (see §6a).
- `run`: one row per occurrence. Fields: plan_id, scheduled_for, amount_kobo, fee_kobo, provider, status, request_reference (unique), provider_session_id, attempts, error.
  - Statuses: `scheduled → reserved → processing → pending → successful | failed | skipped_insufficient_funds | skipped_protected | missed`.
- `ledger_account`: one per user (`user_wallet`), plus system accounts (`liberty_pool`, `paystack_settlement`, `fees`, `suspense`).
- `ledger_entry`: **double-entry and append-only**; each transaction's lines sum to zero. Covers top-ups, payouts, fees, reservations, releases and reversals. A user's balance is `SUM(entries)` on their wallet account. There's no balance column that can drift.
- `funding_account`: the user's Liberty virtual account (NUBAN). Inflows to it are attributed to that user.
- `inflow`: normalised inflow events (Liberty bank transfer or Paystack card) plus raw payload and verification status, keyed by provider + session_id/reference (unique).
- `bank`: a static list of banks with NIP and CBN codes. It's seeded, since Liberty has no bank-list endpoint.
- `notification` / `outbox`: push, in-app and WhatsApp-mock messages.
- `audit_log`: every create, edit or pause, and every money action.

All money is stored as **integer kobo**.

## 5. Scheduling and payout rules (the part that must be boringly reliable)

1. **Schedule maths** runs in `Africa/Lagos` using an rrule-style generator. "Monthly on the 31st" falls back to the month's last day.
2. **Materialise runs** ahead of time, up to the next 35 days. That gives the calendar real rows and lets the funding calculator count real occurrences.
3. **Idempotency:** `request_reference = run.id` (a UUID), with a unique DB constraint. A run can never be sent twice.
4. **Never blind-retry.** If a transfer call times out or the outcome is unknown, we run a **TSQ** (`verify_transfer`) before doing anything else. We retry only on a confirmed failure.
5. **Pending → final:** the worker polls TSQ at 30s, 2m, 10m and 1h. After that the run is flagged for you to review.
6. **Reserve, then send.** In one DB transaction, the worker checks `wallet balance ≥ amount + ₦50 fee` and moves that sum from the wallet into a `reserved` hold. Only then does it call the provider. On success the hold becomes a real debit to `liberty_pool` and `fees`. On a confirmed failure the hold is released back to the wallet. Two runs due at the same minute can never spend the same naira twice.
7. **Protection check:** before reserving, the worker applies the protection rules in §6a. A non-priority run that would eat into money protected for priority plans is skipped as `skipped_protected`. You get a push: "⛽ Fuel skipped to protect 💛 Mum & 🍲 Upkeep. Top up ₦X to send it now."
   - **Insufficient funds:** if even a priority run can't be covered, it's `skipped_insufficient_funds` and you get a one-tap "top up & send now".
   - You choose per plan whether a skipped run is dropped or retried later that day (after a top-up).
   - **Ordering:** runs due at the same minute go priority plans first (by your rank), then the rest by rank.
8. **Missed window** (for example, the server was down): send late if within 6h, otherwise mark it missed and ask you. A ₦3k upkeep from yesterday shouldn't fire silently today.
9. **Guardrails:**
   - Daily spend cap and per-plan cap
   - "Pause everything" kill switch
   - New recipients must pass name enquiry and your confirmation
   - PIN re-entry to create or edit plans and recipients

## 6. Funding model

- **Real money in one place:** all money physically sits in **one Liberty pool account**, and every payout's `source_account` is the pool NUBAN.
- **One balance per user:** each user has **one balance**, held only in our ledger, and all plans draw from it. Users can **protect** important plans so other plans can't drain the money they need (see §6a).
- **Ways to fund:**
  1. **Bank transfer** to your personal Liberty virtual account (NUBAN). We confirm the inflow, then credit `user_wallet` and debit `liberty_pool`.
  2. **Card debit via Paystack** (optional). Paystack's webhook plus a verify call confirm it, then we credit `user_wallet` and debit `paystack_settlement`.
- **Inflow safety:** an inflow is credited only once it is verified (`verify_event` for Liberty, verify-transaction for Paystack). The unique key on provider + session_id means a replayed webhook can never credit twice.
- **Reconciliation:** a daily job sums the ledger and checks it against the provider transaction records (TSQ / verify), then flags any mismatch. With no balance endpoint, our ledger plus the per-transaction checks is the whole picture.
- **Funding calculator:**
  - Pick a horizon: this week, this month, the next 3 months or a custom range.
  - It shows the exact runs, **amount + ₦50 fee per run**, the total needed, your current balance (minus any active holds) and the top-up amount.
  - It also shows a **runway**: "Funded until Fri 24 Oct 🎯".

## 6a. Protecting important plans (priorities and allocations)

The problem: one shared balance means a big "nice-to-have" plan could leave nothing for Mum or daily upkeep. Users can protect plans in two ways. Both are pure ledger maths, with no extra bank accounts.

### Option A: Priority plans (recommended default)
Mark 1–2 plans (any number is allowed) as **🛡️ Priority**. The system **calculates the monthly requirement itself** from each plan's schedule. You never type a reserve amount.

**Protected floor (monthly, prorated)**
- **Window = the current calendar month.** On the 1st of every month the floor resets to the new month's full requirement.
- **Prorated to what's left of the month:**
  - floor = Σ over priority plans of (amount + ₦50 fee) × the runs **still due from now until month-end**
  - Mid-month (e.g. the 11th of a 30-day month), daily upkeep counts **20** remaining days, not 30.
  - A plan created or resumed mid-month counts only its remaining runs. A plan ending mid-month counts only up to its end date.
  - A monthly plan (Mum) counts in full until it's paid that month, then drops to 0.
- **Free balance** = balance − active holds − allocations − protected floor.

**Priority order (max 3)**
- Priorities are numbered **1, 2, 3**, and there are at most three. Priority 1 is paid first.
- **Priority k** goes out only if the balance left afterwards still covers the remaining runs this month of **priorities 1 … k−1**.
- **Non-priority plans** go out only if the balance left afterwards still covers **all** remaining priority runs.
- **Changing the order:** setting a plan to slot k pushes the plans at k and below down one place. If that would make a 4th priority, the plan pushed out stops being a priority, and the user sees the new order and is warned before confirming.
- **Data model:** `plan.priority_rank` ∈ {null, 1, 2, 3}, with a unique constraint per user.

**Rules**
- A **priority run** goes out whenever `balance − holds ≥ amount + fee`. It draws from the protected money, and the floor shrinks by the same amount.
- A **non-priority run** goes out only if `free balance ≥ amount + fee`, i.e. only if paying it leaves the balance **≥ the remaining priority requirement**. Otherwise it's skipped (`skipped_protected`).
- If the balance is already below the floor, every non-priority plan is held. Priority plans run in rank order until the money runs out.
- **Same-moment runs:** priority first (by rank), then the others (by rank).

**Month forecast (no surprises)**
- **When it runs:** on the 1st of each month, after every top-up, and whenever a plan changes.
- **What it does:** simulates the rest of the month run by run and tells you upfront which payments will be skipped, and the exact top-up that saves them.
  > "This month: 🛡️ priorities fully covered ✅ · 🤝 Cousin (₦25,000, Nov 30) will be skipped — top up ₦16,600 to cover it."

**Worked example (your numbers, November 2026 = 30 days, balance ₦190,000)**
| Priority plan | Calculation | Requirement |
|---|---|---|
| 🍲 Upkeep ₦5k daily | 30 × (5,000 + 50) | ₦151,500 |
| 💛 Mum ₦30k on the 30th | 1 × (30,000 + 50) | ₦30,050 |
| **Protected floor on Nov 1** | | **₦181,550** |
| **Free = 190,000 − 181,550** | | **₦8,450** |

- 🤝 Cousin needs ₦25,050. Paying it would leave ₦164,950, which is below the ₦181,550 priority requirement, so **Cousin is not paid**. The Nov 1 forecast already says so and asks for **₦16,600** to cover it.
- **Every day:** Upkeep goes out. The balance and the floor both drop by ₦5,050, so free stays at ₦8,450.
- **Nov 30, step by step:**
  1. The last Upkeep goes out at 6am. Balance ₦38,500, floor ₦30,050 (Mum).
  2. Mum is paid first. Balance ₦8,450.
  3. Cousin needs ₦25,050, so it's skipped, and you get a push with the ₦16,600 top-up button.
- **If you top up ₦16,600 anytime in November,** the forecast turns green and Cousin is paid on the 30th.
- **Dec 1:** the floor resets to December's full prorated requirement.

**Worked example 2: the same non-priority payment on different days (fees left out for clarity)**
🍲 Upkeep ₦5k/day for 30 days (₦150k/month) is **priority**. 💛 Mum ₦30k is **not** priority. The wallet holds ₦150,000 at the moment Mum is due.

| Mum due on | Upkeep still due this month | Needed for a successful month | Balance after paying Mum | Result |
|---|---|---|---|---|
| **2nd** | 28 days × ₦5k = ₦140k | ₦140k + ₦30k = ₦170k | ₦120k (< ₦140k) | ❌ **Skipped**: it would break upkeep |
| **3rd** | 27 days × ₦5k = ₦135k | ₦135k + ₦30k = **₦165k** | ₦120k (< ₦135k) | ❌ **Skipped**: top up ₦15k to send |
| **20th** | 10 days × ₦5k = ₦50k | ₦50k + ₦30k = ₦80k | ₦120k (≥ ₦50k) | ✅ **Sent** |

- **"Days still due"** means the upkeep runs after today's 6am run, through month-end.
- **With fees on,** each payment adds ₦50. On the 3rd that makes ₦135,000 + 27 × ₦50 + ₦30,050 = **₦166,400**.

### Option B: Allocation (fixed earmark)
Ring-fence a **fixed amount** for a plan. For example, *"keep ₦60,000 for 💛 Mum, no matter what"*. That sum is set aside in a ledger sub-account (`user_wallet:allocation:{plan}`) that **only that plan can spend**. Everything else draws from what's left.

- **Top-ups:** you choose how they split, either *fill allocations first* (default) or *add to free balance only*.
- **Topping up an allocation:** when the plan spends from its allocation, the earmark drops. You choose whether it **auto-refills** from free balance, up to the set amount, on each top-up.
- **Turning it off:** removing an allocation returns its money to free balance.

### How they combine
- A plan can have **one** of `none`, `priority` or `allocation`.
- **Order of protection:**
  1. Allocations are untouchable by other plans.
  2. The priority floor is computed on the remaining (non-allocated) balance.
  3. Non-priority plans spend only what's free after both.
- **Guardrail:** you can't save a protection setup that is already underwater, e.g. allocations bigger than your balance, without seeing a warning and the exact top-up needed.

### In the UI
- **Home balance bar** is split into segments: 🔒 Allocated · 🛡️ Protected for priorities · 💸 Free to spend.
- **Plan cards** show a 🛡️ Priority or 🔒 ₦60k allocated badge, and say what's at risk ("Next Fuel will be skipped unless you add ₦12k").
- **Sentence builder** gets an extra chip: "…and **[🛡️ protect it]**".
- **Funding calculator** shows totals for priority-only and for everything, e.g. "₦81,900 keeps your priorities safe · ₦229,900 covers everything".

## 6b. Sign-up and KYC (three steps, nothing else)

**Order:** splash → 3 intro cards → **NIN → ID photo → selfie** → "You're verified" plus the user's account number → first plan.

1. **NIN:** the user enters 11 digits. We look it up through a licensed identity provider and show the name, date of birth and masked phone number: "Is this you?"
2. **ID photo:** NIN slip/card, driver's licence, voter's card or passport. A camera capture (or upload) of the front. We check that the image is clear, all four corners are visible, and the name matches the NIN.
3. **Selfie:** taken with the front camera. A liveness check plus a face match against the NIN photo and the ID photo.
4. **Then, automatically:**
   - We create the user's Liberty virtual account (`POST /api/v1/wema/virtual_accounts/`), named from the verified NIN record.
   - The user lands on Home with that account number ready.

**Implementation**
- **Provider:** a `KycProvider` interface (`lookupNin`, `checkDocument`, `matchSelfie`), **mocked for now**. Candidate real providers: Smile ID, Dojah, Prembly (IdentityPass), YouVerify, QoreID.
- **Selfie capture:** in the PWA we use `<input type="file" capture="user">`, which opens the camera on phones. A proper in-app camera with liveness prompts can come later.
- **Data protection (NDPA 2023):**
  - The NIN is encrypted at rest and shown masked.
  - ID and selfie images go to a private bucket with short-lived signed URLs and a set retention period.
  - The raw provider response is kept for audit.
- **Statuses:** `kyc_status` is one of `not_started | nin_verified | doc_uploaded | verified | rejected | needs_review`. Money features unlock only at `verified`.
- **Limits:** confirm with Liberty compliance which CBN KYC tier NIN + ID + selfie gives, and the daily or balance limits for that tier.

**Getting into the app (decided)**
- **When identity is verified:**
  1. A 6-digit **OTP** goes by SMS to the phone number on the NIN record.
  2. The user creates a **4-digit PIN** and confirms it. Easy PINs like 1234 or 0000 are rejected.
  3. The user can turn on **Face ID** (a WebAuthn passkey on that device). Then they're in.
- **Returning on the same device:** Face ID unlocks the app straight away, with "Use PIN instead" as a fallback.
- **New device or after signing out:** an OTP to the NIN phone, then the PIN, then the option to turn on Face ID again.
- **PIN storage:** hashed with argon2, never stored or logged in plain text. **5 wrong PINs** lock the account and require an OTP to reset.
- **Approvals:** Face ID or the PIN also approve money-moving changes: new recipients, new or edited plans, and raised caps.

## 7. UX and visual direction: fun, young, vibrant

**Feel:** bold colour blocks, chunky rounded cards, playful emoji and micro-animations. It should feel more like a game than a bank.
- **Palette (suggestion):** electric violet `#6C3BFF`, lime `#C6F432`, coral `#FF6B5B`, sun `#FFC83D` on off-white. Dark mode gets a deep ink background.
- **Type:** a rounded geometric display face (e.g. *Bricolage Grotesque* or *Clash Display*) with *Inter* for numbers. Naira amounts are big and bold.
- **Motion:** cards bounce in, a coin-drop animation plays when a transfer succeeds, confetti when a month is fully funded, and a swipe gesture pauses or resumes a plan.

**Screens (mobile-first, also laid out for desktop):**
1. **Home**
   - Hero card with a live countdown to the next drop ("⛽ ₦40,000 in 2h 14m")
   - Balance and a runway bar
   - "Today" and "This week" strips
2. **Plans:** colourful plan cards with emoji, amount, cadence and next run, plus a pause toggle.
3. **New plan: sentence builder** (the signature UX):
   > Send **[₦40,000]** for **[⛽ Fuel]** to **[Me]** every **[Week]** on **[Friday]** at **[2:00 PM]**
   - Tap any bold chip to change it.
   - A live preview shows the next 5 dates and the monthly cost.
4. **Fund:**
   - Total-needed breakdown
   - A big account number with copy and share buttons
   - Optional Paystack card top-up
5. **Calendar:** month view with dots per plan. Tap a day to see its drops.
6. **Activity:** a timeline of transfers, top-ups and messages, with statuses.
7. **People:**
   - Recipients with verified names (from name enquiry)
   - WhatsApp numbers
   - A preview of each person's message
8. **Settings:** PIN, caps, kill switch, notification prefs, provider status.

**PWA:** manifest and icons, plus offline shell caching. Web Push works on Android, and on iOS 16.4+ once the app is added to the home screen. An install prompt appears after the first plan is created.

**Later, fun extras:** natural-language quick add ("40k fuel every friday 2pm"), a monthly "wrapped" summary, and streaks.

## 8. Build phases

| Phase | Scope | Outcome |
|---|---|---|
| **0. Setup** ✅ | Django + DRF backend, React (Vite) frontend, Docker Compose (Postgres, API, worker, frontend), pytest, env config | `docker compose up` runs everything |
| **1. Core engine** ✅ | Data model, schedule maths, run materialiser, **double-entry ledger with reserve/settle/release**, ₦50 fee logic, **protection engine (priority floor + allocations)**, funding calculator, worker loop, **MockPaymentProvider** (transfers, TSQ, inflow webhooks, with a dev "simulate a top-up" button), **MockMessenger**; heavy unit tests (especially ledger and idempotency) | Plans fire on time against fake money |
| **2. App UI** ✅ | All screens above in React; sign-up (NIN → ID → selfie → SMS code → PIN → Face ID), sign-in, app lock; installable PWA; Vercel-ready (docs/DEPLOY.md). Web push still to come. | You can use it end-to-end with the mock |
| **3. Liberty for real** | LibertyProvider: token refresh, name enquiry, `transfer_money` from the pool NUBAN, TSQ, virtual accounts, inflow webhook and verify. Liberty's payloads get mapped onto our normalised events once we have samples. | Real API calls, tested with tiny amounts |
| **4. Live pilot (you only)** | Deploy (the same Docker images), live keys in a secret manager, caps set low (e.g. ₦5k/day), one plan to your own account | First real drops 🎉 |
| **5. Scale up personal use** | Fuel, upkeep, Mum, cousin; monitoring and alerts (Sentry), daily ledger reconciliation | Daily driver |
| **6. Optional / later** | Paystack card funding, Paystack as an alternative or fallback transfer rail, real WhatsApp provider, multi-user onboarding/KYC, NL quick-add | Ready to open up |

## 9. Decisions log

| Topic | Decision |
|---|---|
| Wallet balance endpoint | None. Liberty is a pool account, and **our ledger** holds every balance. |
| Per-plan accounts / pots | No provider accounts per plan. There's one shared balance, with optional **🛡️ priority** (dynamic protected floor) or **🔒 allocation** (fixed earmark) per plan, all in the ledger (§6a). |
| Priority protection | The floor is the **system-calculated, monthly prorated** requirement of the priority plans (remaining runs this month × (amount + ₦50)). A non-priority payment is skipped if it would leave the balance below that. It resets on the 1st. |
| Sandbox / test mode | Mocked for now. |
| Transfer fee | ₦50 per outward transfer, included in "total needed". |
| Webhook payloads | Mocked for now, behind normalised event types. |
| Paystack | Optional: card-debit funding and/or an outward transfer rail. |
| Runtime | Docker for everything (Node 22 in containers). |
| WhatsApp | Mocked (outbox and an in-app preview). |
| Paystack | Card top-ups on Paystack's checkout, with saved cards (token stored encrypted) for one-tap top-ups. The card fee is passed on and shown first (switchable). Payouts and name checks can run through Paystack (`PAYOUT_PROVIDER=paystack`). Webhooks are signature-checked, and every event is re-verified with Paystack. |
| Sign-up | NIN → ID photo → selfie, then OTP to the NIN phone, then a PIN, then Face ID (optional). |
| Sign-in | Face ID or PIN on a known device. New device: OTP, then PIN. |
| Payout to "me" | To your own bank account, saved as a verified recipient. |

### Still open (none of these block Phase 0–2)
1. **Allocation auto-refill:** on or off by default?
2. **KYC tier limits:** confirm with Liberty compliance what NIN + ID + selfie unlocks.

## 10. Security note ⚠️
The public Postman collection exposes some **non-placeholder credentials**:
- the `wema_bearer` and `sharedToken` variables
- an `Api_key` header on "name enquiry"
- several bearer JWTs

If any of these are real, **rotate them** and swap them for `{{variables}}` in the published docs. This app will keep every key server-side, in env vars or a secret manager. Nothing will be in the client or the repo.
