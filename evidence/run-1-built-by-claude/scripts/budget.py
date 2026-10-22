#!/usr/bin/env python3
"""Month to date against Sam's plan. Runs `plan.py --check` first and stops if the plan is wrong.

Per plan line: ok / watch / over / not posted.
  A set bill (fixed = 1): ok if what posted is within the plan, over if above, not posted if nothing yet.
  A line Sam controls (fixed = 0): ok if at or under the pace line (plan x days gone / days in month),
    watch if above the pace line but within the plan, over if above the plan, not posted if nothing yet.
Flex pool = income - committed - lumpy set-asides - savings (all from the plan).
Flex spent = spending in categories that no plan line claims. Flex left = pool - flex spent.
Cushion on the current pace = income - (set bills at plan, the other committed lines at pace,
  lumpy and savings at plan, flex at pace). Also shows what is on the card (next month's cash)
  against what came straight from the bank. Every number comes from the plan and the ledger.
"""
import argparse
import calendar
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import plan as P  # noqa: E402
from ledgerlib import money  # noqa: E402

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def q(x):
    return Decimal(x).quantize(CENT)


def compute(res, rows, month, as_of, card_accounts):
    """res: result of plan.check. rows: ledger rows. Returns everything budget.py prints."""
    y, m = int(month[:4]), int(month[5:])
    dim = calendar.monthrange(y, m)[1]
    day = as_of.day
    frac = Decimal(day) / Decimal(dim)
    cat_line = {x["category"]: x["line"] for x in res["map"]}
    by_line, oneoff, flex_cats = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    card_total, bank_total, unplanned_loan, unplanned_income = ZERO, ZERO, ZERO, ZERO
    for r in rows:
        if not (r["date"][:7] == month and r["date"] <= as_of.isoformat()) or r["kind"] in ("unclassified", "invest"):
            continue
        amt, cat, kind = Decimal(r["amount"]), r["category"], r["kind"]
        line = cat_line.get(cat)
        if kind in ("spend", "loan") and line != P.ONE_OFF:
            if r["account"] in card_accounts:
                card_total += -amt
            else:
                bank_total += -amt
        if line == P.ONE_OFF:
            oneoff[cat] += -amt
        elif line:
            by_line[line] += -amt
        elif kind == "spend":
            flex_cats[cat] += -amt
        elif kind == "loan":
            unplanned_loan += -amt
        elif kind == "income":
            unplanned_income += amt
    lines, income_plan, extra_income = [], ZERO, []
    committed_proj = lumpy_plan = savings_plan = ZERO
    for p in res["plan"]:
        plan_amt = abs(p["amount"])
        if p["block"] == "income":
            posted = -by_line.get(p["line"], ZERO)
            income_plan += plan_amt
            status = "not posted" if posted == 0 else ("ok" if posted >= plan_amt else "partly posted")
            if posted > plan_amt:
                extra_income.append({"line": p["line"], "extra": posted - plan_amt, "note": p["note"]})
            lines.append({**p, "plan": plan_amt, "spent": posted, "pace": None, "status": status, "projected": plan_amt})
            continue
        spent = by_line.get(p["line"], ZERO)
        pace = q(plan_amt * frac)
        if spent == 0:
            status = "not posted"
        elif p["fixed"] == 1 or p["block"] != "committed":
            status = "ok" if spent <= plan_amt else "over"
        else:
            status = "ok" if spent <= pace else ("watch" if spent <= plan_amt else "over")
        if p["block"] == "committed":
            projected = plan_amt if p["fixed"] == 1 else q(spent / frac)
            committed_proj += projected
        else:
            projected = plan_amt
            if p["block"] == "lumpy":
                lumpy_plan += plan_amt
            else:
                savings_plan += plan_amt
        lines.append({**p, "plan": plan_amt, "spent": spent, "pace": pace, "status": status, "projected": projected})
    committed_plan = sum((l["plan"] for l in lines if l["block"] == "committed"), ZERO)
    flex_pool = income_plan - committed_plan - lumpy_plan - savings_plan
    flex_spent = sum(flex_cats.values(), ZERO)
    flex_proj = q(flex_spent / frac)
    cushion = income_plan - committed_proj - lumpy_plan - savings_plan - flex_proj
    return {"month": month, "as_of": as_of, "day": day, "dim": dim, "lines": lines, "flex_pool": flex_pool,
            "flex_spent": flex_spent, "flex_left": flex_pool - flex_spent, "flex_cats": dict(flex_cats),
            "flex_projected": flex_proj, "cushion": cushion, "income_plan": income_plan,
            "card": card_total, "bank": bank_total, "oneoff": dict(oneoff), "extra_income": extra_income,
            "unplanned_loan": unplanned_loan, "unplanned_income": unplanned_income}


def render(b):
    def n(x):
        return f"{x:,.2f}"

    out = [f"BUDGET {b['month']}, month to date through {b['as_of']} (day {b['day']} of {b['dim']})", ""]
    head = f"{'Block':<10}{'Line':<32}{'Plan':>11}{'So far':>11}{'Pace':>11}  Status"
    out += [head, "-" * len(head)]
    for l in b["lines"]:
        pace = n(l["pace"]) if l["pace"] is not None else ""
        kind = "set" if l["fixed"] == 1 else ""
        out.append(f"{l['block']:<10}{l['line'][:31]:<32}{n(l['plan']):>11}{n(l['spent']):>11}{pace:>11}  {l['status']} {kind}".rstrip())
    out += ["",
            f"Flex pool (plan)            {n(b['flex_pool']):>12}",
            f"Flex spent so far           {n(b['flex_spent']):>12}   in categories no plan line claims",
            f"Flex left                   {n(b['flex_left']):>12}",
            f"Cushion on current pace     {n(b['cushion']):>12}   (set bills at plan, the rest at pace)",
            "",
            f"On the card (next month's cash) {n(b['card']):>10}",
            f"Straight from the bank          {n(b['bank']):>10}"]
    for x in b["extra_income"]:
        out += ["", f"Income above plan on '{x['line']}': {n(x['extra'])}. The note on that line says: {x['note']}"]
    if b["flex_cats"]:
        out += ["", "Flex spending by category:"] + [f"  {c:<26}{n(v):>11}" for c, v in sorted(b["flex_cats"].items(), key=lambda kv: -kv[1])]
    if b["oneoff"]:
        out += ["", "One-offs kept out of the budget:"] + [f"  {c:<26}{n(v):>11}" for c, v in sorted(b["oneoff"].items())]
    if b["unplanned_loan"]:
        out.append(f"Loan payments outside the plan: {n(b['unplanned_loan'])}")
    if b["unplanned_income"]:
        out.append(f"Income outside the plan: {n(b['unplanned_income'])}")
    return "\n".join(out)


class BudgetError(Exception):
    """The budget cannot be built; the message says why."""


def prepare(root, month=None, as_of_arg=None):
    """Run the plan check, pick the month and date, and compute. Returns (result, plan_check, current_to)."""
    root = Path(root)
    res = P.check(root)
    if res["errors"]:
        raise BudgetError(P.render(res))
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    cov = {c["account"]: c["covered_to"] for c in L.read_csv(root / "ledger" / "coverage.csv")}
    if not cov:
        raise BudgetError("STOP: ledger/coverage.csv is empty; run scripts/ingest.py first.")
    current_to = date.fromisoformat(min(cov.values()))
    month = month or current_to.strftime("%Y-%m")
    y, m = int(month[:4]), int(month[5:])
    month_end = date(y, m, calendar.monthrange(y, m)[1])
    as_of = date.fromisoformat(as_of_arg) if as_of_arg else min(current_to, month_end)
    if as_of < date(y, m, 1):
        raise BudgetError(f"STOP: the ledger is only checked through {current_to}; there is nothing for {month} yet.")
    card_accounts = {a for a, v in res["accounts"].items() if v["liability"]}
    return compute(res, rows, month, as_of, card_accounts), res, current_to


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--month", help="YYYY-MM (default: the month the ledger is current to)")
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: the date every account is checked through)")
    args = ap.parse_args(argv)
    try:
        b, res, current_to = prepare(args.root, args.month, args.as_of)
    except BudgetError as e:
        print(e)
        return 2
    print(render(b))
    if res["warnings"]:
        print("\nHeads-up from the plan check:\n  " + "\n  ".join(res["warnings"]))
    if (date.today() - current_to).days > 7:
        print(f"\nSTALE: the ledger is only checked through {current_to}. Drop fresh downloads into exports/ and run ingest.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
