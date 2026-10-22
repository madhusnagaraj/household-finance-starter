#!/usr/bin/env python3
"""Year bridge for investment accounts: start, money in, money out, market change, end.

Money in and out is ONLY money crossing the account's edge (contributions and
withdrawals). Dividends, interest, fees, buys, sells and reinvestments are inside
the account, so they belong to market change. That way money Sam moved is never
mistaken for money the market lost.

Every number comes from the statements and the ledger. The "what the market did"
check compares the account's price change each month with the price change of the
fund it holds, using the share prices printed on the statements themselves.
Thresholds are fixed here, before looking at results:
  a month is flagged if the two differ by more than 0.50 percentage points,
  a year if they differ by more than 1.00 percentage point cumulatively.
Both figures are estimates (month-end prices, flows weighted by day).
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import statements as S  # noqa: E402
from ledgerlib import DataError, money  # noqa: E402

ZERO = Decimal("0.00")
MONTH_FLAG_PP = Decimal("0.50")
YEAR_FLAG_PP = Decimal("1.00")


def pct(x):
    return (x * 100).quantize(Decimal("0.01"))


def months_for(account, rows, stmts):
    out, prev = [], None
    for s in sorted((x for x in stmts if x["kind"] == "tidewell"), key=lambda x: x["start"]):
        contig = prev is not None and prev["end"].year * 12 + prev["end"].month + 1 == s["end"].year * 12 + s["end"].month
        start = prev["end"] + timedelta(days=1) if contig else s["start"]
        days = (s["end"] - start).days + 1
        flows = [r for r in rows if r["account"] == account and r["action"] in ("CONTRIBUTION", "WITHDRAWAL")
                 and start.isoformat() <= r["date"] <= s["end"].isoformat()]
        weighted = ZERO
        for r in flows:
            t = (date.fromisoformat(r["date"]) - start).days
            weighted += Decimal(r["amount"]) * Decimal(days - t) / Decimal(days)
        base = s["begin_value"] + weighted
        acct_ret = s["market_change"] / base if base else None
        sym = next(iter(s["holdings"]), None)
        fund_ret = None
        if contig and sym and sym in prev["holdings"]:
            fund_ret = s["holdings"][sym]["price"] / prev["holdings"][sym]["price"] - 1
        diff_pp = abs(pct(acct_ret) - pct(fund_ret)) if acct_ret is not None and fund_ret is not None else None
        out.append({"statement": s, "start": start, "contig": contig, "base": base,
                    "in": s["contributions"], "out": s["withdrawals"],
                    "market_change": s["market_change"] + s["dividends"],  # dividends are inside the account
                    "price_effect": s["market_change"], "dividends": s["dividends"],
                    "acct_ret": acct_ret, "fund_ret": fund_ret, "diff_pp": diff_pp,
                    "flag": diff_pp is not None and diff_pp > MONTH_FLAG_PP, "symbol": sym})
        prev = s
    return out


def build(account, rows, stmts):
    months = months_for(account, rows, stmts)
    by_year = defaultdict(list)
    for m in months:
        by_year[m["statement"]["end"].year].append(m)
    years = []
    for year, ms in sorted(by_year.items()):
        start_v, end_v = ms[0]["statement"]["begin_value"], ms[-1]["statement"]["end_value"]
        money_in = sum((m["in"] for m in ms), ZERO)
        money_out = sum((m["out"] for m in ms), ZERO)
        mc = sum((m["market_change"] for m in ms), ZERO)
        chain_ok = all(a["statement"]["end_value"] == b["statement"]["begin_value"] for a, b in zip(ms, ms[1:]))
        # where money went when it left: the other side of each withdrawal in the ledger
        by_id = {r["id"]: r for r in rows}
        dest = defaultdict(lambda: ZERO)
        for r in rows:
            if r["account"] == account and r["action"] == "WITHDRAWAL" and str(year) == r["date"][:4]:
                other = by_id.get(r["pair_id"])
                dest[other["account"] if other else "unknown"] += -Decimal(r["amount"])
        acct_cum, fund_cum, n = Decimal(1), Decimal(1), 0
        for m in ms:
            if m["acct_ret"] is not None and m["fund_ret"] is not None:
                acct_cum *= 1 + m["acct_ret"]
                fund_cum *= 1 + m["fund_ret"]
                n += 1
        cum_diff = abs(pct(acct_cum - 1) - pct(fund_cum - 1)) if n else None
        years.append({
            "account": account, "year": year, "from": ms[0]["start"].isoformat(), "to": ms[-1]["statement"]["end"].isoformat(),
            "start_value": start_v, "money_in": money_in, "money_out": money_out,
            "money_out_to": "; ".join(f"{a}: {money(v)}" for a, v in sorted(dest.items())) or "none",
            "market_change": mc, "end_value": end_v,
            "bridge_check": end_v - (start_v + money_in + money_out + mc),
            "statements_chain": chain_ok, "months_compared": n,
            "acct_price_return_pct": pct(acct_cum - 1) if n else None,
            "fund_price_return_pct": pct(fund_cum - 1) if n else None,
            "cumulative_gap_pp": cum_diff,
            "flag": ("CHECK" if (cum_diff is not None and cum_diff > YEAR_FLAG_PP) or any(m["flag"] for m in ms) else "ok"),
            "note": ("partial year: statements cover " + ms[0]["start"].isoformat() + " to " + ms[-1]["statement"]["end"].isoformat()
                     if not (ms[0]["start"].month == 1 and ms[-1]["statement"]["end"].month == 12) else "full year"),
        })
    return months, years


def render(months, years):
    out = ["YEAR BRIDGE (investment accounts)", "",
           "Money in and out = only money crossing the account's edge. Dividends, buys, sells and reinvestments are market change.", ""]
    for y in years:
        out += [f"{y['account']} {y['year']}  ({y['note']})",
                f"  start value      {money(y['start_value']):>14}  ({y['from']})",
                f"  money in         {money(y['money_in']):>14}",
                f"  money out        {money(y['money_out']):>14}  went to: {y['money_out_to']}",
                f"  market change    {money(y['market_change']):>14}  (price change plus dividends)",
                f"  end value        {money(y['end_value']):>14}  ({y['to']})",
                f"  bridge check     {money(y['bridge_check']):>14}  (end minus the four lines above; must be 0.00)",
                f"  statements chain: {'yes, each month opens where the last closed' if y['statements_chain'] else 'NO'}",
                f"  against the fund's own price change over {y['months_compared']} months (estimates): "
                f"account {y['acct_price_return_pct']}%, fund {y['fund_price_return_pct']}%, gap {y['cumulative_gap_pp']} points -> {y['flag']}", ""]
    head = f"{'Month ending':<14}{'Start':>13}{'In':>10}{'Out':>12}{'Market chg':>12}{'End':>13}{'Acct %':>8}{'Fund %':>8}{'Gap pp':>8}  Flag"
    out += [head, "-" * len(head)]
    for m in months:
        s = m["statement"]

        def f(x):
            return f"{pct(x)}" if x is not None else "-"

        out.append(f"{str(s['end']):<14}{money(s['begin_value']):>13}{money(m['in']):>10}{money(m['out']):>12}"
                   f"{money(m['market_change']):>12}{money(s['end_value']):>13}{f(m['acct_ret']):>8}{f(m['fund_ret']):>8}"
                   f"{(str(m['diff_pp']) if m['diff_pp'] is not None else '-'):>8}  {'CHECK' if m['flag'] else ''}")
    out += ["", f"Flag thresholds (set before looking): month {MONTH_FLAG_PP} points, year {YEAR_FLAG_PP} point."]
    return "\n".join(out) + "\n"


def run(root, stmts=None, quiet=False):
    root = Path(root)
    cfg = L.load_json(root / "scripts" / "config.json")
    if stmts is None:
        stmts, _ = S.load_statements(root / cfg.get("statements_dir", "statements"))
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    all_months, all_years = [], []
    for acct, a in cfg["accounts"].items():
        if a["control"] == "statement_brokerage":
            m, y = build(acct, rows, stmts)
            all_months += [(acct, x) for x in m]
            all_years += y
    cols = ["account", "year", "from", "to", "start_value", "money_in", "money_out", "money_out_to", "market_change",
            "end_value", "bridge_check", "statements_chain", "months_compared", "acct_price_return_pct",
            "fund_price_return_pct", "cumulative_gap_pp", "flag", "note"]

    out_rows = []
    for y in all_years:
        r = dict(y)
        for k in ("start_value", "money_in", "money_out", "market_change", "end_value", "bridge_check"):
            r[k] = money(y[k])
        for k in ("acct_price_return_pct", "fund_price_return_pct", "cumulative_gap_pp"):
            r[k] = "" if y[k] is None else str(y[k])
        r["statements_chain"] = "yes" if y["statements_chain"] else "NO"
        out_rows.append(r)
    L.write_csv(root / "ledger" / "year_bridge.csv", cols, out_rows)
    mcols = ["account", "month_ending", "start", "money_in", "money_out", "dividends", "price_change", "end",
             "account_price_return_pct", "fund_price_return_pct", "gap_pp", "flag"]
    L.write_csv(root / "reports" / "year_bridge_months.csv", mcols, [
        {"account": a, "month_ending": str(m["statement"]["end"]), "start": money(m["statement"]["begin_value"]),
         "money_in": money(m["in"]), "money_out": money(m["out"]), "dividends": money(m["dividends"]),
         "price_change": money(m["price_effect"]), "end": money(m["statement"]["end_value"]),
         "account_price_return_pct": "" if m["acct_ret"] is None else str(pct(m["acct_ret"])),
         "fund_price_return_pct": "" if m["fund_ret"] is None else str(pct(m["fund_ret"])),
         "gap_pp": "" if m["diff_pp"] is None else str(m["diff_pp"]), "flag": "CHECK" if m["flag"] else ""}
        for a, m in all_months])
    report = render([m for _, m in all_months], all_years)
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "year_bridge_report.txt").write_text(report, encoding="utf-8")
    if not quiet:
        print(report)
    return {"months": all_months, "years": all_years, "report": report}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    try:
        res = run(args.root)
    except DataError as e:
        print(f"STOP: {e}")
        return 2
    return 2 if any(y["bridge_check"] != 0 or y["flag"] != "ok" for y in res["years"]) else 0


if __name__ == "__main__":
    sys.exit(main())
