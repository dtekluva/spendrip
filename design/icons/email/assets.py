"""
Images for SpenDrip's emails, drawn from the same icons and Kobo as the app (email clients can't show inline SVG).

    python3 design/icons/email/assets.py

Writes landing/email/*.png (served from spendrip.com/email, settings.EMAIL_ASSET_BASE), at 3x for sharp phones:
  wordmark.png        the white wordmark with the drop over the i, for the navy header
  kobo-happy.png      Kobo, for "Kobo's take"
  cat-<category>.png  each Finance category's plan tile (manifest "categories")
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "landing/email"
sys.path.insert(0, str(HERE.parent))
from build import glyph  # noqa: E402

SUN = "#FFD23F"
DROP = '<svg viewBox="0 0 40 52"><path d="M20 0S0 24 0 33a20 20 0 0 0 40 0C40 24 20 0 20 0z"/></svg>'


def kobo(mood: str) -> str:
    """The app's drawn Kobo as static SVG markup (bundles kobo-static.tsx with the frontend's esbuild)."""
    fe = ROOT / "frontend"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "kobo.cjs"
        subprocess.run([str(fe / "node_modules/.bin/esbuild"), str(HERE / "kobo-static.tsx"), "--bundle", "--platform=node",
                        "--jsx=automatic", "--external:@rive-app/*", "--log-level=warning", f"--outfile={out}"],
                       check=True, cwd=fe, env={"NODE_PATH": str(fe / "node_modules"), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
        return subprocess.run(["node", str(out), mood], check=True, capture_output=True, text=True, cwd=fe).stdout


def main():
    m = json.loads((HERE.parent / "manifest.json").read_text())
    plans = {p["key"]: p for p in m["plans"]}
    svg = lambda body, colour, size: (f'<svg viewBox="0 0 256 256" width="{size}" height="{size}" fill="{colour}" '
                                      f'style="color:{colour};--duo-acc:{SUN};--duo-op:.9">{body}</svg>')
    items = []  # (file, html)
    items.append(("wordmark", f'<span class="wm">spendr<span class="i">ı{DROP}</span>p</span>'))
    items.append(("kobo-happy", f'<span class="k">{kobo("happy")}</span>'))
    for cat, key in m["categories"].items():
        p, hue = plans[key], m["hues"][plans[key]["hue"]]
        items.append((f"cat-{cat}", f'<span class="tile" style="background:{hue["bg"]}">{svg(glyph(p["icon"], "f"), hue["ink"], 20)}</span>'))

    # Kobo's look comes from the app's stylesheet (the .kobo rules), minus the colours that need the app's variables.
    kobo_css = "".join(l for l in (ROOT / "frontend/src/styles.css").read_text().splitlines() if l.startswith(".kobo"))
    css = f"""
      body{{margin:0;padding:20px;background:transparent}} .x{{display:inline-block;margin:10px;line-height:0}}
      .wm{{font-family:Unbounded,'Arial Black',sans-serif;font-weight:800;font-size:26px;letter-spacing:-.03em;color:#fff;line-height:1.3;
           display:inline-block;padding-top:6px}}
      .wm .i{{position:relative;display:inline-block}}
      .wm .i svg{{position:absolute;left:50%;top:-.24em;width:.34em;height:.44em;translate:-50% 0;fill:{SUN}}}
      .tile{{width:36px;height:36px;border-radius:12px;display:grid;place-items:center}}
      .x{{width:max-content}} .tile{{flex:none}}
      .k .kobo,.k svg{{width:56px !important;height:67px !important}} {kobo_css} .kobo .k-shadow{{fill:#0E1233}}
      *{{animation:none !important}}"""
    page_html = (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" '
                 f'href="https://fonts.googleapis.com/css2?family=Unbounded:wght@800&display=swap"><style>{css}</style></head><body>'
                 + "".join(f'<div class="x" id="{name}">{h}</div>' for name, h in items) + "</body></html>")
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        page = b.new_page(device_scale_factor=3)
        page.set_content(page_html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        for name, _ in items:
            page.locator(f"#{name}").screenshot(path=str(OUT / f"{name}.png"), omit_background=True)
            print(f"landing/email/{name}.png")
        b.close()


if __name__ == "__main__":
    main()
