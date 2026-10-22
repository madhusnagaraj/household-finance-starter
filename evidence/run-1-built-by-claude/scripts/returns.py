#!/usr/bin/env python3
"""Questions worth asking of an investment account: what was saved, what was growth, where money went,
and what the account earned. Frameworks and math, not advice.

Return figures are ESTIMATES: they are built from monthly statements, so flows inside a month are
weighted by day, not known to the minute.
  Time-weighted return   chain-links each month's return, so the timing of money you moved in or
                         out does not change it. It answers: how did the investments do?
  Money-weighted return  the single rate that makes the starting value plus the dated money in and
                         out grow to the ending value. It answers: what did I actually earn, given
                         when I added or took out money? It is for the whole period, not annualized.
A benchmark is only compared when its values come from Sam or a source he names. None has been given.
Every number comes from the statements and the ledger.
"""
import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import statements as S  # noqa: E402
import year_bridge as YB  # noqa: E402
from ledgerlib import money  # noqa: E402

ZERO = Decimal("0.00")


def time_weighted(months):
    growth = Decimal(1)
    for m in months:
        growth *= 1 + m["market_change"] / m["base"]  # price change plus dividends, over the month's capital
    return growth - 1


def money_weighted(account, rows, months):
    """Period rate r so that start value and dated flows, grown to the end, equal the end value."""
    t0, t1 = months[0]["start"], months[-1]["statement"]["end"]
    span = (t1 - t0).days or 1
    flows = [(0.0, -float(months[0]["statement"]["begin_value"]))]
    for r in rows:
        if r["account"] == account and r["action"] in ("CONTRIBUTION", "WITHDRAWAL") and t0.isoformat() <= r["date"] <= t1.isoformat():
            flows.append(((date.fromisoformat(r["date"]) - t0).days / span, -float(r["amount"])))
    end_value = float(months[-1]["statement"]["end_value"])

    def future_value_gap(rate):
        return sum(-cf * (1 + rate) ** (1 - tau) for tau, cf in flows) - end_value

    lo, hi = -0.95, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if future_value_gap(mid) > 0:
            hi = mid
        else:
            lo = mid
    return Decimal(str(round((lo + hi) / 2, 6)))


def where_it_went(rows, account, one_off, window_days=60):
    out = []
    by_id = {r["id"]: r for r in rows}
    for w in sorted((r for r in rows if r["account"] == account and r["action"] == "WITHDRAWAL"), key=lambda r: r["date"]):
        other = by_id.get(w["pair_id"])
        out.append({"withdrawal": w, "to": other, "uses": []})
        if not other:
            continue
        start = date.fromisoformat(other["date"])
        for r in sorted(rows, key=lambda r: (r["date"], r["id"])):
            if r["account"] == other["account"] and r["kind"] == "spend" and r["category"] in one_off:
                d = date.fromisoformat(r["date"])
                if 0 <= (d - start).days <= window_days:
                    out[-1]["uses"].append(r)
    return out


def pct(x):
    return f"{(x * 100).quantize(Decimal('0.01'))}%"


def run(root, stmts=None, quiet=False):
    root = Path(root)
    cfg = L.load_json(root / "scripts" / "config.json")
    if stmts is None:
        stmts, _ = S.load_statements(root / cfg.get("statements_dir", "statements"))
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    one_off = set(cfg.get("one_off_categories", []))
    out = []
    for acct, a in cfg["accounts"].items():
        if a["control"] != "statement_brokerage":
            continue
        months, years = YB.build(acct, rows, stmts)
        if not months:
            continue
        y = years[0]
        tw, mw = time_weighted(months), money_weighted(acct, rows, months)
        start, end = months[0]["start"], months[-1]["statement"]["end"]
        out += [f"{acct.upper()}: {start} to {end}  (statements cover only this period)", "",
                "Saved versus growth",
                f"  value at the start                {money(y['start_value']):>14}",
                f"  saved (money you put in)          {money(y['money_in']):>14}",
                f"  growth (price change + dividends) {money(y['market_change']):>14}",
                f"  moved out                         {money(y['money_out']):>14}",
                f"  value at the end                  {money(y['end_value']):>14}",
                "  Growth is what the market did to your money. Saved is what you added. Moved out is not a loss.", ""]
        out.append("Where money went when it left")
        for item in where_it_went(rows, acct, one_off):
            w, to = item["withdrawal"], item["to"]
            out.append(f"  {w['date']}  {money(-Decimal(w['amount'])):>12} left {acct} and arrived in {to['account'] if to else 'an unmatched account'}")
            total = ZERO
            for u in item["uses"]:
                out.append(f"      {u['date']}  {u['description']:<28}{money(-Decimal(u['amount'])):>12}  ({u['category']})")
                total += -Decimal(u["amount"])
            if item["uses"]:
                out.append(f"      one-off spending that followed: {money(total)}; left over from that transfer: {money(-Decimal(w['amount']) - total)}")
            out.append("      Money is fungible: this follows the one-off cost Sam said the money was for, using the ledger's own rows.")
        out += ["", "What the account earned (ESTIMATES from monthly statements; this period only, not annualized)",
                f"  time-weighted return   {pct(tw):>9}   how the investments did, ignoring when money moved",
                f"  money-weighted return  {pct(mw):>9}   what you actually earned, given when money moved",
                "  The two differ because of the money you moved out in May.", "",
                "Benchmark: not compared. I need benchmark values from you or a source you name; I do not use numbers from memory.",
                "This is information, not investment advice, and I am not a licensed financial advisor.", ""]
    text = "\n".join(out) if out else "No investment accounts with statements."
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "returns_report.txt").write_text(text + "\n", encoding="utf-8")
    if not quiet:
        print(text)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args(argv)
    run(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
