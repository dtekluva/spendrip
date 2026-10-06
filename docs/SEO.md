# SEO for spendrip.com

Last updated: 3 October 2026.

## What gets indexed

- **spendrip.com** (Netlify site, `landing/`) is the public site meant to be found.
- **app.spendrip.com** is the signed-in app. It's kept out of search with an `X-Robots-Tag: noindex, nofollow` header and a matching meta tag. It isn't blocked in robots.txt, because then Google couldn't read the noindex instruction.

## How the site is built

| File | What it does |
|---|---|
| `landing/index.html` | Home page: title, description, canonical, Open Graph/X tags, and one JSON-LD graph (Organization, WebSite with site name, WebApplication, WebPage, FAQPage generated from the visible FAQ). |
| `landing/content.py` | Content for every guide and product page. |
| `landing/build_pages.py` | Turns `content.py` into static pages with the shared header and footer, canonical, OG tags, JSON-LD (WebPage, BreadcrumbList, Article, FAQPage), and `sitemap.xml`. Run `python3 landing/build_pages.py` after any content edit and commit the output. |
| `site.css`, `article.css`, `tools.js` | Shared styles and the two calculators (fees, black tax). The fee rules mirror `backend/engine/fees.py`; change both together. |
| `og-image.png`, `favicon.ico`, `site.webmanifest`, `robots.txt`, `sitemap.xml`, `llms.txt` | Sharing image, icons, manifest, crawler rules, sitemap, and a summary for AI tools. |
| `<key>.txt`, `.indexnow-key` | IndexNow key, so Bing (and the AI tools that use Bing's index) hear about changes immediately. |

## Pages and target searches

| Page | Aimed at |
|---|---|
| `/scheduled-transfers/` | scheduled transfer app Nigeria; schedule payment to bank account |
| `/fees/` | transfer charges; ₦50 stamp duty; transfer fee calculator |
| `/priorities/` | protecting important payments (product) |
| `/security/` | is SpenDrip safe |
| `/send-money-to-parents-monthly/` | send money to my mum every month; send money to parents automatically |
| `/upkeep-allowance/` | monthly upkeep allowance for wife; feeding allowance |
| `/student-allowance/` | monthly allowance for student in university; pocket money |
| `/black-tax-nigeria/` | black tax in Nigeria; how to manage black tax; black tax calculator |
| `/standing-order-vs-scheduled-transfer/` | standing order meaning; standing order GTBank; standing order vs scheduled transfer |
| `/salary-split-nigeria/` | 50/30/20 in naira; how to budget my salary |
| `/glossary/` | what does schedule transfer mean; upkeep meaning |

Keyword traps:
- Bare "automatic transfer" means generator ATS switches in Nigeria.
- Bare "upkeep" now often means NELFUND student-loan upkeep.

Always add "money", "bank" or "wife/family".

## Money-management keywords (added 6 Oct 2026)

Positioning SpenDrip as a budgeting tool that also does the paying, not only a transfer scheduler. Google ignores the `keywords` meta tag, so these only work in titles, headings, page copy and new pages.

| Cluster | Searches to target | Where |
|---|---|---|
| Budget that runs itself | budget app Nigeria; automatic budgeting; budget planner that pays; how to stick to a budget; monthly budget planner naira | New page `/automatic-budget/`; home title and FAQ |
| Expense management | personal expense manager; manage monthly expenses; track recurring expenses; household expense app | New page `/household-expenses/` |
| Allowance and spending control | daily spending allowance; give myself a weekly allowance; stop overspending salary; spend money in drips | `/salary-split-nigeria/`, new `/pay-yourself-allowance/` |
| Household payroll (group plans) | pay house help salary; pay driver salary monthly; domestic staff payroll; pay multiple people at once; bulk transfer Nigeria | New page `/household-payroll/` |
| Planned family support | family budget; dependants budget; send money to siblings monthly | `/black-tax-nigeria/`, `/send-money-to-parents-monthly/` |
| Bills by transfer | pay rent monthly; pay school fees in instalments; pay landlord automatically; recurring payments | New page `/rent-and-school-fees/` |
| Cash-flow planning | know what's going out this month; monthly money outlook; low balance reminder | Home features section (month outlook email) |

Don't use: "savings" or "save money" as a product claim (SpenDrip holds money only to send it; savings implies interest and deposit rules), "bill payment" (we don't pay billers, only bank accounts), "budget executor" (nobody searches it; fine as an internal line).

### Google Trends check (Nigeria, past 12 months, 6 Oct 2026)

Relative interest, scaled so that **"standing order" = 13** (the anchor in every comparison). Trend = second half of the year vs the first.

| Search | Interest | Trend | What people actually mean (related searches) |
|---|---|---|---|
| pay salary | 166 | −16% | Mostly government salary news; no clear intent |
| house help | 127 | +20% | Mostly Nollywood films ("My House Help"), some agencies. Not payroll intent |
| payroll | 110 | −12% | "what is payroll", students, payroll software |
| how to budget | 100 | −24% | "how to create a budget", budgeting for a wedding |
| salary payment | 57 | −7% | No related queries; news-driven |
| pay rent | 55 | +17% | No related queries |
| budgeting | 55 | −10% | Students ("what is budgeting"), but **"budgeting apps" rising +160%** |
| how to save money | 44 | +3% | |
| money management | 38 | −5% | "money management skills", PDFs, books |
| pocket money | 29 | 0% | "pocket money app" |
| driver salary | 23 | −18% | Jobs abroad (Kuwait, Canada truck drivers). Not our intent |
| black tax | 16 | −63% | |
| standing order (anchor) | 13 | +20% | |
| budget app | 12 | −85% (one spike) | |
| family budget | 9 | −60% | |
| monthly budget | 4 | +28% | |
| upkeep allowance | 2 | −4% | |
| automatic transfer | 1 | −78% | Generator ATS switches (known trap) |
| payroll software, domestic staff, expense tracker, budgeting apps, monthly expenses | about 1 or less | | Too small for Trends |
| bulk transfer, scheduled transfer, salary split, expense app, house help salary, spending allowance, recurring payment, send money to parents, school fees installment | 0 | | Below Trends' threshold |

Takeaways:
- The budgeting cluster is the real volume ("how to budget", "budgeting", "money management", "how to save money"), and "budgeting apps" is rising. `/automatic-budget/` should answer "how to create a budget" in its first lines.
- Payroll volume is large but mostly informational or news. Our long-tail ("pay house help salary", "pay staff monthly") is too small for Trends to show; that's normal and still worth a page because the intent is exact and competition is low.
- Product words ("scheduled transfer", "bulk transfer", "recurring payment") have almost no search in Nigeria. People describe the problem, not the product: write titles in their words.
- Trends shows relative interest only, not search counts. Check real impressions in Search Console 4 to 6 weeks after the pages go live.

## Writing rules (finance, Nigeria)

- Answer the question in the first lines. Use naira examples.
- Cite and date every outside fact.
- Keep fees in sync with the app.
- No "best", "cheapest", "safer than [competitor]", "guaranteed", "insured", "licensed" or "CBN-approved".
- Comparisons are factual tables with a "checked on" date. This follows the CBN advertising rules (27 Nov 2025) as best practice.

## Backlog (from the research)

1. **Search Console and Bing Webmaster Tools.** Done 3 Oct 2026: Search Console verified by DNS TXT, sitemap submitted, and Bing imported from Search Console. Still to do: watch the sitemap status in both.
2. **App-by-app guide:** how to schedule a transfer on OPay, PalmPay, Kuda and Moniepoint. These are high-demand quick wins, but write them only with verified, current steps and screenshots.
3. **Trust pages:** About (real team bios), Contact, Privacy and Terms. Privacy and Terms need a lawyer. These carry E-E-A-T signals for a finance site.
4. **Entity building:** LinkedIn, X, Crunchbase, Instagram and TikTok profiles with the same name, logo and description, added to Organization `sameAs`. Wikidata only after press coverage.
5. **PR and community:**
   - Pitch the stamp-duty and black-tax angles to Techpoint (startups@techpoint.africa), TechCabal, Nairametrics and Legit.ng.
   - Answer upkeep and stipend threads on Nairaland, saying openly that you work for SpenDrip.
   - Short Kobo how-to videos for TikTok and Reels.
6. **Original data:** a "Black Tax Pulse" reader survey earns links and AI citations.
7. **Diaspora pages** (en-GB/en-US with hreflang) only once SpenDrip supports funding from abroad.
8. **Measure:**
   - Search Console, filtered to Nigeria, including its AI features report.
   - Referrals from chatgpt.com and perplexity.ai.
   - A monthly check of about 20 prompts in ChatGPT, Perplexity and Gemini, such as "app to send money to my parents every month in Nigeria".

## Sources

The full research report with sources is in the session notes. Key references:
- Google's AI optimisation guide (May 2026): https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- FAQ rich results removed (May 2026): https://developers.google.com/search/updates
- Site names: https://developers.google.com/search/docs/appearance/site-names
- Core Web Vitals (INP < 200 ms): https://developers.google.com/search/docs/appearance/core-web-vitals
- CBN advertising rules: https://techpoint.africa/insight/cbn-marketing-regulations-for-financial-institutions/
- Stamp duty from 2026: https://www.thecable.ng/banks-to-start-charging-senders-n50-stamp-duty-on-transfers-above-n10k-from-january/
- Paystack transfer fees: https://support.paystack.com/en/articles/2130370
