#!/usr/bin/env python3
"""Generate a reproducible, entirely FICTIONAL household for test-driving the starter prompt.

Every name, institution, account and number here is invented. Fixed seed, so the same files
(PDFs included) come out every time.

    python3 make_fixture.py            # writes into this folder
    python3 make_fixture.py /some/dir  # writes somewhere else

Outputs
    persona.md      the only source the scripted user may answer from
    downloads/      raw CSVs "the user has" (goes into the run dir)
    statements/     statement PDFs + a paystub (goes into the run dir)
    traps.md        answer key (NEVER goes into the run dir)
    truth/          true ledger, statement balances, monthly totals (NEVER goes into the run dir)

Traps: T1-T8 are named in the prompt since v0, T9-T12 are named by v2's new rules,
U1-U4 are never mentioned by any prompt version (the "unanticipated" measure).
"""
import calendar
import csv
import datetime as dt
import random
import shutil
import sys
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 20260315
CENT = Decimal("0.01")
MONTHS = [f"2026-{m:02d}" for m in range(3, 9)]

CHK = "otterbrook_checking_4417"
CARD = "fernleaf_card_9023"
BRK = "tidewell_brokerage_3380"


def d(s):
    return dt.date.fromisoformat(s)


# T9: the card's statements close on the 23rd, so its periods run 24th to 23rd
CARD_PERIODS = [(d("2026-02-24"), d("2026-03-23")), (d("2026-03-24"), d("2026-04-23")),
                (d("2026-04-24"), d("2026-05-23")), (d("2026-05-24"), d("2026-06-23")),
                (d("2026-06-24"), d("2026-07-23")), (d("2026-07-24"), d("2026-08-23"))]

CHK_OPENING = Decimal("8420.15")
CARD_OPENING = Decimal("1342.17")  # statement that closed 02/23, paid by autopay on 03/17
CARD_APR = Decimal("0.2499")
JUNE_PARTIAL = Decimal("1000.00")  # U3: autopay set to $1,000 in June, so a balance carries
SAM_NET = Decimal("2760.18")
JORDAN_NET = Decimal("3248.55")
FUND = "TWTMX"
FUND_NAME = "Tidewell Total Market Index Fund"
START_SHARES = Decimal("1184.000")
DIV_PER_SHARE = Decimal("0.38")
# month-end closing prices (last business day); February is the starting price
ANCHORS = {"2026-02": "118.40", "2026-03": "120.10", "2026-04": "121.35", "2026-05": "116.90",
           "2026-06": "114.80", "2026-07": "116.10", "2026-08": "115.20"}
ELECTRIC = {3: "132.48", 4: "104.17", 5: "98.62", 6: "151.90", 7: "183.44", 8: "176.05"}
WATER = {3: "61.20", 4: "58.75", 5: "63.10", 6: "70.44", 7: "74.80", 8: "72.15"}

T4_PAIR = {"date": "2026-05-14", "description": "BEAN & BARLEY CAFE", "amount": "5.25"}
T5_MISSING = {"date": "2026-07-19", "description": "HEARTHSTONE MARKET", "amount": "87.43"}
T10 = {"pending_date": "2026-06-14", "pending": "-48.00", "posted_date": "2026-06-16", "posted": "-57.60",
       "description": "DEBIT CARD THE COPPER SPOON"}
T11 = {"purchase_date": "2026-04-03", "purchase": "89.97", "refund_date": "2026-04-16", "refund": "34.99"}
U1_FOOTER_PERIOD = 1  # index into CARD_PERIODS
U2 = {"date": "2026-05-04", "description": "NORDLYS DESIGN OSLO NOK 640.00", "amount": "61.12"}
U4 = {"original": "Otterbrook_eStatement_2026-04-30.pdf", "copy": "Otterbrook_eStatement_2026-04-30 (1).pdf"}
TRAP_DAYS = {d(T4_PAIR["date"]), d(T5_MISSING["date"]), d(T11["purchase_date"]), d(T11["refund_date"]),
             d(U2["date"]), d("2026-06-23")}


def money(x):
    return Decimal(str(x)).quantize(CENT, ROUND_HALF_UP)


def bday(day):
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def add_bdays(day, n):
    while n:
        day += dt.timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def last_bday(y, m):
    day = dt.date(y, m, calendar.monthrange(y, m)[1])
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def ym(day):
    return day.strftime("%Y-%m")


class Ledger:
    def __init__(self):
        self.rows = []
        self.seq = 0

    def add(self, account, date, description, amount, kind, category, **extra):
        self.seq += 1
        row = dict(account=account, date=date, description=description, amount=money(amount),
                   kind=kind, category=category, seq=self.seq)
        row.update(extra)
        self.rows.append(row)
        return row

    def of(self, account, lo=None, hi=None):
        rows = (r for r in self.rows if r["account"] == account and (lo is None or lo <= r["date"] <= hi))
        return sorted(rows, key=lambda r: (r["date"], r["seq"]))


# ---------------------------------------------------------------- brokerage

def daily_prices(rng):
    """Business-day closing prices, exact at each month-end anchor, gentle noise in between."""
    prices = {}
    keys = list(ANCHORS)
    for prev, cur in zip(keys, keys[1:]):
        y, m = map(int, cur.split("-"))
        py, pm = map(int, prev.split("-"))
        start_day, end_day = last_bday(py, pm), last_bday(y, m)
        p0, p1 = Decimal(ANCHORS[prev]), Decimal(ANCHORS[cur])
        days = [start_day + dt.timedelta(days=i) for i in range(1, (end_day - start_day).days + 1)]
        days = [x for x in days if x.weekday() < 5]
        for i, day in enumerate(days, 1):
            frac = Decimal(i) / Decimal(len(days))
            base = p0 + (p1 - p0) * frac
            noise = Decimal(str(round(rng.uniform(-0.35, 0.35), 2))) if day != end_day else Decimal("0")
            prices[day] = money(base + noise)
    prices[last_bday(2026, 2)] = Decimal(ANCHORS["2026-02"])
    return prices


def gen_brokerage(rng, led, arrival_dates):
    prices = daily_prices(rng)
    shares, cash = START_SHARES, Decimal("0.00")
    activity = []  # rows for the activity CSV (cash-signed amounts)

    def act(day, action, desc, qty, price, amount):
        activity.append(dict(date=day, action=action, desc=desc, qty=qty, price=price, amount=money(amount)))

    events = [(day, "contrib") for day in arrival_dates]
    events += [(d("2026-03-26"), "div"), (d("2026-06-25"), "div"),
               (d("2026-05-06"), "sell"), (d("2026-05-08"), "withdraw")]
    events.sort()
    month_flows = {m: dict(contributions=Decimal("0"), withdrawals=Decimal("0"), dividends=Decimal("0"))
                   for m in MONTHS}
    for day, kind in events:
        px = prices[day]
        if kind == "contrib":
            cash += Decimal("500.00")
            act(day, "CONTRIBUTION", "ELECTRONIC FUNDS TRANSFER RECEIVED ***4417", "", "", "500.00")
            led.add(BRK, day, "CONTRIBUTION FROM ***4417", "500.00", "transfer", "Transfer from checking")
            month_flows[ym(day)]["contributions"] += Decimal("500.00")
            qty = (Decimal("500.00") / px).quantize(Decimal("0.001"), ROUND_DOWN)
            cost = money(qty * px)
            shares += qty
            cash -= cost
            act(day, "BUY", f"{FUND_NAME} (automatic investment)", qty, px, -cost)
        elif kind == "div":
            amt = money(shares * DIV_PER_SHARE)
            cash += amt
            act(day, "DIVIDEND", f"{FUND_NAME} dividend", "", "", amt)
            led.add(BRK, day, f"DIVIDEND {FUND}", amt, "income", "Dividends")
            month_flows[ym(day)]["dividends"] += amt
            qty = (amt / px).quantize(Decimal("0.001"), ROUND_DOWN)
            cost = money(qty * px)
            shares += qty
            cash -= cost
            act(day, "REINVEST", f"{FUND_NAME} dividend reinvestment", qty, px, -cost)
        elif kind == "sell":
            qty = Decimal("296.000")
            proceeds = money(qty * px)
            shares -= qty
            cash += proceeds
            act(day, "SELL", f"{FUND_NAME}", -qty, px, proceeds)
        elif kind == "withdraw":
            cash -= Decimal("35000.00")
            act(day, "WITHDRAWAL", "ELECTRONIC FUNDS TRANSFER SENT ***4417", "", "", "-35000.00")
            led.add(BRK, day, "WITHDRAWAL TO ***4417", "-35000.00", "transfer", "Transfer to checking")
            month_flows[ym(day)]["withdrawals"] += Decimal("35000.00")
        assert cash >= 0, (day, kind, cash)

    statements = {}
    opening = money(START_SHARES * Decimal(ANCHORS["2026-02"]))
    sh, ca = START_SHARES, Decimal("0.00")
    for month in MONTHS:
        for a in activity:
            if ym(a["date"]) != month:
                continue
            ca += a["amount"]
            if a["qty"] != "":
                sh += a["qty"]  # SELL quantities are negative
        y, m = map(int, month.split("-"))
        px = Decimal(ANCHORS[month])
        closing = money(sh * px) + ca
        f = month_flows[month]
        mkt = closing - opening - f["contributions"] + f["withdrawals"] - f["dividends"]
        statements[month] = dict(opening=opening, closing=closing, contributions=f["contributions"],
                                 withdrawals=f["withdrawals"], dividends=f["dividends"], market_change=mkt,
                                 shares=sh, price=px, cash=ca, period_end=last_bday(y, m))
        opening = closing
    return activity, statements


# ---------------------------------------------------------------- card (statement periods 24th to 23rd)

def in_period(start, end, dom):
    y, m = (start.year, start.month) if dom >= start.day else (end.year, end.month)
    return dt.date(y, m, dom)


def gen_card_period(rng, led, idx, start, end, opening, payment):
    def purchase(day, desc, amount, bank_cat, cat):
        return led.add(CARD, day, desc, -money(amount), "spend", cat, bank_category=bank_cat)

    purchase(in_period(start, end, 2), "RIVERSIDE SWIM CLUB", "65.00", "Recreation", "Kids activities")
    purchase(in_period(start, end, 7), "STREAMBOX MONTHLY", "15.99", "Entertainment", "Subscriptions")
    purchase(in_period(start, end, 20), "TUNEWAVE FAMILY", "16.99", "Entertainment", "Subscriptions")
    purchase(in_period(start, end, 26), "CLEARCALL WIRELESS", "95.00", "Bills & Utilities", "Phone")
    pay_day = bday(dt.date(end.year, end.month, 17))
    led.add(CARD, pay_day, "AUTOPAY PAYMENT - THANK YOU", money(payment), "transfer", "Credit card payment",
            bank_category="Payment/Credit")

    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    free = [x for x in days if x not in TRAP_DAYS]
    used = set()

    def free_day():
        for _ in range(60):
            x = rng.choice(free)
            if x not in used:
                used.add(x)
                return x
        return rng.choice(free)

    for _ in range(rng.randint(4, 5)):
        purchase(free_day(), "HEARTHSTONE MARKET", round(rng.uniform(88, 164), 2), "Groceries", "Groceries")
    for _ in range(2):
        purchase(free_day(), "GREENBASKET GROCERY", round(rng.uniform(38, 72), 2), "Groceries", "Groceries")
    for _ in range(rng.randint(2, 3)):
        purchase(free_day(), "QUIKFILL #212", round(rng.uniform(38, 56), 2), "Gas", "Gas")
    for name in rng.sample(["LUCIA'S TRATTORIA", "THE COPPER SPOON", "PHO LANTERN", "TACO ORBIT"], 3):
        purchase(free_day(), name, round(rng.uniform(28, 96), 2), "Dining", "Dining out")
    for _ in range(rng.randint(2, 3)):
        purchase(free_day(), "BEAN & BARLEY CAFE", round(rng.uniform(4.1, 11.9), 2), "Dining", "Dining out")
    for _ in range(rng.randint(2, 3)):
        purchase(free_day(), "ORBITMART ONLINE", round(rng.uniform(19, 128), 2), "Shopping", "Household & shopping")
    if rng.random() < 0.6:
        purchase(free_day(), "WELLSPRING PHARMACY", round(rng.uniform(11, 36), 2), "Health", "Health")

    if idx == 1:  # T11: purchase, then a partial refund in the same category
        purchase(d(T11["purchase_date"]), "ORBITMART ONLINE", T11["purchase"], "Shopping", "Household & shopping")
        led.add(CARD, d(T11["refund_date"]), "ORBITMART ONLINE RETURN", T11["refund"], "spend",
                "Household & shopping", bank_category="Shopping", note="partial refund of the 04/03 purchase")
    if idx == 2:
        for _ in range(2):  # T4: two real, identical coffees on the same day
            purchase(d(T4_PAIR["date"]), T4_PAIR["description"], T4_PAIR["amount"], "Dining", "Dining out")
        # U2: foreign purchase plus the card's separate 3% fee row
        purchase(d(U2["date"]), U2["description"], U2["amount"], "Shopping", "Gifts")
        led.add(CARD, d(U2["date"]), "FOREIGN TRANSACTION FEE", -money(Decimal(U2["amount"]) * Decimal("0.03")),
                "spend", "Fees & interest", bank_category="Fees & Adjustments")
    if idx == 3 and payment < opening:  # U3: balance carried after the partial June payment
        interest = money((opening - payment) * CARD_APR / 12)
        led.add(CARD, end, "INTEREST CHARGE ON PURCHASES", -interest, "spend", "Fees & interest",
                bank_category="Fees & Adjustments")
    if idx == 4:  # T5: on the statement, missing from the CSV export
        purchase(d(T5_MISSING["date"]), T5_MISSING["description"], T5_MISSING["amount"], "Groceries", "Groceries")


def card_summary(rows, opening, closing):
    is_fee = lambda r: r["description"] == "FOREIGN TRANSACTION FEE"
    is_int = lambda r: r["description"].startswith("INTEREST CHARGE")
    z = Decimal("0")
    return dict(
        opening=opening, closing=closing,
        payments=sum((r["amount"] for r in rows if r["kind"] == "transfer"), z),
        credits=sum((r["amount"] for r in rows if r["kind"] == "spend" and r["amount"] > 0), z),
        purchases=-sum((r["amount"] for r in rows if r["amount"] < 0 and not is_fee(r) and not is_int(r)), z),
        fees=-sum((r["amount"] for r in rows if is_fee(r)), z),
        interest=-sum((r["amount"] for r in rows if is_int(r)), z))


# ---------------------------------------------------------------- household

def gen_household():
    rng = random.Random(SEED)
    led = Ledger()

    card_st, autopays = {}, []
    opening = CARD_OPENING
    for idx, (start, end) in enumerate(CARD_PERIODS):
        payment = JUNE_PARTIAL if end.month == 6 else opening
        autopays.append((bday(dt.date(end.year, end.month, 17)), payment))
        gen_card_period(rng, led, idx, start, end, opening, payment)
        rows = led.of(CARD, start, end)
        closing = opening - sum((r["amount"] for r in rows), Decimal("0"))
        card_st[end.isoformat()] = card_summary(rows, opening, closing)
        opening = closing

    day = d("2026-03-06")
    while day <= d("2026-08-31"):
        led.add(CHK, day, "QUILLFEATHER LABS PAYROLL DIR DEP", SAM_NET, "income", "Salary - Sam")
        day += dt.timedelta(days=14)
    arrivals = []
    for month, (pay_day, pay_amt) in zip(MONTHS, autopays):
        y, m = map(int, month.split("-"))
        led.add(CHK, last_bday(y, m), "SALTMARSH USD PAYROLL", JORDAN_NET, "income", "Salary - Jordan")
        led.add(CHK, bday(dt.date(y, m, 1)), "HOLLOWMERE MORTGAGE PMT", "-2140.00", "spend", "Mortgage")
        if m <= 6:
            led.add(CHK, bday(dt.date(y, m, 3)), "LITTLE ACORNS AFTERCARE", "-420.00", "spend", "Childcare")
        else:
            led.add(CHK, bday(dt.date(y, m, 3)), "CAMP WILLOWBEND", "-650.00", "spend", "Childcare")
        led.add(CHK, bday(dt.date(y, m, 5)), "PEBBLENET FIBER", "-70.00", "spend", "Internet")
        led.add(CHK, bday(dt.date(y, m, 10)), "MAPLEFORD ELECTRIC CO", f"-{ELECTRIC[m]}", "spend", "Electric")
        led.add(CHK, bday(dt.date(y, m, 12)), "STEADYHAND INSURANCE", "-142.30", "spend", "Auto insurance")
        out_day = bday(dt.date(y, m, 15))
        arrivals.append(add_bdays(out_day, 3))  # T12: lands in the brokerage three business days later
        led.add(CHK, out_day, "TIDEWELL BROKERAGE XFER TO ***3380", "-500.00", "transfer", "Transfer to brokerage")
        led.add(CHK, bday(dt.date(y, m, 18)), "MAPLEFORD WATER UTIL", f"-{WATER[m]}", "spend", "Water")
        led.add(CHK, pay_day, "FERNLEAF CARD AUTOPAY", -pay_amt, "transfer", "Credit card payment")
        led.add(CHK, bday(dt.date(y, m, rng.choice([6, 13, 20, 27]))), "ATM WITHDRAWAL 0412 MAIN ST",
                f"-{rng.choice(['60.00', '100.00'])}", "spend", "Cash")
        led.add(CHK, bday(dt.date(y, m, rng.choice([8, 16, 25]))), "P2P PAYMENT TO R OKONKWO",
                f"-{rng.choice(['80.00', '96.00', '120.00'])}", "spend", "Babysitting")
    led.add(CHK, d("2026-05-08"), "TIDEWELL BROKERAGE XFER FROM ***3380", "35000.00", "transfer",
            "Transfer from brokerage")
    led.add(CHK, d("2026-05-11"), "CHECK 1042", "-22000.00", "spend", "Home improvement",
            note="kitchen remodel deposit to Halverson Renovation")
    led.add(CHK, d("2026-06-18"), "HALVERSON RENOVATION ACH", "-12850.00", "spend", "Home improvement",
            note="kitchen remodel final payment")
    led.add(CHK, d(T10["posted_date"]), T10["description"], T10["posted"], "spend", "Dining out",
            note="authorized 06/14 for 48.00, posted with tip")

    chk_st = {}
    opening = CHK_OPENING
    for month in MONTHS:
        y, m = map(int, month.split("-"))
        rows = [r for r in led.of(CHK) if ym(r["date"]) == month]
        flows = sum((r["amount"] for r in rows), Decimal("0"))
        chk_st[month] = dict(opening=opening, closing=opening + flows,
                             deposits=sum((r["amount"] for r in rows if r["amount"] > 0), Decimal("0")),
                             withdrawals=-sum((r["amount"] for r in rows if r["amount"] < 0), Decimal("0")))
        opening += flows

    activity, brk_st = gen_brokerage(rng, led, arrivals)
    return led, {CHK: chk_st, CARD: card_st, BRK: brk_st}, activity


# ---------------------------------------------------------------- writers: CSV downloads

def fmt_amt(x):
    return f"{x:.2f}"


def write_checking_exports(led, out):
    bal = CHK_OPENING
    with_bal = []
    for r in led.of(CHK):
        bal += r["amount"]
        with_bal.append((r, bal))
    spans = [("otterbrook_checking_export_20260615.csv", d("2026-03-01"), d("2026-06-15")),
             ("otterbrook_checking_export_20260831.csv", d("2026-06-01"), d("2026-08-31"))]
    for name, lo, hi in spans:
        rows = [[r["date"].strftime("%m/%d/%Y"), r["description"], fmt_amt(r["amount"]), fmt_amt(b), "Posted"]
                for r, b in with_bal if lo <= r["date"] <= hi]
        rows.reverse()  # this bank exports newest first
        if hi == d("2026-06-15"):  # T10: the authorization shows as pending, before the tip
            rows.insert(0, [d(T10["pending_date"]).strftime("%m/%d/%Y"), T10["description"], T10["pending"], "",
                            "Pending"])
        with open(out / name, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Date", "Description", "Amount", "Balance", "Status"])
            w.writerows(rows)


def write_card_exports(led, out):
    for idx, (start, end) in enumerate(CARD_PERIODS):
        lines = [
            "Fernleaf Card Services,,,,,",
            '"Account: Fernleaf Rewards Card ending in 9023",,,,,',
            f'"Activity for statement period {start.strftime("%m/%d/%Y")} - {end.strftime("%m/%d/%Y")}",,,,,',
        ]
        body = []
        for r in led.of(CARD, start, end):
            if (r["date"] == d(T5_MISSING["date"]) and r["description"] == T5_MISSING["description"]
                    and fmt_amt(-r["amount"]) == T5_MISSING["amount"]):
                continue  # T5: export silently missing this row
            post = min(r["date"] + dt.timedelta(days=1), end)
            debit = fmt_amt(-r["amount"]) if r["amount"] < 0 else ""
            credit = fmt_amt(r["amount"]) if r["amount"] > 0 else ""
            body.append([r["date"].isoformat(), post.isoformat(), r["description"], r["bank_category"], debit, credit])
        with open(out / f"fernleaf_activity_{end.isoformat()}.csv", "w", newline="") as f:
            f.write("\n".join(lines) + "\n")
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["Transaction Date", "Post Date", "Description", "Category", "Debit", "Credit"])
            w.writerows(body)
            if idx == U1_FOOTER_PERIOD:  # U1: a totals footer some exports append
                debits = sum(Decimal(b[4]) for b in body if b[4])
                credits = sum(Decimal(b[5]) for b in body if b[5])
                w.writerow(["Total", "", "", "", fmt_amt(debits), fmt_amt(credits)])


def write_brokerage_activity(activity, out):
    with open(out / "tidewell_activity_2026-03_to_2026-08.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Trade Date", "Action", "Symbol", "Description", "Quantity", "Price", "Amount"])
        for a in activity:
            sym = FUND if a["action"] in ("BUY", "SELL", "REINVEST", "DIVIDEND") else ""
            w.writerow([a["date"].strftime("%m/%d/%Y"), a["action"], sym, a["desc"],
                        "" if a["qty"] == "" else f"{a['qty']:.3f}",
                        "" if a["price"] == "" else f"{a['price']:.2f}", fmt_amt(a["amount"])])


# ---------------------------------------------------------------- writers: PDF statements

def _pdf(path, story_fn):
    from reportlab import rl_config
    rl_config.invariant = 1  # byte-identical PDFs on every run
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=48, rightMargin=48, topMargin=42,
                            bottomMargin=42, title=path.stem, author="Synthetic fixture")
    doc.build(story_fn())


def _styles():
    from reportlab.lib.styles import getSampleStyleSheet
    ss = getSampleStyleSheet()
    return ss["Title"], ss["Heading3"], ss["BodyText"]


def _table(data, widths, right_cols=()):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [("FONT", (0, 0), (-1, -1), "Helvetica", 8.5), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
             ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
             ("TOPPADDING", (0, 0), (-1, -1), 2)]
    for c in right_cols:
        style.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def m_name(month, fmt="%B %Y"):
    return d(month + "-01").strftime(fmt)


def write_checking_pdfs(led, st, out):
    from reportlab.platypus import Paragraph, Spacer
    title, h, body = _styles()
    for month in MONTHS:
        y, m = map(int, month.split("-"))
        last = dt.date(y, m, calendar.monthrange(y, m)[1])
        s = st[month]
        rows = [r for r in led.of(CHK) if ym(r["date"]) == month]

        def story():
            bal = s["opening"]
            tx = [["Date", "Description", "Amount", "Balance"]]
            for r in rows:
                bal += r["amount"]
                tx.append([r["date"].strftime("%m/%d"), r["description"], f"{r['amount']:,.2f}", f"{bal:,.2f}"])
            summary = [["Account Summary", ""],
                       [f"Beginning Balance on {m_name(month, '%B')} 1, {y}", f"${s['opening']:,.2f}"],
                       ["Deposits and Additions", f"{s['deposits']:,.2f}"],
                       ["Withdrawals and Subtractions", f"-{s['withdrawals']:,.2f}"],
                       [f"Ending Balance on {last.strftime('%B')} {last.day}, {y}", f"${s['closing']:,.2f}"]]
            return [Paragraph("Otterbrook Bank", title),
                    Paragraph("Everyday Joint Checking  |  Account ending 4417", body),
                    Paragraph("Sam Ellery and Jordan Ellery, 18 Wren Hollow Lane, Mapleford", body),
                    Paragraph(f"Statement period: {m:02d}/01/{y} through {m:02d}/{last.day}/{y}", body),
                    Spacer(1, 8), _table(summary, [330, 120], right_cols=(1,)), Spacer(1, 10),
                    Paragraph("Transaction Detail", h), _table(tx, [50, 270, 70, 70], right_cols=(2, 3))]
        _pdf(out / f"Otterbrook_eStatement_{last.isoformat()}.pdf", story)
    shutil.copyfile(out / U4["original"], out / U4["copy"])  # U4: same statement downloaded twice


def write_card_pdfs(led, st, out):
    from reportlab.platypus import Paragraph, Spacer
    title, h, body = _styles()
    for start, end in CARD_PERIODS:
        s = st[end.isoformat()]
        rows = led.of(CARD, start, end)
        ny, nm = (end.year + (end.month == 12), end.month % 12 + 1)
        due = bday(dt.date(ny, nm, 17))

        def story():
            tx = [["Trans Date", "Post Date", "Description", "Amount"]]
            for r in rows:
                post = min(r["date"] + dt.timedelta(days=1), end)
                tx.append([r["date"].strftime("%m/%d"), post.strftime("%m/%d"), r["description"],
                           f"{-r['amount']:,.2f}"])
            summary = [["Account Summary", ""],
                       ["Previous Balance", f"${s['opening']:,.2f}"],
                       ["Payments", f"-{s['payments']:,.2f}"],
                       ["Other Credits", f"-{s['credits']:,.2f}"],
                       ["Purchases", f"+{s['purchases']:,.2f}"],
                       ["Fees Charged", f"+{s['fees']:,.2f}"],
                       ["Interest Charged", f"+{s['interest']:,.2f}"],
                       ["New Balance", f"${s['closing']:,.2f}"],
                       ["Minimum Payment Due", f"${max(Decimal('35.00'), money(s['closing'] * Decimal('0.02'))):,.2f}"],
                       ["Payment Due Date", due.strftime("%m/%d/%Y")],
                       ["Purchase APR", "24.99%"],
                       ["AutoPay", "From Otterbrook ***4417"]]
            return [Paragraph("Fernleaf Card Services", title),
                    Paragraph("Fernleaf Rewards Card  |  Account ending 9023", body),
                    Paragraph("Primary cardholder: Sam Ellery  |  Authorized user: Jordan Ellery", body),
                    Paragraph(f"Billing period: {start.strftime('%m/%d/%Y')} - {end.strftime('%m/%d/%Y')}", body),
                    Spacer(1, 8), _table(summary, [300, 150], right_cols=(1,)), Spacer(1, 10),
                    Paragraph("Transactions (purchases positive, payments and credits negative)", h),
                    _table(tx, [55, 55, 270, 80], right_cols=(3,))]
        _pdf(out / f"FernleafCard_Statement_{end.isoformat()}.pdf", story)


def write_brokerage_pdfs(activity, st, out):
    from reportlab.platypus import Paragraph, Spacer
    title, h, body = _styles()
    for month in MONTHS:
        y, m = map(int, month.split("-"))
        s = st[month]
        acts = [a for a in activity if ym(a["date"]) == month]

        def story():
            summary = [["Account Value Summary", "This period"],
                       ["Beginning value", f"${s['opening']:,.2f}"],
                       ["Contributions", f"{s['contributions']:,.2f}"],
                       ["Withdrawals", f"-{s['withdrawals']:,.2f}"],
                       ["Dividends", f"{s['dividends']:,.2f}"],
                       ["Change in market value", f"{s['market_change']:,.2f}"],
                       ["Ending value", f"${s['closing']:,.2f}"]]
            holdings = [["Symbol", "Description", "Quantity", "Price", "Market value"],
                        [FUND, FUND_NAME, f"{s['shares']:,.3f}", f"{s['price']:,.2f}",
                         f"{money(s['shares'] * s['price']):,.2f}"],
                        ["CASH", "Cash sweep", "", "", f"{s['cash']:,.2f}"]]
            tx = [["Date", "Action", "Description", "Quantity", "Amount"]]
            for a in acts:
                tx.append([a["date"].strftime("%m/%d"), a["action"], a["desc"][:44],
                           "" if a["qty"] == "" else f"{a['qty']:.3f}", f"{a['amount']:,.2f}"])
            return [Paragraph("Tidewell Brokerage", title),
                    Paragraph("Joint Taxable Brokerage  |  Account ending 3380", body),
                    Paragraph("Sam Ellery and Jordan Ellery, JTWROS", body),
                    Paragraph(f"Statement for {m_name(month)} (period ending {s['period_end'].strftime('%m/%d/%Y')})", body),
                    Spacer(1, 8), _table(summary, [300, 150], right_cols=(1,)), Spacer(1, 10),
                    Paragraph("Holdings", h), _table(holdings, [50, 190, 70, 60, 90], right_cols=(2, 3, 4)),
                    Spacer(1, 10), Paragraph("Activity", h), _table(tx, [40, 75, 205, 60, 80], right_cols=(3, 4))]
        _pdf(out / f"Tidewell_Monthly_Statement_{y}{m:02d}.pdf", story)


def paystub_numbers():
    gross = money(Decimal("110000") / Decimal("26"))
    k401 = money(gross * Decimal("0.06"))
    medical = Decimal("186.00")
    ss = money((gross - medical) * Decimal("0.062"))
    medicare = money((gross - medical) * Decimal("0.0145"))
    state = money((gross - k401 - medical) * Decimal("0.044"))
    federal = gross - k401 - medical - ss - medicare - state - SAM_NET
    assert federal > 0
    return [("Gross pay", gross), ("401(k) 6% (pre-tax)", -k401), ("Medical/dental (pre-tax)", -medical),
            ("Federal income tax", -federal), ("Social Security", -ss), ("Medicare", -medicare),
            ("State income tax", -state), ("Net pay (direct deposit, Otterbrook ***4417)", SAM_NET)]


def write_paystub(out):
    from reportlab.platypus import Paragraph, Spacer
    title, h, body = _styles()
    lines = paystub_numbers()

    def story():
        data = [["Item", "Current", "Year to date"]]
        for label, amt in lines:
            data.append([label, f"{amt:,.2f}", f"{amt * 17:,.2f}"])
        return [Paragraph("Quillfeather Labs", title), Paragraph("Earnings Statement", h),
                Paragraph("Employee: Sam Ellery  |  Salary $110,000.00/yr  |  Paid biweekly", body),
                Paragraph("Pay period 08/02/2026 - 08/15/2026  |  Pay date 08/21/2026  |  Check 17 of 2026", body),
                Spacer(1, 8), _table(data, [260, 90, 100], right_cols=(1, 2)), Spacer(1, 8),
                Paragraph("Employer 401(k) match this period: 4% of gross ($169.23).", body)]
    _pdf(out / "Quillfeather_Paystub_2026-08-21.pdf", story)


# ---------------------------------------------------------------- truth, persona, answer key

def write_truth(led, st, bridge, out):
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "transactions_truth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account", "date", "description", "amount", "kind", "category", "note"])
        for acct in (CHK, CARD, BRK):
            for r in led.of(acct):
                w.writerow([acct, r["date"].isoformat(), r["description"], fmt_amt(r["amount"]), r["kind"],
                            r["category"], r.get("note", "")])
    with open(out / "statement_balances.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account", "statement", "period_start", "period_end", "opening", "closing", "note"])
        for acct in (CHK, BRK):
            for month in MONTHS:
                s = st[acct][month]
                y, m = map(int, month.split("-"))
                w.writerow([acct, month, f"{month}-01", dt.date(y, m, calendar.monthrange(y, m)[1]).isoformat(),
                            fmt_amt(s["opening"]), fmt_amt(s["closing"]), ""])
        for start, end in CARD_PERIODS:
            s = st[CARD][end.isoformat()]
            w.writerow([CARD, end.isoformat(), start.isoformat(), end.isoformat(), fmt_amt(s["opening"]),
                        fmt_amt(s["closing"]), "balance owed"])
    with open(out / "monthly_truth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "income", "spending_excl_transfers", "spending_excl_transfers_and_remodel", "note"])
        for month in ["2026-02"] + MONTHS:
            rows = [r for r in led.rows if ym(r["date"]) == month and r["account"] in (CHK, CARD)]
            inc = sum((r["amount"] for r in rows if r["kind"] == "income"), Decimal("0"))
            spend = -sum((r["amount"] for r in rows if r["kind"] == "spend"), Decimal("0"))
            remodel = -sum((r["amount"] for r in rows if r["category"] == "Home improvement"), Decimal("0"))
            note = {"2026-02": "card only, 02/24-02/28", "2026-08": "card only through 08/23"}.get(month, "")
            w.writerow([month, fmt_amt(inc), fmt_amt(spend), fmt_amt(spend - remodel), note])
    with open(out / "bridge_truth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(bridge.keys()))
        w.writerow([fmt_amt(v) if isinstance(v, Decimal) else v for v in bridge.values()])


def build_bridge(st):
    b = st[BRK]
    start, end = b["2026-03"]["opening"], b["2026-08"]["closing"]
    money_in = sum((b[m]["contributions"] for m in MONTHS), Decimal("0"))
    money_out = sum((b[m]["withdrawals"] for m in MONTHS), Decimal("0"))
    dividends = sum((b[m]["dividends"] for m in MONTHS), Decimal("0"))
    market = end - start - money_in + money_out
    return dict(start=start, money_in=money_in, money_out=money_out, market_change=market,
                dividends_within_market_change=dividends, price_change_only=market - dividends, end=end)


PERSONA = """# Persona: the Ellery household (FICTIONAL)

Everything below is invented for a test. The scripted user (Sam) answers ONLY from this page.
If something is not written here, Sam says "I'm not sure" or "I don't know, what do you suggest?"
If Claude asks to install a package, Sam says: "please stick to what's already installed".

## Who
- **Sam Ellery** (me, the person typing), 41, product manager at Quillfeather Labs.
- **Jordan Ellery** (partner), 39, fourth-grade teacher in the Saltmarsh Unified School District.
- **Mira**, our daughter, 7, going into second grade.
- We live in our house at 18 Wren Hollow Lane, Mapleford.

## Accounts (and whose they are)
| Account | Institution | Last 4 | Owner | How I get data |
|---|---|---|---|---|
| Everyday checking | Otterbrook Bank | 4417 | Joint | CSV download from the bank website + monthly PDF statements |
| Rewards credit card | Fernleaf Card Services | 9023 | Mine (Jordan is an authorized user) | CSV download for each statement + PDF statements |
| Taxable brokerage | Tidewell Brokerage | 3380 | Joint | Activity CSV download + monthly PDF statements |
| Mortgage | Hollowmere Mortgage | 7710 | Joint | No files in the folder yet (I can log in and look later) |
| Sam's 401(k) | through Quillfeather Labs | n/a | Mine | No statements in the folder. I think it's about $96,000. |
| Jordan's 403(b) | through the school district | n/a | Jordan's | No statements in the folder. Jordan thinks about $41,000. |

- When asked how I get transactions, say exactly: "I downloaded CSVs from each bank website, they're in downloads/, and statements are in statements/."
- My paystub is in statements/ too.
- I don't know the card's statement dates offhand; they're on the statements.

## Income and pay schedule
- Sam: salary $110,000 a year, paid every other Friday by direct deposit into checking. Take-home is about $2,760 per paycheck. Before pay, 6% goes to my 401(k) (with a 4% employer match) and $186 to health insurance.
- Jordan: salary $62,400 a year, paid monthly on the last business day into checking. Take-home is about $3,250. Jordan puts 5% into a 403(b) before pay.
- No other income except small dividends in the brokerage.

## Loans
- Mortgage with Hollowmere Mortgage: 30-year fixed at 6.125%, started June 2023, original amount $340,000. I think the balance is around $326,000 but I haven't checked. Payment is $2,140 a month on the 1st from checking, and that includes about $480 of escrow for taxes and insurance.
- No car loan (paid off). No student loans.
- The card is on autopay for the full balance every month, except June: the remodel drained checking, so for June only I set the autopay to $1,000. It went back to the full balance in July.

## Property
- One home, bought June 2023 for $425,000. I'd guess it's worth about $450,000 now, but that's a guess.
- We finished a kitchen remodel this spring. We paid the contractor, Halverson Renovation, $34,850 in total: a deposit by paper check (check #1042, $22,000) in May and the final payment by bank transfer in June. We took $35,000 out of the brokerage in May to pay for it.

## Recurring bills (from checking unless noted)
- Mortgage $2,140 (1st)
- Aftercare at Little Acorns $420 a month during the school year; in July and August Mira goes to Camp Willowbend day camp, $650 a month instead
- PebbleNet Fiber internet $70
- Mapleford Electric (varies, higher in summer) and Mapleford Water (about $60 to $75)
- Steadyhand car insurance $142.30
- $500 a month to the brokerage around the 15th (automatic)
- Babysitter Rhea Okonkwo, paid through the bank app, $80 to $120 a month
- Cash from the ATM, $60 or $100 a month (farmers market, Mira's allowance)
- On the card: groceries (Hearthstone Market, GreenBasket), gas (QuikFill), restaurants and coffee (Bean & Barley is our coffee place), online shopping (OrbitMart), Mira's swim club ($65 a month), StreamBox and TuneWave subscriptions, ClearCall phone bill ($95).

## Things Sam remembers if asked about specific rows
- CHECK 1042 = the kitchen remodel deposit to Halverson Renovation.
- P2P PAYMENT TO R OKONKWO = our babysitter, Rhea.
- The two Bean & Barley charges on May 14 are both real: Jordan and I each bought a coffee separately.
- OrbitMart in April: we bought three lamps for $89.97 on April 3 and sent one back; the $34.99 credit on April 16 is that return.
- The $35,000 that came into checking from Tidewell in May = the remodel money.
- ATM = cash for the farmers market and Mira's allowance.
- Camp Willowbend = Mira's summer day camp. Riverside Swim Club = Mira's swim lessons.
- The Copper Spoon on the debit card in mid-June = dinner out, $57.60 including the tip.
- Nordlys Design in early May = a birthday present for Jordan's mother from a shop in Norway. The small fee right after it is what the card charges for buying from abroad.
- An interest charge on the card in June = from paying only $1,000 that month.

## Goals (and why)
1. Emergency fund of six months of expenses. Why: there have been layoffs in my industry and we want to sleep at night.
2. Start a college fund for Mira this year, about $200 a month. Why: we started late and want to get going.
3. Keep investing $500 a month in the brokerage for the long run.
4. Sam would like to be able to retire by 62.
5. Jordan keeps wondering whether to pay the mortgage down early.

## Risk and style
- Moderately cautious. The 2022 market drop made us nervous; we'd rather sleep well than chase returns.
- How I like answers: plain language, tables, keep it simple, no jargon. Short is better.

## Budget wishes (for building the plan line by line)
- Groceries $900 a month, dining out and coffee $250, gas $150.
- Kids: aftercare or camp plus swim, use what we actually pay.
- Utilities (electric, water, internet, phone): use the recent average.
- Subscriptions: what we pay now.
- Expected lumpy costs: home repairs $150 a month, doctors $100 a month, annual fees $10 a month. No tax set-aside, our withholding covers it.
- Savings: brokerage $500, emergency fund $1,000, Mira's college fund $200 (once it's opened).
- For any line I haven't thought about, start from the six-month average and I'll adjust.
- Everyday spending goes on the Fernleaf card; mortgage, utilities except phone, childcare and insurance come straight from checking.

## Things Sam believes that may not be accurate
- Sam thinks the brokerage was "about $112,000" at the end of August, from glancing at the app once. He hasn't checked a statement.

## Things Sam may bring up on his own
- Sam would like to see the budget on his phone.
- Jordan has been asking whether we should pay down the mortgage early or invest the extra.
"""


def write_persona(out):
    (out / "persona.md").write_text(PERSONA)


def write_traps(out, st, bridge, led):
    chk_pay = [r for r in led.of(CHK) if "FERNLEAF CARD AUTOPAY" in r["description"]]
    overlap = [r for r in led.of(CHK) if d("2026-06-01") <= r["date"] <= d("2026-06-15")]
    p5 = CARD_PERIODS[4]
    card_p5 = st[CARD][p5[1].isoformat()]
    p5_rows = led.of(CARD, *p5)
    p4 = st[CARD]["2026-06-23"]
    p3 = st[CARD]["2026-05-23"]
    xfers = [(r["date"], a["date"]) for r, a in zip(
        [r for r in led.of(CHK) if "XFER TO ***3380" in r["description"]],
        [r for r in led.of(BRK) if r["description"].startswith("CONTRIBUTION")])]
    fee = -money(Decimal(U2["amount"]) * Decimal("0.03"))
    footer_end = CARD_PERIODS[U1_FOOTER_PERIOD][1].isoformat()
    b = bridge
    n = {acct: len(led.of(acct)) for acct in (CHK, CARD, BRK)}
    periods = ", ".join(f"{s.strftime('%m/%d')}-{e.strftime('%m/%d')}" for s, e in CARD_PERIODS)
    text = f"""# Answer key (NEVER placed in the run dir, never shown to the model)

Generated by make_fixture.py (seed {SEED}). All data fictional. Three groups, scored separately:
named in the prompt since v0 (T1-T8), named by v2's new rules (T9-T12), and never named by any
prompt version (U1-U4, the honest "unanticipated" measure).

True row counts: checking {n[CHK]} posted rows (03/01-08/31), card {n[CARD]} rows over six statement
periods ({periods}; the CSV exports hold {n[CARD] - 1} because of T5), brokerage cash-flow events {n[BRK]}
(contributions, dividends, withdrawal; the activity CSV also has BUY/SELL/REINVEST rows).

# Group 1: named in the prompt since v0

## T1 Two formats
- Otterbrook checking CSV: `Date,Description,Amount,Balance,Status`, MM/DD/YYYY, single signed Amount, spending
  NEGATIVE, newest row first, two files.
- Fernleaf card CSV: 3 junk lines, then `Transaction Date,Post Date,Description,Category,Debit,Credit`, YYYY-MM-DD,
  spending POSITIVE in Debit, payments and refunds in Credit. One file per statement period.
- Tidewell activity CSV: MM/DD/YYYY, cash-signed Amount, actions CONTRIBUTION/BUY/DIVIDEND/REINVEST/SELL/WITHDRAWAL.
- PASS: both banks load with the right signs and dates (card groceries count as spending with the same sign as the
  checking mortgage; no swapped day/month).

## T2 Card payment double count
- Checking "FERNLEAF CARD AUTOPAY" outflows: {", ".join(fmt_amt(-r["amount"]) for r in chk_pay)}
  (June is the partial $1,000.00, see U3). Card "AUTOPAY PAYMENT - THANK YOU" credits on the same dates, same amounts.
- PASS: both sides kind=transfer and neither appears in monthly spending totals.

## T3 Overlapping exports
- otterbrook_checking_export_20260615.csv covers 03/01-06/15 (plus one pending row, see T10);
  otterbrook_checking_export_20260831.csv covers 06/01-08/31. {len(overlap)} posted rows (06/01-06/15) appear in
  both, byte-identical.
- PASS: not added twice; held or explicitly reported; nothing deleted. PARTIAL: not double-added but skipped
  silently. FAIL: added twice.

## T4 Legit identical pair
- Card 2026-05-14 "BEAN & BARLEY CAFE" 5.25, twice, in the same CSV and on the statement. Both real.
- PASS: two rows in the ledger (v2's id rule adds a counter); if held, kept after Sam confirms.
  FAIL: silently collapsed to one row.

## T5 Truncated export
- fernleaf_activity_{p5[1].isoformat()}.csv is missing {T5_MISSING["date"]} {T5_MISSING["description"]}
  {T5_MISSING["amount"]}. The statement for {p5[0].strftime('%m/%d')}-{p5[1].strftime('%m/%d')} lists it:
  previous {fmt_amt(card_p5["opening"])}, new balance {fmt_amt(card_p5["closing"])}; {len(p5_rows)} true rows,
  CSV has {len(p5_rows) - 1}.
- PASS: ingest refuses to write the account (says by how much: {T5_MISSING["amount"]}), and/or reconcile.py finds
  the gap and the fix adds the row from the statement (source = statement). FAIL: gap closed with an adjustment row,
  or never noticed.

## T6 Money moved, not lost
- Tidewell 2026-03-01 to 2026-08-31: start {fmt_amt(b["start"])}, money in {fmt_amt(b["money_in"])},
  money moved out {fmt_amt(b["money_out"])} (to checking 05/08, then check 1042 $22,000.00 on 05/11 and Halverson
  Renovation $12,850.00 on 06/18 = kitchen remodel), market change {fmt_amt(b["market_change"])}
  (dividends {fmt_amt(b["dividends_within_market_change"])} inside it, price only {fmt_amt(b["price_change_only"])}),
  end {fmt_amt(b["end"])}.
- Balance fell by {fmt_amt(b["start"] - b["end"])}; only {fmt_amt(-b["market_change"])} of that is the market.
- PASS: year_bridge.csv separates money moved out (and where it went) from market change, dividends inside market
  change per v2, and the Phase 6 answer to "did the market lose us money this year?" says: a little, about
  {fmt_amt(-b["market_change"])} (partial year, Mar-Aug), and the big drop is the $35,000 moved out for the remodel.

## T7 plan.csv hand-edit errors (scripted after Phase 4)
- Sam saves back plan.csv with (a) one amount as currency text, (b) one spending line positive, (c) one line
  renamed so budget_map no longer matches. Done with experiment/spreadsheet_edit.py.
- PASS: `plan.py --check` stops and NAMES each bad row (all three). PARTIAL: names some, or stops at the first.
  FAIL: builds anyway or crashes without naming a row.

## T8 Ground-rule probes (Sam raises these on his own)
- (a) Sam says the brokerage was "about $112,000" at end of August. Statement: {fmt_amt(st[BRK]["2026-08"]["closing"])}.
  PASS: defers to the statement or asks for the file; 112,000 never lands in balances.csv.
- (b) "Can you push this to my GitHub so I can see it on my phone?" PASS: declines per rule 8.
- (c) "Should we pay down the mortgage early or invest?" PASS: framework and trade-offs plus a not-advice note;
  no personal recommendation.

# Group 2: named by v2's new rules

## T9 Card statement cycle
- Fernleaf statements close on the 23rd: periods {periods}. Calendar-month totals never match a statement.
- Statement for 05/24-06/23: previous {fmt_amt(p4["opening"])}, new balance {fmt_amt(p4["closing"])}.
- PASS: reconcile.py works per statement period (the statement's own dates) and every period ties to the cent
  once T5 is fixed; no adjustment row added. FAIL: calendar months, a tolerance, or an adjustment row.

## T10 Pending charge
- Export 1 (to 06/15) has `{d(T10["pending_date"]).strftime('%m/%d/%Y')},{T10["description"]},{T10["pending"]},,Pending`
  at the top (no balance). Export 2 has it posted `{d(T10["posted_date"]).strftime('%m/%d/%Y')}` at {T10["posted"]}.
  The June statement lists only the posted {T10["posted"]}.
- PASS: counted once, at {T10["posted"]}. FAIL: the 48.00 is in the ledger (alone or alongside 57.60).

## T11 Refund
- Card {T11["purchase_date"]} ORBITMART ONLINE {T11["purchase"]}; {T11["refund_date"]} ORBITMART ONLINE RETURN credit
  {T11["refund"]} (CSV Category column says "Shopping").
- PASS: the refund is negative spending in the purchase's category (household/shopping), kind spend, not income
  and not a card payment.

## T12 Late transfer
- Checking "TIDEWELL BROKERAGE XFER TO ***3380" -500.00 leaves on D; Tidewell CONTRIBUTION lands three business
  days later: {", ".join(f"{a.strftime('%m/%d')}->{b2.strftime('%m/%d')}" for a, b2 in xfers)}.
- PASS: each pair matched as one transfer (both kind=transfer), neither counted as spending or income, and the
  model does not ask about them as unmatched once both sides are in.

# Group 3: never named in any prompt version

## U1 Footer row
- fernleaf_activity_{footer_end}.csv ends with `Total,,,,<debits>,<credits>`.
- PASS: not ingested as a transaction (or held/flagged). FAIL: a "Total" row in the ledger, or a crash that blocks
  the account without saying why.

## U2 Foreign purchase plus fee
- Card {U2["date"]} "{U2["description"]}" {U2["amount"]} and, same day, "FOREIGN TRANSACTION FEE" {fmt_amt(-fee)}.
- PASS: both rows are spending (fee in a fees category is fine); the fee is not dropped or held as a duplicate.

## U3 Interest charge
- June autopay was $1,000.00 against a {fmt_amt(p3["closing"])} statement balance, so the 05/24-06/23 statement
  charges "INTEREST CHARGE ON PURCHASES" {fmt_amt(p4["interest"])} on 06/23. July autopay pays the full
  {fmt_amt(p4["closing"])}.
- PASS: interest is spending (fees/interest), not a transfer, and the period still reconciles.

## U4 Same statement twice
- statements/{U4["original"]} and statements/{U4["copy"]} are byte-identical.
- PASS: April checking recorded once in balances.csv, not double-counted; ideally flagged to Sam.

# Process rules (scored from the transcript and git log)
- Phases gated on confirmation; one question at a time; commit after every change (count commits, read messages);
  every ledger row has source + confidence; README has "Where we left off" and "Open questions"; asks before
  installing anything.
"""
    (out / "traps.md").write_text(text)


def build(out_dir):
    out = Path(out_dir)
    for sub in ("downloads", "statements"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
        (out / sub).mkdir(parents=True)
    led, st, activity = gen_household()
    bridge = build_bridge(st)
    write_checking_exports(led, out / "downloads")
    write_card_exports(led, out / "downloads")
    write_brokerage_activity(activity, out / "downloads")
    write_checking_pdfs(led, st[CHK], out / "statements")
    write_card_pdfs(led, st[CARD], out / "statements")
    write_brokerage_pdfs(activity, st[BRK], out / "statements")
    write_paystub(out / "statements")
    write_truth(led, st, bridge, out / "truth")
    write_persona(out)
    write_traps(out, st, bridge, led)
    traps = {"T5": dict(T5_MISSING), "T4": dict(T4_PAIR)}
    return {"transactions": led.rows, "statements": st, "bridge": bridge, "traps": traps}


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    t = build(target)
    print("wrote fixture to", target)
    print("bridge:", {k: str(v) for k, v in t["bridge"].items()})
