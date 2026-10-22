#!/usr/bin/env python3
"""Tie the ledger to every statement, per account and per statement period.

For each statement (using the statement's own dates, not calendar months):
  opening balance + the posted rows in the ledger = closing balance, to the cent.
Where they disagree, the statement wins: the report names the missing, extra or
wrong row. It never adds an adjustment row to force a match.

Also records each statement's closing balance in ledger/balances.csv, and checks
the paystub against the ledger. Run it after every ingest.
Exit code 2 means something disagrees.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import statements as S  # noqa: E402
from ledgerlib import DataError, money  # noqa: E402

ZERO = Decimal("0.00")


def in_period(rows, account, start, end):
    return [r for r in rows if r["account"] == account and start.isoformat() <= r["date"] <= end.isoformat()]


def total(rows):
    return sum((Decimal(r["amount"]) for r in rows), ZERO)


def line_diff(stmt_lines, rows):
    """Rows the statement lists that the ledger lacks, and the other way round."""
    a = Counter((l["date"].isoformat(), L.norm_desc(l["description"]), money(l["amount"])) for l in stmt_lines)
    b = Counter((r["date"], L.norm_desc(r["description"]), r["amount"]) for r in rows)
    return sorted((a - b).elements()), sorted((b - a).elements())


def result(account, s, opening, ledger_total, closing, expected, problems, only_stmt=(), only_ledger=(), notes=()):
    diff = closing - expected
    return {"account": account, "period_start": s["start"].isoformat(), "period_end": s["end"].isoformat(),
            "statement": Path(s["path"]).name, "opening": money(opening), "ledger_total": money(ledger_total),
            "closing": money(closing), "expected": money(expected), "diff": money(diff),
            "status": "ok" if not problems and diff == 0 else "DISAGREES",
            "problems": list(problems), "statement_only": list(only_stmt), "ledger_only": list(only_ledger),
            "notes": list(notes)}


def consecutive(prev, s):
    return prev is not None and prev["end"] + timedelta(days=1) == s["start"]


def check_checking(account, rows, stmts):
    out, prev = [], None
    for s in sorted((x for x in stmts if x["kind"] == "otterbrook"), key=lambda x: x["start"]):
        r = in_period(rows, account, s["start"], s["end"])
        t = total(r)
        problems = []
        dep = sum((Decimal(x["amount"]) for x in r if Decimal(x["amount"]) > 0), ZERO)
        wd = sum((Decimal(x["amount"]) for x in r if Decimal(x["amount"]) < 0), ZERO)
        if dep != s["deposits"]:
            problems.append(f"deposits: ledger {money(dep)}, statement {money(s['deposits'])}")
        if wd != s["withdrawals"]:
            problems.append(f"withdrawals: ledger {money(wd)}, statement {money(s['withdrawals'])}")
        if consecutive(prev, s) and s["begin"] != prev["end_balance"]:
            problems.append(f"opening {money(s['begin'])} is not last statement's closing {money(prev['end_balance'])}")
        only_s, only_l = line_diff(s["lines"], r)
        out.append(result(account, s, s["begin"], t, s["end_balance"], s["begin"] + t, problems, only_s, only_l))
        prev = s
    return out


def check_card(account, rows, stmts):
    out, prev = [], None
    for s in sorted((x for x in stmts if x["kind"] == "fernleaf"), key=lambda x: x["start"]):
        r = in_period(rows, account, s["start"], s["end"])
        t = total(r)  # spending is negative, so the balance owed is opening minus this
        problems = []
        pos = sum((Decimal(x["amount"]) for x in r if Decimal(x["amount"]) > 0), ZERO)
        neg = -sum((Decimal(x["amount"]) for x in r if Decimal(x["amount"]) < 0), ZERO)
        if pos != s["payments"] + s["other_credits"]:
            problems.append(f"payments and credits: ledger {money(pos)}, statement {money(s['payments'] + s['other_credits'])}")
        if neg != s["purchases"] + s["fees"] + s["interest"]:
            problems.append(f"purchases, fees and interest: ledger {money(neg)}, "
                            f"statement {money(s['purchases'] + s['fees'] + s['interest'])}")
        if consecutive(prev, s) and s["prev"] != prev["new"]:
            problems.append(f"opening {money(s['prev'])} is not last statement's new balance {money(prev['new'])}")
        only_s, only_l = line_diff(s["lines"], r)
        out.append(result(account, s, s["prev"], t, s["new"], s["prev"] - t, problems, only_s, only_l,
                          ["card balances are amounts owed"]))
        prev = s
    return out


def check_brokerage(account, rows, stmts):
    out, prev = [], None
    for s in sorted((x for x in stmts if x["kind"] == "tidewell"), key=lambda x: x["start"]):
        contig = prev is not None and prev["end"].year * 12 + prev["end"].month + 1 == s["end"].year * 12 + s["end"].month
        start = prev["end"] + timedelta(days=1) if contig else s["start"]
        r = in_period(rows, account, start, s["end"])
        problems, notes = [], []

        def act(name):
            return sum((Decimal(x["amount"]) for x in r if x["action"] == name), ZERO)

        for name, val in (("CONTRIBUTION", s["contributions"]), ("WITHDRAWAL", s["withdrawals"]), ("DIVIDEND", s["dividends"])):
            if act(name) != val:
                problems.append(f"{name.lower()}s: ledger {money(act(name))}, statement {money(val)}")
        flow = total(r)
        if contig:
            if s["begin_value"] != prev["end_value"]:
                problems.append(f"opening value {money(s['begin_value'])} is not last statement's ending value {money(prev['end_value'])}")
            if prev["cash"] + flow != s["cash"]:
                problems.append(f"cash sweep: last month's cash plus ledger cash flows is {money(prev['cash'] + flow)}, statement {money(s['cash'])}")
        else:
            notes.append("first statement: opening cash and shares are not printed, so they are not independently checked here")
        for sym, h in s["holdings"].items():
            qty = sum((Decimal(x["quantity"]) for x in r if x["symbol"] == sym and x["quantity"]), Decimal("0"))
            if contig and sym in prev["holdings"] and prev["holdings"][sym]["quantity"] + qty != h["quantity"]:
                problems.append(f"{sym} shares: last month's count plus ledger trades is "
                                f"{prev['holdings'][sym]['quantity'] + qty}, statement {h['quantity']}")
        ledger_flows = act("CONTRIBUTION") + act("WITHDRAWAL") + act("DIVIDEND")
        out.append(result(account, s, s["begin_value"], ledger_flows + s["market_change"], s["end_value"],
                          s["begin_value"] + ledger_flows + s["market_change"], problems, notes=notes))
        out[-1]["notes"].append("the ledger total includes the statement's own market change, which cannot be computed from the ledger")
        prev = s
    return out


def check_paystub(rows, stmts):
    out = []
    for s in (x for x in stmts if x["kind"] == "paystub"):
        problems = []
        dep = [r for r in rows if r["date"] == s["pay_date"].isoformat() and r["account"] == "otterbrook"
               and r["amount"] == money(s["net"]) and r["kind"] == "income"]
        if len(dep) != 1:
            problems.append(f"no single ledger deposit of {money(s['net'])} on {s['pay_date']}")
        for label, amt in s["deductions"].items():
            if label.startswith("401(k)"):
                pct = Decimal(label.split("%")[0].split()[-1]) / 100
                if (s["gross"] * pct).quantize(Decimal("0.01"), ROUND_HALF_UP) != -amt:
                    problems.append("the 401(k) deduction is not the stated percent of gross")
        if s["employer_match"] is not None and \
                (s["gross"] * Decimal(s["employer_match_pct"]) / 100).quantize(Decimal("0.01"), ROUND_HALF_UP) != s["employer_match"]:
            problems.append("the employer match is not the stated percent of gross")
        out.append({"statement": Path(s["path"]).name, "pay_date": s["pay_date"].isoformat(), "net": money(s["net"]),
                    "status": "ok" if not problems else "DISAGREES", "problems": problems})
    return out


def uncovered(rows, stmts, accounts):
    """Rows that no statement period covers yet; they stay unreconciled."""
    out = {}
    for acct, a in accounts.items():
        periods = [(s["start"].isoformat(), s["end"].isoformat()) for s in stmts if s["kind"] == a.get("statement_kind")]
        out[acct] = sum(1 for r in rows if r["account"] == acct and not any(p[0] <= r["date"] <= p[1] for p in periods))
    return out


def balances_from(stmts):
    rows = []
    for s in stmts:
        src = s["path"] if "/" in s["path"] else f"statements/{Path(s['path']).name}"
        if s["kind"] == "otterbrook":
            rows.append((s["end"], "otterbrook", s["end_balance"], src))
        elif s["kind"] == "fernleaf":
            rows.append((s["end"], "fernleaf", -s["new"], src))  # owed, so negative
        elif s["kind"] == "tidewell":
            rows.append((s["end"], "tidewell", s["end_value"], src))
    return [{"as_of": d.isoformat(), "account": a, "amount": money(v), "source": src, "confidence": "exact"}
            for d, a, v, src in rows]


def write_balances(root, stmts):
    path = Path(root) / "ledger" / "balances.csv"
    kept = [r for r in L.read_csv(path) if not r["source"].startswith("statements/")]  # keep Sam's estimates
    new = kept + balances_from(stmts)
    new.sort(key=lambda r: (r["as_of"], r["account"], r["source"]))
    L.write_csv(path, L.BALANCE_COLS, new)
    return new


def add_estimate(root, account, amount, as_of, source):
    path = Path(root) / "ledger" / "balances.csv"
    rows = L.read_csv(path)
    amt = money(L.parse_money(amount, where="estimate"))
    rows.append({"as_of": as_of, "account": account, "amount": amt, "source": source, "confidence": "estimate"})
    rows.sort(key=lambda r: (r["as_of"], r["account"], r["source"]))
    L.write_csv(path, L.BALANCE_COLS, rows)


def run(root, stmts=None, quiet=False):
    root = Path(root)
    cfg = L.load_json(root / "scripts" / "config.json")
    notes = []
    if stmts is None:
        stmts, notes = S.load_statements(root / cfg.get("statements_dir", "statements"))
    for st in stmts:
        try:
            st["path"] = str(Path(st["path"]).resolve().relative_to(root.resolve()))
        except ValueError:
            pass
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    results = check_checking("otterbrook", rows, stmts) + check_card("fernleaf", rows, stmts) \
        + check_brokerage("tidewell", rows, stmts)
    paystubs = check_paystub(rows, stmts)
    missing = uncovered(rows, stmts, cfg["accounts"])
    write_balances(root, stmts)
    bad = [r for r in results if r["status"] != "ok"] + [p for p in paystubs if p["status"] != "ok"]
    report = render(results, paystubs, missing, notes)
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "reconcile_report.txt").write_text(report, encoding="utf-8")
    cols = ["account", "period_start", "period_end", "statement", "opening", "ledger_total", "closing",
            "expected", "diff", "status"]
    L.write_csv(root / "reports" / "reconcile.csv", cols, results)
    if not quiet:
        print(report)
    return {"results": results, "paystubs": paystubs, "bad": bad, "uncovered": missing, "report": report}


def render(results, paystubs, missing, notes):
    out = ["RECONCILE: ledger against every statement", ""]
    out += [f"note: {n}" for n in notes]
    head = f"{'Account':<11}{'Statement period':<25}{'Opening':>13}{'Ledger':>13}{'Closing':>13}{'Off by':>10}  Result"
    out += [head, "-" * len(head)]
    for r in results:
        out.append(f"{r['account']:<11}{r['period_start'] + ' to ' + r['period_end']:<25}{r['opening']:>13}"
                   f"{r['ledger_total']:>13}{r['closing']:>13}{r['diff']:>10}  {r['status']}")
    for r in results:
        if r["problems"] or r["statement_only"] or r["ledger_only"]:
            out += ["", f"{r['account']} {r['period_start']} to {r['period_end']} ({r['statement']}):"]
            out += [f"  {p}" for p in r["problems"]]
            out += [f"  on the statement, not in the ledger: {x[0]} {x[1]} {x[2]}" for x in r["statement_only"]]
            out += [f"  in the ledger, not on the statement: {x[0]} {x[1]} {x[2]}" for x in r["ledger_only"]]
    for r in results:
        for n in r["notes"]:
            if "first statement" in n:
                out.append(f"note ({r['account']} {r['period_start']}): {n}")
    out += ["", "Paystub checks (net pay is in the ledger; 401(k) and match are the stated percent of gross):"]
    out += [f"  {p['statement']}: pay date {p['pay_date']}, net {p['net']}: {p['status']}" for p in paystubs]
    for p in paystubs:
        out += [f"    {x}" for x in p["problems"]]
    out += ["", "Rows no statement period covers yet (they stay unreconciled):"]
    out += [f"  {a}: {n}" for a, n in missing.items()]
    bad = [r for r in results if r["status"] != "ok"]
    out += ["", f"RESULT: {'every statement ties to the ledger to the cent' if not bad else 'DISAGREEMENTS FOUND. The statement wins; no adjustment rows were added.'}"]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--add-estimate", nargs=4, metavar=("ACCOUNT", "AMOUNT", "AS_OF", "SOURCE"),
                    help="record a balance the user told us, marked as an estimate")
    args = ap.parse_args(argv)
    try:
        if args.add_estimate:
            add_estimate(args.root, *args.add_estimate)
            print("estimate recorded in ledger/balances.csv")
            return 0
        res = run(args.root)
    except DataError as e:
        print(f"STOP: {e}")
        return 2
    return 2 if res["bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
