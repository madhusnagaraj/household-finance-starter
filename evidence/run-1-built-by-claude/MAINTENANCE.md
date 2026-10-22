# Keeping the household finance system up

This file is the checklist. It holds no numbers: every number comes from a script. Run the command, read what it prints, and say what it says.

## Rules for every routine
1. **Scripts do the arithmetic.** Never type a number into a page or report. Change the data, run the script, show its output.
2. **If a check fails, stop and show Sam.** Never loosen a check, a tolerance or a total to make it pass. When numbers disagree: statements, then ledger CSVs, then bank or app downloads, then Sam's spreadsheets, then any page or report. Fix the lower one.
3. **Read-only.** Nothing here logs in to a bank or changes anything in a bank, card or app. Anything that needs fixing there is listed for Sam, who decides.
4. **No passwords, no MFA codes.** If something asks for a login, stop and tell Sam.
5. **Commit after every change** with a clear message. This folder never gets a remote and is never pushed.
6. **Private.** Balances, account numbers and transactions stay in this folder.
7. **Not financial advice.** Frameworks, facts and trade-offs. End every projection with the note that this is not licensed financial advice.
8. **A page or dashboard is only a render of script output.** `scripts/render_page.py` makes `reports/budget_phone.html`. Never edit a number on it; change the data and run the script.

## How every routine starts (Sam's job, about two minutes)
Nothing here can log in for you, so each routine starts with fresh files in the folder:

| For | Where to get it | Put it in |
|---|---|---|
| Otterbrook checking | The bank site: a CSV of posted transactions with the running balance | `exports/<today's date>/` |
| Fernleaf card | The card site: the CSV of activity for each new billing period | `exports/<today's date>/` |
| Tidewell brokerage | The brokerage site: the activity CSV | `exports/<today's date>/` |
| Statements (monthly) | Each site's PDF statement | `statements/`, named by account and month, like the existing ones |

Keep the files exactly as the site gives them. Raw downloads are never edited.

## Cadence
| Routine | When | Time | Command |
|---|---|---|---|
| Weekly | Sunday evening (Sam's choice; his paychecks land on Fridays, so a weekend check sees them posted) | 5 minutes | `python3 scripts/routine.py weekly` |
| Monthly | The 5th, once all three statements have landed (the card closes on the 23rd; the bank and brokerage close at month end) | 20 minutes | `python3 scripts/routine.py monthly` |
| Quarterly | The first week of January, April, July and October | Longer than monthly | `python3 scripts/routine.py quarterly` |
| Annual | January, after year-end tax documents arrive | A longer session | Checklist below |
| Event-driven | A new account, loan, job or property | As needed | Checklist below |

Each routine includes the one before it: monthly runs everything weekly does, and quarterly runs everything monthly does. A routine stops at the first step that fails and says which.

## Weekly (5 minutes): sync, budget, anything odd
1. Sam drops fresh downloads into `exports/<today's date>/`.
2. Run `python3 scripts/routine.py weekly`.
3. Read "Worth a look". For each item:
   - *Out of date*: the downloads were not added. Add them and rerun.
   - *Rows with no rule yet*: run `python3 scripts/unsorted.py`, ask Sam what each payee is, and add a rule to `ledger/rules.csv` (added by Sam, with the date).
   - *Possible duplicates*: show Sam the rows in `ledger/held.csv`; he answers add or duplicate, and the answer is remembered.
   - *Transfers with no other side*: show Sam. Do not guess.
   - *Budget lines over or watch*: report them. Nothing to fix; it is information. Sam changes the plan, not me.
4. Look at `reports/budget_phone.html`.
5. Commit.

## Monthly (20 minutes after the statements land): reconcile, month-end review
1. Sam drops the new statement PDFs into `statements/` and the matching downloads into `exports/<today's date>/`.
2. Run `python3 scripts/routine.py monthly`.
3. **Reconcile.** Every statement must tie to the ledger to the cent. If one does not, the statement wins. The report names the missing, extra or wrong row. If a statement lists a row the download lacks, show Sam and wait for his yes before running `python3 scripts/ingest.py --accept-missing <account> --approved-by Sam --approved-on <date>`. Never add an adjustment row to force a match.
4. **Month-end review**, from the budget for the month just ended: how much of the flex pool was left, the cushion, the lines that went over, and the card total (next month's cash).
5. In a month with an extra paycheck, say so. Sam's rule: the extra paycheck goes to the emergency fund.
6. Ask Sam whether any plan line should change. He edits `ledger/plan.csv` in his spreadsheet app and saves it back as CSV. The checker runs first and names any row that is wrong. Tip for the spreadsheet: format the amount column as plain Number with two decimals and no currency symbol or thousands separator, and keep the minus sign on spending.
7. Update the README's "Where we left off" and "Open questions". Commit.

## Quarterly: investments, net worth, the year bridge
1. Run `python3 scripts/routine.py quarterly` after the monthly steps pass.
2. **Investments.** Read the year bridge: money in, money out (and where it went), market change. Money Sam moved is never counted as a market loss. If the bridge flags a month, investigate; do not widen the threshold.
3. **Net worth.** Read the table. Anything marked *estimate* is what Sam told us from memory; replace it with a statement when one arrives (retirement accounts, the mortgage). Say which balances are old.
4. Ask Sam for the latest retirement and mortgage statements and put them in `statements/`.
5. Check progress on the goals in the README (emergency fund, Mira's college fund, brokerage, retirement). Use frameworks and trade-offs, not recommendations.
6. Commit.

## Annual (January)
- **Taxes.** Gather: both employers' year-end pay statements, the brokerage's year-end tax documents (they show any gain or loss from selling investments, such as the sale made for the kitchen remodel), the mortgage interest statement, childcare receipts. Give the list to Sam and whoever prepares the return. This is not tax advice.
- **History.** Run the quarterly routine for the full year; save a copy of that year's `ledger/plan.csv` into `archive/<year>/` before changing it.
- **Plan for the new year.** Review every plan line with Sam; update the dates of the extra-paycheck months; check the yearly costs (car registration, annual fees, repairs).
- **Insurance and estate check.** Ask Sam about each: home and auto policies and renewal dates, life insurance, will, who is named on the 401(k) and 403(b), an umbrella policy, guardianship for Mira. Record what exists and what does not in the README. Do not recommend products.
- **Emergency fund.** Compare the actual fund with the six-months-of-expenses target, using the definition of expenses Sam chose.
- Commit.

## Event-driven
| When | Do this |
|---|---|
| New bank, card or brokerage account | Add the account and its download format to `scripts/config.json`; add rules to `ledger/rules.csv`; put the first statement in `statements/`; run the weekly routine; confirm the totals tie. The emergency fund and Mira's college fund accounts are not opened yet: when they are, do this and map their transfers to the plan's savings lines |
| New loan | Add the loan to the README profile, a rule for the payment (kind `loan`), and its statement balance to `ledger/balances.csv`; add a plan line |
| New job or pay change | Update the pay lines in `ledger/plan.csv`, add a rule for the new payer (kind `income`), and ask about the retirement plan and match |
| New property or a big purchase | Add it to the README profile and `ledger/balances.csv`; decide with Sam whether a category is a one-off in `ledger/budget_map.csv` |
| A check stops a run | Show Sam what stopped it and wait. Do not loosen anything |

## What a STOP means
| Message | Meaning | What to do |
|---|---|---|
| `STOP: <account> was NOT written` (ingest) | The account does not match the bank's balance or its statement | Read the report; the statement wins. Show Sam the missing or extra row |
| `DISAGREEMENTS FOUND` (reconcile) | A statement does not tie to the ledger | Same |
| `PLAN HAS ERRORS` | The plan or the category map has a bad row | Read the row it names; ask Sam |
| `nothing for <month> yet` | The ledger does not reach that month | Add fresh downloads |

## Scheduled tasks (not set up in this session)
This session cannot create scheduled tasks, so these are not running. If you want them later, these are the two prompts to schedule (the weekly on Sunday evening, the monthly on the 5th). They point at this file and the scripts and restate no numbers:

- **Weekly:** "Open the household finance folder. Read MAINTENANCE.md, then run `python3 scripts/routine.py weekly`. Report in plain language with tables: what is out of date, what needs a rule, which budget lines are over or on watch. If any step stops, stop and tell me. Do not type any number yourself, and do not log in anywhere."
- **Monthly:** "Open the household finance folder. Read MAINTENANCE.md, then run `python3 scripts/routine.py monthly`. Report whether every statement ties to the ledger, the month-end review from the budget, and anything that needs my answer. If any step stops, stop and tell me. Do not type any number yourself, and do not log in anywhere."

Until then, this file is the checklist and you start each routine by hand.
