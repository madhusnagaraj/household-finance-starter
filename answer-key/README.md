# Answer key: don't copy this into your practice folder

This is how the test was scored. If Claude can see these files, it reads the answers instead of finding the problems.

- `traps.md`: the 16 planted problems, in three groups (named in the prompt, added after review, never named), with what a pass looks like.
- `truth/`: the true transactions and balances the practice files were generated from.
- `make_fixture.py` and `test_make_fixture.py`: the generator for the practice files (fixed seed, so it rebuilds them byte for byte) and its checks.
- `score_run.py`: compares a finished ledger against `truth/`.
