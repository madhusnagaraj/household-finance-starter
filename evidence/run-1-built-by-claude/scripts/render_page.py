#!/usr/bin/env python3
"""Render the budget as ONE self-contained page for a phone: reports/budget_phone.html.

A page is only a render of script output. Every number comes from budget.py; nothing on it is
typed or editable. It has no scripts, no fonts, no images and no network calls, so opening it
sends nothing anywhere. It carries plan lines and totals only: no payee names, no account
numbers, no account balances. It is still private household data: it stays in this folder
until Sam chooses to copy it somewhere himself.
"""
import argparse
import html
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a64;--line:#e4e1d8;--card:#fff;--ok:#1f6b45;--watch:#8a5a00;--over:#a32a2a;--np:#5a5a55}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151512;--fg:#ecebe5;--mute:#a3a29a;--line:#2e2d28;--card:#1d1d19;--ok:#6fcf9a;--watch:#e8b04a;--over:#ff8f8f;--np:#b5b4ab}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 -apple-system,system-ui,"Segoe UI",sans-serif}
main{max-width:640px;margin:0 auto;padding:20px 16px 40px}h1{font-size:22px;margin:0 0 4px}h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--mute);margin:26px 0 8px}
.sub{color:var(--mute);margin:0 0 16px}.stale{background:var(--card);border:1px solid var(--over);border-radius:10px;padding:10px 12px;margin:0 0 16px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.tile b{display:block;font-size:20px;font-variant-numeric:tabular-nums}.tile span{color:var(--mute);font-size:13px}
.row{display:grid;grid-template-columns:1fr auto;gap:2px 12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:0 0 8px}
.row .n{font-weight:600}.row .st{justify-self:end;font-size:13px;font-weight:600}.row .m{color:var(--mute);font-size:14px;font-variant-numeric:tabular-nums}
.ok{color:var(--ok)}.watch{color:var(--watch)}.over{color:var(--over)}.np{color:var(--np)}
footer{color:var(--mute);font-size:13px;margin-top:28px}
"""

LABEL = {"ok": "ok", "watch": "watch", "over": "over", "not posted": "not posted", "partly posted": "partly posted"}
CLS = {"ok": "ok", "watch": "watch", "over": "over", "not posted": "np", "partly posted": "watch"}
BLOCKS = [("income", "Income"), ("committed", "Committed lines"), ("lumpy", "Expected lumpy costs"), ("savings", "Savings")]


def n(x):
    return f"{x:,.2f}"


def render(b, stale_note, warnings):
    e = html.escape
    out = ["<!doctype html><html lang=en><head><meta charset=utf-8>",
           "<meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>Household budget</title><style>" + CSS + "</style></head><body><main>",
           f"<h1>Budget {e(b['month'])}</h1>",
           f"<p class=sub>Month to date through {e(str(b['as_of']))} (day {b['day']} of {b['dim']})</p>"]
    if stale_note:
        out.append(f"<p class=stale>{e(stale_note)}</p>")
    out.append("<div class=grid>")
    for label, val in (("Flex pool (plan)", b["flex_pool"]), ("Flex left", b["flex_left"]),
                       ("Cushion on current pace", b["cushion"]), ("Flex spent so far", b["flex_spent"]),
                       ("On the card (next month's cash)", b["card"]), ("Straight from the bank", b["bank"])):
        out.append(f"<div class=tile><b>{n(val)}</b><span>{e(label)}</span></div>")
    out.append("</div>")
    for key, title in BLOCKS:
        lines = [l for l in b["lines"] if l["block"] == key]
        if not lines:
            continue
        out.append(f"<h2>{e(title)}</h2>")
        for l in lines:
            pace = f" &middot; pace {n(l['pace'])}" if l["pace"] is not None and key == "committed" and l["fixed"] == 0 else ""
            out.append(f"<div class=row><span class=n>{e(l['line'])}</span>"
                       f"<span class='st {CLS[l['status']]}'>{e(LABEL[l['status']])}</span>"
                       f"<span class=m>plan {n(l['plan'])} &middot; so far {n(l['spent'])}{pace}</span></div>")
    for x in b["extra_income"]:
        out.append(f"<h2>Extra income</h2><div class=row><span class=n>{e(x['line'])}: {n(x['extra'])} above plan</span>"
                   f"<span class=m>{e(x['note'])}</span></div>")
    if b["oneoff"]:
        out.append("<h2>One-offs kept out of the budget</h2>")
        out += [f"<div class=row><span class=n>{e(c)}</span><span class=m>{n(v)}</span></div>" for c, v in sorted(b["oneoff"].items())]
    out.append("<footer>This page is a render of the budget script's output. Nothing on it can be edited; change the plan "
               "in plan.csv and rebuild. It is private household data.")
    if warnings:
        out.append("<br>" + "<br>".join(e(w) for w in warnings))
    out.append("</footer></main></body></html>")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--month")
    ap.add_argument("--as-of")
    args = ap.parse_args(argv)
    try:
        b, res, current_to = budget.prepare(args.root, args.month, args.as_of)
    except budget.BudgetError as err:
        print(err)
        return 2
    stale = ""
    if (date.today() - current_to).days > 7:
        stale = f"Out of date: the ledger is only checked through {current_to}. Add fresh downloads and run ingest.py."
    page = render(b, stale, res["warnings"])
    out = Path(args.root) / "reports" / "budget_phone.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(page):,} bytes). Self-contained; no network, no scripts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
