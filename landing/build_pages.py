"""
Builds the SEO content pages for spendrip.com from pages.json, plus sitemap.xml.

    python3 build_pages.py

Each page gets the same header and footer as the home page, a unique title and description, a canonical URL,
Open Graph / X tags, and JSON-LD (WebPage + BreadcrumbList, Article for guides, FAQPage when it has FAQs).
The output is plain HTML in landing/<slug>/index.html, so Netlify serves it with no build step.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
SITE = "https://spendrip.com"
APP = "https://app.spendrip.com"
TODAY = date.today().isoformat()
HOME_UPDATED = "2026-10-03"

DROP = '<svg viewBox="0 0 40 52"><path d="M20 0S0 24 0 33a20 20 0 0 0 40 0C40 24 20 0 20 0z"/></svg>'
WORDMARK = f'spendr<span class="i">ı{DROP}</span>p'


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def text(s: str) -> str:
    """Plain text of a small HTML fragment (for JSON-LD)."""
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def nav(pages: list[dict]) -> str:
    guides = [p for p in pages if p.get("nav")]
    links = "".join(f'<a href="/{p["slug"]}/">{esc(p["nav"])}</a>' for p in guides)
    return f'''<nav class="top" id="nav">
  <div class="wrap bar">
    <a class="logo wm" href="/" aria-label="SpenDrip home">{WORDMARK}</a>
    <div class="links"><a href="/#how">How it works</a>{links}<a href="/#faq">FAQ</a></div>
    <div class="ctas"><a class="btn btn-ghost" href="{APP}">Sign in</a><a class="btn btn-dark" href="{APP}">Get started free</a></div>
  </div>
</nav>'''


def footer(pages: list[dict]) -> str:
    guides = "".join(f'<a href="/{p["slug"]}/">{esc(p["short"])}</a>' for p in pages if p.get("footer"))
    return f'''<footer>
  <div class="wrap">
    <div class="fbar">
      <div style="display:flex;flex-direction:column;gap:10px;max-width:320px">
        <a class="wm" href="/" style="text-decoration:none">{WORDMARK}</a>
        <span>Money that shows up on time, for you and the people you look after.</span>
      </div>
      <div class="cols">
        <div><b>Product</b><a href="/#how">How it works</a><a href="/#priorities">Priorities</a><a href="/#safety">Safety</a><a href="/fees/">Fees</a></div>
        <div><b>Guides</b>{guides}</div>
        <div><b>Get started</b><a href="{APP}">Create an account</a><a href="{APP}">Sign in</a><a href="/#faq">FAQ</a></div>
        <div><b>Company</b><a href="/about/">About</a><a href="/contact/">Contact</a></div>
      </div>
    </div>
    <div class="legal"><span>© {date.today().year} SpenDrip. Built for Nigeria.</span><span>Payments are processed by Paystack.</span></div>
  </div>
</footer>'''


def page_html(p: dict, pages: list[dict]) -> str:
    url = f"{SITE}/{p['slug']}/"
    crumbs = [{"name": "Home", "url": f"{SITE}/"}] + [{"name": p["short"], "url": url}]
    graph = [
        {"@type": p.get("page_type", "WebPage"), "@id": f"{url}#webpage", "url": url, "name": p["title"], "description": p["description"],
         "inLanguage": "en-NG", "isPartOf": {"@id": f"{SITE}/#website"}, "about": {"@id": f"{SITE}/#app"},
         "dateModified": p.get("updated", TODAY),
         "primaryImageOfPage": {"@type": "ImageObject", "url": f"{SITE}/og-image.png", "width": 1200, "height": 630}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": c["name"], "item": c["url"]} for i, c in enumerate(crumbs)]},
    ]
    if p.get("type") == "article":
        graph.append({"@type": "Article", "@id": f"{url}#article", "headline": p["h1"], "description": p["description"],
                      "inLanguage": "en-NG", "mainEntityOfPage": {"@id": f"{url}#webpage"},
                      "datePublished": p.get("published", TODAY), "dateModified": p.get("updated", TODAY),
                      "author": {"@type": "Organization", "@id": f"{SITE}/#org", "name": "SpenDrip"},
                      "publisher": {"@id": f"{SITE}/#org"}, "image": f"{SITE}/og-image.png"})
    if p.get("faq"):
        graph.append({"@type": "FAQPage", "@id": f"{url}#faq", "mainEntity": [
            {"@type": "Question", "name": text(q), "acceptedAnswer": {"@type": "Answer", "text": text(a)}} for q, a in p["faq"]]})
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=1).replace("</", "<\\/")

    body = "".join(f'<section class="art-sec"><h2 id="{s.get("id", "")}">{s["h2"]}</h2>{s["html"]}</section>' for s in p["sections"])
    faq = ""
    if p.get("faq"):
        faq = '<section class="art-sec"><h2 id="faq">Questions people ask</h2><div class="faq">' + "".join(
            f'<details><summary>{q}</summary><p>{a}</p></details>' for q, a in p["faq"]) + "</div></section>"
    related = [r for r in pages if r["slug"] in p.get("related", [])]
    rel = ""
    if related:
        rel = '<section class="art-sec"><h2>Keep reading</h2><div class="rel">' + "".join(
            f'<a class="rel-card" href="/{r["slug"]}/"><b>{esc(r["h1"])}</b><span>{esc(r["description"])}</span></a>' for r in related) + "</div></section>"
    toc = ""
    if len(p["sections"]) >= 4:
        toc = '<nav class="toc" aria-label="On this page"><b>On this page</b>' + "".join(
            f'<a href="#{s["id"]}">{text(s["h2"])}</a>' for s in p["sections"] if s.get("id")) + "</nav>"

    return f'''<!doctype html>
<html lang="en-NG">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(p["title"])}</title>
<meta name="description" content="{esc(p["description"])}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta name="theme-color" content="#0B1040">
<meta property="og:type" content="{'article' if p.get('type') == 'article' else 'website'}">
<meta property="og:site_name" content="SpenDrip">
<meta property="og:locale" content="en_NG">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(p.get('og_title', p['title']))}">
<meta property="og:description" content="{esc(p['description'])}">
<meta property="og:image" content="{SITE}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/og-image.png">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600;700;800&family=Figtree:wght@400;500;600;700;800&display=swap">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="/article.css">
<script defer src="https://stats.spendrip.com/k.js" data-website-id="51431cff-9282-4431-aaf6-22c3d7e6e476" data-domains="spendrip.com"></script>
<script defer src="/track.js"></script>
<script type="application/ld+json">
{ld}
</script>
{"".join(f'<script src="/{x}" defer></script>' for x in p.get("scripts", []))}
</head>
<body>
{nav(pages)}
<main class="article">
  <div class="wrap art-wrap">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Home</a><span>›</span><span>{esc(p["short"])}</span></nav>
    <header class="art-head">
      <span class="eyebrow">{esc(p.get("eyebrow", "Guide"))}</span>
      <h1>{p["h1"]}</h1>
      <p class="lead">{p["lead"]}</p>
      <div class="art-cta"><a class="btn btn-dark" href="{APP}">Get started free</a><span class="small">Free to join · fees shown before you start</span></div>
      <p class="small muted">Updated {date.fromisoformat(p.get("updated", TODAY)).strftime("%-d %B %Y")}</p>
    </header>
    {toc}
    <div class="art-body">{body}{faq}</div>
    <aside class="art-cta-box">
      <h2>Set it once. SpenDrip sends it on time.</h2>
      <p>Schedule transfers to yourself or anyone with a Nigerian bank or wallet account. Free to join.</p>
      <a class="btn btn-sun" href="{APP}">Get started free</a>
    </aside>
    {rel}
  </div>
</main>
{footer(pages)}
</body>
</html>
'''


LOST_KOBO = """<svg class="lost-kobo" viewBox="0 0 120 166" aria-hidden="true">
  <defs><linearGradient id="lk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE27A"/><stop offset="1" stop-color="#FFC400"/></linearGradient></defs>
  <ellipse cx="60" cy="160" rx="34" ry="5" fill="#0B1040" opacity=".12"/>
  <g fill="none" stroke="#E0A400" stroke-width="6" stroke-linecap="round"><path d="M48 132 L43 152"/><path d="M72 132 L79 149"/></g>
  <ellipse cx="38" cy="155" rx="10" ry="5.5" fill="#2436F2" transform="rotate(-12 38 155)"/>
  <ellipse cx="85" cy="151" rx="10" ry="5.5" fill="#1726C9" transform="rotate(24 85 151)"/>
  <path d="M33 153 h6 M81 148 h6" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
  <path d="M60 6S14 66 14 92a46 46 0 0 0 92 0C106 66 60 6 60 6z" fill="url(#lk)" stroke="#E0A400" stroke-width="2"/>
  <ellipse cx="40" cy="64" rx="7" ry="12" fill="#fff" opacity=".55" transform="rotate(25 40 64)"/>
  <circle cx="45" cy="92" r="5.5" fill="#0E1233"/><circle cx="75" cy="92" r="5.5" fill="#0E1233"/>
  <circle cx="47" cy="90" r="1.8" fill="#fff"/><circle cx="77" cy="90" r="1.8" fill="#fff"/>
  <ellipse cx="60" cy="112" rx="6" ry="7" fill="#0E1233"/>
  <ellipse cx="34" cy="106" rx="7" ry="4" fill="#FF4F8B" opacity=".35"/><ellipse cx="86" cy="106" rx="7" ry="4" fill="#FF4F8B" opacity=".35"/>
  <text x="98" y="36" font-family="Unbounded,Arial Black,sans-serif" font-weight="800" font-size="30" fill="#2436F2">?</text>
</svg>"""


def not_found_html(pages: list[dict]) -> str:
    """Netlify serves /404.html for any address that doesn't exist, with a real 404 status."""
    guides = "".join(f'<a class="rel-card" href="/{p["slug"]}/"><b>{esc(p["h1"])}</b><span>{esc(p["description"])}</span></a>'
                     for p in pages if p["slug"] in ("scheduled-transfers", "fees", "send-money-to-parents-monthly", "security"))
    return f'''<!doctype html>
<html lang="en-NG">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Page not found | SpenDrip</title>
<meta name="robots" content="noindex">
<meta name="theme-color" content="#0B1040">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600;700;800&family=Figtree:wght@400;500;600;700;800&display=swap">
<link rel="stylesheet" href="/site.css">
<link rel="stylesheet" href="/article.css">
<script defer src="https://stats.spendrip.com/k.js" data-website-id="51431cff-9282-4431-aaf6-22c3d7e6e476" data-domains="spendrip.com"></script>
<style>
.nf{{display:grid;gap:22px;justify-items:center;text-align:center;padding:56px 0 24px}}
.nf .lost-kobo{{width:120px;height:166px;animation:nf-bob 2.6s ease-in-out infinite}}
@keyframes nf-bob{{0%,100%{{transform:translateY(0) rotate(-4deg)}}50%{{transform:translateY(-8px) rotate(4deg)}}}}
@media (prefers-reduced-motion:reduce){{.nf .lost-kobo{{animation:none}}}}
.nf h1{{font-family:var(--display,Unbounded,sans-serif);font-size:clamp(30px,5vw,48px);margin:0;line-height:1.1}}
.nf p{{font-size:18px;max-width:46ch;margin:0;color:var(--muted,#5D6390)}}
.nf .acts{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}}
.nf-code{{font-weight:800;letter-spacing:.14em;font-size:13px;color:var(--muted,#5D6390)}}
.nf-lost,.nf-chill{{display:grid;gap:18px;justify-items:center}}
.nf [hidden]{{display:none}}
.chill-kobo{{width:min(340px,90vw);height:auto}}
</style>
<script>
  // Two 404 moods: puzzled Kobo or chilling Kobo, picked at random each visit.
  document.addEventListener("DOMContentLoaded", function () {{
    if (Math.random() < 0.5) return;
    document.querySelector(".nf-lost").hidden = true;
    document.querySelector(".nf-chill").hidden = false;
  }});
</script>
</head>
<body>
{nav(pages)}
<main class="article">
  <div class="wrap art-wrap">
    <section class="nf" data-v="lost">
      <div class="nf-lost">
        {LOST_KOBO}
        <span class="nf-code">ERROR 404</span>
        <h1>Kobo can't find this page</h1>
        <p>The link may be old or mistyped. Your money is fine: this is only a missing page on our website.</p>
      </div>
      <div class="nf-chill" hidden>
        <img class="chill-kobo" src="/kobo-chill.svg" width="340" height="250" alt="Kobo relaxing in a deckchair with sunglasses, a gold chain and a glass of zobo">
        <span class="nf-code">ERROR 404 · KOBO'S CHILL SPOT</span>
        <h1>Oops, you've landed in Kobo's chill spot</h1>
        <p>Not sure this is what you were looking for. Kobo's on a break here, but your drips aren't: everything still goes out on time.</p>
      </div>
      <div class="acts"><a class="btn btn-dark" href="/">Go to the home page</a><a class="btn btn-ghost" href="{APP}">Open the app</a></div>
    </section>
    <section class="art-sec"><h2>Popular pages</h2><div class="rel">{guides}</div></section>
  </div>
</main>
{footer(pages)}
</body>
</html>
'''


def sitemap(pages: list[dict]) -> str:
    # Google ignores <priority> and <changefreq>; it uses <lastmod> when it's accurate.
    urls = [(f"{SITE}/", HOME_UPDATED)] + [(f"{SITE}/{p['slug']}/", p.get("updated", TODAY)) for p in pages]
    items = "".join(f"\n  <url><loc>{u}</loc><lastmod>{m}</lastmod></url>" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}\n</urlset>\n'


def main():
    from content import PAGES as pages
    for p in pages:
        out = ROOT / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page_html(p, pages))
        print("wrote", out.relative_to(ROOT))
    (ROOT / "sitemap.xml").write_text(sitemap(pages))
    (ROOT / "404.html").write_text(not_found_html(pages))
    print("wrote 404.html")
    print("wrote sitemap.xml with", len(pages) + 1, "URLs")


if __name__ == "__main__":
    main()
