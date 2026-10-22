#!/usr/bin/env python3
"""First draft of ledger/plan.csv and ledger/budget_map.csv, from what Sam decided on 2026-10-22.

Kept as the record of where the first plan came from. Sam owns the plan from here and edits
plan.csv himself; this script refuses to run if plan.csv already has any lines.

Two kinds of amounts:
  Sam's own numbers, exactly as he said them (groceries, dining, gas, the lumpy set-asides, savings).
  Numbers worked out from the ledger by script, following his instructions:
    pay            what actually lands: two of Sam's paychecks; Jordan's monthly pay
    childcare      a twelfth of a year: 10 school months of aftercare plus July and August of camp
    swim, subscriptions  what is paid now
    anything Sam did not name   the six-month average
"""
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import plan as P  # noqa: E402
import spending_history as H  # noqa: E402

CENT = Decimal("0.01")


def q(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


def latest_amount(rows, category):
    r = max((r for r in rows if r["category"] == category), key=lambda r: (r["date"], r["id"]))
    return abs(Decimal(r["amount"]))


def latest_month_total(rows, category, month):
    return sum((abs(Decimal(r["amount"])) for r in rows if r["category"] == category and r["date"][:7] == month), Decimal("0"))


def main(root):
    root = Path(root)
    rows = L.read_csv(root / "ledger" / "transactions.csv")
    cov = {c["account"]: (c["covered_from"], c["covered_to"]) for c in L.read_csv(root / "ledger" / "coverage.csv")}
    existing = P.check(root)
    if existing["plan"]:
        print("STOP: plan.csv already has lines. Sam owns it now; this seed script will not touch it.")
        return 2

    def avg(*cats):
        return H.six_month_average(rows, cov, set(cats))

    aftercare, camp = latest_amount(rows, "Kids: aftercare"), latest_amount(rows, "Kids: day camp")
    childcare = q((10 * aftercare + 2 * camp) / 12)
    subs = latest_month_total(rows, "Subscriptions", "2026-07")
    sam_pay = 2 * latest_amount(rows, "Pay: Sam")

    # (block, line, amount as a positive size, fixed, paid_by, note, ledger categories mapped to it)
    plan = [
        ("income", "Pay: Sam", sam_pay, 1, "bank",
         "Plain month: two paychecks. The third paycheck in a month (this October, next April) is extra and goes to the emergency fund (Sam, 2026-10-22)",
         ["Pay: Sam"]),
        ("income", "Pay: Jordan", avg("Pay: Jordan"), 1, "bank",
         "What actually lands each month (Sam, 2026-10-22). A summer gap is not known; the bank shows pay June to August", ["Pay: Jordan"]),
        ("committed", "Mortgage", avg("Mortgage"), 1, "bank", "Total payment on the 1st. The split with escrow is not confirmed yet", ["Mortgage"]),
        ("committed", "Groceries", Decimal("900"), 0, "card", "Sam, 2026-10-22", ["Groceries"]),
        ("committed", "Dining out and coffee", Decimal("250"), 0, "card", "Sam, 2026-10-22. Restaurants and the coffee place together", ["Dining", "Dining: coffee"]),
        ("committed", "Gas", Decimal("150"), 0, "card", "Sam, 2026-10-22", ["Auto: gas"]),
        ("committed", "Childcare: aftercare and camp", childcare, 1, "bank",
         "A twelfth of the year: 10 school months of aftercare plus July and August of day camp (Sam). Camp months run over this line, school months run under",
         ["Kids: aftercare", "Kids: day camp"]),
        ("committed", "Swim lessons", latest_amount(rows, "Kids: swim"), 1, "card", "What is paid now (Sam, 2026-10-22)", ["Kids: swim"]),
        ("committed", "Babysitter", avg("Kids: babysitter"), 0, "bank", "Six-month average; Sam to adjust", ["Kids: babysitter"]),
        ("committed", "Electric", avg("Utilities: electric"), 1, "bank", "Six-month average; higher in summer. Treated as a bill because it posts once a month", ["Utilities: electric"]),
        ("committed", "Water", avg("Utilities: water"), 1, "bank", "Six-month average. Treated as a bill because it posts once a month", ["Utilities: water"]),
        ("committed", "Internet", avg("Utilities: internet"), 1, "bank", "Six-month average", ["Utilities: internet"]),
        ("committed", "Phone", avg("Utilities: phone"), 1, "card", "Six-month average. On the card", ["Utilities: phone"]),
        ("committed", "Subscriptions", subs, 1, "card", "What is paid now (Sam, 2026-10-22)", ["Subscriptions"]),
        ("committed", "Car insurance", avg("Auto: insurance"), 1, "bank", "Six-month average", ["Auto: insurance"]),
        ("committed", "Cash", avg("Cash"), 0, "bank", "Six-month average; Sam to adjust", ["Cash"]),
        ("committed", "Shopping", avg("Shopping"), 0, "card", "Six-month average; Sam to adjust", ["Shopping"]),
        ("committed", "Gifts", avg("Gifts"), 0, "card", "Six-month average; Sam to adjust", ["Gifts"]),
        ("committed", "Fees and interest", avg("Fees & interest"), 0, "card", "Six-month average. Should be near zero when the card is paid in full", ["Fees & interest"]),
        ("lumpy", "Home repairs", Decimal("150"), 0, "card", "Sam, 2026-10-22. Set aside each month for when something breaks", []),
        ("lumpy", "Doctors and health", Decimal("100"), 0, "card", "Sam, 2026-10-22. Pharmacy purchases count against it", ["Health"]),
        ("lumpy", "Annual fees", Decimal("10"), 0, "card", "Sam, 2026-10-22", []),
        ("savings", "Brokerage", Decimal("500"), 1, "bank", "Sam, 2026-10-22. Already automatic, around the 15th", ["Savings: brokerage"]),
        ("savings", "Emergency fund", Decimal("1000"), 1, "bank",
         "Sam, 2026-10-22. No separate account exists yet; until one is opened this stays in checking", []),
        ("savings", "College fund (Mira)", Decimal("200"), 1, "bank",
         "Sam, 2026-10-22. Starts once the account is opened; not opened yet", []),
    ]
    for block, line, size, fixed, paid_by, note, cats in plan:
        amount = q(size) if block == "income" else -q(size)
        res, bad = P.add_line(root, block, line, format(amount, "f"), str(fixed), paid_by, note)
        if bad:
            print("NOT ADDED:", line, bad)
            return 2
        for c in cats:
            res, bad = P.add_map(root, c, line, "")
            if bad:
                print("NOT MAPPED:", c, bad)
                return 2
    res, bad = P.add_map(root, "Home: kitchen remodel", P.ONE_OFF, "One-off, funded from the brokerage; kept out of the monthly budget")
    if bad:
        print("NOT MAPPED:", bad)
        return 2
    final = P.check(root)
    print(P.render(final))
    return 2 if final["errors"] else 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent))
