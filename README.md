# household-finance-starter

A copy-paste prompt for building a personal finance manager with Claude: one folder of plain files where every number traces back to a statement. Plus a made-up household to practice on, and the evidence from testing the prompt before it was published.

Companion to the post **How to Build a Personal Finance Manager With Claude** on [madhunagaraj.com](https://www.madhunagaraj.com).

## Start here

1. **Practice first.** Make a new, empty folder. Copy in only `practice-household/statements/` and `practice-household/downloads/`. Keep `practice-household/ANSWERS.md` open beside you, not in the folder.
2. **Open the folder in Claude** (the Code tab in Claude's desktop app, or a Cowork task) and turn memory off before you start.
3. **Paste the prompt** from [`prompt/starter-prompt.md`](prompt/starter-prompt.md) as your first message, and answer the interview as the made-up household.
4. **Then do yours** in another new, empty folder, with your own statements.

## What's in here

| Folder | What it is | Copy it into your folder? |
|---|---|---|
| `prompt/` | The starter prompt (v3) and the changelog of every version | Paste the prompt; don't copy the folder |
| `practice-household/` | Statements and bank downloads for the made-up Ellery household, and the interview answers | Only `statements/` and `downloads/` |
| `answer-key/` | The planted problems and the true numbers, used to score the test | **No.** Claude would read the answers |
| `evidence/` | How the prompt was tested, what it caught and missed, and the files Claude built | No |

## Privacy, in short

Whatever Claude reads is sent to Anthropic's model, in both Claude Code and Cowork. Claude Code keeps the folder and scripts on your computer; Cowork (Pro and Max, since October 6, 2026) runs in the cloud, and Anthropic's own Cowork safety page advises against giving it financial documents. Turn memory off, check your model training setting, and use a folder that holds nothing else. If that settles it, use only the practice household.

## How it was tested

v2 of the prompt ran once, in a Claude Code test session, on the made-up household with 16 planted problems. It caught 7 of the 8 problems the prompt names (the eighth came out right but silently), all 4 named by rules added after review, and all 4 it was never told about. One household, one run, a scripted user, isolation by instructions rather than an operating system sandbox: details and limits in [`evidence/`](evidence/). A second, shorter run re-tested v3's fixes; one of them ("keep every file inside the folder") did not stop the model writing a scratch file outside it, which is why Claude Code's Manual mode matters.

*Not financial advice. The prompt asks Claude for frameworks, facts and trade-offs; the decisions about your money stay yours.*

MIT licensed. The views expressed here are my own and are not related to or reflective of my work or any organization I am affiliated with.
