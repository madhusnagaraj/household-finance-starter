#!/usr/bin/env python3
"""Monthly totals from ledger/transactions.csv (by the date the bank posted each row).

What counts where:
  Income   = pay (kind income). Dividends and sales inside the brokerage are NOT income here.
  Spent    = everyday spending (kind spend), refunds netted off, one-off categories shown apart.
  Mortgage = loan payments (kind loan).
  Moves between our own accounts (card payments, money to and from the brokerage) are left out.
  Unsorted = rows with no rule yet (how many, money in, money out); they are in none of the other columns.
A month is flagged partial if any account's checked coverage does not reach both ends of it.
Every number comes from the ledger; nothing is typed by hand.
"""
import argparse
import calendar
import json
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402

ZERO = Decimal("0.00")
FIELDS = ["income_in", "spent_out", "oneoff_out", "loan_out", "transfers_net", "invest_net",
          "unsorted_rows", "unsorted_in", "unsorted_out", "rows"]


def compute(rows, coverage, one_off):
    """rows: ledger rows (dicts). coverage: {account: (from_iso, to_iso)}. Returns a list of month dicts."""
    by = defaultdict(lambda: {k: ZERO for k in FIELDS})
    for r in rows:
        t, a, kind = by[r["date"][:7]], Decimal(r["amount"]), r["kind"]
        t["rows"] += 1
        if kind == "income":
            t["income_in"] += a
        elif kind == "spend":
            t["oneoff_out" if r["category"] in one_off else "spent_out"] -= a
        elif kind == "loan":
            t["loan_out"] -= a
        elif kind == "transfer":
            t["transfers_net"] += a
        elif kind == "invest":
            t["invest_net"] += a
        else:
            t["unsorted_rows"] += 1
            t["unsorted_in" if a > 0 else "unsorted_out"] += abs(a)
    out = []
    for m in sorted(by):
        y, mo = int(m[:4]), int(m[5:])
        first, last = date(y, mo, 1).isoformat(), date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()
        short = [a for a, (f, t) in coverage.items() if not (f <= first and t >= last)]
        out.append(dict(month=m, partial=short, **by[m]))
    return out


def render(months, coverage):
    def n(d):
        return f"{d:,.2f}"

    head = (f"{'Month':<9}{'Income':>11}{'Spent':>11}{'Remodel':>11}{'Mortgage':>11}"
            f"{'Unsorted':>9}{'in':>11}{'out':>10}  Note")
    lines = [head, "-" * len(head)]
    for m in months:
        note = ("PARTIAL: " + ", ".join(m["partial"]) + " not fully covered") if m["partial"] else ""
        lines.append(f"{m['month']:<9}{n(m['income_in']):>11}{n(m['spent_out']):>11}{n(m['oneoff_out']):>11}"
                     f"{n(m['loan_out']):>11}{int(m['unsorted_rows']):>9}{n(m['unsorted_in']):>11}"
                     f"{n(m['unsorted_out']):>10}  {note}")
    lines += ["", "Coverage the numbers rest on:"]
    lines += [f"  {a}: {f} to {t}" for a, (f, t) in coverage.items()]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    cfg = L.load_json(root / "scripts" / "config.json")
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    coverage = {c["account"]: (c["covered_from"], c["covered_to"]) for c in L.read_csv(root / "ledger" / "coverage.csv")}
    missing = [a for a in cfg["accounts"] if a not in coverage]
    if missing:
        print(f"STOP: no checked coverage for {missing}. Those accounts were not written; fix that first.")
        return 2
    months = compute(rows, coverage, set(cfg.get("one_off_categories", [])))
    (root / "reports").mkdir(exist_ok=True)
    cols = ["month", "partial"] + FIELDS
    L.write_csv(root / "reports" / "monthly_totals.csv", cols,
                [dict(m, partial=";".join(m["partial"]), **{k: (str(int(m[k])) if k in ("unsorted_rows", "rows") else L.money(m[k]))
                                                            for k in FIELDS}) for m in months])
    print(render(months, coverage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
