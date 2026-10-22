#!/usr/bin/env python3
"""Net worth from the latest balance of every account in ledger/balances.csv.

Assets are plus, amounts owed are minus. Each row says where it came from and how sure we are:
exact (a statement) or estimate (what Sam told us, until a statement replaces it). Dates differ
between accounts, and the total says so. Every number comes from balances.csv.
"""
import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
from ledgerlib import money  # noqa: E402


def latest(rows):
    best = {}
    for r in rows:
        k = r["account"]
        if k not in best or (r["as_of"], r["confidence"] == "exact") > (best[k]["as_of"], best[k]["confidence"] == "exact"):
            best[k] = r
    return sorted(best.values(), key=lambda r: -Decimal(r["amount"]))


def summarize(rows):
    rows = latest(rows)
    total = sum((Decimal(r["amount"]) for r in rows), Decimal("0.00"))
    est = sum((Decimal(r["amount"]) for r in rows if r["confidence"] != "exact"), Decimal("0.00"))
    return rows, total, est


def render(rows, total, est, today):
    out = [f"{'Account':<22}{'Balance':>14}  {'As of':<12}{'Confidence':<12}Source", "-" * 100]
    for r in rows:
        out.append(f"{r['account']:<22}{Decimal(r['amount']):>14,.2f}  {r['as_of']:<12}{r['confidence']:<12}{r['source'][:50]}")
    ages = [(today - date.fromisoformat(r["as_of"])).days for r in rows if r["confidence"] == "exact"]
    out += ["", f"Net worth {total:,.2f}, of which {est:,.2f} rests on estimates Sam gave from memory (no statement yet).",
            "Accounts are as of different dates, so this is a snapshot, not a single-day figure."]
    if ages and max(ages) > 45:
        out.append(f"Statement-based balances are up to {max(ages)} days old: add newer statements.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    rows, total, est = summarize(L.read_csv(root / "ledger" / "balances.csv"))
    if not rows:
        print("No balances recorded yet; run scripts/reconcile.py.")
        return 2
    print(render(rows, total, est, date.today()))
    (root / "reports").mkdir(exist_ok=True)
    L.write_csv(root / "reports" / "networth.csv", ["account", "amount", "as_of", "confidence", "source"],
                [{k: r[k] for k in ("account", "amount", "as_of", "confidence", "source")} for r in rows]
                + [{"account": "TOTAL", "amount": money(total), "as_of": "", "confidence": "", "source": "sum of the rows above"}])
    return 0


if __name__ == "__main__":
    sys.exit(main())
