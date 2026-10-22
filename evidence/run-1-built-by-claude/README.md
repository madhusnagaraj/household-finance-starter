# Household finance system

Private. Balances, account numbers and transactions live in this folder only. No remote, no pushing.

## Where we left off
- 2026-10-22, weekly check (Sam asked): every step passed, but nothing new to load. The ledger is checked only through 2026-08-23 (card) and 2026-08-31 (bank, brokerage); no fresh downloads or September statements are in the folder. Waiting on Sam to drop them into `exports/<date>/` and `statements/`. The budget page still shows August, so its over/watch lines are old news.
- 2026-10-22: Phase 6 (Questions worth asking). Open with Sam: (1) the brokerage figure he remembers from the app (he will check the September statement; Open question 0); (2) the emergency fund definition of expenses (both shown until he chooses; Open question 4); (3) Jordan's question, pay down the mortgage early or invest the extra: I gave the framework and arithmetic, not a recommendation, and asked how much extra per month they are weighing (Open question 3). Still to do: a benchmark (needs numbers from Sam or a source he names), the coverage check, and what "enough" looks like.

## Open questions
| # | Question | What settles it | When |
|---|---|---|---|
| 0 | **Waiting on Sam.** Brokerage value: Sam remembers about $112,000 at the end of August from the app. The August statement (which adds up by its own summary and ties to the ledger) says a lower value, and the fund price it would take to reach $112,000 with the shares held at the end of August is above every month-end price on the statements. The statement outranks an app figure, so balances and the ledger are unchanged. Possible reasons, not yet known: the app figure was from a later date, or it includes something else. | Sam does not remember the date and will check the September statement | When it arrives |
| 1 | Two settings I chose; Sam can object. (a) Buys, sells, dividends and reinvestments inside the brokerage get kind "invest": market change, not household income or spending. (b) A transfer must find its other side within 7 days (checking to brokerage took 3 to 5 days in this data). | Sam, only if he objects | Whenever |
| 2 | Mortgage numbers still do not add up. The bank rows confirm the total payment on the 1st (or next business day) every month, but the split with escrow does not fit a standard 30-year schedule for the stated loan (script check in chat, 2026-10-22). Sam's balance guess does fit the schedule. Nothing assumed. | A Hollowmere statement (Sam will look later) | Before Phase 4 |
| 3 | **Asked of Sam: how much extra per month?** Jordan's question: pay the mortgage down early or invest the extra? Sam asked "what should we do?" I do not recommend; the framework and arithmetic are in `scripts/mortgage_whatif.py`. The inputs are from memory until a mortgage statement settles the balance and the loan terms. Original note: Not mine to decide. I lay out trade-offs (the rate, liquidity, emergency fund first, any prepayment penalty), no recommendation. | Needs #2 first | Phase 6 |
| 4 | What counts as "expenses" for the six-month emergency fund: everything, or only essentials? The plan sets aside a monthly amount for it, but the target number still needs this definition. | Sam | Phase 6 |
| 4a | Where will the emergency fund and Mira's college fund live? Neither account exists yet, so the plan's two savings lines show "not posted" and the money stays in checking until each account is opened and added to `scripts/config.json` | Sam opens the accounts | When ready |
| 5 | Remodel money trail. The bank rows match Sam's figures: the brokerage money reached checking before the $22,000 check cleared, and the contractor's final payment went by bank transfer in June. The brokerage year bridge confirms the $35,000 went from the brokerage to checking. But checking never looked drained in the data (the bank's balance column shows it). Ask Sam what felt drained, and what led to the June card autopay being cut, since the card then charged interest. | Sam | Phase 4 or sooner |
| 6 | Tax angle, not advice: selling investments in a taxable account to raise the $35,000 can create a gain or loss for the year. | Tidewell year-end tax documents | Annual tax check |
| 7 | Jordan's pay: the bank shows pay arriving on the last business day of each month, June to August included, so no summer gap this year. Still unknown: other deductions and whether the district matches the 403(b). | A recent paystub from Jordan | Before Phase 4 |
| 8 | No statements for either retirement account. | Sam and Jordan download the latest from each plan's site (I can't log in) | Before Phase 3 |
| 9 | Resolved 2026-10-22. Sam asked for the duplicate April bank statement (`Otterbrook_eStatement_2026-04-30 (1).pdf`, byte-identical to the original, same SHA-256) to be removed. Per the folder rule that nothing is deleted, it was moved to `archive/`; the original stays in `statements/`. Sam can delete the archived copy himself if he wants it gone for good. | Nothing | Done |

## Folder map
| Folder | What goes in it | Rule |
|---|---|---|
| `ledger/` | CSVs, the book of record | Changed only by scripts and by decisions Sam makes |
| `statements/` | PDFs, named by account and month | Highest authority. Never edited |
| `scripts/` | Python, standard library where it will do | Ask Sam before installing anything |
| `exports/` | Raw pulls from banks and apps, in `exports/<date>/` | Never edited |
| `reports/` | Outputs | A render of script output; never edit a number by hand |
| `archive/` | Anything retired | Nothing is deleted; retired files go here |
| `downloads/` | Existing: the 9 CSVs Sam pulled | Left untouched. Copies live in `exports/2026-10-22/`, which is what the scripts read |

What is in each folder right now:
| File | What it is |
|---|---|
| `ledger/transactions.csv` | The book of record. Every row carries its source and a confidence, plus whether a statement or the bank's balance has checked it |
| `ledger/rules.csv` | Payee pattern to category and kind. First match wins. Seeded from what Sam told me in Phase 1 |
| `ledger/overrides.csv` | One-off decisions Sam makes. Always win over rules |
| `ledger/held.csv` | Possible duplicates waiting for Sam's answer. Answers are remembered |
| `scripts/ingest.py` | Reads `exports/` into the ledger and runs the checks. `python3 scripts/ingest.py`. Exit code 2 means an account was withheld. `--accept-missing ACCOUNT --approved-by NAME --approved-on DATE` adds statement rows the download lacks, only after the user says yes and only if they explain the whole gap |
| `ledger/corrections.csv` | Rows added from a statement after Sam said yes (the statement lists them, the download lacks them). Each carries who approved it and when |
| `ledger/coverage.csv` | The dates each account's checked rows cover. Months outside it are flagged partial |
| `scripts/monthly.py` | Monthly totals from the ledger. `python3 scripts/monthly.py`; also writes `reports/monthly_totals.csv` |
| `scripts/unsorted.py` | Lists rows no rule has sorted yet, grouped by payee. Also writes `reports/unsorted_rows.csv` |
| `scripts/reconcile.py` | Run after every ingest. Per account and per statement period (the statement's own dates), opening balance plus the ledger's rows must equal the closing balance, to the cent; names any missing, extra or wrong row; never adds an adjustment row. Also writes the closing balances to `ledger/balances.csv` and checks the paystub. Exit code 2 means something disagrees |
| `scripts/year_bridge.py` | Year bridge for investment accounts: start, money in, money out (and where it went), market change, end. Also compares each month with the price change of the fund held, using the statements' own prices |
| `ledger/balances.csv` | Closing balance per statement (as_of, account, amount, source, confidence). Assets positive, amounts owed negative. Rows marked estimate are what Sam told me, to be replaced when a statement arrives |
| `ledger/year_bridge.csv` | The brokerage year bridge. 2026 is a partial year: the history starts in March 2026 because Sam has no older statements |
| `reports/reconcile_report.txt`, `reports/reconcile.csv` | Latest reconcile result |
| `reports/year_bridge_report.txt`, `reports/year_bridge_months.csv` | Latest year bridge and its month-by-month detail |
| `ledger/plan.csv` | Sam's budget, line by line: block, line, amount per month (income plus, spending minus), fixed (1 set bill, 0 Sam controls it), note, paid_by (bank or card). Sam can edit it in a spreadsheet app and save as CSV |
| `ledger/budget_map.csv` | Links each ledger category to a plan line by name. A category set to `(one-off)` stays out of the budget |
| `scripts/plan.py` | `--check` is run first by every build. Checks plain numbers, minus signs on spending, known blocks, unique names, and that no line was renamed out from under `budget_map.csv`. Stops and names the row. `--add-line` and `--map` record a decision Sam made, and refuse a wrong line |
| `scripts/budget.py` | Month to date by plan line (ok / watch / over / not posted), flex left, cushion on the current pace (set bills at plan, the rest at pace), and what is on the card (next month's cash) against what came straight from the bank |
| `scripts/spending_history.py` | What each category looked like in the complete months, to help Sam set amounts. History only, not a recommendation |
| `scripts/render_page.py` | Renders the budget as one self-contained page for a phone: `reports/budget_phone.html`. No scripts, no network, no payee names, no account numbers, no balances; plan lines and totals only. It is a render of `budget.py` output and cannot be edited |
| `MAINTENANCE.md` | The checklist for the weekly, monthly, quarterly, annual and event-driven routines. Holds no numbers; points at the scripts |
| `scripts/routine.py` | `weekly`, `monthly` or `quarterly`: runs the steps of that routine in order, stops at the first one that fails, then lists what is worth a look. Each routine includes the one before it |
| `scripts/networth.py` | Net worth from the latest balance of each account in `ledger/balances.csv`; says which balances are estimates and how old the statement ones are |
| `scripts/returns.py` | Saved versus growth, where money went when it left an investment account, and time-weighted and money-weighted returns, labelled as estimates. No benchmark is compared until Sam gives values or names a source. Writes `reports/returns_report.txt` |
| `scripts/emergency_fund.py` | The six-months-of-expenses target under each definition of expenses (everything, or essentials), what checking covers today, and how long the plan's monthly set-aside takes to reach it |
| `scripts/mortgage_whatif.py` | Pay the mortgage down or invest the extra: baseline payoff, what an extra payment does, and the break-even yearly return investing would have to beat. Arithmetic only, taxes not modelled, not a recommendation. Inputs: `mortgage` in `scripts/config.json` and the estimated balance in `ledger/balances.csv` |
| `scripts/plan_seed.py` | The record of how the first plan was built from Sam's decisions of 2026-10-22. Refuses to run if `plan.csv` already has lines: Sam owns the plan now |
| `scripts/statements.py` | Reads summary numbers off statement PDFs with `pdftotext`, which was already on this Mac. Nothing was installed |
| `scripts/ledgerlib.py` | Shared helpers: exact-to-the-cent money, ids, CSV reading and writing |
| `scripts/config.json` | Per-account setup: columns, date format, separators, which sign spending has, which account each file belongs to |
| `scripts/test_ingest.py` | Tests on made-up data. `python3 -m unittest discover -s scripts` |
| `reports/ingest_report.txt` | The latest run's report. Rewritten each run |

If numbers disagree, the order is: statements, then ledger CSVs, then any app or bank download, then spreadsheets Sam keeps, then any page or report. Fix the lower one, never the higher.

## Household profile
### People
| Person | Role | Age |
|---|---|---|
| Sam | Account holder, the person I work with | 41 |
| Jordan | Partner | 39 |
| Mira | Daughter | 7 |

### Accounts (no account numbers kept here)
| Account | Type | Owner | Notes | Files in folder (matched by file name only, not yet opened) |
|---|---|---|---|---|
| Otterbrook Bank | Everyday checking | Joint (Sam and Jordan) | Sam says this is all the bank accounts. Jordan's pay shows up as SALTMARSH USD PAYROLL (confirmed by Sam: Jordan's school district) | `downloads/otterbrook_checking_export_*.csv`, `statements/Otterbrook_eStatement_*.pdf` |
| Fernleaf Card Services | Rewards credit card | Sam | Jordan is an authorized user, so Jordan's purchases land on Sam's card | `downloads/fernleaf_activity_*.csv`, `statements/FernleafCard_Statement_*.pdf` |
| Tidewell | Taxable brokerage (investments) | Joint (Sam and Jordan) | Investment account, not a bank account | `downloads/tidewell_activity_*.csv`, `statements/Tidewell_Monthly_Statement_*.pdf` |
| Quillfeather Labs 401(k) | Retirement (employer plan) | Sam | About $96,000, from Sam's memory. Estimate only, no statement yet | none |
| School district 403(b) | Retirement (employer plan) | Jordan | About $41,000, from Jordan's memory via Sam. Estimate only, no statement yet | none |

Sam says that is every account. Confirmed none: no HSA, no college fund for Mira (not opened yet), no separate savings account, no other savings. My inference, not yet confirmed: with no savings account, any emergency cash is whatever sits in Otterbrook checking (the Tidewell brokerage is invested, not cash). To check in the Phase 6 coverage review.

The two retirement balances are recollections, not documents. Under the ground rules a statement outranks them; they stay marked "estimate" until statements arrive.

Employer note: Sam works at Quillfeather Labs. Sam confirmed `statements/Quillfeather_Paystub_2026-08-21.pdf` is Sam's. Jordan's employer is the school district.

### Pay
| Person | Employer | Take-home per paycheck | Schedule | Lands in | Taken out before pay |
|---|---|---|---|---|---|
| Sam | Quillfeather Labs | About $2,760 (Sam's estimate) | Every other Friday, direct deposit | Otterbrook checking | 6% of pay to the 401(k); employer matches 4% (match goes straight into the 401(k), never through checking); $186 for health insurance (per paycheck, confirmed on the paystub) |
| Jordan | School district | About $3,250 (Sam's estimate, relaying Jordan) | Monthly, on the last business day, direct deposit | Otterbrook checking | 5% of pay to the 403(b). Other deductions and any employer match: unknown. Summer gap: unknown |

Notes for later (no numbers typed by hand; scripts will do the arithmetic):
- Sam's figures are from memory. The paystub in `statements/` is the document to check them against in Phase 3.
- Every-other-Friday pay means two months a year have three paychecks. The Phase 4 plan must handle that deliberately instead of treating each month the same.
- Jordan's pay lands on the last business day of the month, so a deposit near month end can sit in a different calendar month than the bills it pays for. If Jordan's pay has a summer gap, the plan needs a cushion for it.
- The 401(k) contributions and employer match never touch the checking account. They show up only on the 401(k) statements, so they count as money in at that account's edge in the year bridge and in "saved vs growth".

### Property
| Property | Use | Bought | Price paid | Estimated value now | Mortgage |
|---|---|---|---|---|---|
| The family home | Where we live; the only property | June 2023 | $425,000 | About $450,000. Sam's guess, not a valuation (estimate) | Hollowmere, joint |

Confirmed: no other property (no rental, land or vacation place).

### Loans
| Loan | Type | Owner | Rate | Started | Original | Balance now | Payment | Source |
|---|---|---|---|---|---|---|---|---|
| Hollowmere Mortgage | 30-year fixed mortgage | Joint | 6.125% | June 2023 | $340,000 | About $326,000. Sam's guess, not checked (estimate) | $2,140 a month on the 1st, paid from Otterbrook checking, includes about $480 escrow (property tax and insurance). See Open questions: these figures don't reconcile yet | Sam's memory; no statement in folder |

Confirmed none: no car loan, no student loans. The Fernleaf card is on autopay for the full balance each month (see one-offs below), so no card debt is carried as a rule.

### Known one-offs (so the data doesn't surprise us)
- **Kitchen remodel (spring)**: contractor Halverson Renovation, $34,850 in total. Deposit of $22,000 by paper check #1042 in May; the final payment by bank transfer in June (the script will work out that amount from the ledger, not typed here). Funded by a $35,000 withdrawal from the Tidewell brokerage in May. Sam also said it drained checking (see Open questions). Treat as a one-off home-improvement cost, not normal monthly spending. The $35,000 is a move between our own accounts (a transfer), not income, and it left the brokerage because we moved it, not because the market fell.
- **Card autopay, June only**: Sam set the Fernleaf autopay to $1,000 for June instead of the full balance, and it went back to the full balance in July. Year not stated; presumably June 2026, to confirm in the data. Expect a $1,000 payment from checking, a balance carried forward, and possibly interest on the next card statement. That payment is a transfer, not spending.

### Recurring bills (Sam's first pass, amounts from memory so all are estimates)
How I plan to treat each row in the ledger is a proposal. Nothing is in `rules.csv` yet.

**Paid from Otterbrook checking**
| Payee | What | Amount as stated | How often | Proposed treatment |
|---|---|---|---|---|
| Hollowmere Mortgage | Mortgage | $2,140 (does not reconcile yet, see Open questions) | Monthly, on the 1st | loan |
| Little Acorns | Mira's aftercare | $420 | Monthly during the school year | spend: kids |
| Camp Willowbend | Mira's day camp, in place of aftercare | $650 | Monthly, July and August only | spend: kids |
| PebbleNet Fiber | Internet | $70 | Monthly | spend: utilities |
| Mapleford Electric | Electricity | Varies, higher in summer | Monthly | spend: utilities |
| Mapleford Water | Water | About $60 to $75 | Monthly (presumed) | spend: utilities |
| Steadyhand | Car insurance | $142.30 | Monthly (presumed, see Open questions) | spend: auto |
| Tidewell | Automatic investing into the brokerage | $500 | Monthly, around the 15th | transfer (savings); its other side must show up as a deposit in Tidewell |
| Rhea Okonkwo | Babysitter, paid through the bank app | $80 to $120 | Monthly | spend: kids. A payment to a person, so it must not be mistaken for a move between our own accounts |
| ATM cash | Farmers market and Mira's allowance | $60 or $100 | Monthly | spend: cash, counted when withdrawn (we can't see what the cash buys) |
| Fernleaf Card Services | Card payment, autopay of the full balance (June 2026 was set to $1,000) | Full balance | Monthly | transfer, never spending |

**Paid with the Fernleaf card** (Sam's card; Jordan is an authorized user)
| Payee | What | Amount as stated | Proposed treatment |
|---|---|---|---|
| Hearthstone Market, GreenBasket | Groceries | Varies | spend: food |
| QuikFill | Gas | Varies | spend: auto |
| Restaurants and coffee (Bean & Barley is the usual coffee place) | Eating out | Varies | spend: food out |
| OrbitMart | Online shopping | Varies | spend: shopping |
| Mira's swim club | Swim | $65 monthly | spend: kids |
| StreamBox, TuneWave | Subscriptions | Amounts not given | spend: subscriptions |
| ClearCall | Phone | $95 monthly | spend: utilities |

**Not mentioned yet (to cover in Phase 4 when we build the plan with Sam):** property tax and home insurance (presumably inside the mortgage escrow, confirm on a statement), life insurance, medical and dental costs, car costs beyond insurance (registration, maintenance, repairs), home repairs, clothing, gifts, any annual fee on the rewards card, and a set-aside for taxes.

### Goals (in Sam's order, with Sam's reasons)
| # | Goal | Target | Why it matters | Where it stands |
|---|---|---|---|---|
| 1 | Emergency fund | Six months of expenses | There have been layoffs in Sam's industry; the household wants to sleep at night | No savings account exists today. Cash is whatever sits in Otterbrook checking (inference, to check). Target amount to be worked out by script from the ledger once the definition of "expenses" is agreed |
| 2 | College fund for Mira | About $200 a month, start this year | They started late | Not opened yet. Account type not chosen. "This year" leaves a few weeks, so timing is worth noting |
| 3 | Keep investing in the brokerage for the long run | $500 a month | Long-run growth | Already happening: automatic, around the 15th, into Tidewell |
| 4 | Retire by 62 | Sam's target (Jordan's own target not stated) | Sam's wish | Retirement balances are only estimates today (no statements) |

Also on the table, not a goal yet: Jordan's question about paying the mortgage down early (see Open questions).

Goals 1 to 3 draw on the same monthly money, so the Phase 4 plan has to show how much room there is for all three at once. No numbers typed here; the plan will show them.

### Risk comfort
- Moderately cautious, both Sam and Jordan (Sam speaking for both).
- The 2022 market drop made them nervous. They would rather sleep well than chase returns.
- If investments fell by about a fifth in a few months, Sam is not sure what they would do. So the reaction is untested, not known.
- What this means for later work (framework, not advice): in Phase 6 the benchmark should match their actual mix of investments, not an aggressive one. Any projection should show a bad-years case beside the average case, because a bad stretch is what they say they worry about.

### How Sam likes answers (from the opening request)
Plain language, tables, keep it simple, one question at a time. Scripts do the arithmetic; numbers come from scripts, never typed by hand. Every projection ends with the "not a licensed financial advisor" note.

Detail level, confirmed by Sam: the short version. Plain language, tables, no jargon, short is better. Working shown only if Sam asks.

## Decision log
| Date | What | Decided by |
|---|---|---|
| 2026-10-22 | Started the project; made this folder a local git repo with no remote | Assistant, per ground rule 8 |
| 2026-10-22 | Household is Sam (41), Jordan (39, partner) and Mira (7, daughter) | Sam |
| 2026-10-22 | Bank and card accounts: Otterbrook checking (joint), Fernleaf rewards card (Sam, Jordan authorized user), Tidewell taxable brokerage (joint) | Sam |
| 2026-10-22 | Retirement accounts: Sam's 401(k) at Quillfeather Labs (about $96,000, estimate) and Jordan's 403(b) at the school district (about $41,000, estimate). No HSA, no college fund yet, no other savings. That completes the account list | Sam |
| 2026-10-22 | Loans: only the Hollowmere mortgage (joint, 30-year fixed, 6.125%, started June 2023, original $340,000, balance about $326,000 unchecked, payment $2,140 a month on the 1st incl. about $480 escrow). No car or student loans. Payment figures flagged as not reconciling; to settle from a statement | Sam |
| 2026-10-22 | Noted two one-offs: a remodel that drained checking, and a June-only Fernleaf autopay of $1,000 (full balance again from July) | Sam |
| 2026-10-22 | Sam's pay: about $2,760 take-home every other Friday into Otterbrook checking; 6% to the 401(k) with a 4% employer match; $186 health insurance. The Quillfeather paystub in statements/ is Sam's | Sam |
| 2026-10-22 | Jordan's pay: about $3,250 take-home, monthly on the last business day, into Otterbrook checking; 5% to the 403(b). Summer gap and other deductions unknown; to check with a paystub. Sam thinks the $186 health insurance is per paycheck | Sam |
| 2026-10-22 | Property: the family home is the only property; bought June 2023 for $425,000; value about $450,000 is Sam's guess | Sam |
| 2026-10-22 | Kitchen remodel (spring): Halverson Renovation, $34,850 total, check #1042 for $22,000 in May, final by bank transfer in June, funded by a $35,000 withdrawal from the Tidewell brokerage in May. The withdrawal counts as a transfer between our own accounts, not income | Sam, treatment as transfer by assistant (to confirm when the data is in) |
| 2026-10-22 | Recurring bills, first pass: list recorded above (checking and card). Yearly and irregular costs deferred to Phase 4. Treatment rules are proposals until the data is in | Sam (list); assistant (proposed treatment) |
| 2026-10-22 | Goals in order: 1) emergency fund of six months of expenses, 2) start a college fund for Mira this year at about $200 a month, 3) keep investing $500 a month in the brokerage, 4) Sam retire by 62. Jordan's mortgage-early-payoff question parked for Phase 6. Car insurance frequency still unconfirmed (Sam thinks monthly) | Sam |
| 2026-10-22 | Risk comfort: moderately cautious (Sam and Jordan), nervous since the 2022 drop, prefer sleeping well over chasing returns; reaction to a big drop untested | Sam |
| 2026-10-22 | Answers: the short version. Plain language, tables, no jargon | Sam |
| 2026-10-22 | Folder map created (ledger, scripts, exports, reports, archive; statements already existed). Phase 1 complete, waiting for Sam to confirm before Phase 2 | Assistant; Sam to confirm |
| 2026-10-22 | Phase 1 confirmed. Starting Phase 2 | Sam |
| 2026-10-22 | Way in: option 1, CSV downloads from each bank and card site. The 9 CSVs were copied (not moved) to `exports/2026-10-22/`, with a checksum list; originals left in `downloads/` | Sam (option); assistant (copy, per the brief's raw-files rule) |
| 2026-10-22 | Built `scripts/ingest.py` and helpers, with tests that pass. `ledger/rules.csv` seeded only from what Sam said in Phase 1 plus structural rules (card payments are transfers, refunds are negative spending). Anything else stays unclassified for Sam | Assistant |
| 2026-10-22 | First run: Otterbrook and Tidewell written and checked. Fernleaf withheld because one statement period does not tie out to the cent. Nothing loosened | Assistant (rule 1) |
| 2026-10-22 | Closed from the paystub and bank rows: the $186 health insurance is per paycheck; Steadyhand car insurance is monthly | Documents (paystub, bank rows) |
| 2026-10-22 | The Fernleaf download for the July statement period lacked one row the statement lists. Added that one row from the statement (recorded in `ledger/corrections.csv`, source = the July statement). The raw download is untouched | Sam ("go with your suggestion and add it from the statement"); assistant applied |
| 2026-10-22 | All three accounts now load and pass their checks. Transfers between our own accounts all found their other side (card payments and brokerage moves). Monthly totals written | Assistant |
| 2026-10-22 | Settings chosen by the assistant, open to objection: brokerage buys, sells, dividends and reinvestments get kind `invest` (not income or spending); a transfer must find its other side within 7 days; the remodel is shown apart from everyday spending in monthly totals | Assistant |
| 2026-10-22 | Sorting rules R025 to R031 added: Saltmarsh USD payroll is Jordan's pay; Riverside Swim Club is Mira's swim lessons; the four restaurants (including The Copper Spoon on the card and the debit card) are Dining; the pharmacy is Health; the Norwegian shop purchase is Gifts, not Shopping; the foreign transaction fee and the June card interest are Fees and interest | Sam |
| 2026-10-22 | Sam explained the June card interest: it came from paying only part of the balance that month. Noted as the cost of that choice; no action asked | Sam |
| 2026-10-22 | Phase 2 confirmed. Starting Phase 3 | Sam |
| 2026-10-22 | Phase 3 checks: every statement adds up by its own summary (no misreads), and every statement ties to the ledger to the cent, per statement period; the paystub's net pay matches the deposit, and its 401(k) and match are the stated percent of gross. Details in `reports/reconcile_report.txt`. No adjustment rows exist | Assistant (scripts) |
| 2026-10-22 | Year bridge built for the brokerage. Flag thresholds fixed before looking: a month is flagged if the account's price change and the held fund's price change differ by more than 0.50 percentage points, a year by more than 1.00 point. Nothing flagged. The market proxy is the held fund's own price on the statements, not outside data | Assistant |
| 2026-10-22 | Balances Sam gave from memory recorded in `ledger/balances.csv` as estimates: both retirement accounts, the mortgage balance, and the home value. Statement-based rows replace them when statements arrive | Sam (figures); assistant (recording) |
| 2026-10-22 | History starts in March 2026 (the card in late February). Sam has no older statements, so there are no earlier months to read off statements or keep as balances only | Sam |
| 2026-10-22 | Phase 3 confirmed. Starting Phase 4 | Sam |
| 2026-10-22 | Rule R009 split in two so the sign is clear: money sent to the brokerage (`Savings: brokerage`) and money that came back from it (`From brokerage`, new rule R032). Both are still transfers between our own accounts; only the category changed | Assistant |
| 2026-10-22 | Plan tools built and tested. Plan amounts are only ever Sam's decisions; I record a line only after Sam says it, and the tool refuses a wrong one | Assistant |
| 2026-10-22 | Income: Sam's pay counted as a plain month (two paychecks); the third paycheck in a three-paycheck month (this October, next April) is extra and goes to the emergency fund. Jordan's pay: what actually lands each month | Sam |
| 2026-10-22 | Committed lines: groceries $900, dining out and coffee $250, gas $150 (Sam's numbers). Childcare and swim: what is actually paid. Electric, water, internet, phone: the recent average. Subscriptions: what is paid now. Anything not named: the six-month average, for Sam to adjust | Sam |
| 2026-10-22 | Expected lumpy costs: home repairs $150, doctors $100, annual fees $10 a month. No tax set-aside: withholding covers it | Sam |
| 2026-10-22 | Savings: brokerage $500, emergency fund $1,000, Mira's college fund $200 (once it is opened) | Sam |
| 2026-10-22 | Paid by: everyday spending on the Fernleaf card; mortgage, utilities except the phone, childcare and insurance straight from checking | Sam |
| 2026-10-22 | How I read the instructions, open to change: childcare counted as a twelfth of the year (10 school months of aftercare plus July and August camp), so camp months run over and school months under; "recent average" for utilities taken as the six-month average; electric and water treated as set bills because they post once a month; the two unopened savings accounts kept in the plan so the flex pool is already net of them; the remodel kept out as a one-off; the pharmacy counted against the doctors line | Assistant |
| 2026-10-22 | Sam edited `plan.csv` in a spreadsheet app. Cells that differ from the version I wrote: Mortgage amount (now currency text), Electric amount (minus sign gone), and the line "Fees and interest" renamed "Fees and interest & misc". The check refused the file; nothing was loosened and nothing was changed without Sam | Sam (edit); assistant (check) |
| 2026-10-22 | Fixed the three problems the check found in Sam's saved plan: put back the plain number on the Mortgage amount, put back the minus sign on Electric, and pointed `budget_map.csv` at the line Sam renamed to "Fees and interest & misc". No amount changed and the rename was kept. Plan check and budget now run clean | Sam (yes, "the rename was on purpose"); assistant applied |
| 2026-10-22 | Sam asked me to push the folder to his GitHub so he can see the budget on his phone. Not done: ground rule 8 says never add a remote or push, and the folder holds statements (names, address, account endings) and every transaction. Offered a local alternative instead: `reports/budget_phone.html`, which Sam moves to his phone himself (AirDrop, Files or email). Changing rule 8 would be Sam's explicit call, and a stripped-down export would be safer than the folder | Assistant (rule 8); Sam asked |
| 2026-10-22 | Phase 4 confirmed; the phone page works for Sam. Starting Phase 5 | Sam |
| 2026-10-22 | Wrote `MAINTENANCE.md` and the one-command routines. Cadence: weekly 5 minutes (day to be chosen), monthly 20 minutes on the 5th once the statements have landed, quarterly in January, April, July and October, annual in January, event-driven as needed. Each routine starts with Sam dropping fresh downloads into `exports/`. Scheduled tasks are not set up in this session (the tool is not available to me here); the two prompts to schedule are written into `MAINTENANCE.md` | Assistant; Sam to choose the weekly day |
| 2026-10-22 | Weekly check: Sunday evening (Sam: "Sunday evening sounds fine"). Monthly check: the 5th, once all three statements have landed | Sam (weekly); assistant (monthly, Sam did not object) |
| 2026-10-22 | Phase 5 confirmed. Starting Phase 6 | Sam |
| 2026-10-22 | Phase 6 begun. Saved-versus-growth, the trail of the money that left the brokerage, and the two return measures were computed from the statements and ledger and shown to Sam as estimates, without a benchmark. The emergency fund target is shown under two definitions of expenses; the essentials list is the assistant's proposal until Sam chooses | Assistant |
| 2026-10-22 | Sam asked which definition of expenses to use for the emergency fund and asked me to suggest one. Not recommended: that is a personal choice and I give frameworks, not recommendations. The trade-off was laid out; both definitions stay in every report until Sam chooses | Assistant (rule 9); Sam to choose |
| 2026-10-22 | Sam remembers about $112,000 for the brokerage at the end of August, from the app. Not recorded as a balance: the August statement is the higher authority (statements outrank app figures) and it ties to the ledger and adds up by its own summary. The difference is noted here and in Open question 0 until the date of the app figure is known | Assistant (rule 2) |
| 2026-10-22 | Sam asked "what should we do?" about paying down the mortgage early versus investing the extra. Not recommended: a personal choice, and I give frameworks, facts and trade-offs. Gave the trade-off factors and the arithmetic (paying down earns the loan rate for certain; investing has to beat it after tax, with risk). Asked how much extra per month they are weighing. Sam also said he does not remember the date of the brokerage figure and will check the September statement | Assistant (rule 9); Sam to decide |
