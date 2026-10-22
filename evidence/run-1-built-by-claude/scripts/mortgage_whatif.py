#!/usr/bin/env python3
"""Pay the mortgage down early, or invest the extra? The arithmetic, not a recommendation.

What it shows:
  1. The baseline: the standard monthly principal-and-interest payment for the stated loan, and how
     long the current balance takes to clear and what interest remains.
  2. What an extra monthly payment does to payoff time and interest.
  3. The break-even: the average yearly return that investing the same extra money would have to beat,
     for the two choices to end up equal. Paying down a fixed-rate loan is a certain return equal to
     the loan rate (before tax); investing is an uncertain one. A table of HYPOTHETICAL returns shows
     how the answer flips; those rates are illustrations, not forecasts and not a benchmark.
Inputs are Sam's, from memory, until a mortgage statement confirms them (config.json: "mortgage",
and the estimated balance in ledger/balances.csv). Taxes, fees, any prepayment penalty and any
interest deduction are NOT modelled. I am not a licensed financial advisor.
"""
import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
from ledgerlib import money  # noqa: E402

CENT = Decimal("0.01")


def q(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def standard_payment(principal, annual_pct, months):
    r = Decimal(annual_pct) / 100 / 12
    return q(principal * r / (1 - (1 + r) ** -months))


def amortize(balance, annual_pct, payment, extra=Decimal("0")):
    """Months to clear and total interest, rounding interest to the cent each month like a lender."""
    r = Decimal(annual_pct) / 100 / 12
    bal, months, interest = Decimal(balance), 0, Decimal("0")
    while bal > 0 and months < 1200:
        i = q(bal * r)
        pay = min(payment + extra, bal + i)
        if pay <= i:
            raise ValueError("the payment does not cover the interest")
        bal = bal + i - pay
        interest += i
        months += 1
    return months, interest


def future_value(monthly, annual_return, months):
    """What equal monthly contributions grow to, compounding monthly (contribution at each month end)."""
    r = Decimal(str(annual_return)) / 12
    if r == 0:
        return monthly * months
    return monthly * ((1 + r) ** months - 1) / r


def compare(balance, annual_pct, payment, extra, annual_return):
    """End-wealth difference at the baseline payoff date: invest the extra (B) minus pay extra, then invest the freed payment (A)."""
    n0, _ = amortize(balance, annual_pct, payment)
    nA, _ = amortize(balance, annual_pct, payment, extra)
    r = Decimal(str(annual_return)) / 12
    freed = payment + extra
    a = future_value(freed, annual_return, n0 - nA)
    b = future_value(extra, annual_return, n0)
    return b - a, (n0, nA)


def break_even(balance, annual_pct, payment, extra):
    lo, hi = Decimal("0.0"), Decimal("0.30")
    for _ in range(60):
        mid = (lo + hi) / 2
        diff, _ = compare(balance, annual_pct, payment, extra, mid)
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--extra", type=Decimal, action="append", help="extra per month (repeat for several), e.g. --extra 500")
    args = ap.parse_args(argv)
    root = Path(args.root)
    cfg = L.load_json(root / "scripts" / "config.json")["mortgage"]
    bal_row = max((b for b in L.read_csv(root / "ledger" / "balances.csv") if b["account"] == "mortgage_hollowmere"),
                  key=lambda b: b["as_of"])
    balance = abs(Decimal(bal_row["amount"]))
    pay = standard_payment(Decimal(cfg["original_amount"]), cfg["rate_pct"], cfg["term_months"])
    n0, i0 = amortize(balance, cfg["rate_pct"], pay)
    print(f"Loan as I have it (from memory, confidence: {bal_row['confidence']}; a mortgage statement settles it):")
    print(f"  rate {cfg['rate_pct']}% fixed, original {money(Decimal(cfg['original_amount']))}, {cfg['term_months']} months")
    print(f"  balance used {money(balance)} as of {bal_row['as_of']}")
    print(f"  standard monthly principal and interest for those terms: {money(pay)} (the bank rows show a larger total that includes escrow)")
    print(f"\nBaseline from here: {n0} months to clear ({n0 / 12:.1f} years), interest still to pay {money(i0)}")
    for x in args.extra or []:
        nA, iA = amortize(balance, cfg["rate_pct"], pay, x)
        be = break_even(balance, cfg["rate_pct"], pay, x)
        print(f"\nExtra {money(x)} a month toward principal:")
        print(f"  clears in {nA} months instead of {n0} ({(n0 - nA) / 12:.1f} years sooner); interest saved {money(i0 - iA)}")
        print(f"  break-even: investing the same extra has to average about {be * 100:.2f}% a year, after tax and fees, "
              f"over the whole {n0} months to match. Paying down earns the loan rate for certain.")
        print(f"  {'Hypothetical yearly return':<28}{'Invest minus pay-down, at the baseline payoff date':>52}")
        for rate in ("0.03", "0.05", "0.07", "0.09"):
            d, _ = compare(balance, cfg["rate_pct"], pay, x, rate)
            print(f"  {float(rate) * 100:>5.1f}% (illustration, not a forecast){'':<4}{money(q(d)):>20}")
    print("\nNot modelled: taxes, the mortgage interest deduction, fees, any prepayment penalty, how the lender applies extra payments, "
          "or the risk that investment returns come in below the break-even in the years you need the money. Not advice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
