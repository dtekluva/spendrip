# SpenDrip

Money that shows up on time. Schedule payouts to yourself and the people you look after, such as fuel every Friday at 2 PM, upkeep every morning, or Mum at month-end. You top up once, and SpenDrip sends each "drip" on time, protecting your priorities first.

- **Plan and decisions:** [docs/PLAN.md](docs/PLAN.md)
- **Clickable UI mock:** [docs/mock/spendrip-mock.html](docs/mock/spendrip-mock.html) (open it in a browser)

## Run it

You need Docker.

```bash
cp .env.example .env          # defaults use mock providers, so no real money moves
docker compose up -d --build
docker compose exec backend python manage.py seed_demo
```

| What | Where |
|---|---|
| React app | http://localhost:5173 |
| API | http://localhost:8010/api/health · `/api/summary` · `/api/plans` · `/api/activity` |
| Django admin | http://localhost:8010/admin (demo / demo) |
| Postgres | localhost:5434 (spendrip / spendrip) |

Dev-only helpers (on when `SPENDRIP_DEV_TOOLS=true`):

```bash
curl -X POST localhost:8010/api/dev/top-up -H 'Content-Type: application/json' -d '{"amount_naira": 50000}'
curl -X POST localhost:8010/api/dev/tick     # run one worker tick now
```

## Tests

```bash
docker compose exec backend pytest
```

The tests cover the schedule maths, priority protection (the worked examples from the plan), the ledger (including two runs racing for the same money), the worker (sending, retries, failures, missed runs, pause, daily cap) and the Liberty adapter.

## Layout

```
backend/
  engine/          pure Python: schedules, priority protection, month forecast
  accounts/        user, PIN, KYC records
  drips/           recipients, plans, runs, the worker (manage.py run_worker)
  ledger/          double-entry ledger, funding accounts, inflows
  notifications/   outbox (WhatsApp is mocked; messages land here)
  providers/       Liberty adapter, mocks, message copy
  api/             REST endpoints
frontend/          React + TypeScript (Vite)
docs/              plan and UI mock
```

## Money rules

- **Amounts:** all money is integer kobo.
- **Ledger:** append-only and double-entry. Every transaction sums to zero.
- **Idempotency:** each run's id is the transfer reference, and runs are unique per plan and time, so nothing can be paid twice.
- **Sending:** money is set aside under a row lock before any transfer call. If a call fails midway, the worker checks the transfer status with the provider and never resends blindly.
- **Releasing:** money returns to the wallet only when the provider confirms the transfer failed.
