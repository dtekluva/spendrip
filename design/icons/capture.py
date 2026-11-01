"""
Screenshots of the icon system on real screens, for review: the local app (docker compose, :5173, demo account) and
the website (python3 -m http.server 8765 -d landing). Writes design/icons/review/*.png.

    python3 design/icons/capture.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "review"
APP, SITE = "http://localhost:5173", "http://localhost:8765"
PHONE = {"width": 390, "height": 844}
# (name, path, height): the app scrolls inside its own frame, so long screens get a tall window instead of a full-page shot
SCREENS = [("home", "/", 1960), ("plans", "/plans", 1900), ("newplan", "/plans/new", 844), ("picker", "/plans/new", 844),
           ("finance", "/finance", 3300), ("profile", "/profile", 1400), ("settings", "/settings", 2150)]


def sign_in(page, look):
    page.goto(APP + "/")
    page.evaluate("""async (look) => {
      const csrf = () => decodeURIComponent((document.cookie.split('; ').find((c) => c.startsWith('csrftoken=')) || '').split('=')[1] || '');
      const post = async (path, body) => (await fetch('/api' + path, { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(body) })).json();
      await fetch('/api/me', { credentials: 'include' });
      const s = await post('/auth/signin/start', { email: 'demo@spendrip.com' });
      await post('/auth/signin/verify', { email: 'demo@spendrip.com', code: s.dev_code, pin: '2580' });
      // The look is saved on the account, so set it there (local demo account only).
      await fetch('/api/me/settings', { method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ look }) });
      localStorage.setItem('sd-seen-splash', '1');
    }""", look)


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        for look in ("light", "themed"):
            ctx = browser.new_context(viewport=PHONE, device_scale_factor=2)
            page = ctx.new_page()
            sign_in(page, look)
            for name, path, height in SCREENS:
                page.set_viewport_size({"width": PHONE["width"], "height": height})
                for _ in range(2):  # the local session sometimes drops between pages; sign in again if so
                    page.goto(APP + path)
                    page.wait_for_timeout(600)
                    for _ in range(10):  # tap through the splash until the app shows
                        if not page.locator(".splash").count():
                            break
                        page.locator(".splash").click(force=True)
                        page.wait_for_timeout(500)
                    page.wait_for_selector(".splash", state="detached", timeout=15000)
                    page.wait_for_timeout(2200)
                    if page.evaluate("fetch('/api/me', { credentials: 'include' }).then((r) => r.json()).then((j) => j.signed_in)"):
                        break
                    sign_in(page, look)
                if name == "picker":
                    try:
                        page.wait_for_selector(".sentence .chip", timeout=10000)
                    except Exception:
                        page.screenshot(path=str(OUT / "debug.png")); raise
                    page.locator(".sentence .chip").nth(1).click()
                    page.wait_for_timeout(700)
                page.screenshot(path=str(OUT / f"{name}-{look}.png"))
                print(name, look)
            ctx.close()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(SITE + "/")
        page.evaluate("document.querySelectorAll('.reveal').forEach((e) => e.classList.add('in', 'shown', 'visible'))")
        page.add_style_tag(content=".reveal{opacity:1 !important;transform:none !important} *{animation-play-state:paused !important}")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "site-desktop.png"), full_page=True)
        for i, sel in enumerate(["header", "#how", "#plan", "#plan + section", "#priorities", "#safety", "#guides"]):
            page.locator(sel).first.screenshot(path=str(OUT / f"site-{i}.png"))
        ctx = browser.new_context(viewport=PHONE, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(SITE + "/")
        page.add_style_tag(content=".reveal{opacity:1 !important;transform:none !important} *{animation-play-state:paused !important}")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "site-phone-hero.png"))
        print("site")
        sign_in(page := browser.new_context().new_page(), "dark")  # put the demo account back on its own look
        browser.close()


if __name__ == "__main__":
    main()
