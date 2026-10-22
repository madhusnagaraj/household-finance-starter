"""Read the summary numbers off statement PDFs.

Uses the `pdftotext` tool that is already on this Mac (poppler). Nothing was
installed for this. Each parser also checks that the statement adds up by its
own summary; if it does not, we have misread it (or it is wrong) and we stop.
"""
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from ledgerlib import DataError, fmt_dec, parse_money


def pdf_text(path):
    exe = shutil.which("pdftotext")
    if not exe:
        raise DataError("pdftotext was not found. Ask Sam before installing anything.")
    out = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True)
    if out.returncode != 0:
        raise DataError(f"{path}: pdftotext failed: {out.stderr.strip()}")
    return out.stdout


def _us(s):
    return datetime.strptime(s, "%m/%d/%Y").date()


def _amount(text, label, path, flags=re.M):
    m = re.search(rf"^\s*{label}\s+[\$+]?(-?[\d,]+\.\d\d)\s*$", text, flags)
    if not m:
        raise DataError(f"{path}: could not find '{label}'")
    return parse_money(m.group(1), ".", ",", f"{path} {label}")


def _resolve(mmdd, start, end):
    """A statement line shows month/day only. Pick the year that puts it in or just before the period."""
    mo, dy = (int(x) for x in mmdd.split("/"))
    for y in sorted({start.year, end.year}):
        d = date(y, mo, dy)
        if start - timedelta(days=45) <= d <= end:
            return d
    raise DataError(f"cannot place {mmdd} inside {start} to {end}")


def parse_fernleaf(text, path):
    m = re.search(r"Billing period:\s*(\d\d/\d\d/\d{4})\s*-\s*(\d\d/\d\d/\d{4})", text)
    if not m:
        raise DataError(f"{path}: no billing period found")
    start, end = _us(m.group(1)), _us(m.group(2))
    s = {
        "kind": "fernleaf", "path": str(path), "start": start, "end": end,
        "prev": _amount(text, "Previous Balance", path),
        "payments": abs(_amount(text, "Payments", path)),
        "other_credits": abs(_amount(text, "Other Credits", path)),
        "purchases": _amount(text, "Purchases", path),
        "fees": _amount(text, "Fees Charged", path),
        "interest": _amount(text, "Interest Charged", path),
        "new": _amount(text, "New Balance", path),
    }
    s["self_check_diff"] = fmt_dec(
        s["new"] - (s["prev"] - s["payments"] - s["other_credits"]
                    + s["purchases"] + s["fees"] + s["interest"]))
    # Lines in the statement, converted to ledger signs (spending negative).
    lines = []
    for line in text.splitlines():
        t = re.match(r"^\s+(\d\d/\d\d)\s+(\d\d/\d\d)\s+(.+?)\s{2,}(-?[\d,]+\.\d\d)\s*$", line)
        if t:
            amt = parse_money(t.group(4), ".", ",", f"{path} line")
            lines.append({"txn_date": _resolve(t.group(1), start, end),
                          "date": _resolve(t.group(2), start, end),
                          "description": t.group(3).strip(), "amount": fmt_dec(-amt)})
    s["lines"] = lines
    return s


def parse_otterbrook(text, path):
    m = re.search(r"Statement period:\s*(\d\d/\d\d/\d{4})\s+through\s+(\d\d/\d\d/\d{4})", text)
    if not m:
        raise DataError(f"{path}: no statement period found")
    start, end = _us(m.group(1)), _us(m.group(2))

    def bal(label):
        mm = re.search(rf"^\s*{label}.*?\s+\$?(-?[\d,]+\.\d\d)\s*$", text, re.M)
        if not mm:
            raise DataError(f"{path}: could not find '{label}'")
        return parse_money(mm.group(1), ".", ",", f"{path} {label}")

    s = {"kind": "otterbrook", "path": str(path), "start": start, "end": end,
         "begin": bal("Beginning Balance"), "deposits": bal("Deposits and Additions"),
         "withdrawals": bal("Withdrawals and Subtractions"), "end_balance": bal("Ending Balance")}
    s["self_check_diff"] = fmt_dec(s["end_balance"] - (s["begin"] + s["deposits"] + s["withdrawals"]))
    lines = []
    for line in text.splitlines():
        t = re.match(r"^\s+(\d\d/\d\d)\s+(.+?)\s{2,}(-?[\d,]+\.\d\d)\s+(-?[\d,]+\.\d\d)\s*$", line)
        if t:
            lines.append({"date": _resolve(t.group(1), start, end), "description": t.group(2).strip(),
                          "amount": parse_money(t.group(3), ".", ",", f"{path} line"),
                          "balance": parse_money(t.group(4), ".", ",", f"{path} line")})
    s["lines"] = lines
    return s


def parse_tidewell(text, path):
    m = re.search(r"Statement for (\w+) (\d{4}) \(period ending (\d\d/\d\d/\d{4})\)", text)
    if not m:
        raise DataError(f"{path}: no statement period found")
    end = _us(m.group(3))
    start = datetime.strptime(f"{m.group(1)} 1 {m.group(2)}", "%B %d %Y").date()

    def val(label):
        mm = re.search(rf"^\s*{label}\s+\$?(-?[\d,]+\.\d\d)\s*$", text, re.M)
        if not mm:
            raise DataError(f"{path}: could not find '{label}'")
        return parse_money(mm.group(1), ".", ",", f"{path} {label}")

    holdings = {}
    for mm in re.finditer(r"^\s*([A-Z]{3,6})\s+.*?\s+([\d,]+\.\d{3})\s+([\d,]+\.\d\d)\s+([\d,]+\.\d\d)\s*$", text, re.M):
        holdings[mm.group(1)] = {"quantity": Decimal(mm.group(2).replace(",", "")),
                                 "price": parse_money(mm.group(3), ".", ",", path),
                                 "value": parse_money(mm.group(4), ".", ",", path)}
    cash = re.search(r"^\s*CASH\s+Cash sweep\s+([\d,]+\.\d\d)\s*$", text, re.M)
    if not cash:
        raise DataError(f"{path}: could not find the cash sweep line")
    s = {"kind": "tidewell", "path": str(path), "start": start, "end": end,
         "begin_value": val("Beginning value"), "contributions": val("Contributions"),
         "withdrawals": val("Withdrawals"), "dividends": val("Dividends"),
         "market_change": val("Change in market value"), "end_value": val("Ending value"),
         "cash": parse_money(cash.group(1), ".", ",", path), "holdings": holdings}
    s["self_check_diff"] = fmt_dec(
        s["end_value"] - (s["begin_value"] + s["contributions"] + s["withdrawals"]
                          + s["dividends"] + s["market_change"]))
    s["holdings_diff"] = fmt_dec(
        s["end_value"] - (sum((h["value"] for h in holdings.values()), Decimal("0")) + s["cash"]))
    return s


def parse_paystub(text, path):
    m = re.search(r"Pay period\s+(\d\d/\d\d/\d{4})\s*-\s*(\d\d/\d\d/\d{4})\s*\|\s*Pay date\s+(\d\d/\d\d/\d{4})", text)
    if not m:
        raise DataError(f"{path}: no pay period found")
    items = {}
    for line in text.splitlines():
        t = re.match(r"^\s*(.+?)\s{2,}(-?[\d,]+\.\d\d)\s+(-?[\d,]+\.\d\d)\s*$", line)
        if t:
            items[t.group(1).strip()] = (parse_money(t.group(2), ".", ",", path), parse_money(t.group(3), ".", ",", path))
    gross = items.get("Gross pay")
    net = next((v for k, v in items.items() if k.startswith("Net pay")), None)
    if gross is None or net is None:
        raise DataError(f"{path}: could not find gross pay and net pay")
    deductions = {k: v[0] for k, v in items.items() if k != "Gross pay" and not k.startswith("Net pay")}
    match = re.search(r"match this period:\s*(\d+)% of gross \(\$([\d,]+\.\d\d)\)", text)
    s = {"kind": "paystub", "path": str(path), "start": _us(m.group(1)), "end": _us(m.group(2)),
         "pay_date": _us(m.group(3)), "gross": gross[0], "net": net[0], "deductions": deductions,
         "employer_match_pct": int(match.group(1)) if match else None,
         "employer_match": parse_money(match.group(2), ".", ",", path) if match else None}
    s["self_check_diff"] = fmt_dec(s["net"] - (s["gross"] + sum(deductions.values(), Decimal("0"))))
    return s


def parse_statement(path):
    text = pdf_text(path)
    if "Earnings Statement" in text:
        return parse_paystub(text, path)
    if "Fernleaf Card Services" in text:
        return parse_fernleaf(text, path)
    if "Otterbrook Bank" in text:
        return parse_otterbrook(text, path)
    if "Tidewell Brokerage" in text:
        return parse_tidewell(text, path)
    return {"kind": "other", "path": str(path)}


def load_statements(directory):
    """Parse every statement PDF. Returns (statements, notes).

    A second copy of the same statement is noted and ignored; two statements
    with the same period but different numbers stop the run.
    """
    directory = Path(directory)
    found, notes = {}, []
    if not directory.is_dir():
        return [], notes
    for p in sorted(directory.glob("*.pdf")):
        s = parse_statement(p)
        if s["kind"] == "other":
            notes.append(f"{p.name}: not a bank, card or brokerage statement, skipped for ledger checks")
            continue
        if s["self_check_diff"] != 0 or s.get("holdings_diff", 0) != 0:
            raise DataError(
                f"{p.name}: the statement does not add up by its own summary "
                f"(off by {s['self_check_diff']}; holdings off by {s.get('holdings_diff', 0)}). "
                "Either I misread it or it is wrong. Stopping.")
        key = (s["kind"], s["start"], s["end"])
        if key in found:
            a = {k: v for k, v in found[key].items() if k != "path"}
            b = {k: v for k, v in s.items() if k != "path"}
            if a == b:
                first, second = Path(found[key]["path"]), p
                found[key]["path"] = str(min(first, second, key=lambda x: (len(x.name), x.name)))  # cite the cleaner name
                notes.append(f"{first.name} and {second.name} are exact copies of each other; one is used, both left in place")
                continue
            raise DataError(f"{p.name} and {Path(found[key]['path']).name} cover the same period but differ")
        found[key] = s
    return sorted(found.values(), key=lambda x: (x["kind"], x["start"])), notes
