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
