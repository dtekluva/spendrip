# Kobo library: poses, outfits and seasons

Status: plan, 4 Oct 2026. Kobo today has 11 moods in Rive (`public/kobo.riv`, number input `moodIndex`): idle, happy, celebrate, send, fill, waiting, worried, puddle, sleep, peek, point.

## How to build it in Rive (so it scales)

Keep **three independent layers** in the one artboard, each driven from the view model:

| Input | Type | What it does |
|---|---|---|
| `moodIndex` | number (exists) | Face and body pose: what Kobo is *doing*. |
| `outfit` | enum, new | What Kobo is *wearing*: none, santa, flag cape, gele… Any outfit works with any mood. |
| `lookX`, `lookY` | number −1…1, new | Where the pupils point. The app feeds the pointer/finger position, so the eyes follow again (today only the drawn fallback did this, which is why the Rive Kobo doesn't track). |
| `palette` | enum or colour props, new | Accent colours for the season (confetti, sparkles, backdrop glow). |

The app picks the outfit by date, from a small `season` value the API sends with `/summary`. That way an event can be switched on, moved (moon-sighted holidays shift) or switched off from the server, without an app release.

Rules for every outfit: it must read at 40 px (the chip hint, the Activity rows), keep the face uncovered, and have a reduced-motion version.

## Legs (new, 4 Oct 2026)

Kobo can have short legs, shorts and blue trainers (brand cobalt `#2436F2`, white laces), but only where movement or attitude needs them. Legs are never bare: everyday shorts are navy `#1E2560` with a white drawstring; outfits can swap them (pink beach shorts on the chilling 404, trousers for formal looks). Most poses stay legless so Kobo still reads as a drop at 40 px.

Build them as a `legs` boolean (or a `legsPose` number) in the view model, separate from `moodIndex`, so a pose can switch them on.

| Pose | Legs? | Why |
|---|---|---|
| idle, waiting, worried, sleep, peek, puddle | No | A drop sitting still; legs add clutter. |
| happy | Optional, a small bounce | |
| celebrate | **Yes**: jumping, kicking out | The biggest win from legs. |
| send | **Yes**: running, a dust puff behind | Shows money moving. |
| fill (money arriving) | Yes: a little tap dance | |
| point | Yes: weight on one foot | |
| Lost (404) | **Yes**: standing, feet turned out, one heel up | Live now on the 404 page. |
| Chilling (404) | **Yes**: stretched out on the deckchair, crossed at the ankle | Live now on the 404 page. |
| Selfie coach, walking in, waving goodbye | Yes | Walking in and out of screens. |
| Seasonal: Independence Day march, football kick, dancing at New Year | Yes | |

**In the app since 4 Oct 2026:** celebrate only (legs kick out on the jump). The Rive file (`frontend/public/kobo.riv`, 320×460 artboard) has `legs` (0–1) and `lift` (−47 = standing) inputs; `RiveKobo.tsx` eases them in over 220 ms for the moods in `LEG_MOODS`. The running legs on *send* are built in the file but not switched on in the app yet.

Today's drawings with legs live in `landing/build_pages.py` (`LOST_KOBO`) and `landing/kobo-chill.svg`; the Rive version should match their proportions (legs about a quarter of the drop's height).

## 1. Product poses (needed regardless of season)

| Pose | Where it's used | Notes |
|---|---|---|
| Thinking / loading | Every "Checking…" spinner | Replace the generic spinner; a 2-second loop. |
| Lost | 404 pages (site and app) | Looking around with a "?"; live today as a drawing, should become Rive. |
| Offline | No network, gateway errors | Unplugged cable or a little umbrella in "rain". |
| Oops | "Something went wrong" | Distinct from *worried* (money) so errors don't feel like money trouble. |
| Locked / guard | PIN screen, security page | Holding a padlock or shield. |
| Selfie coach | Liveness check | Turns its own head left and right in time with the countdown, so people copy it. Directly helps the verification failures we saw. |
| Holding an ID card | ID photo step | |
| Counting coins | Fees, top-up quote | |
| Catching coins | Top-up received | Pair with *fill*. |
| Wave hello / goodbye | Welcome, sign-out | |
| High-five / thumbs up | Plan saved, first drip | |
| Shrug | Empty states ("nothing yet") | |
| Ringing a bell | Notifications, the update bar | |
| Megaphone | "New version ready", announcements | |
| Family of drops | Group payouts | Kobo with two or three mini drops behind it. |
| Calendar / clock | Scheduling sheets, the day-ahead reminder | |
| Gift | Referrals, if we add them | |

## 2. Seasons and events (Nigeria first)

Dates for moon-sighted holidays are approximate; the server switch handles the exact day.

| Event | When | Colours and meaning | Outfit idea | Pairs with |
|---|---|---|---|---|
| **New Year** | 1 Jan | Midnight blue and gold: a fresh start | Party hat, sparkler | Month outlook email on the 1st |
| **Back to school** | early Jan, late Apr, mid Sep | Primary colours | School bag, glasses | Student allowance plans |
| **Ramadan** | ~8 Feb–9 Mar 2027 | Deep green and gold, night blue | Small lantern, crescent; calm, kind poses (no food jokes) | |
| **Valentine's** | 14 Feb | Pink and red: love, care | Holding a heart | "Send love, on schedule" |
| **Mothering Sunday** | 7 Mar 2027 (4th Sunday of Lent; Nigeria follows the UK date) | Soft gold and coral | Gele and flowers | The "Mama" headline: our strongest moment of the year |
| **Eid al-Fitr (Sallah)** | ~9–10 Mar 2027 | Green and gold | Lantern, crescent, festive cap | Family support plans |
| **Easter** | 26–29 Mar 2027 (Good Friday to Easter Monday) | Lilac and spring yellow: renewal | Holding a painted egg or lily (no religious symbols on the drop itself) | |
| **Workers' Day** | 1 May | Red and navy | Hard hat or overalls | Household payroll (group plans) |
| **Eid al-Adha (Sallah)** | ~16–17 May 2027 | Green and gold | Lantern; a small ram companion if it's done kindly | |
| **Children's Day** | 27 May | Bright primaries | Balloon, school cap | Allowances |
| **Democracy Day** | 12 Jun | Green and white | Holding a small flag | |
| **Father's Day** | 3rd Sunday of June | Navy and tan | Cap or bow tie | |
| **New Yam Festival** | Aug (varies by community) | Earth tones | Holding a yam | Regional; optional |
| **Independence Day** | 1 Oct | Green-white-green: the flag | Flag cape, bunting; the biggest national moment | |
| **Black Friday** | late Nov | Black and gold | Shopping bag | Only if we run an offer |
| **Christmas** | 24–26 Dec | Red, green and gold | Santa hat, gift | "Send the December money early" |
| **Harmattan** | Dec–Feb | Dusty beige | Scarf, squinting at dust | Fun, low-priority |
| **Rainy season** | Apr–Oct | Grey-blue | Umbrella | Fun, low-priority |

## 3. Sport (with a trademark warning)

AFCON, the World Cup and the Olympics are huge in Nigeria, but their names, logos, mascots and the Olympic rings are protected trademarks. Use **generic** sport looks only:

| Moment | Look |
|---|---|
| Football tournaments (AFCON early 2027 and others) | Green-white jersey, football, a cheering pose. Never the tournament logo or the words in marketing. |
| Olympics (LA, July 2028) | A gold medal and a torch; no rings, no five-colour ring motif. |

## 4. Personal moments

| Moment | Notes |
|---|---|
| The person's birthday | We hold the date of birth from the ID check. Only use it with consent: add a "Celebrate my birthday" switch first. |
| One year with SpenDrip | Anniversary of the account. |
| First drip, 10th, 100th | Celebrate pose plus a badge. |
| First group payout | Family-of-drops pose. |
| All priorities covered for 3 months | A small streak moment. |

## 5. Avoid

- Spraying money at parties (owambe): spraying or mutilating naira is an offence under the CBN Act, so no "spraying" poses, even as a joke.
- Religious symbols on Kobo itself; keep faith holidays to colours, lanterns, eggs and greetings.
- Political party colours or logos.
- Anything that makes fun of fasting, poverty or debt.

## Build order

1. `lookX` / `lookY` (eye tracking) and the `outfit` layer with its first outfit, since every season depends on it.
2. Product poses: selfie coach, thinking, lost, offline, oops.
3. Christmas and New Year, which are the next two moments.
4. Ramadan, Valentine's, Mothering Sunday and Eid al-Fitr: four events in about five weeks in Feb–Mar 2027.
