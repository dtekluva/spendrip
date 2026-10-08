# Monthly Boost: ₦50,000 to one SpenDrip user a month

Status: **idea, 8 Oct 2026.** Not built. Needs the approvals in section 1 first.

## The idea

Every month, one randomly chosen SpenDrip user gets ₦50,000 added to their balance to boost their plans ("Mama's money, on us this month"). It's a give-back that creates word of mouth, and it's a marketing cost of ₦600,000 a year plus fees.

## 1. Before launching (legal)

In Nigeria a prize draw open to the public is a regulated **promotion**. Get these confirmed by a lawyer before the first draw:

- **FCCPC approval.** The Federal Competition and Consumer Protection Act requires the Commission's approval for consumer promotions and competitions. Apply with the rules (section 3), the prize, dates and how the draw is run.
- **Lottery and gaming authority.** Random-draw promotions have needed a permit from the National Lottery Regulatory Commission. Since the Supreme Court's November 2024 ruling, lotteries and gaming are mainly for the states, so the Lagos State Lotteries and Gaming Authority may be the one to ask. A lawyer should say which permits apply.
- **No purchase necessary.** Entry must not depend on paying (a top-up or a fee). A paid entry makes it look like a lottery. Every verified user with an active plan is entered for free.
- **Tax.** Ask the accountant whether the prize needs withholding tax or reporting.
- **Advertising.** Under the CBN's advertising rules, don't call it "free money" or overstate odds; always link to the rules.

## 2. How it works

- **Who's in:** verified users with at least one active plan on the last day of the month, account in good standing, not staff or their families. One entry per person.
- **The draw:** on the 1st, an admin runs `python manage.py monthly_boost_draw`. It picks a winner at random using a seed published in advance (e.g. the hash of that month's entry list plus a public number), and stores the entry list, seed and result so the draw can be audited.
- **The prize:** ₦50,000 credited to the winner's balance, recorded in the ledger as a marketing expense (a "promotions" account, so it never touches other users' money). It works like any balance: it can fund drips or be sent to their own account.
- **Telling them:** email, in-app and push, plus a Kobo celebration screen in the app. They don't have to do anything to receive it.
- **Publicity:** we only name a winner publicly (first name and city) if they agree.
- **Admin:** a Promotions page in the admin with each month's entries, seed, winner and payout.

## 3. Rules page (spendrip.com/boost-rules)

Organiser, dates, who can enter, no purchase necessary, how the winner is chosen, the prize, how and when it's credited, what happens if the winner's account is closed or under review (redraw), privacy, and that the promotion can end with notice. Linked from the Terms.

## 4. Build size

About a day: the draw command and audit table, the ledger posting, the messages and celebration screen, an admin page, and the rules page.
