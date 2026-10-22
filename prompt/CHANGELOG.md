# Changelog

Every change to the prompt, with the reason. v0 was the author's original.

## Changelog v0 → v1 (research stage, 2026-10-15)

| # | Change | Why (sources checked 2026-10-15) |
|---|---|---|
| 1 | "Where" now offers Claude Code or Cowork, with a privacy note for each | Cowork runs in the cloud on Pro/Max since 2026-10-06 and Anthropic's "Use Claude Cowork safely" says to avoid granting financial documents; Anthropic points local-only work to Claude Code in the desktop app. Author chose "both, reader picks". |
| 2 | Turn off Memory in Cowork before pasting | Rule 6 can't stop Cowork memory; the toggle is per task and set before start. |
| 3 | CSV line softened | No source supports "almost every bank"; download windows are often 90 days to 18 months. |
| 4 | "paystub (payslip)" | US-only term. |
| 5 | "Work only in the folder I've opened or connected" | Venue-neutral, and scopes Claude to one folder. |
| 6 | README gets "Where we left off" and "Open questions" | The live essay promises both; v0 never created them. |
| 7 | Git fallback to dated copies in archive/ | Git under cloud Cowork is unverified. |
| 8 | Phase 5: routines start with fresh downloads; scheduled tasks only if the app supports them | Claude can't log in to banks (rule 5), so a "sync" can only process files already dropped in. |
| 9 | Phase 6: time-weighted vs benchmark, money-weighted as your own result, both labeled estimates | v0 paired both measures with the benchmark; only time-weighted is benchmark-comparable. |

## Changelog v1 → v2 (critique panel, 2026-10-15)

| # | Change | Why (which reviewer raised it) |
|---|---|---|
| 1 | Rule 1: exact cents; if a check fails, stop; never loosen a check to pass | Claude writes the checks too, and a failing check invites a tolerance (domain P0-4, skeptic P0-1) |
| 2 | Rule 2: raw downloads stay untouched | "Fix the lower one" clashed with "exports never edited" (domain P2) |
| 3 | Phase 1: pre-tax savings in the interview | "How much I saved" misses money that never touches checking (domain P2) |
| 4 | Scripts: standard library where it will do, ask before installing | pandas is often missing on a reader's own machine; decimal gives exact cents (domain P1-10) |
| 5 | Phase 2 config: debit/credit columns, date format, separator, decimal mark, one source per account | Real downloads need more than date/payee/amount (domain P1-7) |
| 6 | Phase 2: posted rows only; stable id rule with a same-day counter | Pending charges post later at a different amount; a date+payee+amount hash merges a real identical pair (domain P1-6) |
| 7 | Phase 2: refunds; transfers must pair within a few days | A transfer with no other side may be the only record of spending; pairing stands in for double-entry (domain P1-8, skeptic P1-6) |
| 8 | Phase 2: held.csv, remembered answers, idempotent ingest | Re-running must not re-ask or re-add (domain P1-6) |
| 9 | Phase 2: check total must come from a total Claude didn't compute; say where; unreconciled until a statement covers it | Bank CSVs carry no total; weekly downloads would otherwise be refused or checked against an invented total (domain P0-2, skeptic P0-1) |
| 10 | Phase 3: check each statement against its own summary first | The most trusted source is read by the least reliable method (skeptic P1-3, domain #3) |
| 11 | Phase 3: scripts/reconcile.py by statement period; never an adjustment row; leave gaps open | Card cycles don't match calendar months; an eager model forces a match (domain P0-1, skeptic P0-1) |
| 12 | Phase 3: months beyond the download window | Otherwise nothing to reconcile and the instruction is ambiguous (domain P2) |
| 13 | Year bridge: money in/out defined; check against the statement summary; flag market change far from the market | Dividends/buys counted as flows corrupt the residual; a missing transfer otherwise reports the original "market loss" (domain P0-3, skeptic P1-7) |
| 14 | Phase 4: amounts per month, yearly costs a twelfth | Lumpy costs need one unit (domain P0-5) |
| 15 | Phase 4: flex pool after committed, lumpy set-asides and savings | v1 showed savings money as free to spend (domain P0-5) |
| 16 | Phase 4: cushion projects set bills at plan, the rest at pace | A mortgage on the 1st distorts a straight pace projection (domain P2) |
| 17 | Phase 6: benchmark matches the mix; values from me or a named source, never memory | A benchmark typed from memory breaks rule 1 (domain P1-10) |

## Changelog v2 → v3 (run-1 test drive, 2026-10-22)

Each fix maps to what the test drive showed. Full scoring in `evidence/evidence.md`.

| # | Change | Why (run-1 evidence) |
|---|---|---|
| 1 | Phase 1: copy the ground rules into CLAUDE.md and put a "what to type when you come back" line at the top of README.md | A fresh session with no starter prompt still archived instead of deleting, but only because the first session happened to restate the rules in MAINTENANCE.md and the README folder map. The prompt never asked for that, so it was luck, not design (`evidence/run-1-transcript.md`, day-two test; no CLAUDE.md in `evidence/run-1-built-by-claude/`) |
| 2 | First paragraph: keep every file inside the folder, even temporary ones | The model twice wrote scratch files to `/tmp`, once a copy of the household's budget plan. It noticed both times and deleted them (`evidence/run-1-transcript.md`, turns 14 and 21). "Work only in the folder" didn't stop it |
| 3 | Phase 2: list any identical same-day pair for me to confirm | The two identical coffees were both kept, which was correct, but Sam was never told. `ledger/held.csv` stayed empty for the whole run, so a real merchant double charge would also pass in silence (`evidence/run-1-built-by-claude/ledger/transactions.csv`, ids `...-1` and `...-2` on 2026-05-14) |
| 4 | "PHASE 1 - Know" becomes "PHASE 1: Know" (all six), and "CSVs - the book of record" becomes "CSVs, the book of record" | Cosmetic: no dash stand-ins in the house style |
| 5 | Phase 3: market figures for the bridge sense check come from the statements, from me or from a named source, never from memory | Run 1 did this on its own, using the fund's prices printed on the statements (`evidence/run-1-built-by-claude/reports/year_bridge_report.txt`). Phase 6 already had this rule and Phase 3 didn't. Preventive: no failure was observed |

Considered and not changed: one question per turn (one lapse, and the rule is already plain); the day-two session's `git -c core.hooksPath=/dev/null` habit (no hooks existed, so nothing was bypassed, and a beginner's folder has none to protect).
