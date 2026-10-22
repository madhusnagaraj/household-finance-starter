#!/usr/bin/env python3
"""Emergency fund: what "six months of expenses" comes to, under each definition of expenses.

Sam chooses the definition. Two are shown:
  everything   every committed line plus the expected lumpy costs in the plan (not savings)
  essentials   only the lines named in scripts/config.json: "essential_lines" once Sam has chosen,
               otherwise "essential_lines_proposed" (marked as a proposal)
Also shows what is in checking now (it is operating cash for the month's bills too, so this is a
rough guide) and how many months of the plan's monthly set-aside it takes to reach each target.
Frameworks and math, not advice: I am not a licensed financial advisor. Every number is computed.
"""
import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import plan as P  # noqa: E402
from ledgerlib import money  # noqa: E402

ZERO = Decimal("0.00")
MONTHS = 6


def compute(plan, balances, cash_account, essentials, setaside_line="Emergency fund"):
    spend = [p for p in plan if p["block"] in ("committed", "lumpy")]
    everything = sum((abs(p["amount"]) for p in spend), ZERO)
    names = {p["line"] for p in plan}
    missing = [n for n in essentials if n not in names]
    ess = sum((abs(p["amount"]) for p in spend if p["line"] in essentials), ZERO)
    cash = next((Decimal(b["amount"]) for b in sorted(balances, key=lambda b: b["as_of"], reverse=True)
                 if b["account"] == cash_account), None)
    cash_as_of = next((b["as_of"] for b in sorted(balances, key=lambda b: b["as_of"], reverse=True)
                       if b["account"] == cash_account), "")
    setaside = next((abs(p["amount"]) for p in plan if p["line"] == setaside_line), ZERO)
    rows = []
    for name, monthly in (("everything", everything), ("essentials", ess)):
        target = monthly * MONTHS
        rows.append({"definition": name, "monthly": monthly, "target": target,
                     "checking_covers": (cash / monthly) if cash is not None and monthly else None,
                     "months_of_setaside": (target / setaside) if setaside else None})
    return {"rows": rows, "cash": cash, "cash_as_of": cash_as_of, "setaside": setaside, "missing": missing}


def render(res, proposed):
    out = [f"{'Definition':<12}{'Monthly':>12}{'6 months':>13}{'Checking covers':>20}{'Set-aside months to reach it':>32}", "-" * 89]
    for r in res["rows"]:
        cov = f"{r['checking_covers']:.1f} months" if r["checking_covers"] is not None else "-"
        sa = f"{r['months_of_setaside']:.1f}" if r["months_of_setaside"] is not None else "-"
        out.append(f"{r['definition']:<12}{money(r['monthly']):>12}{money(r['target']):>13}{cov:>20}{sa:>32}")
    out += ["", f"Checking balance used: {money(res['cash'])} as of {res['cash_as_of']} (statement). It also pays the month's bills.",
            f"The plan sets aside {money(res['setaside'])} a month for the emergency fund; extra paychecks go to it too."]
    if proposed:
        out.append("The essentials list is MY PROPOSAL, not yet Sam's choice (config key essential_lines_proposed).")
    if res["missing"]:
        out.append(f"STOP: essentials names lines the plan does not have: {res['missing']}")
    out.append("The brokerage is invested money, not cash: it can fall in value and selling it can create a tax bill. Not advice.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    cfg = L.load_json(root / "scripts" / "config.json")
    chk = P.check(root)
    if chk["errors"]:
        print(P.render(chk))
        return 2
    chosen = cfg.get("essential_lines")
    lines = chosen if chosen else cfg.get("essential_lines_proposed", [])
    res = compute(chk["plan"], L.read_csv(root / "ledger" / "balances.csv"), "otterbrook", lines)
    print(render(res, not chosen))
    return 2 if res["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
