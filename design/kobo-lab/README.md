# Kobo design files

Kobo, SpenDrip's mascot, is drawn and animated in Rive. This folder keeps the source with the code.

| File | What it is |
|---|---|
| `kobo.rev` | The **editable** Rive file (Rive's "backup" format). Open it in the Rive editor to change Kobo. |
| `kobo.riv` | The **runtime** export. The app uses an identical copy at `frontend/public/kobo.riv`. |
| `kobo-before-legs-2026-10-04.riv` | Kobo as he was before legs, hands and outfits, kept to compare and roll back. |
| `index.html` | Kobo lab: today's Kobo vs. the latest file, with mood, legs/hands and eye-following controls. |
| `events.html` | Every seasonal outfit side by side, live. |

Preview the lab pages with any static server, e.g. `python3 -m http.server 8766 -d design/kobo-lab`, then open http://localhost:8766.

## What's inside the Rive file

Artboard `Kobo` (320×500), state machine `State Machine 1`, view model `ViewModel1` with number inputs:

| Input | Meaning |
|---|---|
| `moodIndex` | 0 idle, 1 happy, 2 celebrate, 3 send, 4 fill, 5 waiting, 6 worried, 7 puddle, 8 sleep, 9 peek, 10 point |
| `lookX`, `lookY` | Where the eyes look (about −8…8 and −6…6) |
| `legs`, `hands` | 0–1, legs+shorts and hands visibility |
| `lift` | −47 when standing on his legs, 0 otherwise |
| `xmas`, `newyear`, `love`, `mama`, `sallah`, `easter`, `naija`, `halloween`, `thanksgiving`, `stpatrick`, `usmom`, `juneteenth`, `july4` | 0–1, the seasonal outfits |

See `docs/kobo-library.md` for the design plan.

## Changing Kobo

1. Open `kobo.rev` in Rive and make the change.
2. Export for runtime and save it as both `design/kobo-lab/kobo.riv` and `frontend/public/kobo.riv`; export a backup over `kobo.rev`.
3. If the artboard size changes, update the height ratio in `frontend/src/components/RiveKobo.tsx`.
