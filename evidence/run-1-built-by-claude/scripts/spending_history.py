#!/usr/bin/env python3
"""What each ledger category looked like in the complete months, to help Sam set plan amounts.

Only months where every account is fully covered are used. Spending shows as a plus number;
refunds reduce it. The numbers are history, not a recommendation. Sam sets the plan.
"""
import argparse
import calendar
import sys
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
from ledgerlib import money  # noqa: E402

ZERO = Decimal("0.00")


def complete_months(rows, coverage):
    months = sorted({r["date"][:7] for r in rows})
    out = []
    for m in months:
        y, mo = int(m[:4]), int(m[5:])
        first, last = date(y, mo, 1).isoformat(), date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()
        if all(f <= first and t >= last for f, t in coverage.values()):
            out.append(m)
    return out


def history(rows, months):
    per = defaultdict(lambda: defaultdict(lambda: ZERO))
    kind_of = {}
    for r in rows:
        if r["date"][:7] in months and r["kind"] in ("spend", "loan", "income", "transfer") and r["category"]:
            sign = 1 if r["kind"] == "income" else -1
            per[r["category"]][r["date"][:7]] += sign * Decimal(r["amount"])
            kind_of[r["category"]] = r["kind"]
    out = []
    for cat, by in per.items():
        vals = [by.get(m, ZERO) for m in months]
        if kind_of[cat] == "transfer" and not cat.startswith("Savings"):
            continue  # card payments and the like are not a household cost
        out.append({"category": cat, "kind": kind_of[cat], "months": months,
                    "by_month": {m: by.get(m, ZERO) for m in months},
                    "average": (sum(vals, ZERO) / len(vals)).quantize(Decimal("0.01")),
                    "low": min(vals), "high": max(vals)})
    return sorted(out, key=lambda x: (x["kind"] != "income", -x["average"]))


def six_month_average(rows, coverage, categories, months=6):
    """Average per month over each account's checked window (about six months), spending as a plus number.

    A category's rows are counted inside the window of the account that holds them, so the card's
    last partial month is not undercounted and checking's full months are used in full.
    """
    total = ZERO
    for r in rows:
        if r["category"] in categories and r["account"] in coverage:
            f, t = coverage[r["account"]]
            if f <= r["date"] <= t and r["kind"] in ("spend", "loan", "income"):
                total += (Decimal(r["amount"]) if r["kind"] == "income" else -Decimal(r["amount"]))
    return (total / months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    coverage = {c["account"]: (c["covered_from"], c["covered_to"]) for c in L.read_csv(root / "ledger" / "coverage.csv")}
    months = complete_months(rows, coverage)
    if not months:
        print("No complete months yet.")
        return 2
    h = history(rows, months)
    print(f"Complete months used: {', '.join(months)}\n")
    head = f"{'Category':<26}{'Kind':<9}" + "".join(f"{m[5:]:>11}" for m in months) + f"{'Average':>11}{'Low':>10}{'High':>10}"
    print(head)
    print("-" * len(head))
    for x in h:
        print(f"{x['category']:<26}{x['kind']:<9}" + "".join(f"{x['by_month'][m]:>11,.2f}" for m in months)
              + f"{x['average']:>11,.2f}{x['low']:>10,.2f}{x['high']:>10,.2f}")
    (root / "reports").mkdir(exist_ok=True)
    cols = ["category", "kind"] + months + ["average", "low", "high"]
    L.write_csv(root / "reports" / "spending_history.csv", cols,
                [dict({"category": x["category"], "kind": x["kind"], "average": money(x["average"]),
                       "low": money(x["low"]), "high": money(x["high"])},
                      **{m: money(x["by_month"][m]) for m in months}) for x in h])
    return 0


if __name__ == "__main__":
    sys.exit(main())
