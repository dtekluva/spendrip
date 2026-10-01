# Deploying SpenDrip to Vercel

SpenDrip deploys as **two Vercel projects from this one repo**, plus a Postgres database:

| Project | Root directory | What it is |
|---|---|---|
| `spendrip-api` | `backend` | Django API on Vercel's Python runtime (`backend/vercel.json`) |
| `spendrip` (web) | `frontend` | React app (Vite), served as static files (`frontend/vercel.json`) |
| Database | n/a | Postgres from **Neon** (or Supabase, or Vercel Postgres) |

The web app sends `/api/*` to the API through a Vercel rewrite. To the browser, everything comes from one site, so sign-in cookies, CSRF and Face ID all work normally.

## 1. Create the database

1. Create a Neon project (region: Europe/Frankfurt is closest to Lagos).
2. Copy the **pooled** connection string. It contains `-pooler` and ends with `?sslmode=require`.

## 2. Deploy the API

1. In Vercel, go to **Add New → Project**, import `dtekluva/spendrip`, set **Root Directory** to `backend`, and leave Framework as **Other**.
2. Add these environment variables:

| Name | Value |
|---|---|
| `DATABASE_URL` | the Neon pooled URL |
| `DB_CONN_MAX_AGE` | `0` |
| `DJANGO_SECRET_KEY` | a long random string (`python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `.vercel.app,spendrip.com,www.spendrip.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://<your-web-domain>` (e.g. `https://spendrip.vercel.app`) |
| `CORS_ALLOWED_ORIGINS` | same as above |
| `WEBAUTHN_RP_ID` | your web domain without `https://` (e.g. `spendrip.vercel.app`) |
| `WEBAUTHN_ORIGIN` | `https://<your-web-domain>` |
| `CRON_SECRET` | a long random string |
| `SPENDRIP_DEV_TOOLS` | `true` for now (see "Test mode" below) |
| `PAYMENT_PROVIDER` | `mock` (switch to `liberty` once it's tested) |

3. Deploy, then open `https://<api-domain>/api/health`. It should answer `{"ok": true, ...}`.
4. Create the tables from your own machine, pointing at Neon:

```bash
docker compose run --rm --no-deps -e DATABASE_URL='<neon pooled url>' backend python manage.py migrate
docker compose run --rm --no-deps -e DATABASE_URL='<neon pooled url>' backend python manage.py createsuperuser
```

Run `migrate` again after every deploy that adds a migration.

## 3. Deploy the web app

1. Edit `frontend/vercel.json` and replace `REPLACE-WITH-YOUR-API.vercel.app` with your API's domain. Commit the change.
2. In Vercel, go to **Add New → Project**, import the same repo, set **Root Directory** to `frontend`, and leave Framework as **Vite** (it's detected).
3. Deploy. Open the site, and on your phone use **Add to Home Screen** to install it.

## 4. Keep the payout worker ticking

Payouts happen when `/api/cron/tick` runs. `backend/vercel.json` asks Vercel Cron to call it **every minute**, and Vercel sends `Authorization: Bearer $CRON_SECRET` itself.

- **Vercel Pro:** that's all you need.
- **Vercel Hobby (free):** crons run at most once a day, which is too slow. Use a free pinger such as cron-job.org instead. Set it to call `https://<api-domain>/api/cron/tick` every minute with this header:
  `Authorization: Bearer <CRON_SECRET>`

A tick is short and safe to repeat. A database lock stops two ticks from running at once, and a payment can never be sent twice. If a tick is missed, runs still go out within the late window, which is 6 hours.

## 5. Custom domain (spendrip.com)

1. Add `spendrip.com` to the **web** project in Vercel and follow the DNS steps.
2. Then update the API's `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `WEBAUTHN_RP_ID` (`spendrip.com`) and `WEBAUTHN_ORIGIN` (`https://spendrip.com`), and redeploy the API.
3. Face ID passkeys are tied to the domain, so set them up again after moving domains.

## Test mode (where things stand now)

The payment provider, SMS, WhatsApp and KYC are still **mocked**, so no real money moves and no real texts go out. With `SPENDRIP_DEV_TOOLS=true`:

- **Sign-in codes:** SMS codes show on screen (labelled "Test mode").
- **Sign-up:** shows "Use a sample ID / selfie" buttons.
- **Add money:** has test top-up buttons.

Before real money, wire Liberty (`PAYMENT_PROVIDER=liberty` plus the `LIBERTY_*` variables), an SMS provider and a KYC provider, then set `SPENDRIP_DEV_TOOLS=false`.

## Paystack

1. In the Paystack dashboard (**Settings → API Keys & Webhooks**), copy your keys into the API's env vars:
   - **To test:** set `PAYSTACK_MODE=test` with `TEST_PAYSTACK_SECRET_KEY` and `TEST_PAYSTACK_PUBLIC_KEY`.
   - **To go live:** set `PAYSTACK_MODE=live` with `PAYSTACK_SECRET_KEY` and `PAYSTACK_PUBLIC_KEY`.
   - **Safety:** live keys are refused while `SPENDRIP_DEV_TOOLS=true`. Dev tools show sign-in codes on screen, so they must be off in production.
   - **Name checks in test mode:** Paystack allows only 3 real-bank name checks a day. Live mode has no such limit.
2. Set the **webhook URL** to `https://<api-domain>/api/webhooks/paystack`. Card payments and transfers are confirmed through it, and every event is checked against its Paystack signature.
3. Set `PUBLIC_APP_URL` on the API to your web address (e.g. `https://spendrip.com`). After paying, Paystack sends people back to `/fund/card` there.
4. Set `FIELD_ENCRYPTION_KEY` to a long random string, and never change it. Saved-card tokens are encrypted with it.
5. **Payouts:** to send through Paystack, set `PAYOUT_PROVIDER=paystack`, then:
   - **Fund your Paystack balance.** Transfers come out of it.
   - **Turn off transfer OTP** (**Settings → Preferences**). Otherwise Paystack asks for a code on every transfer, and scheduled payouts can't go out.

## Liberty webhook

When Liberty is live, set its callback URL to `https://<api-domain>/api/webhooks/liberty`. Optionally set `LIBERTY_WEBHOOK_SECRET` and have Liberty send it as `X-SpenDrip-Secret`. Every inflow is checked with Liberty (`verify_event`) before it's credited, and each one is credited only once.
