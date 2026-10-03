# Kobo, the SpenDrip drop

Kobo exists in two versions that behave the same way:

| File | What it is |
|---|---|
| `frontend/public/kobo.riv` | The Rive runtime file the app loads (12 KB). |
| `docs/kobo/kobo.rev` | An editable backup of the Rive source. Open it in the Rive editor to change Kobo. |
| `frontend/src/components/Kobo.tsx` | The SVG + CSS Kobo. It shows instantly while Rive loads, and is used for "eyes follow your finger" and for people who turn on reduce motion. |
| `frontend/src/components/RiveKobo.tsx` | Plays `kobo.riv` and sets the mood. |

## How the app picks a mood

The Rive file has one number, `moodIndex`, on its view model. The state machine (`State Machine 1`) switches to the matching animation with a 250 ms blend:

| moodIndex | Mood | Used when |
|---|---|---|
| 0 | idle | Nothing to do |
| 1 | happy | The month is covered |
| 2 | celebrate | Plan created, fully funded, verified |
| 3 | send | A drip just went out |
| 4 | fill | Money was added |
| 5 | waiting | A drip is waiting for a top-up |
| 6 | worried | Priorities are short |
| 7 | puddle | Something went wrong |
| 8 | sleep | Everything is paused |
| 9 | peek | Lock screen, empty states |
| 10 | point | One arm up, pointing at something above (plan builder hint). Arms are hidden in every other mood. |

In code you never use the numbers: `<Kobo mood="celebrate" />` handles it.

## Changing Kobo

1. Open `docs/kobo/kobo.rev` in the Rive editor (or the cloud file it came from).
2. Keep the artboard name `Kobo`, the state machine name, and the `moodIndex` number with values 0–10.
3. Export for runtime (`.riv`) and replace `frontend/public/kobo.riv`. Export a fresh `.rev` backup here too.

The Rive file was built through Rive's MCP server, step by step, with a snapshot after each step.
