#!/usr/bin/env python3
"""Load raw bank/card/brokerage CSV exports into ledger/transactions.csv.

What it does, in order:
  1. Reads each export through the per-account setup in scripts/config.json.
  2. Keeps only posted rows (pending rows change before they post).
  3. Gives every row a stable id (the bank's own if there is one; none of ours
     do, so account + date + amount + payee + a counter, so two real identical
     charges stay two).
  4. Skips rows already in the ledger, HOLDS possible duplicates in
     ledger/held.csv for the user, and never deletes anything.
  5. Checks each account against a total this script did not compute
     (the bank's running balance, or the statement's own numbers). If it does
     not match to the cent, that account is NOT written and the gap is shown.
  6. Classifies with ledger/rules.csv; ledger/overrides.csv always wins.
  7. Pairs transfers between our own accounts and lists any without a partner.

Running it twice on the same files changes nothing.
Standard library only (statement PDFs are read with the pdftotext tool).
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
import statements as S  # noqa: E402
from ledgerlib import DataError, money  # noqa: E402

ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- reading the exports

def load_config(root):
    with open(Path(root) / "scripts" / "config.json", encoding="utf-8") as f:
        return json.load(f)


def parse_file(src, path, root):
    rel = str(path.relative_to(root))
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    hi = next((i for i, l in enumerate(lines) if l.startswith(src["header_starts_with"])), None)
    if hi is None:
        raise DataError(f"{rel}: no header row starting '{src['header_starts_with']}'")
    period = None
    if src.get("period_line_regex"):
        for l in lines[:hi]:
            m = re.search(src["period_line_regex"], l)
            if m:
                period = tuple(datetime.strptime(g, src["period_date_format"]).date() for g in m.groups())
        if period is None:
            raise DataError(f"{rel}: statement period line not found above the header")
    cols, dec, thou = src["columns"], src.get("decimal", "."), src.get("thousands", "")
    reader = csv.DictReader(lines[hi:], delimiter=src.get("delimiter", ","))
    missing = [c for c in cols.values() if c not in (reader.fieldnames or [])]
    if missing:
        raise DataError(f"{rel}: expected columns not found: {missing}")
    rows, pending, trailer, failures = [], 0, None, []
    for n, rec in enumerate(reader, start=hi + 2):
        where = f"{rel} line {n}"
        vals = [(v or "").strip() for v in rec.values() if not isinstance(v, list)]
        if not any(vals):
            continue
        if src.get("trailer_first_column") and vals[0] == src["trailer_first_column"]:
            trailer = rec
            continue
        if "status" in cols and (rec[cols["status"]] or "").strip() != src["posted_status"]:
            pending += 1
            continue
        raw_date = (rec[cols["date"]] or "").strip()
        if raw_date == "":
            pending += 1  # no post date yet
            continue
        try:
            d = datetime.strptime(raw_date, src["date_format"]).date()
        except ValueError:
            raise DataError(f"{where}: date '{raw_date}' does not match {src['date_format']}")
        if "amount" in cols:
            a = L.parse_money(rec[cols["amount"]], dec, thou, where)
            if a is None:
                raise DataError(f"{where}: empty amount")
            if src["spending_is"] == "positive":
                a = -a
        else:
            debit = L.parse_money(rec[cols["debit"]], dec, thou, where)
            credit = L.parse_money(rec[cols["credit"]], dec, thou, where)
            if debit is None and credit is None:
                raise DataError(f"{where}: neither a debit nor a credit")
            a = (credit if credit is not None else ZERO) - (debit if debit is not None else ZERO)
        row = {"line": n, "date": d.isoformat(), "amount": money(a),
               "description": (rec[cols["description"]] or "").strip(),
               "txn_date": "", "bank_category": "", "bank_balance": "",
               "action": "", "symbol": "", "quantity": "", "price": ""}
        if "txn_date" in cols and (rec[cols["txn_date"]] or "").strip():
            row["txn_date"] = datetime.strptime(rec[cols["txn_date"]].strip(), src["date_format"]).date().isoformat()
        if "bank_category" in cols:
            row["bank_category"] = (rec[cols["bank_category"]] or "").strip()
        for k in ("action", "symbol", "quantity", "price"):
            if k in cols:
                row[k] = (rec[cols[k]] or "").strip()
        if "balance" in cols:
            b = L.parse_money(rec[cols["balance"]], dec, thou, where)
            if b is None:
                raise DataError(f"{where}: posted row has no running balance")
            row["bank_balance"] = money(b)
        rows.append(row)

    f = {"src": src, "account": src["account"], "path": path, "rel": rel, "rows": rows,
         "pending": pending, "period": period, "opening": None, "closing": None,
         "failures": failures,
         "min_date": min((r["date"] for r in rows), default=None),
         "max_date": max((r["date"] for r in rows), default=None)}

    # Check 1: the bank's own running balance must chain row to row.
    if "balance" in cols and rows:
        seq = rows if src.get("order") == "oldest_first" else rows[::-1]
        for prev, cur in zip(seq, seq[1:]):
            expect = Decimal(prev["bank_balance"]) + Decimal(cur["amount"])
            if expect != Decimal(cur["bank_balance"]):
                failures.append({"where": f"{rel} line {cur['line']}", "check": "running balance chain",
                                 "expected": money(expect), "got": cur["bank_balance"],
                                 "diff": money(Decimal(cur["bank_balance"]) - expect),
                                 "note": f"after {cur['date']} {cur['description']} {cur['amount']}"})
        f["opening"] = Decimal(seq[0]["bank_balance"]) - Decimal(seq[0]["amount"])
        f["closing"] = Decimal(seq[-1]["bank_balance"])

    # Check 2: totals printed in the file itself (a total we did not compute).
    if trailer is not None and "debit" in cols:
        for key, label in (("debit", "debits"), ("credit", "credits")):
            printed = L.parse_money(trailer[cols[key]], dec, thou, rel)
            ours = ZERO
            for r in rows:
                amt = Decimal(r["amount"])
                if key == "debit" and amt < 0:
                    ours += -amt
                if key == "credit" and amt > 0:
                    ours += amt
            if printed is not None and printed != ours:
                failures.append({"where": rel, "check": f"file's own total of {label}",
                                 "expected": money(printed), "got": money(ours),
                                 "diff": money(ours - printed), "note": ""})

    # Check 3: every row falls inside the file's own stated period.
    if period:
        for r in rows:
            if not (period[0].isoformat() <= r["date"] <= period[1].isoformat()):
                failures.append({"where": f"{rel} line {r['line']}", "check": "row inside the file's period",
                                 "expected": f"{period[0]} to {period[1]}", "got": r["date"],
                                 "diff": "", "note": r["description"]})
    return f


def load_corrections(root):
    out = []
    for i, c in enumerate(L.read_csv(Path(root) / "ledger" / "corrections.csv"), start=2):
        if not (c.get("account") or "").strip():
            continue
        where = f"ledger/corrections.csv line {i}"
        try:
            datetime.strptime(c["date"], "%Y-%m-%d")
            int(c["counter"] or 1)
        except ValueError:
            raise DataError(f"{where}: bad date or counter")
        c["amount"] = money(L.parse_money(c["amount"], where=where))
        if not (c.get("approved_by") or "").strip() or not (c.get("approved_on") or "").strip():
            raise DataError(f"{where}: a correction needs approved_by and approved_on")
        c["counter"] = int(c["counter"] or 1)
        out.append(c)
    return out


def corrections_as_files(account, corr):
    """Approved rows read off a statement behave like one more small file."""
    files = []
    for source in sorted({c["source"] for c in corr}):
        rows = [{"line": 0, "date": c["date"], "amount": c["amount"], "description": c["description"],
                 "txn_date": c.get("txn_date", ""), "bank_category": c.get("bank_category", ""),
                 "bank_balance": "", "action": "", "symbol": "", "quantity": "", "price": "",
                 "counter": c["counter"]} for c in corr if c["source"] == source]
        files.append({"src": {}, "account": account, "path": Path(source), "rel": source, "rows": rows,
                      "pending": 0, "period": None, "opening": None, "closing": None, "failures": [],
                      "min_date": min(r["date"] for r in rows), "max_date": max(r["date"] for r in rows),
                      "pseudo": True})
    return files


def find_files(root, cfg):
    files = []
    for ex in sorted(p for p in (Path(root) / "exports").glob("*") if p.is_dir()):
        for src in cfg["sources"]:
            for p in sorted(ex.glob(src["glob"])):
                files.append(parse_file(src, p, Path(root)))
    files.sort(key=lambda f: (f["rel"].split("/")[1], f["path"].name))
    return files


# --------------------------------------------------------------------------- merging into the ledger

def new_ledger_row(account, rid, r, f):
    row = {c: "" for c in L.LEDGER_COLS}
    row.update({"id": rid, "account": account, "date": r["date"], "amount": r["amount"],
                "description": r["description"], "kind": "unclassified", "source": f["rel"],
                "confidence": "exact", "recon": "unreconciled", "txn_date": r["txn_date"],
                "bank_category": r["bank_category"], "bank_balance": r["bank_balance"],
                "action": r["action"], "symbol": r["symbol"], "quantity": r["quantity"], "price": r["price"]})
    return row


def possible_duplicate(work, account, rid, r, f, file_ids, days):
    day = datetime.strptime(r["date"], "%Y-%m-%d").date()
    for c in sorted(work.values(), key=lambda x: (x["date"], x["id"])):
        if c["account"] != account or c["id"] == rid or c["id"] in file_ids:
            continue
        if c["amount"] != r["amount"] or L.norm_desc(c["description"]) != L.norm_desc(r["description"]):
            continue
        if f["rel"] == c["source"] or f["rel"] in c["also_in"].split(";"):
            continue  # same file: identical rows there are two real charges
        if abs((datetime.strptime(c["date"], "%Y-%m-%d").date() - day).days) <= days:
            return c
    return None


def merge_account(account, afiles, existing, held, dup_days):
    work = {r["id"]: dict(r) for r in existing}
    stats, newly_held, failures = Counter(), [], []
    for f in afiles:
        counters, items = Counter(), []
        for r in f["rows"]:
            extra = "|".join(r.get(k, "") for k in f["src"].get("id_extra", []))
            key = (r["date"], r["amount"], L.norm_desc(r["description"]), extra)
            counters[key] += 1
            n = int(r["counter"]) if r.get("counter") else counters[key]
            items.append((L.make_id(account, r["date"], r["amount"], r["description"], extra, n), r))
        file_ids = {rid for rid, _ in items}
        for rid, r in items:
            stats["read"] += 1
            if rid in work:
                w = work[rid]
                stats["already"] += 1
                if w["source"] != f["rel"]:
                    also = set(filter(None, w["also_in"].split(";")))
                    also.add(f["rel"])
                    w["also_in"] = ";".join(sorted(also))
                    if w["bank_balance"] and r["bank_balance"] and w["bank_balance"] != r["bank_balance"]:
                        failures.append({"where": f["rel"], "check": "same row, same balance in both files",
                                         "expected": w["bank_balance"], "got": r["bank_balance"],
                                         "diff": money(Decimal(r["bank_balance"]) - Decimal(w["bank_balance"])),
                                         "note": f"{r['date']} {r['description']}"})
                continue
            h = held.get(rid)
            if h is not None:
                if h["decision"] == "duplicate":
                    stats["held_dropped"] += 1
                    continue
                if h["decision"] != "add":
                    stats["held_open"] += 1
                    continue
            else:
                c = None if f.get("pseudo") else possible_duplicate(work, account, rid, r, f, file_ids, dup_days)  # an approved row is not a guess
                if c is not None:
                    held[rid] = {"held_id": rid, "account": account, "date": r["date"], "amount": r["amount"],
                                 "description": r["description"], "source": f["rel"], "matches_id": c["id"],
                                 "matches_source": c["source"], "decision": "", "decided_by": "", "decided_on": "",
                                 "reason": f"same amount and payee as {c['id']} (dated {c['date']}), "
                                           f"from a different file, within {dup_days} days"}
                    newly_held.append(rid)
                    stats["held_open"] += 1
                    continue
            work[rid] = new_ledger_row(account, rid, r, f)
            stats["new"] += 1
    return work, stats, newly_held, failures


# --------------------------------------------------------------------------- checks against totals we did not compute

def in_period(rows, start, end):
    return [r for r in rows if start.isoformat() <= r["date"] <= end.isoformat()]


def check_running_balance(afiles, work):
    files = [f for f in afiles if f["rows"] and not f.get("pseudo")]
    if not files:
        return [], "bank's running balance column", {}
    earliest = min(files, key=lambda f: (f["min_date"], f["max_date"]))
    latest = max(files, key=lambda f: (f["max_date"], f["min_date"]))
    got = earliest["opening"] + sum((Decimal(r["amount"]) for r in work.values()), ZERO)
    fails = []
    if got != latest["closing"]:
        fails.append({"where": "whole account", "check": "opening balance + all rows = last running balance",
                      "expected": money(latest["closing"]), "got": money(got),
                      "diff": money(got - latest["closing"]),
                      "note": f"from {earliest['rel']} to {latest['rel']}"})
    marks = {rid: ("yes", "bank running balance") for rid in work}
    return fails, "bank's running balance column", marks


def check_card(afiles, work, stmts):
    fails, notes, marks = [], [], {}
    cards = {(s["start"], s["end"]): s for s in stmts if s["kind"] == "fernleaf"}
    for f in afiles:
        if f.get("pseudo"):
            continue
        s = cards.get(f["period"])
        if s is None:
            notes.append(f"{f['path'].name}: no statement found for {f['period'][0]} to {f['period'][1]}; rows stay unreconciled")
            continue
        rows = in_period(work.values(), s["start"], s["end"])
        total = sum((Decimal(r["amount"]) for r in rows), ZERO)
        computed = s["prev"] - total  # the card balance grows when spending (negative amounts) is added
        if computed != s["new"]:
            ledger_lines = Counter((r["date"], L.norm_desc(r["description"]), r["amount"]) for r in rows)
            stmt_lines = Counter((l["date"].isoformat(), L.norm_desc(l["description"]), money(l["amount"])) for l in s["lines"])
            missing, seen = [], Counter()
            for l in s["lines"]:
                k = (l["date"].isoformat(), L.norm_desc(l["description"]), money(l["amount"]))
                seen[k] += 1
                if seen[k] > ledger_lines.get(k, 0):
                    missing.append({"account": f["account"], "date": k[0], "txn_date": l["txn_date"].isoformat(),
                                    "amount": k[2], "description": l["description"], "bank_category": "",
                                    "counter": seen[k], "source": s["path"]})
            fails.append({"where": f"statement {s['start']} to {s['end']} ({Path(s['path']).name})",
                          "missing_rows": missing,
                          "check": "previous balance minus rows = new balance on the statement",
                          "expected": money(s["new"]), "got": money(computed), "diff": money(s["new"] - computed),
                          "note": "", "statement_only": sorted((stmt_lines - ledger_lines).elements()),
                          "download_only": sorted((ledger_lines - stmt_lines).elements())})
        else:
            for r in rows:
                marks[r["id"]] = ("yes", f"statement {s['end']}")
    for s in cards.values():
        if s["start"] and not any(f["period"] == (s["start"], s["end"]) for f in afiles):
            notes.append(f"Statement {s['start']} to {s['end']} has no matching download yet")
    return fails, "each statement's previous and new balance", marks, notes


def check_brokerage(afiles, work, stmts):
    fails, notes, marks = [], [], {}
    tw = sorted((s for s in stmts if s["kind"] == "tidewell"), key=lambda s: s["start"])
    dates = [r["date"] for r in work.values()]
    if not dates:
        return fails, "each monthly statement", marks, notes
    dmin, dmax = min(dates), max(dates)
    prev = None
    for s in tw:
        if s["end"].isoformat() < dmin or s["start"].isoformat() > dmax:
            continue
        contiguous = prev is not None and prev["end"].year * 12 + prev["end"].month + 1 == s["end"].year * 12 + s["end"].month
        start = prev["end"] + timedelta(days=1) if contiguous else s["start"]
        rows = in_period(work.values(), start, s["end"])
        label = f"statement {start} to {s['end']}"
        bad = len(fails)

        def sum_action(name):
            return sum((Decimal(r["amount"]) for r in rows if r["action"] == name), ZERO)

        for name, stmt_val in (("CONTRIBUTION", s["contributions"]), ("WITHDRAWAL", s["withdrawals"]),
                               ("DIVIDEND", s["dividends"])):
            ours = sum_action(name)
            if ours != stmt_val:
                fails.append({"where": label, "check": f"{name.lower()}s total", "expected": money(stmt_val),
                              "got": money(ours), "diff": money(ours - stmt_val), "note": ""})
        flow = sum((Decimal(r["amount"]) for r in rows), ZERO)
        if contiguous:
            opening_cash = prev["cash"]
        else:
            opening_cash = s["cash"] - flow
            notes.append(f"{label}: opening cash is not on the statement, so it was worked out from the closing cash "
                         f"({money(opening_cash)}); this period's cash is not independently checked")
            if opening_cash < 0:
                fails.append({"where": label, "check": "opening cash cannot be negative",
                              "expected": ">= 0.00", "got": money(opening_cash), "diff": "", "note": ""})
        if opening_cash + flow != s["cash"]:
            fails.append({"where": label, "check": "cash sweep: last month's cash + cash flows = cash on statement",
                          "expected": money(s["cash"]), "got": money(opening_cash + flow),
                          "diff": money(opening_cash + flow - s["cash"]), "note": ""})
        for sym, h in s["holdings"].items():
            qty = sum((Decimal(r["quantity"]) for r in rows if r["symbol"] == sym and r["quantity"]), Decimal("0"))
            if contiguous and sym in prev["holdings"]:
                opening_qty = prev["holdings"][sym]["quantity"]
            else:
                opening_qty = h["quantity"] - qty
                notes.append(f"{label}: opening {sym} shares worked out from the closing count ({opening_qty}); not independently checked")
            if opening_qty + qty != h["quantity"]:
                fails.append({"where": label, "check": f"{sym} share count", "expected": str(h["quantity"]),
                              "got": str(opening_qty + qty), "diff": str(opening_qty + qty - h["quantity"]), "note": ""})
        if len(fails) == bad:
            for r in rows:
                marks[r["id"]] = ("yes", f"statement {s['end']}" + ("" if contiguous else " (flows tie; opening cash derived)"))
        prev = s
    return fails, "each monthly statement (flows, cash sweep, share count)", marks, notes


def compute_coverage(acfg, control, afiles, rows, stmts):
    """Which dates this account's ledger rows fully cover, so months can be flagged partial.

    Card: the downloads' own statement periods. Brokerage: the monthly statements that were checked.
    Checking: the statement periods, but only if the first statement's opening balance and the last
    statement's closing balance match the download.
    """
    real = [f for f in afiles if not f.get("pseudo") and f["rows"]]
    dates = sorted(r["date"] for r in rows)
    lo, hi = dates[0], dates[-1]
    if control == "statement_card":
        return (min(f["period"][0] for f in real).isoformat(), max(f["period"][1] for f in real).isoformat(),
                "the downloads' own statement periods")
    ss = sorted((s for s in stmts if s["kind"] == acfg.get("statement_kind") and s["end"].isoformat() >= lo
                 and s["start"].isoformat() <= hi), key=lambda s: s["start"])
    if not ss:
        return lo, hi, "first and last downloaded row (no statements)"
    if control == "statement_brokerage":
        return ss[0]["start"].isoformat(), ss[-1]["end"].isoformat(), "the monthly statements that were checked"
    earliest = min(real, key=lambda f: (f["min_date"], f["max_date"]))
    latest = max(real, key=lambda f: (f["max_date"], f["min_date"]))
    start = ss[0]["start"].isoformat() if ss[0]["begin"] == earliest["opening"] else lo
    end = ss[-1]["end"].isoformat() if ss[-1]["end_balance"] == latest["closing"] else hi
    return start, end, "statement periods whose opening and closing balances match the download"


# --------------------------------------------------------------------------- rules

def load_rules(path):
    rules = []
    for r in L.read_csv(path):
        if not (r.get("rule_id") or "").strip():
            continue
        if r["kind"] not in L.KINDS:
            raise DataError(f"rule {r['rule_id']}: unknown kind '{r['kind']}'")
        if r["field"] not in ("description", "action"):
            raise DataError(f"rule {r['rule_id']}: field must be description or action")
        try:
            r["_rx"] = re.compile(r["pattern"], re.I)
        except re.error as e:
            raise DataError(f"rule {r['rule_id']}: bad pattern '{r['pattern']}': {e}")
        rules.append(r)
    return rules


def load_overrides(path):
    out = {}
    for r in L.read_csv(path):
        if not (r.get("id") or "").strip():
            continue
        if r["kind"] not in L.KINDS or r["kind"] == "unclassified":
            raise DataError(f"override for {r['id']}: needs a real kind, got '{r['kind']}'")
        out[r["id"]] = r
    return out


def classify(row, rules, overrides, accounts):
    """Returns (category, kind, class_by, pair_with, pair_waiver). Overrides always win."""
    ov = overrides.get(row["id"])
    if ov:
        res = (ov["category"], ov["kind"], "override", ov.get("pair_with", ""), ov.get("pair_waiver", ""))
    else:
        res = ("", "unclassified", "", "", "")
        for rule in rules:
            if rule["account"] not in ("*", row["account"]):
                continue
            if rule["_rx"].search(row[rule["field"]] or ""):
                res = (rule["category"], rule["kind"], f"rule:{rule['rule_id']}", rule.get("pair_with", ""), "")
                break
    if res[1] == "income" and (Decimal(row["amount"]) <= 0 or accounts[row["account"]]["liability"]):
        raise DataError(f"{res[2]} would make {row['id']} ({row['description']}, {row['amount']}) income, "
                        "but income must be money coming in to a non-card account. "
                        "Card credits are payments (transfer) or refunds (negative spending).")
    return res


def pair_transfers(rows, meta, window):
    """Each transfer needs its other side in the ledger within `window` days."""
    pairs = {}
    transfers = sorted((r for r in rows if r["kind"] == "transfer"), key=lambda r: (r["date"], r["id"]))
    for r in transfers:
        if r["id"] in pairs:
            continue
        want = meta[r["id"]]["pair_with"]
        best = None
        for c in transfers:
            if c["id"] in pairs or c["id"] == r["id"] or c["account"] == r["account"]:
                continue
            if want and c["account"] != want:
                continue
            cw = meta[c["id"]]["pair_with"]
            if cw and cw != r["account"]:
                continue
            if Decimal(c["amount"]) != -Decimal(r["amount"]):
                continue
            gap = abs((datetime.strptime(c["date"], "%Y-%m-%d") - datetime.strptime(r["date"], "%Y-%m-%d")).days)
            if gap > window:
                continue
            k = (gap, c["date"], c["id"])
            if best is None or k < best[0]:
                best = (k, c)
        if best:
            pairs[r["id"]] = best[1]["id"]
            pairs[best[1]["id"]] = r["id"]
    return pairs


# --------------------------------------------------------------------------- the run

def run(root, stmts=None, quiet=False):
    root = Path(root)
    cfg = load_config(root)
    accounts = cfg["accounts"]
    notes_all = []
    if stmts is None:
        stmts, notes_all = S.load_statements(root / cfg.get("statements_dir", "statements"))
    files = find_files(root, cfg)
    ledger_path, held_path = root / "ledger" / "transactions.csv", root / "ledger" / "held.csv"
    old_rows = L.read_csv(ledger_path)
    held = {h["held_id"]: h for h in L.read_csv(held_path)}
    for st in stmts:
        try:
            st["path"] = str(Path(st["path"]).resolve().relative_to(root.resolve()))
        except ValueError:
            pass
    corrections = load_corrections(root)
    rules = load_rules(root / "ledger" / "rules.csv")
    overrides = load_overrides(root / "ledger" / "overrides.csv")

    result_rows, summary, refused, coverage = [], {}, {}, []
    for acct, acfg in accounts.items():
        afiles = [f for f in files if f["account"] == acct]
        existing = [r for r in old_rows if r["account"] == acct]
        if not afiles:
            result_rows += existing
            summary[acct] = {"status": "no files", "read": 0, "pending": 0, "new": 0, "already": 0,
                             "held_open": 0, "control": "", "notes": []}
            continue
        afiles = afiles + corrections_as_files(acct, [c for c in corrections if c["account"] == acct])
        work, stats, newly_held, fails = merge_account(acct, afiles, existing, held, cfg["duplicate_window_days"])
        for f in afiles:
            fails += f["failures"]
        notes, marks = [], {}
        if acfg["control"] == "running_balance":
            more, control, marks = check_running_balance(afiles, work)
        elif acfg["control"] == "statement_card":
            more, control, marks, notes = check_card(afiles, work, stmts)
        elif acfg["control"] == "statement_brokerage":
            more, control, marks, notes = check_brokerage(afiles, work, stmts)
        else:
            raise DataError(f"{acct}: unknown control '{acfg['control']}'")
        fails += more
        summary[acct] = {"read": stats["read"], "pending": sum(f["pending"] for f in afiles),
                         "new": stats["new"], "already": stats["already"], "held_open": stats["held_open"],
                         "held_dropped": stats["held_dropped"], "control": control, "notes": notes,
                         "files": [f["rel"] for f in afiles]}
        if fails:
            refused[acct] = fails
            summary[acct]["status"] = "STOPPED, not written"
            result_rows += existing  # unchanged
            continue
        for rid, r in work.items():
            r["recon"], r["recon_basis"] = marks.get(rid, ("unreconciled", ""))
        summary[acct]["status"] = "OK"
        result_rows += list(work.values())
        coverage.append(dict(zip(L.COVERAGE_COLS, (acct,) + compute_coverage(acfg, acfg["control"], afiles, list(work.values()), stmts))))

    # Rows for accounts that are not in the setup are kept as they are (nothing is ever deleted).
    result_rows += [r for r in old_rows if r["account"] not in accounts]

    # Classify, then pair transfers.
    meta = {}
    for r in result_rows:
        if r["account"] in refused or r["account"] not in accounts:
            meta[r["id"]] = {"pair_with": "", "waiver": ""}
            continue
        cat, kind, by, pw, waiver = classify(r, rules, overrides, accounts)
        r["category"], r["kind"], r["class_by"] = cat, kind, by
        meta[r["id"]] = {"pair_with": pw, "waiver": waiver}
    pairs = pair_transfers(result_rows, meta, cfg["transfer_window_days"])
    unpaired = []
    for r in result_rows:
        r["pair_id"] = pairs.get(r["id"], "")
        if r["kind"] == "transfer" and not r["pair_id"] and not meta[r["id"]]["waiver"]:
            other = meta[r["id"]]["pair_with"]
            why = (f"its other side belongs to {other}, which was not written this run"
                   if other in refused or (other and not any(x["account"] == other for x in result_rows))
                   else f"no row with the opposite amount within {cfg['transfer_window_days']} days")
            unpaired.append((r, why))

    result_rows.sort(key=lambda r: (r["date"], r["account"], r["id"]))
    L.write_csv(ledger_path, L.LEDGER_COLS, result_rows)
    L.write_csv(held_path, L.HELD_COLS, [held[k] for k in sorted(held)])
    L.write_csv(root / "ledger" / "coverage.csv", L.COVERAGE_COLS, coverage)

    report = build_report(cfg, files, summary, refused, result_rows, unpaired, notes_all, held, corrections)
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "ingest_report.txt").write_text(report, encoding="utf-8")
    if not quiet:
        print(report)
    return {"refused": refused, "summary": summary, "rows": result_rows, "unpaired": unpaired,
            "held": held, "report": report}


def build_report(cfg, files, summary, refused, rows, unpaired, notes_all, held, corrections):
    out = ["HOUSEHOLD LEDGER - INGEST REPORT", ""]
    out.append("Files read")
    for f in files:
        out.append(f"  {f['rel']}: {len(f['rows'])} posted rows, {f['pending']} pending skipped")
    out += [""] + [f"  note: {n}" for n in notes_all]
    out.append("Accounts")
    for acct, s in summary.items():
        out.append(f"  {acct}: {s.get('status')}")
        out.append(f"     rows read {s['read']}, new {s['new']}, already in ledger {s['already']}, "
                   f"pending skipped {s['pending']}, held for you {s['held_open']}")
        out.append(f"     total comes from: {s['control']}")
        for n in s["notes"]:
            out.append(f"     note: {n}")
    for acct, fails in refused.items():
        out += ["", f"STOP: {acct} was NOT written. Nothing was loosened to make it pass."]
        for x in fails:
            diff = f" Off by {x['diff']}." if x["diff"] else ""
            out.append(f"  {x['where']}: {x['check']}. Expected {x['expected']}, got {x['got']}.{diff} {x['note']}".rstrip())
            for item in x.get("statement_only", []):
                out.append(f"     on the statement but not in the download: {item[0]}  {item[1]}  {item[2]}")
            for item in x.get("download_only", []):
                out.append(f"     in the download but not on the statement: {item[0]}  {item[1]}  {item[2]}")
    if corrections:
        out += ["", "Rows added from a statement with approval (ledger/corrections.csv):"]
        out += [f"  {c['account']} {c['date']} {c['description']} {c['amount']} from {c['source']}, "
                f"approved by {c['approved_by']} on {c['approved_on']}" for c in corrections]
    open_held = [h for h in held.values() if not h["decision"]]
    if open_held:
        out += ["", "Possible duplicates held for you (ledger/held.csv):"]
        out += [f"  {h['date']} {h['description']} {h['amount']} ({h['reason']})" for h in open_held]
    out += ["", f"Ledger rows: {len(rows)}"]
    unc = [r for r in rows if r["kind"] == "unclassified"]
    out.append(f"Rows with no rule yet: {len(unc)}")
    if unpaired:
        out += ["", "Transfers waiting for their other side:"]
        out += [f"  {r['account']} {r['date']} {r['description']} {r['amount']} - {why}" for r, why in unpaired]
    return "\n".join(out) + "\n"


def accept_missing(root, account, approved_by, approved_on, stmts=None):
    """After the user says yes: add the rows that a statement lists but the download lacks.

    Only when those rows explain the whole gap and the download has nothing the
    statement lacks. The raw download is never touched.
    """
    root = Path(root)
    res = run(root, stmts=stmts, quiet=True)
    fails = res["refused"].get(account)
    if not fails:
        raise DataError(f"{account} is not stopped, so there is nothing to add")
    rows = []
    for x in fails:
        explained = ("missing_rows" in x and not x["download_only"] and x["missing_rows"]
                     and Decimal(x["diff"]) + sum((Decimal(m["amount"]) for m in x["missing_rows"]), ZERO) == 0)
        if not explained:
            raise DataError("Not safe to add automatically: the rows missing from the download do not explain "
                            "the whole gap, or the download has rows the statement lacks. Needs a look first.")
        rows += x["missing_rows"]
    path = root / "ledger" / "corrections.csv"
    existing = L.read_csv(path)

    def key(c):
        return (c["account"], c["date"], c["amount"], c["description"], str(c["counter"]), c["source"])

    have = {key(c) for c in existing}
    for m in rows:
        row = dict(m, reason="on the statement but missing from the download",
                   approved_by=approved_by, approved_on=approved_on)
        if key(row) not in have:
            existing.append(row)
    L.write_csv(path, L.CORRECTION_COLS, existing)
    return run(root, stmts=stmts, quiet=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--accept-missing", metavar="ACCOUNT",
                    help="after the user's yes: add rows a statement lists but the download lacks")
    ap.add_argument("--approved-by")
    ap.add_argument("--approved-on", help="YYYY-MM-DD")
    args = ap.parse_args(argv)
    try:
        if args.accept_missing:
            if not (args.approved_by and args.approved_on):
                raise DataError("--accept-missing needs --approved-by and --approved-on")
            res = accept_missing(args.root, args.accept_missing, args.approved_by, args.approved_on)
            print(res["report"])
            return 2 if res["refused"] else 0
        res = run(args.root)
    except DataError as e:
        print(f"STOP: {e}")
        return 2
    return 2 if res["refused"] else 0


if __name__ == "__main__":
    sys.exit(main())
