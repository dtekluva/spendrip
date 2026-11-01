# SpenDrip icons

One family ([Phosphor](https://phosphoricons.com), MIT) plus five icons drawn for SpenDrip, shared by the app and the
website. `manifest.json` is the source of truth; `build.py` turns it into code for both.

```
python3 design/icons/build.py      # after editing manifest.json or custom/*.svg
python3 design/icons/capture.py    # optional: review screenshots (local app on :5173, site on :8765)
```

## Three weights, one job each

| Weight | Use | App | Website |
|---|---|---|---|
| Regular | Everyday UI: navigation, buttons, rows. Monochrome, follows the text colour | `<Ic name="calendar" />` | `<svg class="i"><use href="#i-calendar-r"/></svg>` |
| Fill | Selected states (the current tab), status marks | `<Ic name="home" weight="f" />` | `#i-home-f` |
| Duotone | Features, onboarding, empty states, tips. Blue lines on soft yellow; white lines on the navy look | `<Feature name="protected" />` | `<svg class="i i-duo"><use href="#i-protected-d"/></svg>` |

Plan icons are always filled, on their colour tile: `<PlanIcon emoji={plan.emoji} />` or `<PlanIcon category="food" />`
in the app, `<span class="t pt pt-yellow"><svg class="i"><use href="#i-plan-upkeep"/></svg></span>` on the site.

## Drawn for SpenDrip (`custom/`)

Built on the brand droplet, on Phosphor's 256 grid with 16-unit round strokes so they sit with the rest:
**drip** (a plan: money in small regular drops), **protected** (a shield holding a drop), **priority** (a ranked list led
by a drop), **finance** (a split ring around a drop) and **fund** (add money: a drop with a plus). Each has
`name.svg`, `name-fill.svg` and `name-duotone.svg`; the duotone back layer uses
`style="fill:var(--duo-acc,currentColor);opacity:var(--duo-op,.2)"` so the colour comes from CSS.

## Plan tiles: colour by meaning

A plan's colour comes from what it's for (`hues` in the manifest): blue getting around, yellow food and the home, pink
family and giving, violet rent, teal bills and data, orange school and staff, coral health, green savings, slate
everything else. Finance charts use the same colour per category (`chart` overrides where two categories share a hue).

## Emoji

- Plans keep storing an emoji (`Plan.emoji`), so WhatsApp messages and emails still read "💛 Mum". The app shows the
  icon for it. `also` lists older and similar emoji (skin tones are ignored), so plans saved before this still match.
- An emoji the system doesn't know is shown as typed, on a neutral tile: it's the person's own choice.
- Emoji stay where they're part of a message: WhatsApp and email text, Kobo's speech, AI-written text.
- Kobo and the droplet are the brand's warmth; they're not icons and aren't replaced.

## Website guide pages

`landing/build_pages.py` turns plan emoji in `content.py` copy ("⛽ Fuel", "🧑🏾‍🍳 Musa") into the same plan tiles, using
this manifest, then runs `build.py` to inline the symbols. Write content with emoji as usual; unknown emoji stay as typed.

## Adding an icon

Add it to `ui` (or `plans`) in `manifest.json` with its Phosphor name and the weights it needs (`r`, `f`, `d`), run
`build.py`, and use the name. Only listed weights are bundled, so keep the lists short.
