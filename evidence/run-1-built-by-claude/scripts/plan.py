#!/usr/bin/env python3
"""Check ledger/plan.csv and ledger/budget_map.csv. Every build runs this first.

plan.csv (Sam edits it in a spreadsheet app and saves it back as CSV):
  block,line,amount,fixed,note,paid_by
    block    income | committed | lumpy | savings
    line     the name of the plan line (must be unique)
    amount   per month, a plain number: income plus, everything else minus
             (yearly costs as a twelfth)
    fixed    1 = a set bill, 0 = Sam controls it
    paid_by  bank | card
budget_map.csv links each ledger category to a plan line, by the line's name:
  category,line,note        (line "(one-off)" keeps a category out of the budget)

The flex pool is what is left of income after the committed lines, the lumpy-cost
set-asides and savings. If anything is wrong this stops and names the row.
Exit code 2 means the plan or the map has an error.
"""
import argparse
import csv
import difflib
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledgerlib as L  # noqa: E402
from ledgerlib import money  # noqa: E402

PLAN_COLS = ["block", "line", "amount", "fixed", "note", "paid_by"]
MAP_COLS = ["category", "line", "note"]
BLOCKS = ["income", "committed", "lumpy", "savings"]
PAID_BY = ["bank", "card"]
ONE_OFF = "(one-off)"
PLAIN = re.compile(r"^-?\d+(\.\d{1,2})?$")
ZERO = Decimal("0.00")


def read_table(path, required):
    """Read a CSV saved from a spreadsheet app: tolerate a BOM, stray spaces and blank rows."""
    errors, rows = [], []
    p = Path(path)
    if not p.exists():
        return None, rows
    with open(p, newline="", encoding="utf-8-sig") as f:
        data = list(csv.reader(f))
    if not data:
        errors.append(f"{p.name}: the file is empty")
        return errors, rows
    header = [h.strip().lower() for h in data[0]]
    missing = [c for c in required if c not in header]
    if missing:
        errors.append(f"{p.name} row 1: missing column(s) {missing}. The header must include {required}")
        return errors, rows
    for i, cells in enumerate(data[1:], start=2):
        if not any(c.strip() for c in cells):
            continue
        rec = {h: (cells[k].strip() if k < len(cells) else "") for k, h in enumerate(header)}
        rec["row"] = i
        rows.append(rec)
    return errors, rows


def check(root):
    root = Path(root)
    cfg = L.load_json(root / "scripts" / "config.json")
    errors, warnings = [], []
    e, plan_raw = read_table(root / "ledger" / "plan.csv", PLAN_COLS)
    if e is None:
        errors.append("ledger/plan.csv does not exist yet")
        plan_raw = []
    else:
        errors += e
    plan, names = [], {}
    for r in plan_raw:
        where = f"plan.csv row {r['row']}" + (f" ({r['line']})" if r["line"] else "")
        bad = False
        if r["block"] not in BLOCKS:
            errors.append(f"{where}: block '{r['block']}' is not one of {BLOCKS}")
            bad = True
        if not r["line"]:
            errors.append(f"{where}: the line has no name")
            bad = True
        elif r["line"].lower() in names:
            errors.append(f"{where}: the name is used twice (also on row {names[r['line'].lower()]}); names must be unique")
            bad = True
        else:
            names[r["line"].lower()] = r["row"]
        amt = None
        if not PLAIN.match(r["amount"]):
            hint = ""
            if re.search(r"[\$,()\s%]", r["amount"]):
                hint = " Remove $, commas, brackets, spaces and %."
            if "−" in r["amount"] or "–" in r["amount"]:
                hint = " That minus sign is a long dash; type a plain - instead."
            errors.append(f"{where}: amount '{r['amount']}' is not a plain number like -2140.00.{hint}")
            bad = True
        else:
            amt = Decimal(r["amount"])
            if r["block"] == "income" and amt < 0:
                errors.append(f"{where}: income must be a plus number, got {r['amount']}")
                bad = True
            if r["block"] in ("committed", "lumpy", "savings") and amt > 0:
                errors.append(f"{where}: spending needs a minus sign, got {r['amount']}")
                bad = True
        if r["fixed"] not in ("0", "1"):
            errors.append(f"{where}: fixed must be 1 (a set bill) or 0 (you control it), got '{r['fixed']}'")
            bad = True
        if r["paid_by"] not in PAID_BY:
            errors.append(f"{where}: paid_by must be one of {PAID_BY}, got '{r['paid_by']}'")
            bad = True
        if not bad:
            plan.append({"block": r["block"], "line": r["line"], "amount": amt.quantize(Decimal("0.01")),
                         "fixed": int(r["fixed"]), "note": r.get("note", ""), "paid_by": r["paid_by"], "row": r["row"]})

    # the map from ledger categories to plan lines
    e, map_raw = read_table(root / "ledger" / "budget_map.csv", ["category", "line"])
    bmap, seen = [], {}
    if e is None:
        warnings.append("ledger/budget_map.csv does not exist yet; nothing links ledger categories to plan lines")
    else:
        errors += e
    line_names = {p["line"] for p in plan} | {r["line"] for r in plan_raw if r["line"]}
    for r in map_raw:
        where = f"budget_map.csv row {r['row']} ({r['category']})"
        if not r["category"] or not r["line"]:
            errors.append(f"{where}: both category and line are needed")
            continue
        if r["category"] in seen:
            errors.append(f"{where}: this category is already mapped on row {seen[r['category']]}; one line per category")
            continue
        seen[r["category"]] = r["row"]
        if r["line"] != ONE_OFF and r["line"] not in line_names:
            close = difflib.get_close_matches(r["line"], sorted(line_names), n=1, cutoff=0.5)
            hint = f" Was it renamed? Closest line in plan.csv: '{close[0]}'." if close else ""
            errors.append(f"{where}: maps to '{r['line']}', but plan.csv has no line with that name.{hint}")
            continue
        bmap.append({"category": r["category"], "line": r["line"], "note": r.get("note", ""), "row": r["row"]})

    # what the ledger holds that the map does not cover
    ledger = L.read_csv(root / "ledger" / "transactions.csv")
    mapped = {m["category"] for m in bmap}
    unmapped = defaultdict(int)
    for r in ledger:
        if r["kind"] in ("spend", "loan", "income") and r["category"] and r["category"] not in mapped:
            unmapped[(r["kind"], r["category"])] += 1
    for (kind, cat), n in sorted(unmapped.items()):
        what = {"spend": "counts as flex spending", "loan": "is an unplanned loan payment", "income": "is income outside the plan"}[kind]
        warnings.append(f"category '{cat}' ({n} ledger rows) is in no plan line, so it {what}")
    used = {m["line"] for m in bmap}
    for p in plan:
        if p["block"] in ("committed", "lumpy") and p["line"] not in used:
            warnings.append(f"plan line '{p['line']}' has no ledger category mapped to it, so no spending will ever show against it")

    sums = {b: sum((p["amount"] for p in plan if p["block"] == b), ZERO) for b in BLOCKS}
    flex = sum(sums.values(), ZERO)
    if plan and flex < 0:
        warnings.append("the plan spends more than the income it lists (the flex pool is negative)")
    return {"plan": plan, "map": bmap, "errors": errors, "warnings": warnings, "sums": sums, "flex_pool": flex,
            "accounts": cfg["accounts"]}


def render(res):
    out = []
    if res["errors"]:
        out += ["PLAN HAS ERRORS. Fix these rows in the spreadsheet and save as CSV again:"] + [f"  {e}" for e in res["errors"]]
    if res["warnings"]:
        out += ["Heads-up:"] + [f"  {w}" for w in res["warnings"]]
    s = res["sums"]
    if not res["errors"]:
        out += ["", "Plan, per month (script output):",
                f"  income                   {money(s['income']):>12}",
                f"  committed lines          {money(s['committed']):>12}",
                f"  expected lumpy set-asides{money(s['lumpy']):>12}",
                f"  savings                  {money(s['savings']):>12}",
                f"  flex pool (what is left) {money(res['flex_pool']):>12}"]
    return "\n".join(out)


def write_rows(path, cols, rows):
    L.write_csv(path, cols, rows)


def add_line(root, block, line, amount, fixed, paid_by, note):
    path = Path(root) / "ledger" / "plan.csv"
    old = path.read_text(encoding="utf-8-sig") if path.exists() else None
    e, rows = read_table(path, PLAN_COLS)
    rows = [{c: r.get(c, "") for c in PLAN_COLS} for r in rows] if e is not None else []
    rows.append({"block": block, "line": line, "amount": amount, "fixed": fixed, "note": note, "paid_by": paid_by})
    write_rows(path, PLAN_COLS, rows)
    res = check(root)
    mine = [e for e in res["errors"] if re.search(rf"plan\.csv row {len(rows) + 1}\b", e)]
    if mine:
        if old is None:
            path.unlink()
        else:
            path.write_text(old, encoding="utf-8")
        return res, mine
    return res, []


def add_map(root, category, line, note):
    path = Path(root) / "ledger" / "budget_map.csv"
    old = path.read_text(encoding="utf-8-sig") if path.exists() else None
    e, rows = read_table(path, ["category", "line"])
    rows = [{c: r.get(c, "") for c in MAP_COLS} for r in rows] if e is not None else []
    rows.append({"category": category, "line": line, "note": note})
    write_rows(path, MAP_COLS, rows)
    res = check(root)
    mine = [e for e in res["errors"] if re.search(rf"budget_map\.csv row {len(rows) + 1}\b", e)]
    if mine:
        if old is None:
            path.unlink()
        else:
            path.write_text(old, encoding="utf-8")
        return res, mine
    return res, []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--check", action="store_true", help="check the plan and the map (the default)")
    ap.add_argument("--add-line", nargs=6, metavar=("BLOCK", "LINE", "AMOUNT", "FIXED", "PAID_BY", "NOTE"),
                    help="add one plan line after Sam has decided it; it is checked, and refused if wrong")
    ap.add_argument("--map", nargs=3, metavar=("CATEGORY", "LINE", "NOTE"), help="link a ledger category to a plan line")
    args = ap.parse_args(argv)
    if args.add_line:
        res, mine = add_line(args.root, *args.add_line)
        if mine:
            print("NOT ADDED:\n  " + "\n  ".join(mine))
            return 2
        print(f"added plan line '{args.add_line[1]}'")
    if args.map:
        res, mine = add_map(args.root, *args.map)
        if mine:
            print("NOT ADDED:\n  " + "\n  ".join(mine))
            return 2
        print(f"mapped '{args.map[0]}' to '{args.map[1]}'")
    if not (args.add_line or args.map):
        res = check(args.root)
    print(render(res))
    return 2 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
