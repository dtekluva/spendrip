"""
The monthly Search Console report: how spendrip.com did in Google search last month, and what to do about it.

Built from plain rows (see search_console.Client.query) so it can be tested without Google. Sections:
headline numbers, top searches, new searches, quick wins (ranked 4–20), low click rate (ranked well, rarely clicked),
content gaps (searched, but no page ranks), and pages (including sitemap pages that never showed up).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from html import escape

import requests

COUNTRY = "nga"           # Search Console's code for Nigeria
SITEMAP = "https://spendrip.com/sitemap.xml"

# Thresholds are low on purpose while the site is new; raise them as traffic grows.
NEW_MIN_IMPRESSIONS = 3
QUICK_WIN_POSITION = (4, 20)
QUICK_WIN_MIN_IMPRESSIONS = 10
LOW_CTR_MAX_POSITION = 5
LOW_CTR = 0.03
LOW_CTR_MIN_IMPRESSIONS = 20
GAP_MIN_POSITION = 20
GAP_MIN_IMPRESSIONS = 5
TOP = 15


def last_month(today: date) -> tuple[date, date]:
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def month_before(start: date) -> tuple[date, date]:
    return last_month(start)


@dataclass
class Data:
    start: date
    end: date
    totals: dict            # Nigeria, this month: clicks, impressions, ctr, position
    totals_prev: dict
    totals_world: dict
    queries: list[dict]     # Nigeria, this month
    queries_prev: list[dict]
    pages: list[dict]       # all countries, this month
    sitemap: list[str] = field(default_factory=list)


def fetch(client, today: date) -> Data:
    start, end = last_month(today)
    pstart, pend = month_before(start)
    one = lambda rows: rows[0] if rows else {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    return Data(
        start=start, end=end,
        totals=one(client.query(start, end, [], COUNTRY)),
        totals_prev=one(client.query(pstart, pend, [], COUNTRY)),
        totals_world=one(client.query(start, end, [])),
        queries=client.query(start, end, ["query"], COUNTRY),
        queries_prev=client.query(pstart, pend, ["query"], COUNTRY),
        pages=client.query(start, end, ["page"]),
        sitemap=sitemap_urls(),
    )


def sitemap_urls(url: str = SITEMAP) -> list[str]:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return re.findall(r"<loc>([^<]+)</loc>", r.text)
    except requests.RequestException:
        return []


# ---------------------------------------------------------------- analysis

def sections(d: Data) -> dict:
    prev = {q["query"]: q for q in d.queries_prev}
    by_imp = sorted(d.queries, key=lambda q: -q["impressions"])
    top = [{**q, "change": q["impressions"] - prev[q["query"]]["impressions"] if q["query"] in prev else None} for q in by_imp[:TOP]]
    new = [q for q in by_imp if q["query"] not in prev and q["impressions"] >= NEW_MIN_IMPRESSIONS][:10]
    lo, hi = QUICK_WIN_POSITION
    wins = [q for q in by_imp if lo <= q["position"] <= hi and q["impressions"] >= QUICK_WIN_MIN_IMPRESSIONS][:10]
    low_ctr = [q for q in by_imp if q["position"] <= LOW_CTR_MAX_POSITION and q["ctr"] < LOW_CTR
               and q["impressions"] >= LOW_CTR_MIN_IMPRESSIONS][:10]
    gaps = [q for q in by_imp if q["position"] > GAP_MIN_POSITION and q["impressions"] >= GAP_MIN_IMPRESSIONS][:10]
    pages = sorted(d.pages, key=lambda p: -p["impressions"])[:10]
    seen = {_norm(p["page"]) for p in d.pages}
    unseen = [u for u in d.sitemap if _norm(u) not in seen]
    return {"top": top, "new": new, "wins": wins, "low_ctr": low_ctr, "gaps": gaps, "pages": pages, "unseen": unseen}


def _norm(url: str) -> str:
    return url.split("#")[0].rstrip("/").replace("://www.", "://")


def _pct(a: float, b: float) -> str:
    if not b:
        return "new" if a else "–"
    return f"{(a - b) / b:+.0%}"


# ---------------------------------------------------------------- rendering

def _num(v) -> str:
    return f"{v:,.0f}"


def _row(q: dict, key: str = "query", change: bool = False) -> list[str]:
    cells = [q[key].replace("https://spendrip.com", "") or "/", _num(q["clicks"]), _num(q["impressions"]),
             f"{q['ctr']:.1%}", f"{q['position']:.1f}"]
    if change:
        cells.append("new" if q.get("change") is None else f"{q['change']:+,}")
    return cells


HEAD = ["Search", "Clicks", "Shown", "Click rate", "Position"]


def render(d: Data) -> tuple[str, str, str]:
    """(subject, text, html)"""
    s = sections(d)
    t, p, w = d.totals, d.totals_prev, d.totals_world
    month = d.start.strftime("%B %Y")
    plural = lambda n, word: f"{_num(n)} {word}{'' if n == 1 else 's'}"
    subject = f"🔎 SpenDrip in Google, {month}: {plural(t['clicks'], 'click')}, shown {plural(t['impressions'], 'time')} in Nigeria"
    headline = [
        ("Clicks", _num(t["clicks"]), _pct(t["clicks"], p["clicks"])),
        ("Times shown", _num(t["impressions"]), _pct(t["impressions"], p["impressions"])),
        ("Click rate", f"{t['ctr']:.1%}", f"was {p['ctr']:.1%}"),
        ("Average position", f"{t['position']:.1f}", f"was {p['position']:.1f}" if p["position"] else "–"),
    ]
    blocks: list[tuple[str, str, list[str], list[list[str]]]] = [
        ("Top searches", "Nigeria, by times shown. Change is against the month before.", HEAD + ["Change"],
         [_row(q, change=True) for q in s["top"]]),
        ("New this month", "Searches that showed SpenDrip for the first time.", HEAD, [_row(q) for q in s["new"]]),
        ("Quick wins", "Ranked 4 to 20: page one or the top three is close. Strengthen the page that ranks, add the exact phrase to "
         "a heading, and link to it from other pages.", HEAD, [_row(q) for q in s["wins"]]),
        ("Shown but not clicked", "In the top 5 but under 3% click rate. Rewrite the page title and description so they answer "
         "this search.", HEAD, [_row(q) for q in s["low_ctr"]]),
        ("Content gaps", "People search this, but SpenDrip ranks below 20. A new page, or a section on an existing one, could answer it.",
         HEAD, [_row(q) for q in s["gaps"]]),
        ("Pages", "All countries, by times shown.", ["Page", "Clicks", "Shown", "Click rate", "Position"],
         [_row(q, key="page") for q in s["pages"]]),
    ]
    if s["unseen"]:
        blocks.append(("Pages not showing up yet", "In the sitemap, but never shown in search this month. Check them in Search Console's "
                       "URL Inspection and request indexing.", ["Page"], [[u.replace("https://spendrip.com", "") or "/"] for u in s["unseen"]]))

    world = f"Worldwide: {_num(w['clicks'])} clicks, {_num(w['impressions'])} times shown."
    # plain text
    text = [subject, "", *[f"{k}: {v} ({c})" for k, v, c in headline], world, ""]
    for title, note, head, rows in blocks:
        text += [title.upper(), note] + ([" | ".join(head)] + [" | ".join(r) for r in rows] if rows else ["Nothing this month."]) + [""]
    text.append("Search Console: https://search.google.com/search-console")
    # html
    cell = "padding:6px 8px;border-bottom:1px solid #ECEEF7;font-size:13px;color:#3b4070;text-align:{a}"
    html_blocks = []
    for title, note, head, rows in blocks:
        tbl = ('<p style="margin:0;font-size:13px;color:#8a8fb5">Nothing this month.</p>' if not rows else
               '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse"><tr>'
               + "".join(f'<th style="{cell.format(a="left" if i == 0 else "right")};color:#8a8fb5;font-weight:600">{escape(h)}</th>'
                         for i, h in enumerate(head)) + "</tr>"
               + "".join("<tr>" + "".join(f'<td style="{cell.format(a="left" if i == 0 else "right")}">{escape(c)}</td>'
                                         for i, c in enumerate(r)) + "</tr>" for r in rows) + "</table>")
        html_blocks.append(f'<h2 style="margin:26px 0 4px;font-size:17px;color:#0E1233">{escape(title)}</h2>'
                           f'<p style="margin:0 0 10px;font-size:13px;line-height:1.5;color:#3b4070">{escape(note)}</p>{tbl}')
    tiles = "".join(f'<td style="padding:10px;background:#F4F5FB;border-radius:12px;width:25%"><div style="font-size:12px;color:#8a8fb5">'
                    f'{escape(k)}</div><div style="font-size:20px;font-weight:800;color:#0E1233">{escape(v)}</div>'
                    f'<div style="font-size:12px;color:#3b4070">{escape(c)}</div></td>' for k, v, c in headline)
    html = f"""<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#F4F5FB;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F5FB;padding:24px 8px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:#ffffff;border-radius:20px;overflow:hidden">
<tr><td style="background:#0B1040;padding:18px 24px;font-size:22px;font-weight:800;color:#ffffff">spendrip<span style="color:#FFD23F">.</span>
<span style="font-size:14px;font-weight:600;color:#c9cdf0"> · Google search, {escape(month)}</span></td></tr>
<tr><td style="padding:22px 24px">
<p style="margin:0 0 12px;font-size:13px;color:#8a8fb5">Nigeria, {d.start:%-d %b} to {d.end:%-d %b}, against the month before.</p>
<table width="100%" cellpadding="0" cellspacing="6" style="border-collapse:separate"><tr>{tiles}</tr></table>
<p style="margin:10px 0 0;font-size:13px;color:#3b4070">{escape(world)}</p>
{"".join(html_blocks)}
<p style="margin:26px 0 0"><a href="https://search.google.com/search-console" style="display:inline-block;background:#0B1040;color:#FFD23F;font-weight:800;font-size:14px;text-decoration:none;padding:12px 20px;border-radius:12px">Open Search Console</a></p>
</td></tr></table></td></tr></table></body></html>"""
    return subject, "\n".join(text), html
