# Run 2 transcript: targeted re-test of starter-prompt-v3, Phases 1 and 2 (2026-10-22)

Same set-up as run 1 so the prompt is the only variable: fresh general-purpose subagent, model `sonnet`,
the IDENTICAL harness note (only the folder path changed; deliberately NOT adding "/tmp" to the note,
so v3's "keep every file inside it, even temporary ones" carries that alone), verbatim v3 prompt,
user played by the orchestrator from `fixture/persona.md`, reusing run 1's answers where the questions match.
Run folder: scratchpad `hh-run-2/` seeded with the same 9 downloads and 20 statements.

**What this re-test checks (v3 changes 1 and 3, plus 2 by observation):**
1. Phase 1 writes the ground rules to `CLAUDE.md` and a "what to type when you come back" line at the top of README.
2. No files written outside the folder (observational: run 1 slipped twice, at Phase 2 hashing and Phase 4 diffing).
3. Phase 2 lists the identical 05/14 Bean & Barley pair for Sam to confirm.
Stops after Phase 2 is confirmed.

---

## Turn 1 (assistant)
git init, fictional identity, no remote, baseline commit `4b10046`; listed (not opened) downloads/ and statements/; noted the April Otterbrook PDF appears twice "probably a duplicate download to check in Phase 2". Asked Phase 1 Q1 (who is in the household).

## Turn 1 (user, Sam): all Phase 1 answers in one message (same persona facts as run 1, batched to keep the re-test short)
> (full persona answer: household; accounts and owners; pay; loans; property and remodel; bills; goals; risk; answer style. Verbatim text in the SendMessage below.)

## Interruption (harness, not the user)
The model-under-test's turn 2 was cut off by an account rate limit (HTTP 429) partway through writing README. After the reset it received a harness-marked note (not a user message): check the folder state and continue where it stopped.

## Turn 2 (assistant): end of Phase 1 (after the interruption)
Checked folder state after the cut-off; everything committed; downloads/ and statements/ untouched and unopened. Summary table, every figure marked as estimate. **Re-caught the persona mortgage inconsistency by script** (`scripts/phase1_sanity.py`: P&I $2,065.88 vs $2,140 - $480 = $1,660.00; balance fits), changed nothing. Duplicate April PDF identical byte for byte. 10 open questions. Folder map shown.
**v3 change 1, VERIFIED ON DISK:** `CLAUDE.md` holds the nine ground rules verbatim (incl. "never delete", "Never add a remote", rule 9) plus phase order and style; **README line 1: "To pick up where we left off, type: `Pick up where we left off on our household finance system. Read README.md and CLAUDE.md first.`"** 4 commits, 0 remotes. Stopped at the Phase 1 gate.

## Turn 2 (user, Sam)
> Confirmed. For transactions: I downloaded CSVs from each bank website, they're in downloads/, and statements are in statements/.

## Turn 3 (assistant): Phase 2 ingest
Copied downloads to `exports/2026-10-22/` with a checksum file. Every statement adds up by its own summary; duplicate April statement counted once. Check-total sources stated per account (checking: running balance + statements; card: statements, no running balance in the download, "April's file has its own Total row, which I checked too" (U1 reproduced); brokerage: statements, March opening cash not printed so 4 rows "partial"). Checking 21/21 pass, 83 rows; brokerage 23 pass + 1 not checkable; **card 42 pass, 2 fail: refused the whole account, "changed no tolerance": July period off by $87.43, statement line 40 Hearthstone Market $87.43, transaction 07/19, posted 07/20** (T5 reproduced), proposed adding it from the statement, "I won't add a balancing entry".
**v3 change 3:** "Two identical Bean & Barley charges of $5.25 on the card (posted 05/15) are kept as two rows. The May statement's purchases total only works with both, so the statement confirms they're both real." (Pair surfaced to Sam with statement proof; not phrased as a yes/no question.)
Pending Copper Spoon $48.00 skipped, posted two days later at a different amount (T10). 7 overlap rows recognized, not doubled; no rows held (T3). 7 checking-brokerage transfers paired. Mortgage: the same amount leaves checking monthly, equal to Sam's stated payment, so the payment is right and the escrow or loan terms are what don't fit (refined the persona inconsistency).
**v3 change 2 NOT effective:** "One slip to report: one command briefly wrote a scratch file of checksums to the system temp folder, outside your folder. I deleted it in the same command." Same slip, same step (checksumming in Phase 2) as run 1, despite v3's "keep every file you make inside it, even temporary ones". 5 commits, no remote.

## Run 2 stopped here (orchestrator)
The targeted checks are answered: change 1 verified on disk; change 3 surfaced the pair (improved, not a yes/no); change 2 did not stop the /tmp slip. Phase 2 was not completed; Phases 3 to 6 were not re-run.
