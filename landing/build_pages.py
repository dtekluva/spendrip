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
      </div>
    </div>
    <div class="legal"><span>© {date.today().year} SpenDrip. Built for Nigeria.</span><span>Card payments are processed by Paystack.</span></div>
  </div>
</footer>'''


def page_html(p: dict, pages: list[dict]) -> str:
    url = f"{SITE}/{p['slug']}/"
    crumbs = [{"name": "Home", "url": f"{SITE}/"}] + [{"name": p["short"], "url": url}]
    graph = [
        {"@type": "WebPage", "@id": f"{url}#webpage", "url": url, "name": p["title"], "description": p["description"],
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
    print("wrote sitemap.xml with", len(pages) + 1, "URLs")


if __name__ == "__main__":
    main()
