#!/usr/bin/env python3
"""List the ledger rows that no rule has sorted yet, grouped by payee.

For Sam to answer: say what each payee is, and I add a rule to ledger/rules.csv.
The bank's own label is shown as a hint only; it is not a decision.
"""
import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402


def group(rows):
    g = defaultdict(lambda: {"rows": 0, "total": Decimal("0.00"), "first": "9999", "last": "", "labels": set()})
    for r in rows:
        if r["kind"] != "unclassified":
            continue
        k = (r["account"], r["description"].strip())
        x = g[k]
        x["rows"] += 1
        x["total"] += Decimal(r["amount"])
        x["first"], x["last"] = min(x["first"], r["date"]), max(x["last"], r["date"])
        if r["bank_category"]:
            x["labels"].add(r["bank_category"])
    return sorted(g.items(), key=lambda kv: (kv[0][0], kv[0][1]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    root = Path(args.root)
    groups = group(L.read_csv(root / "ledger" / "transactions.csv"))
    out_rows = [{"account": a, "payee": d, "rows": x["rows"], "total": L.money(x["total"]),
                 "first": x["first"], "last": x["last"], "bank_label": ";".join(sorted(x["labels"]))}
                for (a, d), x in groups]
    (root / "reports").mkdir(exist_ok=True)
    L.write_csv(root / "reports" / "unsorted_rows.csv",
                ["account", "payee", "rows", "total", "first", "last", "bank_label"], out_rows)
    if not out_rows:
        print("Every row has a rule.")
        return 0
    print(f"{'Account':<11}{'Payee':<36}{'Rows':>5}{'Total':>11}  {'Dates':<27}Bank's label")
    for r in out_rows:
        print(f"{r['account']:<11}{r['payee'][:35]:<36}{r['rows']:>5}{r['total']:>11}  "
              f"{r['first'] + ' to ' + r['last']:<27}{r['bank_label']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
