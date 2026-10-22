# Starter prompt: a personal finance manager with Claude

> **Version 3.** v2 was test-driven on a made-up household; v3 adds five small fixes from that run, and a second, shorter run checked the ones that change behavior (see `../evidence/` and `CHANGELOG.md`).

A prompt you paste into Claude to build a household finance system: one folder of plain files where every number traces back to a statement, kept up by short routines, and owned by you.

## Before you start

* Where: Claude's desktop app, one of two ways. Make a folder on your computer (for example `~/Finance`) first.
   * **Claude Code** (the Code tab): open the folder there. It runs on your computer and keeps the folder and the chat history there. A little more hands-on.
   * **Cowork**: connect the folder to a task. Easier, but since October 2026 Cowork runs in the cloud on Pro and Max, so files it opens are processed on Anthropic's servers. Anthropic's own safety page says to avoid giving Cowork financial documents. If you use it anyway, turn off Memory in the + menu before you paste the prompt.
   * Either way, whatever Claude reads is sent to Anthropic's model to be processed. Check your privacy settings (model training) before you start, and keep this folder for finance only.
* Have ready:
   * A list of every account: bank, cards, loans, brokerage, retirement, property.
   * 12 to 24 months of statements as PDFs.
   * A way to get your transactions. Any of these works:
      * CSV downloads from each bank and card website. Most offer them, but many only go back a few months to a year and a half, which is why the statements matter.
      * An export from an app you already use: a budgeting app, an aggregator, Quicken, or a spreadsheet.
      * Just the PDF statements, if nothing else is handy.
   * A recent paystub (payslip).
* No special software needed. Any spreadsheet app works for the one file you'll edit yourself.
* Expect: an afternoon for a first useful view, then a few weeks of short sessions before you can trust it. That's normal, because the slow part is getting the data and the context right.

## The prompt (copy everything in the box)

```text
You're helping me build a personal finance system for my household that I can trust and keep up for years. Work only in the folder I've opened or connected for this task, and keep every file you make inside it, even temporary ones. Go in the phases below and don't start a phase until I've confirmed the one before. Ask me one question at a time. Answer in plain language, use tables, and keep it simple.

WHY THE ORDER MATTERS
A spending dashboard takes an afternoon, but it will be wrong in ways neither of us can see. The value comes from three things built first: one source of truth, every number traceable to a document, and the context about my household written down in files (chats end; files don't). Build those before any charts.

GROUND RULES (every session)
1. Scripts do the arithmetic; you do the reasoning. Never type a number onto a page or report by hand. Change the data, re-run the script, show its output. Store and add amounts exactly, to the cent. If a check fails, stop and show me. Never loosen a check, a tolerance or a total to make it pass.
2. When numbers disagree, this order settles it: statements > ledger CSVs > any app or bank download > spreadsheets I keep > any page or report. Fix the lower one, never the higher (raw downloads in exports/ stay untouched; note the difference instead).
3. Every ledger row carries a source (which document or export) and a confidence (exact or estimate).
4. Read-only by default. Never change anything in my bank, card or any app I use on your own. If something needs fixing there, list it and wait for my yes on each item. Never change amounts or dates, and never delete.
5. Never type passwords or answer MFA prompts. If something asks for a login, stop and tell me.
6. Balances, account numbers and transactions are private. Report them to me in chat and keep them in the folder, never in memory or shared notes.
7. Keep a dated decision log at the bottom of README.md ("what, decided by whom, when"). Once I close a topic, don't reopen it. Keep two short sections at the top of README.md: "Where we left off" and "Open questions". Read them at the start of every session and update them at the end.
8. Make the folder a local git repo and commit after every change with a clear message. Never add a remote or push. If git isn't available where you're running, tell me, and save a dated copy of any file to archive/ before you change it.
9. You're not a licensed financial advisor. Give me frameworks, facts and trade-offs, not personal recommendations, and end every projection with a short note saying so.

PHASE 1: Know the household (one session)
Interview me, one question at a time: who's in the household; every account and whose it is (mine, partner's, joint); take-home pay, savings taken out before pay, and the pay schedule; loans and their rates; properties; recurring bills; goals and why they matter; how risk-averse I am; how I like answers. Write it to README.md. Copy the ground rules above into CLAUDE.md in the folder (Claude Code reads it at the start of every session), and put one line at the top of README.md saying what I should type to pick up where we left off. Create the folder map:
  ledger/      CSVs, the book of record
  statements/  PDFs, named by account and month
  scripts/     Python, standard library where it will do (ask me before installing anything)
  exports/     raw pulls, never edited
  reports/     outputs
  archive/     anything retired
Show me the README and the map, then wait.

PHASE 2: Get the data in
Ask me how I can get my transactions and use the simplest option that works for me:
- CSV (or OFX/QFX) downloads from each bank and card website;
- an export from a budgeting app, aggregator or spreadsheet I already use;
- a read-only connector to my finance app, if one is installed in Claude;
- the PDF statements alone, if that's all I have (slower, but it works).
Save every raw file untouched in exports/<date>/. Then write scripts/ingest.py that:
- reads each source through a small per-account config (its columns, date format, separator and decimal mark, which sign spending has, and which account it belongs to, so no account comes in from two sources), because every bank formats its download differently;
- loads only posted rows (pending ones change before they post) into ledger/transactions.csv, each with a stable id: the bank's own id if the file has one, otherwise account, date, amount and payee plus a counter, so two real identical charges stay two (list any such pair for me to confirm);
- classifies rows with ledger/rules.csv (payee pattern -> category and kind: spend, income, transfer, loan, rental...), with ledger/overrides.csv (one-off decisions I make in chat) always winning;
- treats card payments and moves between my own accounts as transfers, never spending, and refunds as negative spending, never income. Each transfer needs its other side in the ledger within a few days; ask me about any that don't have one;
- matches against rows already in the ledger, HOLDS possible duplicates in ledger/held.csv for me instead of adding them, remembers my answers, and changes nothing if run twice on the same files;
- never deletes anything. It checks each account against a total it didn't compute (the download's running balance, or the statement's opening and closing balance for the same dates), refuses to write that account if they don't match, and says by how much. Tell me where each account's total comes from. Rows no statement covers yet stay marked unreconciled.
Then show me monthly totals and the rows it couldn't classify. I'll tell you what they are, and you add rules.

PHASE 3: Rebuild history from statements
Go through statements/ year by year. First check each statement adds up by its own summary (opening balance, listed totals, closing balance); if it doesn't, you misread it, so tell me which numbers. Record each closing balance and date in ledger/balances.csv (as_of, account, amount, source, confidence). Write scripts/reconcile.py and run it after every ingest: per account and per statement period (the statement's own dates, not calendar months), the opening balance plus the posted rows must equal the closing balance, to the cent. Where they disagree, the statement wins: find the missing, extra or wrong row and show me the fix. Never add an adjustment row to force a match; if you can't find the cause, show me the gap and leave it open. For months my downloads don't reach, ask me whether to read transactions off the statements or keep balances only.
For investment accounts, build ledger/year_bridge.csv per account per year: start, money in, money moved out (and where it went), market change, end. Money in and out means only money crossing the account's edge (contributions, withdrawals, transfers); dividends, interest, fees, buys, sells and reinvestments belong to market change. Check the bridge against the statement's own summary where it prints one, and flag any year where market change is far from what the market did (market figures from the statements, from me or from a source you name, never from memory). That way money I moved is never mistaken for money the market lost.

PHASE 4: The budget, which I own
Build ledger/plan.csv with me line by line, with columns block, line, amount (per month, spending negative; yearly costs as a twelfth), fixed (1 = set bill, 0 = I control it), note, paid_by (bank or card). The blocks:
- income
- committed lines: home, auto, food, utilities, subscriptions, kids, health...
- expected lumpy costs: repairs, doctors, annual fees, a tax set-aside
- savings
What's left after the committed lines, the lumpy-cost set-asides and savings is the flex pool, the money I can spend freely. What's left of it at month end is the cushion.
ledger/budget_map.csv links each category to a plan line by name.
I'll edit plan.csv myself in a spreadsheet app and save it back as CSV. So write scripts/plan.py --check and have every build run it first. It checks for plain numbers, minus signs on spending, known blocks, and no line renamed out from under budget_map. If something's wrong, it stops and names the row.
scripts/budget.py shows month to date by line (ok / watch / over / not posted), flex left, cushion on the current pace (set bills at plan, the rest at pace), and what's on cards (next month's cash) vs what came straight from the bank.

PHASE 5: Routines (only once the numbers match the statements)
Write MAINTENANCE.md with a cadence:
- weekly, 5 minutes: sync, budget, anything odd
- monthly, 20 minutes after statements land: reconcile, month-end review
- quarterly: investments, net worth, the year bridge
- annual: taxes, history, insurance and estate check
- event-driven: new account, loan, job or property
You can't log in to my bank, so each routine starts with me dropping fresh downloads into exports/ (or a read-only connector, if I use one). If this app supports scheduled tasks, set up the weekly and monthly checks as scheduled tasks whose prompts point at MAINTENANCE.md and the scripts instead of restating any numbers. If it doesn't, MAINTENANCE.md is my checklist and I'll start them by hand. Any page or dashboard is only a render of script output; never edit a number on it.

PHASE 6: Questions worth asking
Once it's trustworthy, help me think with the ledger:
- my time-weighted return against a simple benchmark that matches my mix (values from me or a source you name, never from memory), and my money-weighted return (what I actually earned, given when I added or took out money); from monthly statements both are estimates, so label them that way
- how much I saved vs how much was growth
- where money went when it left an investment account
- whether we're covered: insurance, will, beneficiaries, emergency fund, umbrella
- what "enough" looks like vs "more"
Frameworks and math, not advice.

Start with Phase 1: ask me your first question only.
```

## Tips from building the original

* Give Claude statements as files. A balance typed from memory is how wrong numbers get in.
* Teach the rule, not the row. When a category is wrong, add a rule (or fix it in your app, if you use one) so the next import gets it right. Keep overrides.csv for true one-offs.
* Same day each month for downloads. If you're using bank CSVs, grab them right after statements close, so every month lines up with a statement.
* Keep chats short and files long. Anything worth remembering goes into README.md or MAINTENANCE.md, because conversations get trimmed and sessions end.
* Hold off on dashboards until the ledger matches the statements. A pretty page on wrong data is worse than no page.

*Not financial advice. The prompt asks Claude for frameworks, facts and trade-offs; the decisions about your money stay yours.*
