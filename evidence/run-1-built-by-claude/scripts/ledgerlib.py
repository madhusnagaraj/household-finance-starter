"""Shared helpers for the household ledger scripts.

Standard library only. All money is handled as Decimal and kept to the cent.
"""
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation

CENT = Decimal("0.01")

LEDGER_COLS = [
    "id", "account", "date", "amount", "description", "category", "kind",
    "class_by", "source", "also_in", "confidence", "recon", "recon_basis",
    "pair_id", "txn_date", "bank_category", "bank_balance",
    "action", "symbol", "quantity", "price",
]
RULE_COLS = ["rule_id", "account", "field", "pattern", "category", "kind",
             "pair_with", "added_by", "added_on", "note"]
OVERRIDE_COLS = ["id", "category", "kind", "pair_with", "pair_waiver", "note",
                 "decided_by", "decided_on"]
CORRECTION_COLS = ["account", "date", "txn_date", "amount", "description", "bank_category",
                   "counter", "source", "reason", "approved_by", "approved_on"]
COVERAGE_COLS = ["account", "covered_from", "covered_to", "basis"]
BALANCE_COLS = ["as_of", "account", "amount", "source", "confidence"]
HELD_COLS = ["held_id", "account", "date", "amount", "description", "source",
             "matches_id", "matches_source", "reason", "decision",
             "decided_by", "decided_on"]

# spend = money out for living (refunds are negative spend, never income)
# transfer = moves between our own accounts, loan = loan payments,
# invest = activity inside the brokerage (buys, sells, dividends, reinvestments),
# unclassified = no rule yet.
KINDS = {"spend", "income", "transfer", "loan", "rental", "invest", "unclassified"}


class DataError(Exception):
    """Something in the data or a rule is wrong. Stop and show the user."""


def parse_money(text, decimal=".", thousands="", where=""):
    """Parse an amount to an exact Decimal with at most two decimal places.

    Returns None for an empty field.
    """
    t = (text or "").strip().replace("$", "").replace("+", "").replace(" ", "")
    if t == "":
        return None
    if thousands:
        t = t.replace(thousands, "")
    if decimal != ".":
        t = t.replace(decimal, ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise DataError(f"{where}: cannot read '{text}' as an amount")
    if d != d.quantize(CENT):
        raise DataError(f"{where}: '{text}' has more than two decimal places")
    return fmt_dec(d)


def fmt_dec(d):
    """Normalise a Decimal to exactly two places (and never '-0.00')."""
    d = d.quantize(CENT)
    return d + Decimal("0.00") if d == 0 else d


def money(d):
    """Decimal -> text with two decimals, e.g. '-48.00'."""
    return format(fmt_dec(Decimal(d)), "f")


def norm_desc(s):
    return " ".join((s or "").upper().split())


def make_id(account, date_iso, amount_text, desc, extra, counter):
    """Stable id when the bank gives none: account, date, amount and payee,
    plus a counter so two real identical charges stay two."""
    h = hashlib.sha1(
        "|".join([account, date_iso, amount_text, norm_desc(desc), extra]).encode("utf-8")
    ).hexdigest()[:8]
    return f"{account}-{date_iso.replace('-', '')}-{h}-{counter}"


def read_csv(path):
    path = str(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def write_csv(path, cols, rows):
    with open(str(path), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def load_json(path):
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)
