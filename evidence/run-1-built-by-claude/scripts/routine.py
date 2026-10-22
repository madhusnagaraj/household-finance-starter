#!/usr/bin/env python3
"""Run a routine from MAINTENANCE.md in one command: weekly, monthly or quarterly.

Steps run in order and the run STOPS at the first step that fails; it never skips a failed check.
Each routine starts with Sam dropping fresh downloads into exports/<date>/ (nothing here can log in
to a bank). Every number printed comes from the scripts it runs; this file holds none.

    python3 scripts/routine.py weekly
    python3 scripts/routine.py monthly
    python3 scripts/routine.py quarterly
"""
import argparse
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import ledgerlib as L  # noqa: E402


def prev_month(today):
    first = today.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


def steps_for(routine, today):
    weekly = [("Load the new downloads and check each account", ["ingest.py"]),
              ("Check the plan file", ["plan.py", "--check"]),
              ("Budget, month to date", ["budget.py"]),
              ("Refresh the phone page", ["render_page.py"])]
    monthly = weekly + [("Tie every statement to the ledger, to the cent", ["reconcile.py"]),
                        ("Rows with no rule yet", ["unsorted.py"]),
                        ("Monthly totals", ["monthly.py"]),
                        (f"Month-end review: budget for {prev_month(today)}", ["budget.py", "--month", prev_month(today)])]
    quarterly = monthly + [("Investments: year bridge", ["year_bridge.py"]), ("Net worth", ["networth.py"])]
    return {"weekly": weekly, "monthly": monthly, "quarterly": quarterly}[routine]


def run_steps(steps, runner):
    """Run in order; stop at the first failure. runner(args) -> (exit_code, output)."""
    done = []
    for i, (name, args) in enumerate(steps, start=1):
        code, out = runner(args)
        done.append((i, name, args, code, out))
        if code != 0:
            return done, (i, name, out)
    return done, None


def make_runner(root):
    def runner(args):
        p = subprocess.run([sys.executable, str(Path(root) / "scripts" / args[0]), *args[1:], "--root", str(root)],
                           capture_output=True, text=True, cwd=str(root))
        return p.returncode, (p.stdout + p.stderr).strip()
    return runner


def odd_list(root, today):
    """Things worth a look, read from the files the scripts wrote."""
    root = Path(root)
    odd = []
    cov = [c["covered_to"] for c in L.read_csv(root / "ledger" / "coverage.csv")]
    if cov and (today - date.fromisoformat(min(cov))).days > 7:
        odd.append(f"Out of date: the ledger is only checked through {min(cov)}. Drop fresh downloads into exports/ first.")
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    unsorted = sum(1 for r in rows if r["kind"] == "unclassified")
    if unsorted:
        odd.append(f"{unsorted} ledger rows have no rule yet (run scripts/unsorted.py).")
    held = [h for h in L.read_csv(root / "ledger" / "held.csv") if not h["decision"]]
    if held:
        odd.append(f"{len(held)} possible duplicates are waiting for Sam's answer (ledger/held.csv).")
    report = (root / "reports" / "ingest_report.txt")
    if report.exists() and "Transfers waiting for their other side" in report.read_text():
        odd.append("Some transfers have no other side yet (see reports/ingest_report.txt).")
    try:
        b, _, _ = budget.prepare(root)
        for l in b["lines"]:
            if l["status"] in ("over", "watch"):
                odd.append(f"Budget line '{l['line']}' is {l['status']}.")
    except budget.BudgetError:
        pass
    return odd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("routine", choices=["weekly", "monthly", "quarterly"])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--full", action="store_true", help="print each step's full output, not just its status")
    args = ap.parse_args(argv)
    today = date.today()
    done, failed = run_steps(steps_for(args.routine, today), make_runner(args.root))
    print(f"{args.routine.upper()} ROUTINE, {today}")
    print("Start: fresh downloads from each site go into exports/<today's date>/ (I can't log in for you).\n")
    for i, name, cmd, code, out in done:
        print(f"[{i}] {name}: {'ok' if code == 0 else 'STOPPED'}")
        if args.full or code != 0:
            print("    " + out.replace("\n", "\n    "))
    if failed:
        print(f"\nSTOP at step {failed[0]} ({failed[1]}). Nothing was loosened and the later steps did not run. Tell Sam.")
        return 2
    odd = odd_list(args.root, today)
    print("\nWorth a look:" if odd else "\nNothing odd.")
    print("\n".join(f"  - {o}" for o in odd))
    print("\nFiles to open: reports/budget_phone.html, reports/ingest_report.txt"
          + (", reports/reconcile_report.txt, reports/monthly_totals.csv" if args.routine != "weekly" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
