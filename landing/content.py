"""
Content for the spendrip.com guide and product pages. Built into static HTML by build_pages.py.

Writing rules (finance pages, Nigeria):
- Answer the page's question in the first lines. Use real naira examples.
- Cite a source for every outside fact and date it. Keep fees in sync with the app (engine/fees.py).
- No superlatives or comparisons with named providers ("best", "cheapest", "safer than"), and never "guaranteed",
  "insured", "licensed" or "CBN-approved".
"""

UPDATED = "2026-10-03"
APP = "https://app.spendrip.com"

S_STAMP = '<a href="https://www.thecable.ng/banks-to-start-charging-senders-n50-stamp-duty-on-transfers-above-n10k-from-january/" rel="noopener">TheCable</a>'
S_PAYSTACK_FEES = '<a href="https://support.paystack.com/en/articles/2130370" rel="noopener">Paystack</a>'
S_PAYSTACK_DUTY = '<a href="https://support.paystack.com/en/articles/7573314" rel="noopener">Paystack</a>'
S_PIGGY = '<a href="https://techcabal.com/2023/10/31/56-of-earners-pay-black-tax-every-month-according-to-piggyvest-2023-savings-report/" rel="noopener">PiggyVest 2023 Savings Report, via TechCabal</a>'

FEE_TABLE = """
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Each drip of</th><th class="num">SpenDrip fee</th><th class="num">Transfer fee</th><th class="num">Stamp duty</th><th class="num">Total fees</th></tr></thead>
<tbody>
<tr><td>Up to ₦5,000</td><td class="num">₦50</td><td class="num">₦10</td><td class="num">₦0</td><td class="num"><b>₦60</b></td></tr>
<tr><td>₦5,001 to ₦9,999</td><td class="num">₦50</td><td class="num">₦25</td><td class="num">₦0</td><td class="num"><b>₦75</b></td></tr>
<tr><td>₦10,000 to ₦50,000</td><td class="num">₦50</td><td class="num">₦25</td><td class="num">₦50</td><td class="num"><b>₦125</b></td></tr>
<tr><td>Above ₦50,000</td><td class="num">₦50</td><td class="num">₦50</td><td class="num">₦50</td><td class="num"><b>₦150</b></td></tr>
</tbody></table></div>
"""

FEE_CALC = """
<div class="calc" data-calc="fees">
  <div class="row">
    <label>Amount per drip (₦)<input name="amount" inputmode="numeric" value="30000"></label>
    <label>Drips a month<input name="times" inputmode="numeric" value="4"></label>
  </div>
  <div class="out" aria-live="polite"></div>
</div>
"""

PAGES = [
  # ------------------------------------------------------------------ product
  {
    "slug": "scheduled-transfers", "short": "Scheduled transfers", "nav": "Scheduled transfers", "footer": True,
    "eyebrow": "Scheduled transfers in Nigeria",
    "title": "Scheduled Transfers to Any Nigerian Bank or Wallet | SpenDrip",
    "description": "Set up automatic daily, weekly or monthly transfers to yourself or anyone in Nigeria. Pick the day and time, start and end dates, and see every fee before you start.",
    "h1": "Scheduled transfers to any Nigerian bank or wallet",
    "lead": "A scheduled transfer is a payment you set up once that goes out by itself on the day and time you choose. With SpenDrip you can schedule transfers daily, weekly or monthly, to your own account or to anyone with a Nigerian bank or wallet account.",
    "updated": UPDATED, "related": ["fees", "priorities", "send-money-to-parents-monthly", "standing-order-vs-scheduled-transfer"],
    "sections": [
      {"id": "how", "h2": "How a scheduled transfer works on SpenDrip", "html": """
<p>Each schedule is called a <b>drip</b>. You write it as one sentence:</p>
<p class="plan">Send <span class="chip">₦40,000</span> for <span class="chip">⛽ Fuel</span> to <span class="chip">Me</span> every <span class="chip">Friday</span> at <span class="chip">2:00 PM</span>.</p>
<ol>
<li><b>Choose who gets it.</b> Yourself, Mum, a sibling, a driver, anyone with a Nigerian bank or wallet account. SpenDrip shows the name on the account before you save it.</li>
<li><b>Choose how often.</b> Every day, every week on a day you pick, or every month on a date you pick (or the last day of the month).</li>
<li><b>Choose when it starts and stops.</b> Start today or on a date, then let it keep going, run for a number of months, or stop on a set date.</li>
<li><b>Top up your SpenDrip balance.</b> SpenDrip adds up what the month needs, fees included, and tells you the exact amount.</li>
</ol>
<p>On the day, the money goes out at the time you chose (Lagos time). The person can get a WhatsApp message when it lands, and you get an email receipt.</p>"""},
      {"id": "examples", "h2": "What people schedule", "html": """
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Drip</th><th>How often</th><th class="num">Example amount</th></tr></thead>
<tbody>
<tr><td>⛽ Fuel to yourself</td><td>Every Friday</td><td class="num">₦40,000</td></tr>
<tr><td>🍲 Upkeep for home</td><td>Every morning</td><td class="num">₦5,000</td></tr>
<tr><td>💛 Mum's monthly money</td><td>Every month on the 28th</td><td class="num">₦30,000</td></tr>
<tr><td>🎓 Child's school allowance</td><td>Every Monday until the session ends</td><td class="num">₦10,000</td></tr>
<tr><td>🚗 Driver's weekly pay</td><td>Every Saturday</td><td class="num">₦25,000</td></tr>
</tbody></table></div>"""},
      {"id": "short", "h2": "What happens when your balance is short", "html": """
<p>You can rank up to three drips as <a href="/priorities/">priorities</a>. SpenDrip keeps back the money your priorities still need for the rest of the month, so a lower drip waits instead of spending it. When a drip has to wait, you get a note with the exact amount to top up.</p>
<p>A drip never sends money you don't have, and a transfer that fails goes straight back to your balance.</p>"""},
      {"id": "fees", "h2": "What it costs", "html": f"""
<p>Joining is free. Each drip that goes out has three small fees, all shown line by line before you start a plan:</p>
{FEE_TABLE}
<p class="src">Transfer fees are {S_PAYSTACK_FEES}'s published rates. The ₦50 stamp duty on transfers of ₦10,000 and above is a government charge paid by the sender from 2026 ({S_STAMP}). See the full <a href="/fees/">fees page</a> and calculator.</p>"""},
    ],
    "faq": [
      ("Can I schedule a transfer to someone else's bank account?", "Yes. You can send to yourself or anyone with a Nigerian bank or wallet account. SpenDrip checks the name on the account before you save the person."),
      ("Can a scheduled transfer stop on its own?", "Yes. When you set up a plan you can let it keep going, run it for a number of months, or stop it on a date. You see the last payment and the total before you save."),
      ("What time does the money go out?", "At the time you choose, Lagos time. Transfers usually land within minutes."),
      ("Can I pause or cancel a scheduled transfer?", "Yes, any time. Pause one plan, pause everything with one switch, change the amount or day, or delete the plan. Past payments stay in your history."),
    ],
  },
  {
    "slug": "fees", "short": "Fees", "footer": False, "eyebrow": "Fees",
    "title": "SpenDrip Fees & Transfer Charges (2026) + Calculator",
    "description": "Every SpenDrip fee in full: ₦50 per drip, the Paystack transfer fee (₦10, ₦25 or ₦50) and ₦50 stamp duty on ₦10,000 and above. Work out your cost with the calculator.",
    "h1": "SpenDrip fees, in full",
    "lead": "Joining SpenDrip is free. Each scheduled transfer (a drip) costs a ₦50 SpenDrip fee, plus the transfer fee our payment partner charges (₦10, ₦25 or ₦50 depending on the amount) and the government's ₦50 stamp duty on transfers of ₦10,000 and above.",
    "updated": UPDATED, "scripts": ["tools.js"], "related": ["scheduled-transfers", "black-tax-nigeria"],
    "sections": [
      {"id": "table", "h2": "Fees for each drip", "html": FEE_TABLE + f"""
<p class="src">Transfer fees: {S_PAYSTACK_FEES} (Single and bulk transfers). Stamp duty: ₦50 on transfers of ₦10,000 and above, paid by the sender from 2026 ({S_STAMP}; {S_PAYSTACK_DUTY}). Checked 3 October 2026.</p>"""},
      {"id": "groups", "h2": "Paying several people at once", "html": """
<p>A group plan pays several people together, each with their own amount: staff pay, or the whole family's monthly support. The SpenDrip fee is <b>₦100 for the whole payout</b>, however many people are on it. Each person is still a separate bank transfer, so each one has its own transfer fee and, from ₦10,000, its own ₦50 stamp duty.</p>
<p>Example: a driver on ₦80,000, a nanny on ₦70,000 and a gateman on ₦45,000. That's ₦100 SpenDrip fee + ₦125 transfer fees (₦50 + ₦50 + ₦25) + ₦150 stamp duty = <b>₦375 in fees</b> for the whole payout.</p>"""},
      {"id": "calculator", "h2": "Fee calculator", "html": "<p>Type an amount to see what one drip costs, and what a month of them adds up to.</p>" + FEE_CALC},
      {"id": "topups", "h2": "Adding money", "html": """
<p>You top up your SpenDrip balance by card through Paystack. The card fee is shown on the screen before you pay, so you know the exact amount. Bank-transfer top-ups to your own SpenDrip account number are coming soon.</p>"""},
      {"id": "failed", "h2": "If a transfer fails", "html": """
<p>Money is set aside before each transfer and only counted as sent once the bank confirms it. If a transfer fails, the amount goes straight back to your balance.</p>"""},
    ],
    "faq": [
      ("Is SpenDrip free?", "Joining is free. You pay only when a drip goes out: the ₦50 SpenDrip fee plus the transfer fee and, from ₦10,000, the ₦50 stamp duty."),
      ("Who pays the ₦50 stamp duty?", "From 2026 the sender pays ₦50 stamp duty on electronic transfers of ₦10,000 and above. SpenDrip adds it to the drip and shows it as its own line."),
      ("Do the people I pay get charged?", "No. They receive the full amount you scheduled."),
      ("How much does it cost to pay several people at once?", "A group payout has one ₦100 SpenDrip fee for everyone on it. Each person's transfer still has its own transfer fee and, from ₦10,000, ₦50 stamp duty."),
    ],
  },
  {
    "slug": "priorities", "short": "Priorities", "footer": False, "eyebrow": "Priorities",
    "title": "Priorities: Protect the Payments That Matter Most | SpenDrip",
    "description": "Rank up to three scheduled transfers as priorities. SpenDrip keeps back what they still need this month, so lower drips wait instead of spending it.",
    "h1": "Priorities: Mum's money comes first",
    "lead": "Priorities let you rank up to three scheduled transfers. SpenDrip keeps back the money your priorities still need for the rest of the month, so if your balance runs short, lower drips wait instead of spending it.",
    "updated": UPDATED, "related": ["scheduled-transfers", "send-money-to-parents-monthly"],
    "sections": [
      {"id": "how", "h2": "How ranking works", "html": """
<ul>
<li><b>Priority 1</b> is paid first. Priority 2 never spends money priority 1 still needs this month, and priority 3 never spends what 1 and 2 need.</li>
<li><b>Other drips</b> only use what's left after all three priorities are covered.</li>
<li>Fees are counted, so the protected amount is the real amount the month needs.</li>
</ul>"""},
      {"id": "example", "h2": "A worked example", "html": """
<p>November, with ₦190,000 in your balance:</p>
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Plan</th><th>Rank</th><th class="num">Still needed in November</th><th>What happens</th></tr></thead>
<tbody>
<tr><td>🍲 Upkeep, ₦5,000 every day</td><td>1</td><td class="num">₦151,800</td><td>Protected</td></tr>
<tr><td>💛 Mum, ₦30,000 on the 30th</td><td>2</td><td class="num">₦30,125</td><td>Protected</td></tr>
<tr><td>🤝 Cousin, ₦25,000 on the 30th</td><td>None</td><td class="num">₦25,125</td><td>Waits for a top-up</td></tr>
</tbody></table></div>
<p>Upkeep and Mum need ₦181,925 between them, so ₦8,075 is free. The cousin's drip waits rather than eating into Upkeep and Mum, and SpenDrip tells you to top up ₦17,050 so everyone gets paid. (Amounts include fees: ₦60 per upkeep drip, ₦125 for each of the others.)</p>"""},
      {"id": "set", "h2": "Setting priorities", "html": """
<p>Tap <b>Protect it</b> in any plan's sentence, or open <b>Plans</b> and drag your three most important drips into order. When a priority plan ends, the ones below move up.</p>"""},
    ],
    "faq": [
      ("How many priorities can I have?", "Up to three. Making a fourth plan a priority pushes the lowest one out of the list."),
      ("Does a priority drip ever fail because of a lower drip?", "No. Lower drips can only use money that isn't needed by higher priorities for the rest of the month."),
    ],
  },
  {
    "slug": "security", "short": "Security", "footer": False, "eyebrow": "Security",
    "title": "Is SpenDrip Safe? How Your Money and Identity Are Protected",
    "description": "How SpenDrip handles your money and identity: card payments on Paystack, ID and live-selfie checks, account-name checks, bank confirmation and app lock.",
    "h1": "How SpenDrip keeps your money and identity safe",
    "lead": "SpenDrip checks who you are before any money moves, checks who you're paying before you save them, and counts a payment as sent only when the bank confirms it. Here is exactly what happens at each step.",
    "updated": UPDATED, "related": ["fees", "scheduled-transfers"],
    "sections": [
      {"id": "identity", "h2": "Identity checks", "html": """
<p>Before you can add money or send it, you verify with a photo of your ID (NIN slip, driver's licence, voter's card or passport) and three quick live selfies: looking straight, turning one way, then the other, in a random order. The selfies must be taken live in the app, not picked from your gallery. One ID can only verify one account.</p>
<p>New accounts have limits while verification is ID and live selfies only: up to ₦500,000 per transfer and ₦2,000,000 in your balance.</p>"""},
      {"id": "cards", "h2": "Cards", "html": """
<p>You pay on Paystack's secure checkout, so SpenDrip never sees your card number. For one-tap top-ups we keep only an encrypted token from Paystack.</p>"""},
      {"id": "payees", "h2": "Paying the right person", "html": """
<p>When you add someone, SpenDrip looks up the name on their bank account and shows it to you before you save. Each payment goes only to accounts you've saved.</p>"""},
      {"id": "money", "h2": "Every naira accounted for", "html": """
<p>Money is set aside before each transfer and counted as sent only after the bank confirms it. If a transfer fails, it returns to your balance. Every movement is recorded in a double-entry ledger, so balances can always be traced.</p>"""},
      {"id": "app", "h2": "Locking the app", "html": """
<p>Open SpenDrip with Face ID or your PIN. It locks itself after a few minutes away. You can set a daily sending limit and pause every payment with one switch.</p>"""},
    ],
    "faq": [
      ("Does SpenDrip see my card number?", "No. Card payments happen on Paystack's checkout. SpenDrip keeps only an encrypted token for one-tap top-ups."),
      ("Can I use a photo from my gallery for the selfies?", "No. The three face photos must be taken live with the in-app camera. You can upload your ID photo from your gallery."),
    ],
  },
  # ------------------------------------------------------------------ use cases
  {
    "slug": "send-money-to-parents-monthly", "short": "Money for parents", "nav": "For parents", "footer": True,
    "eyebrow": "Family support",
    "title": "Send Your Parents' Monthly Money Automatically | SpenDrip",
    "description": "Set up an automatic monthly transfer to Mum or Dad in Nigeria. Choose the date and time, make it a priority, and they get a WhatsApp message when it lands.",
    "h1": "Send your parents' monthly money automatically",
    "lead": "Set it once: SpenDrip sends Mum or Dad's money on the date you choose every month, keeps it safe from your other spending, and lets them know on WhatsApp when it lands.",
    "updated": UPDATED, "related": ["black-tax-nigeria", "priorities", "scheduled-transfers"],
    "sections": [
      {"id": "setup", "h2": "Set it up in a minute", "html": """
<p class="plan">Send <span class="chip">₦30,000</span> for <span class="chip">💛 Mum</span> to <span class="chip">Mum</span> every <span class="chip">month</span> on <span class="chip">the 28th</span> at <span class="chip">10:00 AM</span>.</p>
<ol>
<li>Add Mum with her bank or wallet account. SpenDrip shows the name on the account so you know it's hers.</li>
<li>Pick the date. Paid on the 25th? Send Mum's money on the 26th, or on the last day of every month.</li>
<li>Tap <b>Protect it</b> to make it priority 1, so other plans can't touch the money it needs.</li>
<li>Add her WhatsApp number if you want her to get a message when it lands.</li>
</ol>"""},
      {"id": "why", "h2": "Why automate it", "html": """
<ul>
<li><b>No more "have you sent it?"</b> Mum hears from the bank, and from WhatsApp, on the same day every month.</li>
<li><b>It's protected.</b> As a priority, Mum's money is set aside before fuel, data or anything else lower down.</li>
<li><b>You see the whole month.</b> The plan shows what this month needs, fees included, and what to top up.</li>
</ul>"""},
      {"id": "more", "h2": "More than one person to support?", "html": """
<p>Most people support more than one person. Make a drip for each: Dad monthly, a sibling's school fees each term, a grandparent's weekly upkeep. Rank the most important three as priorities, and the rest go out when there's money left.</p>
<p>To work out how much of your pay goes to family, try the <a href="/black-tax-nigeria/#calculator">black tax calculator</a>.</p>"""},
    ],
    "faq": [
      ("Does my mum need the SpenDrip app?", "No. She receives a normal bank transfer into her own account. If you add her WhatsApp number, she also gets a message when it lands."),
      ("Can I send to my parents' OPay or PalmPay wallet?", "Yes. You can send to Nigerian bank accounts and wallet accounts."),
      ("What if I'm short one month?", "If Mum is a priority, her money is set aside first. Lower drips wait, and you get a note with the exact amount to top up."),
    ],
  },
  {
    "slug": "upkeep-allowance", "short": "Upkeep allowance", "nav": "Upkeep", "footer": True,
    "eyebrow": "Upkeep",
    "title": "Automatic Upkeep Allowance for Your Spouse and Home | SpenDrip",
    "description": "Send upkeep or feeding money for your home automatically: daily, weekly or monthly, to your spouse or whoever runs the house. Set it once and stop sending it by hand.",
    "h1": "Upkeep for your home, sent automatically",
    "lead": "Upkeep (feeding money, house money) is the money that keeps a home running. With SpenDrip you set the amount and how often once, and it goes to your spouse or whoever runs the house on time, without you remembering each time.",
    "updated": UPDATED, "related": ["send-money-to-parents-monthly", "salary-split-nigeria", "priorities"],
    "sections": [
      {"id": "how-often", "h2": "Daily, weekly or monthly?", "html": """
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>How often</th><th>Works well when</th><th>Example</th></tr></thead>
<tbody>
<tr><td>Every day</td><td>Market runs and small daily costs</td><td class="num">₦5,000 every morning at 6 AM</td></tr>
<tr><td>Every week</td><td>A weekly market day or shopping trip</td><td class="num">₦35,000 every Saturday</td></tr>
<tr><td>Every month</td><td>Planned monthly shopping and bills</td><td class="num">₦150,000 on the 26th</td></tr>
</tbody></table></div>
<p>Daily drips keep spending steady through the month. Note that each drip has its own fees (₦60 for a ₦5,000 drip), so a monthly drip costs less in fees than thirty daily ones. Compare on the <a href="/fees/#calculator">fee calculator</a>.</p>"""},
      {"id": "setup", "h2": "Set it up", "html": """
<p class="plan">Send <span class="chip">₦5,000</span> for <span class="chip">🍲 Upkeep</span> to <span class="chip">Ada</span> every <span class="chip">day</span> at <span class="chip">6:00 AM</span>.</p>
<p>Make upkeep priority 1 so the house is covered first. If your balance runs low, other plans wait and you get a note with the exact amount to top up.</p>"""},
      {"id": "talk", "h2": "Agree the amount together", "html": """
<p>Upkeep works best when you agree the amount and the day together. Seeing the plan in SpenDrip, with the exact monthly total, makes that conversation easier, and changing it later takes a few seconds.</p>"""},
    ],
    "faq": [
      ("Can I send upkeep every day automatically?", "Yes. Choose every day and a time, for example 6:00 AM. The money goes out each day until you pause it or the plan ends."),
      ("Can I change the upkeep amount later?", "Yes. Edit the plan any time; the next drip uses the new amount."),
    ],
  },
  {
    "slug": "student-allowance", "short": "Student allowance", "nav": None, "footer": True,
    "eyebrow": "Students",
    "title": "Send Your Child's School Allowance on Schedule | SpenDrip",
    "description": "Send weekly or monthly pocket money to a child in university or secondary school in Nigeria, and stop it automatically when the session ends.",
    "h1": "Send your child's school allowance on schedule",
    "lead": "Set your child's allowance once: SpenDrip sends it every week or month to their bank or wallet account, and stops on the date the session ends, so there's nothing to remember and nothing to cancel.",
    "updated": UPDATED, "related": ["salary-split-nigeria", "scheduled-transfers"],
    "sections": [
      {"id": "weekly", "h2": "Weekly beats a lump sum", "html": """
<p>A big lump sum at resumption can be gone in two weeks. A smaller weekly drip spreads the money across the session and teaches budgeting without you having to step in.</p>
<p class="plan">Send <span class="chip">₦15,000</span> for <span class="chip">🎓 Tobi's allowance</span> to <span class="chip">Tobi</span> every <span class="chip">Monday</span> at <span class="chip">7:00 AM</span>, <span class="chip">until 31 July</span>.</p>"""},
      {"id": "end", "h2": "Stop it when the session ends", "html": """
<p>Choose <b>until a date</b> and pick the last day of the session, or <b>for a number of months</b>. SpenDrip shows the last payment and the total for the whole session before you save. Pausing during a break doesn't push the end date back.</p>"""},
      {"id": "extras", "h2": "Fees, books and one-offs", "html": """
<p>Keep a separate plan for each kind of cost: weekly allowance, monthly data, a once-a-term fee. Each shows up in the calendar, so you can see the whole term at a glance.</p>"""},
    ],
    "faq": [
      ("Can my child receive the allowance in a wallet like OPay?", "Yes. You can send to Nigerian bank and wallet accounts."),
      ("Can the allowance stop automatically?", "Yes. Set the plan to end on a date or after a number of months."),
    ],
  },
  # ------------------------------------------------------------------ guides
  {
    "slug": "black-tax-nigeria", "short": "Black tax", "nav": "Black tax", "footer": True, "type": "article",
    "eyebrow": "Guide", "scripts": ["tools.js"], "published": UPDATED,
    "title": "Black Tax in Nigeria: How to Support Family Without Going Broke",
    "description": "What black tax means in Nigeria, how common it is, and a practical way to handle it: set a number, automate it, and protect it. With a free black tax calculator.",
    "h1": "Black tax in Nigeria: how to support family without going broke",
    "lead": "Black tax is the money working people regularly send to support parents, siblings and extended family. It's common in Nigeria: 56% of earners in PiggyVest's 2023 survey said they pay it every month. This guide shows a calmer way to handle it.",
    "updated": UPDATED, "related": ["send-money-to-parents-monthly", "salary-split-nigeria", "fees"],
    "sections": [
      {"id": "meaning", "h2": "What black tax means", "html": f"""
<div class="answer"><b>Black tax</b> is the regular financial support many earners give to family members: parents' upkeep, siblings' school fees, medical bills, and help for extended family.</div>
<p>It's often a source of pride, and also of strain when it's unplanned. In PiggyVest's 2023 survey, 56% of earners said they pay black tax every month ({S_PIGGY}).</p>"""},
      {"id": "calculator", "h2": "Black tax calculator", "html": """
<p>Enter your monthly take-home pay and what you send to family each month.</p>
<div class="calc" data-calc="blacktax">
  <div class="row">
    <label>Take-home pay per month (₦)<input name="pay" inputmode="numeric" value="400000"></label>
    <label>Family support per month (₦)<input name="family" inputmode="numeric" value="80000"></label>
  </div>
  <div class="out" aria-live="polite"></div>
</div>
<p class="src">The calculator runs in your browser. Nothing you type is sent anywhere.</p>"""},
      {"id": "number", "h2": "1. Decide the number, not the moment", "html": """
<p>The hardest part of black tax is the unplanned request. Decide a monthly amount you can sustain, after rent, food and your own savings, and treat it as fixed. Many people split it per person: a set amount for parents, a set amount for a sibling's school, and a small pot for emergencies.</p>"""},
      {"id": "automate", "h2": "2. Automate it", "html": """
<p>When the money goes out by itself on a set date, family can plan around it and you stop being asked. In SpenDrip that's one plan per person:</p>
<p class="plan">Send <span class="chip">₦50,000</span> for <span class="chip">💛 Mum & Dad</span> every <span class="chip">month</span> on <span class="chip">the 27th</span>.</p>
<p>They can also get a WhatsApp message when it lands, so "have you sent it?" becomes rare.</p>"""},
      {"id": "protect", "h2": "3. Protect it from everything else", "html": """
<p>Make your most important support a <a href="/priorities/">priority</a>. If money gets tight, priorities are paid first, and lower plans wait instead of eating into them.</p>"""},
      {"id": "no", "h2": "4. Have a plan for extra requests", "html": """
<p>Extra requests will still come. Having a fixed, visible amount makes it easier to say "this month's support has gone out; let's plan the extra for next month" without feeling like you're refusing outright.</p>"""},
    ],
    "faq": [
      ("What is black tax in Nigeria?", "Black tax is the regular money working people send to support family members, such as parents' upkeep, siblings' school fees and medical bills."),
      ("How much should I send to my parents?", "There's no single right amount. Work out what's left after essentials and your own savings, decide a fixed monthly figure you can sustain, and automate it."),
      ("How can I automate family support?", "Set up a monthly scheduled transfer for each person you support. In SpenDrip you choose the date and time, and make the most important ones priorities."),
    ],
  },
  {
    "slug": "standing-order-vs-scheduled-transfer", "short": "Standing orders", "nav": None, "footer": True, "type": "article",
    "eyebrow": "Guide", "published": UPDATED,
    "title": "Standing Order vs Scheduled Transfer in Nigeria",
    "description": "What a standing order is, how Nigerian banks and apps handle recurring payments, and how a standing order compares with a scheduled transfer.",
    "h1": "Standing order vs scheduled transfer in Nigeria",
    "lead": "A standing order is an instruction to your bank to pay a fixed amount to the same account on a regular schedule. A scheduled transfer does the same job from an app, usually with more control over timing and changes.",
    "updated": UPDATED, "related": ["scheduled-transfers", "glossary"],
    "sections": [
      {"id": "standing-order", "h2": "What is a standing order?", "html": """
<div class="answer">A <b>standing order</b> (sometimes called a standing instruction) tells your bank to pay a fixed amount from your account to another account on a regular schedule, until you cancel it.</div>
<p>Nigerian banks offer standing orders through branches, internet banking and USSD. GTBank, for example, has shown customers how to set one up on its *737# service (<a href="https://x.com/gtbank/status/1093461566589161472" rel="noopener">GTBank on X</a>) and publishes a standing order form (<a href="https://gtbank-plc.files.svdcdn.com/production/general/Standing-Order-Instruction-Form.pdf" rel="noopener">GTBank</a>). Union Bank covers standing orders in its <a href="https://www.unionbankng.com/support/faqs/" rel="noopener">FAQs</a>. Steps and charges vary by bank, so check yours.</p>"""},
      {"id": "scheduled", "h2": "What is a scheduled transfer?", "html": """
<div class="answer">A <b>scheduled transfer</b> is a payment you set up in a banking or money app to go out on a future date, once or on repeat.</div>
<p>Several Nigerian apps offer scheduled or recurring transfers, including PalmPay (<a href="https://x.com/palmpay_ng/status/1987114135365337164" rel="noopener">PalmPay on X</a>) and Kuda (<a href="https://x.com/joinkuda/status/1958826528894071280" rel="noopener">Kuda on X</a>). Features differ between apps and change over time.</p>"""},
      {"id": "compare", "h2": "Side by side", "html": """
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th></th><th>Bank standing order</th><th>App scheduled transfer</th><th>SpenDrip</th></tr></thead>
<tbody>
<tr><td>Set up</td><td>Branch, internet banking or USSD</td><td>In the app</td><td>In the app, as one sentence</td></tr>
<tr><td>How often</td><td>Fixed schedule</td><td>Depends on the app</td><td>Daily, weekly or monthly, with start and end dates</td></tr>
<tr><td>Many people from one balance</td><td>One order per payee</td><td>Depends on the app</td><td>Yes, each with its own plan</td></tr>
<tr><td>Short on money</td><td>Depends on the bank</td><td>Depends on the app</td><td>Up to three priorities are paid first; others wait</td></tr>
<tr><td>Recipient notice</td><td>Bank alert</td><td>Bank alert</td><td>Bank alert, plus an optional WhatsApp message</td></tr>
</tbody></table></div>
<p class="src">Bank and app details vary and change. Checked 3 October 2026.</p>"""},
      {"id": "which", "h2": "Which should you use?", "html": """
<p>A bank standing order suits a single fixed payment that rarely changes, like rent to a landlord. A scheduled transfer app suits payments you want to adjust, track in one place, or protect when money is tight, like family support, upkeep and allowances.</p>"""},
    ],
    "faq": [
      ("What does standing order mean in banking?", "It's an instruction to your bank to pay a fixed amount to another account on a regular schedule until you cancel it."),
      ("Can I cancel a standing order?", "Yes. Contact your bank or use the channel you set it up on. Steps vary by bank."),
    ],
  },
  {
    "slug": "salary-split-nigeria", "short": "Salary split", "nav": None, "footer": True, "type": "article",
    "eyebrow": "Guide", "published": UPDATED,
    "title": "How to Split Your Salary in Nigeria (50/30/20 in Naira)",
    "description": "A simple way to split your salary in Nigeria: the 50/30/20 rule worked out in naira, how to adapt it for family support, and how to make it automatic.",
    "h1": "How to split your salary in Nigeria (with worked naira examples)",
    "lead": "A salary split decides, before payday, where each naira goes. The 50/30/20 rule (needs, wants, savings) is a common starting point; for many Nigerian earners it works better with a fourth slice for family support.",
    "updated": UPDATED, "related": ["black-tax-nigeria", "upkeep-allowance", "fees"],
    "sections": [
      {"id": "rule", "h2": "The 50/30/20 rule", "html": """
<div class="answer">The <b>50/30/20 rule</b> splits take-home pay into 50% for needs (rent, food, transport), 30% for wants, and 20% for savings and debt.</div>
<div class="tbl-wrap"><table class="tbl">
<thead><tr><th>Take-home pay</th><th class="num">Needs 50%</th><th class="num">Wants 30%</th><th class="num">Savings 20%</th></tr></thead>
<tbody>
<tr><td>₦250,000</td><td class="num">₦125,000</td><td class="num">₦75,000</td><td class="num">₦50,000</td></tr>
<tr><td>₦400,000</td><td class="num">₦200,000</td><td class="num">₦120,000</td><td class="num">₦80,000</td></tr>
<tr><td>₦700,000</td><td class="num">₦350,000</td><td class="num">₦210,000</td><td class="num">₦140,000</td></tr>
</tbody></table></div>"""},
      {"id": "family", "h2": "Add a slice for family", "html": """
<p>If you support family, give it its own line instead of letting it eat into needs. One option is 40/30/20/10: 40% needs, 30% family and wants together, 20% savings, 10% buffer. Adjust the numbers to your life; the point is that each slice is decided in advance.</p>"""},
      {"id": "automate", "h2": "Make the split happen by itself", "html": """
<p>A split only works if the money actually moves. Schedule each slice to go out right after payday:</p>
<ul>
<li>⛽ Transport: ₦40,000 to yourself every Friday</li>
<li>🍲 Upkeep: ₦5,000 every morning</li>
<li>💛 Family: ₦50,000 to Mum on the 27th</li>
<li>🏦 Savings: ₦80,000 to your savings account on the 26th</li>
</ul>
<p>SpenDrip adds up what the month needs, fees included, so you know exactly how much to top up after payday.</p>"""},
    ],
    "faq": [
      ("Does the 50/30/20 rule work in Nigeria?", "It's a useful starting point. Many Nigerian earners adjust it, for example by adding a fixed slice for family support or a larger share for rent."),
      ("Should I split my salary into different accounts?", "Separating money by purpose helps. Scheduled transfers can move each slice automatically after payday."),
    ],
  },
  {
    "slug": "glossary", "short": "Glossary", "nav": None, "footer": True,
    "eyebrow": "Glossary",
    "title": "Money Terms Explained Simply | SpenDrip Glossary",
    "description": "Plain-English meanings of money terms Nigerians search for: scheduled transfer, standing order, recurring transfer, upkeep, black tax, stamp duty and more.",
    "h1": "Money terms, explained simply",
    "lead": "Short, plain definitions of the money words that come up when you pay people regularly in Nigeria.",
    "updated": UPDATED, "related": ["standing-order-vs-scheduled-transfer", "black-tax-nigeria"],
    "sections": [
      {"id": "terms", "h2": "Terms", "html": """
<h3 id="scheduled-transfer">Scheduled transfer</h3><p>A payment set up in an app to go out on a future date, once or on repeat. <a href="/scheduled-transfers/">More about scheduled transfers</a>.</p>
<h3 id="recurring-transfer">Recurring transfer</h3><p>A scheduled transfer that repeats, for example every week or every month.</p>
<h3 id="standing-order">Standing order</h3><p>An instruction to your bank to pay a fixed amount to another account on a regular schedule. <a href="/standing-order-vs-scheduled-transfer/">Standing order vs scheduled transfer</a>.</p>
<h3 id="drip">Drip</h3><p>SpenDrip's name for one scheduled payment, like ₦40,000 for fuel every Friday at 2 PM.</p>
<h3 id="upkeep">Upkeep</h3><p>Money given regularly to run a home or support a person, such as feeding money for a household. (Not to be confused with NELFUND's student-loan upkeep.) <a href="/upkeep-allowance/">Automating upkeep</a>.</p>
<h3 id="black-tax">Black tax</h3><p>Regular financial support earners give to parents, siblings and extended family. <a href="/black-tax-nigeria/">Guide and calculator</a>.</p>
<h3 id="stamp-duty">Stamp duty (₦50)</h3><p>A government charge of ₦50 on electronic transfers of ₦10,000 and above, paid by the sender from 2026. <a href="/fees/">Fees</a>.</p>
<h3 id="name-enquiry">Account name check</h3><p>Looking up the name on a bank account before sending money, so you can confirm it's the right person.</p>
<h3 id="priority">Priority</h3><p>In SpenDrip, one of up to three ranked plans whose money is kept back for the rest of the month before lower plans can spend it. <a href="/priorities/">How priorities work</a>.</p>"""},
    ],
  },
  # ------------------------------------------------------------------ company
  {
    "slug": "about", "short": "About", "nav": None, "footer": False, "page_type": "AboutPage", "eyebrow": "About SpenDrip",
    "title": "About SpenDrip: Scheduled Transfers Built in Nigeria",
    "description": "SpenDrip is a Nigerian app for scheduled transfers. Set money to go out on the day and time you choose, to yourself or the people you look after, with every fee shown first.",
    "h1": "Money that shows up on time",
    "lead": "SpenDrip is a Nigerian app for scheduled transfers. You top up one balance and set “drips”: payments that go out by themselves, daily, weekly or monthly, to your own account or to anyone with a Nigerian bank or wallet account.",
    "updated": UPDATED, "related": ["security", "fees", "scheduled-transfers"],
    "sections": [
      {"id": "why", "h2": "Why we built it", "html": """
<p>Most of us send the same money again and again: Mum’s monthly upkeep, a sibling’s school allowance, fuel for the week, money moved out of the salary account before it disappears. Banking apps can send money, but only when you remember to, and remembering is the hard part. A late transfer means a call asking “have you sent it?”, and a forgotten one means someone you look after goes without.</p>
<p>SpenDrip does the remembering. You write the plan once, as one sentence:</p>
<p class="plan">Send <span class="chip">₦30,000</span> to <span class="chip">Mum</span> every <span class="chip">month</span> on the <span class="chip">25th</span> at <span class="chip">9:00 AM</span>.</p>
<p>The money goes out on time, and Mum gets a WhatsApp message when it lands.</p>"""},
      {"id": "beliefs", "h2": "What we believe", "html": """
<ul>
<li><b>Show every naira.</b> Before a plan starts you see the SpenDrip fee, the transfer fee and stamp duty as separate lines. Nothing is added later. <a href="/fees/">Our fees</a>.</li>
<li><b>Protect what matters most.</b> Rank up to three drips as priorities. Their money is set aside for the month, so smaller drips wait instead of spending it. <a href="/priorities/">How priorities work</a>.</li>
<li><b>Count it as sent only when the bank says so.</b> If a transfer fails, the money goes back to your balance. <a href="/security/">Security</a>.</li>
<li><b>Know who we’re dealing with.</b> Everyone verifies with an ID photo and live selfies before money moves, and every payee’s account name is checked before it’s saved.</li>
</ul>"""},
      {"id": "how", "h2": "How it works behind the scenes", "html": """
<ul>
<li><b>Card payments</b> are processed by Paystack. SpenDrip never sees your card number.</li>
<li><b>Transfers</b> are sent through Paystack to Nigerian banks and wallets.</li>
<li><b>Your balance</b> is recorded in a double-entry ledger, so every movement can be traced.</li>
</ul>"""},
      {"id": "team", "h2": "Who we are", "html": """
<p>SpenDrip was founded by <b>Inyang Paul</b> and is built in Nigeria, for people who look after others with their money.</p>
<p>Questions, feedback or press: <a href="/contact/">contact us</a>.</p>"""},
    ],
  },
  {
    "slug": "contact", "short": "Contact", "nav": None, "footer": False, "page_type": "ContactPage", "eyebrow": "Contact",
    "title": "Contact SpenDrip: Phone, WhatsApp and Email",
    "description": "Reach the SpenDrip team by phone, WhatsApp or email for help with drips, top-ups and transfers, or for press enquiries.",
    "h1": "Talk to a person",
    "lead": "Questions about a drip, a top-up or a transfer? Reach us directly.",
    "updated": UPDATED, "related": ["security", "fees"],
    "sections": [
      {"id": "reach", "h2": "How to reach us", "html": """
<ul class="contact-list">
<li><b>WhatsApp:</b> <a href="https://wa.me/2348022448089" rel="noopener">0802 244 8089</a></li>
<li><b>Phone:</b> <a href="tel:+2348022448089">0802 244 8089</a></li>
<li><b>Email:</b> <a href="mailto:hello@spendrip.com">hello@spendrip.com</a></li>
<li><b>Press:</b> <a href="mailto:hello@spendrip.com?subject=Press">hello@spendrip.com</a>, with “Press” in the subject</li>
</ul>"""},
      {"id": "first", "h2": "Before you get in touch", "html": """
<ul>
<li><b>A drip didn’t arrive?</b> Open the plan in the app. It shows whether the drip went out, is waiting for money or failed, and why. Failed transfers go back to your balance by themselves.</li>
<li><b>Topped up but your balance didn’t change?</b> Card top-ups usually show within a minute. If it’s been longer, send us the time and the amount.</li>
</ul>"""},
      {"id": "safety", "h2": "Stay safe", "html": """
<p>SpenDrip will never ask for your card number, PIN, OTP or password, by phone, email or WhatsApp. Anyone who asks isn’t us.</p>"""},
    ],
  },
]
