"""Invariants the synthetic household must satisfy before it is worth testing a prompt against.

Run:  python3 -m pytest -q -p no:cacheprovider test_make_fixture.py
"""
import csv
import hashlib
import re
import subprocess
from decimal import Decimal as D
from pathlib import Path

import pytest

import make_fixture as mf


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    out = tmp_path_factory.mktemp("fx")
    truth = mf.build(out)
    return out, truth


def read_checking(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_card(path):
    lines = Path(path).read_text().splitlines()
    rows = list(csv.DictReader(lines[3:]))
    footer = [r for r in rows if r["Transaction Date"] == "Total"]
    rows = [r for r in rows if r["Transaction Date"] != "Total"]
    return lines[:3], rows, footer


def card_files(out):
    return sorted((out / "downloads").glob("fernleaf_activity_*.csv"))


def truth_rows(truth, account, lo=None, hi=None):
    rows = [r for r in truth["transactions"] if r["account"] == account]
    if lo:
        rows = [r for r in rows if lo <= r["date"] <= hi]
    return rows


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


# ---------- determinism ----------

def test_deterministic(tmp_path, fx):
    out, _ = fx
    out2 = tmp_path / "again"
    mf.build(out2)
    for sub in ("downloads", "statements"):
        for p in sorted((out / sub).iterdir()):
            assert p.read_bytes() == (out2 / sub / p.name).read_bytes(), p.name


# ---------- T1: two formats ----------

def test_checking_format(fx):
    out, _ = fx
    files = sorted((out / "downloads").glob("otterbrook_checking_*.csv"))
    assert len(files) == 2
    rows = read_checking(files[0])
    assert list(rows[0].keys()) == ["Date", "Description", "Amount", "Balance", "Status"]
    assert all(re.fullmatch(r"\d\d/\d\d/2026", r["Date"]) for r in rows)
    mortgage = [r for r in rows if "HOLLOWMERE" in r["Description"]]
    pay = [r for r in rows if "QUILLFEATHER" in r["Description"]]
    assert mortgage and all(D(r["Amount"]) < 0 for r in mortgage)
    assert pay and all(D(r["Amount"]) > 0 for r in pay)


def test_card_format(fx):
    out, _ = fx
    files = card_files(out)
    assert len(files) == 6
    junk, rows, _ = read_card(files[0])
    assert not any(l.startswith("Transaction Date") for l in junk)
    assert list(rows[0].keys()) == ["Transaction Date", "Post Date", "Description", "Category", "Debit", "Credit"]
    assert all(re.fullmatch(r"2026-\d\d-\d\d", r["Transaction Date"]) for r in rows)
    groceries = [r for r in rows if "HEARTHSTONE" in r["Description"]]
    assert groceries and all(D(r["Debit"]) > 0 and r["Credit"] == "" for r in groceries)


# ---------- T2: card payment appears on both sides ----------

def test_card_payment_both_sides(fx):
    _, truth = fx
    chk_pay = sorted((r for r in truth_rows(truth, mf.CHK) if "FERNLEAF CARD AUTOPAY" in r["description"]),
                     key=lambda r: r["date"])
    card_pay = sorted((r for r in truth_rows(truth, mf.CARD) if "AUTOPAY PAYMENT" in r["description"]),
                      key=lambda r: r["date"])
    assert len(chk_pay) == len(card_pay) == 6
    for a, b in zip(chk_pay, card_pay):
        assert a["amount"] == -b["amount"] and a["date"] == b["date"]
        assert a["kind"] == b["kind"] == "transfer"


# ---------- T9: card statements close on the 23rd ----------

def test_card_cycle_closes_on_23rd(fx):
    out, truth = fx
    st = truth["statements"][mf.CARD]
    assert list(st) == [p[1].isoformat() for p in mf.CARD_PERIODS]
    for start, end in mf.CARD_PERIODS:
        assert end.day == 23 and start.day == 24
    for f, (start, end) in zip(card_files(out), mf.CARD_PERIODS):
        junk, rows, _ = read_card(f)
        assert f"{start.strftime('%m/%d/%Y')} - {end.strftime('%m/%d/%Y')}" in junk[2]
        dates = {r["Transaction Date"] for r in rows}
        assert min(dates) >= start.isoformat() and max(dates) <= end.isoformat()
    text = pdf_text(out / "statements" / "FernleafCard_Statement_2026-06-23.pdf")
    assert "05/24/2026 - 06/23/2026" in text


def test_autopay_pays_prior_statement_except_june(fx):
    _, truth = fx
    st = truth["statements"][mf.CARD]
    keys = list(st)
    pays = sorted((r for r in truth_rows(truth, mf.CHK) if "FERNLEAF CARD AUTOPAY" in r["description"]),
                  key=lambda r: r["date"])
    expected_prev = [mf.CARD_OPENING] + [st[k]["closing"] for k in keys[:-1]]
    for row, prev in zip(pays, expected_prev):
        if row["date"].month == 6:
            assert -row["amount"] == D("1000.00") < prev  # U3: partial payment
        else:
            assert -row["amount"] == prev


# ---------- T3: overlapping checking exports ----------

def test_checking_overlap(fx):
    out, _ = fx
    f1, f2 = sorted((out / "downloads").glob("otterbrook_checking_*.csv"))
    r1 = [r for r in read_checking(f1) if r["Status"] == "Posted"]
    r2 = read_checking(f2)
    key = lambda r: (r["Date"], r["Description"], r["Amount"], r["Balance"])
    sortable = lambda s: (s[6:], s[:5])
    assert max((r["Date"] for r in r1), key=sortable) == "06/15/2026"
    assert min((r["Date"] for r in r2), key=sortable) == "06/01/2026"
    overlap = [r for r in r1 if r["Date"].startswith("06/")]
    assert 5 <= len(overlap) <= 20
    s2 = [key(r) for r in r2]
    assert all(key(r) in s2 for r in overlap)


# ---------- T10: pending then posted at a different amount ----------

def test_pending_then_posted(fx):
    out, truth = fx
    f1, f2 = sorted((out / "downloads").glob("otterbrook_checking_*.csv"))
    pend = [r for r in read_checking(f1) if r["Status"] == "Pending"]
    assert len(pend) == 1
    p = pend[0]
    assert "COPPER SPOON" in p["Description"] and p["Amount"] == "-48.00" and p["Balance"] == ""
    posted = [r for r in read_checking(f2) if "COPPER SPOON" in r["Description"]]
    assert len(posted) == 1 and posted[0]["Amount"] == "-57.60" and posted[0]["Status"] == "Posted"
    assert not any(r["Status"] == "Pending" for r in read_checking(f2))
    tr = [r for r in truth_rows(truth, mf.CHK) if "COPPER SPOON" in r["description"]]
    assert len(tr) == 1 and tr[0]["amount"] == D("-57.60")
    text = pdf_text(out / "statements" / "Otterbrook_eStatement_2026-06-30.pdf")
    assert "-57.60" in text and "-48.00" not in text


# ---------- T4: legit identical pair ----------

def test_identical_pair_present_and_unique(fx):
    out, truth = fx
    rows = [r for f in card_files(out) for r in read_card(f)[1]]
    pair = [r for r in rows if r["Transaction Date"] == "2026-05-14" and "BEAN & BARLEY" in r["Description"]]
    assert len(pair) == 2 and pair[0] == pair[1]
    seen = {}
    for r in truth["transactions"]:
        k = (r["account"], r["date"], r["description"], r["amount"])
        seen[k] = seen.get(k, 0) + 1
    dupes = [k for k, n in seen.items() if n > 1]
    assert len(dupes) == 1 and dupes[0][2] == "BEAN & BARLEY CAFE"


# ---------- T5: truncated export ----------

def test_one_card_export_missing_exactly_one_row(fx):
    out, truth = fx
    miss = truth["traps"]["T5"]
    short_files = 0
    for f, (start, end) in zip(card_files(out), mf.CARD_PERIODS):
        _, rows, _ = read_card(f)
        expected = len(truth_rows(truth, mf.CARD, start, end))
        if start.isoformat() <= miss["date"] <= end.isoformat():
            assert len(rows) == expected - 1
            short_files += 1
            assert not any(r["Transaction Date"] == miss["date"] and r["Description"] == miss["description"]
                           and r["Debit"] == miss["amount"] for r in rows)
        else:
            assert len(rows) == expected, f.name
    assert short_files == 1
    assert miss["amount"] in pdf_text(out / "statements" / "FernleafCard_Statement_2026-07-23.pdf")


# ---------- T11: partial refund ----------

def test_partial_refund(fx):
    out, truth = fx
    tr = [r for r in truth_rows(truth, mf.CARD) if "ORBITMART" in r["description"] and r["amount"] > 0]
    assert len(tr) == 1
    refund = tr[0]
    buy = [r for r in truth_rows(truth, mf.CARD) if r["date"] == mf.d(mf.T11["purchase_date"])
           and r["description"] == "ORBITMART ONLINE"]
    assert len(buy) == 1 and -buy[0]["amount"] > refund["amount"]
    assert refund["kind"] == "spend" and refund["category"] == buy[0]["category"]
    rows = [r for f in card_files(out) for r in read_card(f)[1]]
    csv_ref = [r for r in rows if r["Description"] == "ORBITMART ONLINE RETURN"]
    assert len(csv_ref) == 1 and csv_ref[0]["Credit"] == mf.T11["refund"] and csv_ref[0]["Category"] == "Shopping"


# ---------- T12: transfer lands three business days later ----------

def test_late_transfer_pairs(fx):
    _, truth = fx
    outs = sorted((r for r in truth_rows(truth, mf.CHK) if "XFER TO ***3380" in r["description"]),
                  key=lambda r: r["date"])
    ins = sorted((r for r in truth_rows(truth, mf.BRK) if r["description"].startswith("CONTRIBUTION")),
                 key=lambda r: r["date"])
    assert len(outs) == len(ins) == 6
    for o, i in zip(outs, ins):
        assert o["amount"] == -i["amount"] and o["kind"] == i["kind"] == "transfer"
        assert i["date"] == mf.add_bdays(o["date"], 3) and (i["date"] - o["date"]).days >= 3


# ---------- U1: footer row ----------

def test_card_footer_row(fx):
    out, _ = fx
    with_footer = []
    for f in card_files(out):
        _, rows, footer = read_card(f)
        if footer:
            with_footer.append(f.name)
            assert len(footer) == 1
            assert Path(f).read_text().rstrip("\n").splitlines()[-1].startswith("Total,")
            assert D(footer[0]["Debit"]) == sum(D(r["Debit"]) for r in rows if r["Debit"])
    assert len(with_footer) == 1


# ---------- U2: foreign purchase plus separate fee ----------

def test_foreign_purchase_and_fee(fx):
    out, truth = fx
    fx_rows = [r for r in truth_rows(truth, mf.CARD) if r["date"] == mf.d(mf.U2["date"])]
    buy = [r for r in fx_rows if r["description"] == mf.U2["description"]]
    fee = [r for r in fx_rows if r["description"] == "FOREIGN TRANSACTION FEE"]
    assert len(buy) == len(fee) == 1
    assert fee[0]["amount"] == -mf.money(-buy[0]["amount"] * D("0.03"))
    assert buy[0]["kind"] == fee[0]["kind"] == "spend"
    rows = [r for f in card_files(out) for r in read_card(f)[1]]
    assert sum(1 for r in rows if r["Description"] == "FOREIGN TRANSACTION FEE") == 1


# ---------- U3: interest after a partial payment ----------

def test_interest_charge(fx):
    _, truth = fx
    st = truth["statements"][mf.CARD]
    rows = [r for r in truth_rows(truth, mf.CARD) if "INTEREST" in r["description"]]
    assert len(rows) == 1 and rows[0]["amount"] < 0 and rows[0]["kind"] == "spend"
    assert rows[0]["date"] == mf.d("2026-06-23")
    assert st["2026-06-23"]["interest"] == -rows[0]["amount"]


# ---------- U4: the same statement saved twice ----------

def test_duplicate_statement_file(fx):
    out, _ = fx
    pdfs = sorted((out / "statements").glob("*.pdf"))
    assert len(pdfs) == 6 * 3 + 1 + 1  # 3 accounts x 6 statements + paystub + one re-download
    hashes = {}
    for p in pdfs:
        hashes.setdefault(hashlib.sha256(p.read_bytes()).hexdigest(), []).append(p.name)
    same = [names for names in hashes.values() if len(names) > 1]
    assert len(same) == 1 and len(same[0]) == 2


# ---------- statements reconcile with the true transactions ----------

def test_checking_statements_reconcile(fx):
    _, truth = fx
    st = truth["statements"][mf.CHK]
    months = list(st)
    for i, month in enumerate(months):
        y, m = map(int, month.split("-"))
        flows = sum((r["amount"] for r in truth_rows(truth, mf.CHK) if (r["date"].year, r["date"].month) == (y, m)),
                    D("0"))
        assert st[month]["opening"] + flows == st[month]["closing"], month
        if i:
            assert st[months[i - 1]]["closing"] == st[month]["opening"]


def test_card_statements_reconcile_by_period(fx):
    _, truth = fx
    st = truth["statements"][mf.CARD]
    keys = list(st)
    for i, ((start, end), k) in enumerate(zip(mf.CARD_PERIODS, keys)):
        flows = sum((r["amount"] for r in truth_rows(truth, mf.CARD, start, end)), D("0"))
        s = st[k]
        assert s["opening"] - flows == s["closing"], k
        assert (s["opening"] - s["payments"] - s["credits"] + s["purchases"] + s["fees"] + s["interest"]
                == s["closing"]), k
        if i:
            assert st[keys[i - 1]]["closing"] == s["opening"]


def test_checking_never_negative(fx):
    _, truth = fx
    bal = truth["statements"][mf.CHK]["2026-03"]["opening"]
    for r in sorted(truth_rows(truth, mf.CHK), key=lambda r: (r["date"], r["seq"])):
        bal += r["amount"]
        assert bal > 0


def test_statement_pdfs_have_text(fx):
    out, truth = fx
    chk = out / "statements" / "Otterbrook_eStatement_2026-03-31.pdf"
    text = pdf_text(chk)
    closing = truth["statements"][mf.CHK]["2026-03"]["closing"]
    assert f"{closing:,.2f}" in text and "Ending Balance" in text


# ---------- T6: money moved, not lost ----------

def test_bridge_identity_and_small_negative_market(fx):
    _, truth = fx
    b = truth["bridge"]
    assert b["start"] + b["money_in"] - b["money_out"] + b["market_change"] == b["end"]
    assert b["money_out"] == D("35000.00") and b["money_in"] == D("3000.00")
    assert -D("0.025") * b["start"] < b["market_change"] < -D("0.003") * b["start"]
    xfer = [r for r in truth_rows(truth, mf.CHK) if r["amount"] == D("35000.00")]
    assert len(xfer) == 1 and xfer[0]["kind"] == "transfer"


def test_brokerage_statements_chain(fx):
    _, truth = fx
    st = truth["statements"][mf.BRK]
    months = list(st)
    for i, month in enumerate(months):
        s = st[month]
        assert s["opening"] + s["contributions"] - s["withdrawals"] + s["dividends"] + s["market_change"] == s["closing"]
        if i:
            assert st[months[i - 1]]["closing"] == s["opening"]
    assert st["2026-03"]["opening"] == truth["bridge"]["start"]
    assert st["2026-08"]["closing"] == truth["bridge"]["end"]


# ---------- persona and answer key ----------

def test_persona_does_not_coach(fx):
    out, _ = fx
    text = (out / "persona.md").read_text().lower()
    for word in ["duplicate", "trap", "check total", "bridge", "overlap", "truncat", "pending", "footer",
                 "statement cycle", "closes on", "23rd", "three business days", "posted"]:
        assert not re.search(r"\b" + re.escape(word), text), word  # \b so "spending" doesn't trip "pending"


def test_traps_answer_key_complete(fx):
    out, _ = fx
    text = (out / "traps.md").read_text()
    for t in [f"T{i}" for i in range(1, 13)] + [f"U{i}" for i in range(1, 5)]:
        assert f"## {t} " in text, t


def test_no_em_dashes_in_generated_text(fx):
    out, _ = fx
    for name in ["persona.md", "traps.md"]:
        assert "\u2014" not in (out / name).read_text(), name
