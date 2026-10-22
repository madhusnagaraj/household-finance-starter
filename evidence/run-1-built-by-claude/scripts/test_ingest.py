"""Tests for ingest.py, using small made-up exports in a scratch folder.

Run from the project folder:  python3 -m unittest discover -s scripts -v
The scratch folder lives under scripts/_testwork/ and is removed after each test.
"""
import shutil
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402
import ledgerlib as L  # noqa: E402
from ledgerlib import DataError  # noqa: E402

HERE = Path(__file__).resolve().parent
WORK = HERE / "_testwork"

OTTER_HEADER = "Date,Description,Amount,Balance,Status\n"
CARD_HEAD = ('Fernleaf Card Services,,,,,\n"Account: Test card",,,,,\n'
             '"Activity for statement period 01/01/2026 - 01/31/2026",,,,,\n'
             "Transaction Date,Post Date,Description,Category,Debit,Credit\n")
TIDE_HEADER = "Trade Date,Action,Symbol,Description,Quantity,Price,Amount\n"
RULES_HEADER = "rule_id,account,field,pattern,category,kind,pair_with,added_by,added_on,note\n"


class Base(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(dir=WORK))
        (self.root / "scripts").mkdir()
        shutil.copy(HERE / "config.json", self.root / "scripts" / "config.json")
        (self.root / "ledger").mkdir()
        (self.root / "ledger" / "overrides.csv").write_text(",".join(L.OVERRIDE_COLS) + "\n")
        (self.root / "ledger" / "held.csv").write_text(",".join(L.HELD_COLS) + "\n")
        self.rules(RULES_HEADER)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def rules(self, text):
        (self.root / "ledger" / "rules.csv").write_text(text)

    def export(self, name, text, day="2026-01-31"):
        d = self.root / "exports" / day
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text)

    def run_ingest(self, stmts=None):
        return ingest.run(self.root, stmts=[] if stmts is None else stmts, quiet=True)

    def ledger(self):
        return L.read_csv(self.root / "ledger" / "transactions.csv")


class TestLoading(Base):
    def test_running_twice_changes_nothing(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/06/2026,SALARY,50.00,140.00,Posted\r\n01/05/2026,COFFEE,-10.00,90.00,Posted\r\n")
        self.run_ingest()
        first = (self.root / "ledger" / "transactions.csv").read_bytes()
        held1 = (self.root / "ledger" / "held.csv").read_bytes()
        self.run_ingest()
        self.assertEqual(first, (self.root / "ledger" / "transactions.csv").read_bytes())
        self.assertEqual(held1, (self.root / "ledger" / "held.csv").read_bytes())
        self.assertEqual(len(self.ledger()), 2)

    def test_two_identical_charges_stay_two(self):
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-03,2026-01-04,BEAN & BARLEY CAFE,Dining,5.25,\n"
                    "2026-01-03,2026-01-04,BEAN & BARLEY CAFE,Dining,5.25,\n")
        self.run_ingest()
        rows = self.ledger()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sorted(r["id"][-2:] for r in rows), ["-1", "-2"])
        self.assertTrue(all(r["amount"] == "-5.25" for r in rows))  # spending is negative

    def test_pending_rows_are_not_loaded(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/07/2026,LUNCH,-48.00,,Pending\n01/06/2026,SALARY,50.00,150.00,Posted\n")
        res = self.run_ingest()
        self.assertEqual([r["description"] for r in self.ledger()], ["SALARY"])
        self.assertEqual(res["summary"]["otterbrook"]["pending"], 1)

    def test_overlapping_exports_do_not_double_count(self):
        a = OTTER_HEADER + "01/06/2026,SALARY,50.00,140.00,Posted\n01/05/2026,COFFEE,-10.00,90.00,Posted\n"
        b = OTTER_HEADER + ("01/08/2026,RENT,-30.00,110.00,Posted\n01/06/2026,SALARY,50.00,140.00,Posted\n"
                            "01/05/2026,COFFEE,-10.00,90.00,Posted\n")
        self.export("otterbrook_checking_export_a.csv", a, "2026-01-07")
        self.export("otterbrook_checking_export_b.csv", b, "2026-01-09")
        res = self.run_ingest()
        self.assertEqual(res["refused"], {})
        self.assertEqual(len(self.ledger()), 3)
        self.assertTrue(any("export_b" in r["also_in"] for r in self.ledger()))


class TestDuplicatesHeld(Base):
    A = OTTER_HEADER + "01/06/2026,SALARY,50.00,140.00,Posted\n01/05/2026,COFFEE,-10.00,90.00,Posted\n"
    # Same coffee, but this download dates it a day later. Balances still show it once.
    B = OTTER_HEADER + "01/06/2026,SALARY,50.00,140.00,Posted\n01/06/2026,COFFEE,-10.00,90.00,Posted\n"

    def setup_files(self):
        self.export("otterbrook_checking_export_a.csv", self.A, "2026-01-07")
        self.export("otterbrook_checking_export_b.csv", self.B, "2026-01-09")

    def test_possible_duplicate_is_held_and_answer_is_remembered(self):
        self.setup_files()
        res = self.run_ingest()
        self.assertEqual(res["refused"], {})  # held, and the totals still tie
        self.assertEqual(len(self.ledger()), 2)
        held = L.read_csv(self.root / "ledger" / "held.csv")
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["decision"], "")
        # The user says it is a duplicate: it stays out, on every later run.
        held[0]["decision"], held[0]["decided_by"], held[0]["decided_on"] = "duplicate", "Sam", "2026-01-10"
        L.write_csv(self.root / "ledger" / "held.csv", L.HELD_COLS, held)
        self.run_ingest()
        self.run_ingest()
        self.assertEqual(len(self.ledger()), 2)
        self.assertEqual(L.read_csv(self.root / "ledger" / "held.csv")[0]["decision"], "duplicate")

    def test_adding_a_held_row_that_the_balance_does_not_support_is_caught(self):
        self.setup_files()
        self.run_ingest()
        held = L.read_csv(self.root / "ledger" / "held.csv")
        held[0]["decision"] = "add"
        L.write_csv(self.root / "ledger" / "held.csv", L.HELD_COLS, held)
        res = self.run_ingest()
        self.assertIn("otterbrook", res["refused"])  # the bank's balance counts that coffee once
        self.assertEqual(res["refused"]["otterbrook"][0]["diff"], "-10.00")


class TestChecks(Base):
    def test_broken_running_balance_refuses_the_account(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/06/2026,SALARY,50.00,999.00,Posted\n01/05/2026,COFFEE,-10.00,90.00,Posted\n")
        res = self.run_ingest()
        self.assertIn("otterbrook", res["refused"])
        self.assertEqual(self.ledger(), [])
        self.assertEqual(res["refused"]["otterbrook"][0]["diff"], "859.00")

    def test_a_row_missing_between_two_downloads_is_caught(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/05/2026,COFFEE,-10.00,90.00,Posted\n", "2026-01-07")
        # second download starts after a gap: a row between them is missing
        self.export("otterbrook_checking_export_b.csv",
                    OTTER_HEADER + "01/09/2026,RENT,-30.00,50.00,Posted\n", "2026-01-09")
        res = self.run_ingest()
        self.assertIn("otterbrook", res["refused"])

    def test_card_that_disagrees_with_its_statement_is_refused_and_shows_the_gap(self):
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n")
        stmt = {"kind": "fernleaf", "path": "FernleafCard_Statement_test.pdf",
                "start": date(2026, 1, 1), "end": date(2026, 1, 31),
                "prev": Decimal("0.00"), "new": Decimal("187.43"),
                "lines": [{"date": date(2026, 1, 4), "txn_date": date(2026, 1, 3),
                           "description": "HEARTHSTONE MARKET", "amount": Decimal("-100.00")},
                          {"date": date(2026, 1, 20), "txn_date": date(2026, 1, 19),
                           "description": "HEARTHSTONE MARKET", "amount": Decimal("-87.43")}]}
        res = self.run_ingest([stmt])
        self.assertIn("fernleaf", res["refused"])
        fail = res["refused"]["fernleaf"][0]
        self.assertEqual(fail["diff"], "87.43")
        self.assertEqual(fail["statement_only"], [("2026-01-20", "HEARTHSTONE MARKET", "-87.43")])
        self.assertEqual(self.ledger(), [])  # nothing written for that account

    def test_card_that_agrees_with_its_statement_is_reconciled(self):
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n")
        stmt = {"kind": "fernleaf", "path": "x.pdf", "start": date(2026, 1, 1), "end": date(2026, 1, 31),
                "prev": Decimal("0.00"), "new": Decimal("100.00"), "lines": []}
        res = self.run_ingest([stmt])
        self.assertEqual(res["refused"], {})
        self.assertEqual(self.ledger()[0]["recon"], "yes")

    def test_one_bad_account_does_not_stop_the_others(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/05/2026,COFFEE,-10.00,90.00,Posted\n01/04/2026,PAY,5.00,999.00,Posted\n")
        self.export("tidewell_activity_a.csv", TIDE_HEADER +
                    "01/10/2026,CONTRIBUTION,,EFT RECEIVED,,,500.00\n")
        res = self.run_ingest()
        self.assertEqual(list(res["refused"]), ["otterbrook"])
        self.assertEqual([r["account"] for r in self.ledger()], ["tidewell"])

    def test_rows_without_a_statement_stay_unreconciled(self):
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n")
        self.run_ingest()
        self.assertEqual(self.ledger()[0]["recon"], "unreconciled")


class TestClassifying(Base):
    def test_refund_is_negative_spending_and_card_payment_is_a_transfer(self):
        self.rules(RULES_HEADER +
                   "R1,fernleaf,description,^AUTOPAY PAYMENT,Card payment,transfer,otterbrook,t,2026-01-01,\n"
                   "R2,fernleaf,description,RETURN,Shopping,spend,,t,2026-01-01,\n")
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-05,2026-01-06,ORBITMART ONLINE RETURN,Shopping,,34.99\n"
                    "2026-01-17,2026-01-18,AUTOPAY PAYMENT - THANK YOU,Payment/Credit,,100.00\n")
        self.run_ingest()
        by = {r["description"]: r for r in self.ledger()}
        self.assertEqual((by["ORBITMART ONLINE RETURN"]["kind"], by["ORBITMART ONLINE RETURN"]["amount"]), ("spend", "34.99"))
        self.assertEqual(by["AUTOPAY PAYMENT - THANK YOU"]["kind"], "transfer")

    def test_a_rule_cannot_turn_a_card_credit_into_income(self):
        self.rules(RULES_HEADER + "R1,*,description,RETURN,Pay,income,,t,2026-01-01,\n")
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-05,2026-01-06,ORBITMART ONLINE RETURN,Shopping,,34.99\n")
        with self.assertRaises(DataError):
            self.run_ingest()

    def test_first_rule_wins_and_overrides_always_win(self):
        self.rules(RULES_HEADER +
                   "R1,*,description,COFFEE,Dining: coffee,spend,,t,2026-01-01,\n"
                   "R2,*,description,COF,Other,spend,,t,2026-01-01,\n")
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/05/2026,COFFEE,-10.00,90.00,Posted\n")
        self.run_ingest()
        row = self.ledger()[0]
        self.assertEqual((row["category"], row["class_by"]), ("Dining: coffee", "rule:R1"))
        L.write_csv(self.root / "ledger" / "overrides.csv", L.OVERRIDE_COLS,
                    [{"id": row["id"], "category": "Gifts", "kind": "spend", "decided_by": "Sam"}])
        self.run_ingest()
        row = self.ledger()[0]
        self.assertEqual((row["category"], row["class_by"]), ("Gifts", "override"))

    def test_unmatched_rows_are_marked_unclassified(self):
        self.export("otterbrook_checking_export_a.csv",
                    OTTER_HEADER + "01/05/2026,MYSTERY SHOP,-10.00,90.00,Posted\n")
        self.run_ingest()
        self.assertEqual(self.ledger()[0]["kind"], "unclassified")


class TestTransfers(Base):
    def test_transfer_pairs_across_a_few_days_and_a_lonely_one_is_flagged(self):
        self.rules(RULES_HEADER +
                   "R1,otterbrook,description,XFER TO,To brokerage,transfer,tidewell,t,2026-01-01,\n"
                   "R2,tidewell,action,^CONTRIBUTION$,From checking,transfer,otterbrook,t,2026-01-01,\n")
        self.export("otterbrook_checking_export_a.csv", OTTER_HEADER +
                    "01/20/2026,XFER TO BROKERAGE,-250.00,500.00,Posted\n"
                    "01/15/2026,XFER TO BROKERAGE,-500.00,750.00,Posted\n"
                    "01/02/2026,PAY,1250.00,1250.00,Posted\n")
        self.export("tidewell_activity_a.csv", TIDE_HEADER +
                    "01/19/2026,CONTRIBUTION,,EFT RECEIVED,,,500.00\n")
        res = self.run_ingest()
        self.assertEqual(res["refused"], {})
        pairs = {r["description"] + r["amount"]: r["pair_id"] for r in self.ledger()}
        self.assertTrue(pairs["XFER TO BROKERAGE-500.00"])
        self.assertTrue(pairs["EFT RECEIVED500.00"])
        self.assertEqual(pairs["XFER TO BROKERAGE-250.00"], "")
        self.assertEqual([r["amount"] for r, _ in res["unpaired"]], ["-250.00"])


def card_statement(prev, new, lines):
    return {"kind": "fernleaf", "path": "FernleafCard_Statement_test.pdf",
            "start": date(2026, 1, 1), "end": date(2026, 1, 31),
            "prev": Decimal(prev), "new": Decimal(new),
            "lines": [{"date": date(2026, 1, d), "txn_date": date(2026, 1, d - 1),
                       "description": desc, "amount": Decimal(amt)} for d, desc, amt in lines]}


class TestCorrections(Base):
    def card_file(self, *rows):
        self.export("fernleaf_activity_a.csv", CARD_HEAD + "".join(rows))

    def test_row_missing_from_the_download_is_added_from_the_statement_once_approved(self):
        self.card_file("2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n")
        stmt = card_statement("0.00", "187.43", [(4, "HEARTHSTONE MARKET", "-100.00"), (20, "HEARTHSTONE MARKET", "-87.43")])
        self.assertIn("fernleaf", self.run_ingest([stmt])["refused"])
        res = ingest.accept_missing(self.root, "fernleaf", "Sam", "2026-01-31", stmts=[stmt])
        self.assertEqual(res["refused"], {})
        rows = self.ledger()
        self.assertEqual(sorted(r["amount"] for r in rows), ["-100.00", "-87.43"])
        self.assertTrue(all(r["recon"] == "yes" for r in rows))
        corr = L.read_csv(self.root / "ledger" / "corrections.csv")
        self.assertEqual((len(corr), corr[0]["approved_by"], corr[0]["source"]),
                         (1, "Sam", "FernleafCard_Statement_test.pdf"))
        # the raw download is untouched and a second run changes nothing
        self.assertNotIn("87.43", (self.root / "exports" / "2026-01-31" / "fernleaf_activity_a.csv").read_text())
        before = (self.root / "ledger" / "transactions.csv").read_bytes()
        self.run_ingest([stmt])
        self.assertEqual(before, (self.root / "ledger" / "transactions.csv").read_bytes())

    def test_a_second_identical_charge_is_not_swallowed(self):
        self.card_file("2026-01-03,2026-01-04,BEAN & BARLEY CAFE,Dining,5.25,\n")
        stmt = card_statement("0.00", "10.50", [(4, "BEAN & BARLEY CAFE", "-5.25"), (4, "BEAN & BARLEY CAFE", "-5.25")])
        res = ingest.accept_missing(self.root, "fernleaf", "Sam", "2026-01-31", stmts=[stmt])
        self.assertEqual(res["refused"], {})
        self.assertEqual(sorted(r["id"][-2:] for r in self.ledger()), ["-1", "-2"])

    def test_it_will_not_add_rows_when_the_gap_is_not_explained(self):
        self.card_file("2026-01-03,2026-01-04,SOMETHING ELSE,Misc,100.00,\n")
        stmt = card_statement("0.00", "150.00", [(4, "HEARTHSTONE MARKET", "-150.00")])
        with self.assertRaises(DataError):
            ingest.accept_missing(self.root, "fernleaf", "Sam", "2026-01-31", stmts=[stmt])
        self.assertEqual(L.read_csv(self.root / "ledger" / "corrections.csv"), [])

    def test_a_later_download_that_includes_the_row_does_not_double_it(self):
        self.card_file("2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n")
        stmt = card_statement("0.00", "187.43", [(4, "HEARTHSTONE MARKET", "-100.00"), (20, "HEARTHSTONE MARKET", "-87.43")])
        ingest.accept_missing(self.root, "fernleaf", "Sam", "2026-01-31", stmts=[stmt])
        self.export("fernleaf_activity_a.csv", CARD_HEAD +
                    "2026-01-03,2026-01-04,HEARTHSTONE MARKET,Groceries,100.00,\n"
                    "2026-01-19,2026-01-20,HEARTHSTONE MARKET,Groceries,87.43,\n", day="2026-02-15")
        res = self.run_ingest([stmt])
        self.assertEqual(res["refused"], {})
        self.assertEqual(len(self.ledger()), 2)


class TestMonthly(unittest.TestCase):
    def row(self, d, amount, kind, category="x"):
        return {"date": d, "amount": amount, "kind": kind, "category": category}

    def test_totals_leave_out_transfers_and_net_refunds_and_flag_partial_months(self):
        import monthly
        rows = [self.row("2026-03-05", "1000.00", "income"),
                self.row("2026-03-06", "-40.00", "spend"),
                self.row("2026-03-07", "15.00", "spend"),             # a refund is negative spending
                self.row("2026-03-08", "-2000.00", "spend", "Home: kitchen remodel"),
                self.row("2026-03-09", "-900.00", "loan"),
                self.row("2026-03-10", "-500.00", "transfer"),
                self.row("2026-03-10", "500.00", "transfer"),
                self.row("2026-03-11", "300.00", "invest"),
                self.row("2026-03-12", "-7.00", "unclassified"),
                self.row("2026-04-02", "-5.00", "spend")]
        cov = {"a": ("2026-03-01", "2026-04-15")}
        m = {x["month"]: x for x in monthly.compute(rows, cov, {"Home: kitchen remodel"})}
        mar = m["2026-03"]
        self.assertEqual((mar["income_in"], mar["spent_out"], mar["oneoff_out"], mar["loan_out"]),
                         (Decimal("1000.00"), Decimal("25.00"), Decimal("2000.00"), Decimal("900.00")))
        self.assertEqual((mar["transfers_net"], mar["unsorted_rows"], mar["unsorted_out"]),
                         (Decimal("0.00"), 1, Decimal("7.00")))
        self.assertEqual(mar["partial"], [])
        self.assertEqual(m["2026-04"]["partial"], ["a"])  # coverage stops mid-April


def ledger_row(account, d, desc, amount, **kw):
    r = {c: "" for c in L.LEDGER_COLS}
    r.update({"id": f"{account}-{d}-{desc}-{amount}", "account": account, "date": d, "description": desc, "amount": amount})
    r.update(kw)
    return r


class TestReconcile(Base):
    def otter(self, **over):
        s = {"kind": "otterbrook", "path": "statements/O_2026-01-31.pdf", "start": date(2026, 1, 1), "end": date(2026, 1, 31),
             "begin": Decimal("100.00"), "deposits": Decimal("50.00"), "withdrawals": Decimal("-10.00"),
             "end_balance": Decimal("140.00"), "self_check_diff": Decimal("0.00"),
             "lines": [{"date": date(2026, 1, 5), "description": "COFFEE", "amount": Decimal("-10.00"), "balance": Decimal("90.00")},
                       {"date": date(2026, 1, 6), "description": "SALARY", "amount": Decimal("50.00"), "balance": Decimal("140.00")}]}
        s.update(over)
        return s

    def test_statement_ties_then_a_changed_row_is_named(self):
        import reconcile
        rows = [ledger_row("otterbrook", "2026-01-05", "COFFEE", "-10.00"), ledger_row("otterbrook", "2026-01-06", "SALARY", "50.00")]
        ok = reconcile.check_checking("otterbrook", rows, [self.otter()])
        self.assertEqual((ok[0]["status"], ok[0]["diff"]), ("ok", "0.00"))
        rows[0]["amount"] = "-12.00"  # a wrong row in the ledger: the statement wins
        bad = reconcile.check_checking("otterbrook", rows, [self.otter()])[0]
        self.assertEqual((bad["status"], bad["diff"]), ("DISAGREES", "2.00"))
        self.assertEqual(bad["statement_only"], [("2026-01-05", "COFFEE", "-10.00")])
        self.assertEqual(bad["ledger_only"], [("2026-01-05", "COFFEE", "-12.00")])

    def test_a_broken_chain_between_statements_is_reported(self):
        import reconcile
        a = self.otter()
        b = self.otter(start=date(2026, 2, 1), end=date(2026, 2, 28), begin=Decimal("141.00"), end_balance=Decimal("141.00"),
                       deposits=Decimal("0.00"), withdrawals=Decimal("0.00"), lines=[])
        res = reconcile.check_checking("otterbrook", [ledger_row("otterbrook", "2026-01-05", "COFFEE", "-10.00"),
                                                      ledger_row("otterbrook", "2026-01-06", "SALARY", "50.00")], [a, b])
        self.assertEqual(res[1]["status"], "DISAGREES")
        self.assertTrue(any("not last statement's closing" in p for p in res[1]["problems"]))

    def test_estimates_you_told_us_survive_a_rewrite_of_balances(self):
        import reconcile
        reconcile.add_estimate(self.root, "home", "450000.00", "2026-10-22", "Sam, from memory")
        reconcile.write_balances(self.root, [self.otter()])
        reconcile.write_balances(self.root, [self.otter()])
        rows = L.read_csv(self.root / "ledger" / "balances.csv")
        self.assertEqual(sorted((r["account"], r["confidence"]) for r in rows), [("home", "estimate"), ("otterbrook", "exact")])


class TestYearBridge(Base):
    def stmt(self, month, begin, contrib, wd, div, change, end, price, qty):
        end_day = date(2026, month, 28)
        return {"kind": "tidewell", "path": f"statements/T_{month}.pdf", "start": date(2026, month, 1), "end": end_day,
                "begin_value": Decimal(begin), "contributions": Decimal(contrib), "withdrawals": Decimal(wd),
                "dividends": Decimal(div), "market_change": Decimal(change), "end_value": Decimal(end),
                "cash": Decimal("0.00"), "holdings": {"FUND": {"quantity": Decimal(qty), "price": Decimal(price), "value": Decimal(end)}}}

    def test_money_moved_out_is_not_counted_as_market_loss(self):
        import year_bridge
        s1 = self.stmt(1, "1000.00", "0.00", "0.00", "0.00", "10.00", "1010.00", "10.00", "101")
        s2 = self.stmt(2, "1010.00", "0.00", "-500.00", "0.00", "5.05", "515.05", "10.05", "51.2")
        rows = [ledger_row("tidewell", "2026-02-10", "EFT SENT", "-500.00", action="WITHDRAWAL", id="t1", pair_id="o1"),
                ledger_row("otterbrook", "2026-02-10", "XFER FROM", "500.00", id="o1", pair_id="t1")]
        months, years = year_bridge.build("tidewell", rows, [s1, s2])
        y = years[0]
        self.assertEqual((y["money_out"], y["market_change"], y["bridge_check"]), (Decimal("-500.00"), Decimal("15.05"), Decimal("0.00")))
        self.assertEqual(y["money_out_to"], "otterbrook: 500.00")
        self.assertEqual(y["flag"], "ok")


PLAN_HEADER = "block,line,amount,fixed,note,paid_by\n"


class TestPlan(Base):
    def setUp(self):
        super().setUp()
        L.write_csv(self.root / "ledger" / "transactions.csv", L.LEDGER_COLS, [])

    def put(self, plan, bmap="category,line,note\n"):
        (self.root / "ledger" / "plan.csv").write_text(plan, encoding="utf-8")
        (self.root / "ledger" / "budget_map.csv").write_text(bmap, encoding="utf-8")
        import plan as P
        return P.check(self.root)

    def test_a_good_plan_adds_up_to_the_flex_pool(self):
        res = self.put(PLAN_HEADER + "income,Pay,1000.00,1,,bank\ncommitted,Rent,-600,1,,bank\n"
                       "lumpy,Repairs,-100.00,0,,bank\nsavings,Brokerage,-50.00,1,,bank\n,,,,,\n")
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["flex_pool"], Decimal("250.00"))

    def test_errors_name_the_row_and_say_what_to_fix(self):
        res = self.put("\ufeff" + PLAN_HEADER +
                       "income,Pay,1000.00,1,,bank\n"               # row 2 fine (BOM tolerated)
                       "committed,Rent,600.00,1,,bank\n"            # row 3 plus sign on spending
                       "committed,Phone,\"$95.00\",1,,card\n"        # row 4 dollar sign
                       "committed,Gas,\u221220.00,0,,card\n"         # row 5 long minus
                       "fun,Dining,-20.00,0,,card\n"                # row 6 unknown block
                       "committed,rent,-5.00,0,,bank\n"             # row 7 duplicate name
                       "committed,Water,-5.00,2,,bank\n")           # row 8 bad fixed
        text = "\n".join(res["errors"])
        for needle in ("plan.csv row 3 (Rent): spending needs a minus sign", "row 4 (Phone): amount '$95.00'",
                       "row 5 (Gas)", "long dash", "row 6 (Dining): block 'fun'", "row 7 (rent): the name is used twice",
                       "row 8 (Water): fixed must be 1"):
            self.assertIn(needle, text)
        self.assertNotIn("row 2", text)

    def test_a_renamed_line_is_caught_in_the_map(self):
        res = self.put(PLAN_HEADER + "committed,Electricity,-130.00,0,,bank\n",
                       "category,line,note\nUtilities: electric,Electric,\n")
        self.assertTrue(any("budget_map.csv row 2" in e and "Closest line in plan.csv: 'Electricity'" in e for e in res["errors"]))

    def test_add_line_refuses_a_wrong_line_and_leaves_the_file_alone(self):
        import plan as P
        self.put(PLAN_HEADER + "income,Pay,1000.00,1,,bank\n")
        before = (self.root / "ledger" / "plan.csv").read_text()
        res, mine = P.add_line(self.root, "committed", "Rent", "600.00", "1", "bank", "")  # plus sign on spending
        self.assertTrue(mine)
        self.assertEqual(before, (self.root / "ledger" / "plan.csv").read_text())
        res, mine = P.add_line(self.root, "committed", "Rent", "-600.00", "1", "bank", "")
        self.assertEqual(mine, [])
        self.assertIn("Rent", (self.root / "ledger" / "plan.csv").read_text())


class TestBudget(Base):
    def test_status_flex_cushion_and_card_versus_bank(self):
        import budget
        import plan as P
        plan = [("income", "Pay", "3000.00", 1), ("committed", "Groceries", "-310.00", 0), ("committed", "Rent", "-500.00", 1),
                ("committed", "Phone", "-50.00", 1), ("committed", "Fun", "-200.00", 0), ("committed", "Gas", "-100.00", 0),
                ("lumpy", "Repairs", "-40.00", 0), ("savings", "Brokerage", "-100.00", 1)]
        res = {"plan": [{"block": b, "line": n, "amount": Decimal(a), "fixed": f, "note": "", "paid_by": "bank", "row": i}
                        for i, (b, n, a, f) in enumerate(plan, 2)],
               "map": [{"category": c, "line": ln} for c, ln in
                       [("Pay: Sam", "Pay"), ("Groceries", "Groceries"), ("Rent", "Rent"), ("Phone", "Phone"), ("Fun", "Fun"),
                        ("Gas", "Gas"), ("Savings: brokerage", "Brokerage"), ("Remodel", P.ONE_OFF)]]}

        def row(d, amt, kind, cat, acct="otterbrook"):
            return {"date": d, "amount": amt, "kind": kind, "category": cat, "account": acct}

        rows = [row("2026-06-05", "3000.00", "income", "Pay: Sam"),
                row("2026-06-03", "-100.00", "spend", "Groceries"), row("2026-06-04", "20.00", "spend", "Groceries"),  # a refund
                row("2026-06-01", "-500.00", "spend", "Rent"), row("2026-06-02", "-150.00", "spend", "Fun", "fernleaf"),
                row("2026-06-06", "-130.00", "spend", "Gas"), row("2026-06-07", "-90.00", "spend", "Dining", "fernleaf"),
                row("2026-06-08", "-100.00", "transfer", "Savings: brokerage"), row("2026-06-09", "-9999.00", "spend", "Remodel"),
                row("2026-06-20", "-77.00", "spend", "Dining"),   # after the as-of date: not counted yet
                row("2026-05-30", "-55.00", "spend", "Dining")]   # another month
        b = budget.compute(res, rows, "2026-06", date(2026, 6, 15), {"fernleaf"})
        status = {l["line"]: l["status"] for l in b["lines"]}
        self.assertEqual(status, {"Pay": "ok", "Groceries": "ok", "Rent": "ok", "Phone": "not posted",
                                  "Fun": "watch", "Gas": "over", "Repairs": "not posted", "Brokerage": "ok"})
        spent = {l["line"]: l["spent"] for l in b["lines"]}
        self.assertEqual(spent["Groceries"], Decimal("80.00"))        # the refund reduces spending
        self.assertEqual((b["flex_pool"], b["flex_spent"], b["flex_left"]), (Decimal("1700.00"), Decimal("90.00"), Decimal("1610.00")))
        self.assertEqual(b["cushion"], Decimal("1410.00"))             # set bills at plan, the rest at pace
        self.assertEqual((b["card"], b["bank"]), (Decimal("240.00"), Decimal("710.00")))
        self.assertEqual(b["oneoff"], {"Remodel": Decimal("9999.00")})  # kept out of everything else
        self.assertEqual(b["extra_income"], [])
        res["plan"][0]["note"] = "extra goes to the emergency fund"
        rows.append(row("2026-06-12", "1000.00", "income", "Pay: Sam"))  # a third paycheck
        b = budget.compute(res, rows, "2026-06", date(2026, 6, 15), {"fernleaf"})
        self.assertEqual((b["extra_income"][0]["extra"], b["extra_income"][0]["note"]),
                         (Decimal("1000.00"), "extra goes to the emergency fund"))


class TestPhonePage(Base):
    def test_page_is_self_contained_and_shows_only_script_numbers(self):
        import budget
        import render_page
        res = {"plan": [{"block": "income", "line": "Pay", "amount": Decimal("1000.00"), "fixed": 1, "note": "n", "paid_by": "bank", "row": 2},
                        {"block": "committed", "line": "Food <b>", "amount": Decimal("-300.00"), "fixed": 0, "note": "", "paid_by": "card", "row": 3}],
               "map": [{"category": "Pay: Sam", "line": "Pay"}, {"category": "Groceries", "line": "Food <b>"}]}
        rows = [{"date": "2026-06-05", "amount": "1000.00", "kind": "income", "category": "Pay: Sam", "account": "otterbrook"},
                {"date": "2026-06-06", "amount": "-120.00", "kind": "spend", "category": "Groceries", "account": "fernleaf",
                 "description": "HEARTHSTONE MARKET"}]
        b = budget.compute(res, rows, "2026-06", date(2026, 6, 15), {"fernleaf"})
        page = render_page.render(b, "Out of date", [])
        for needle in ("1,000.00", "120.00", "Out of date", "Food &lt;b&gt;", "width=device-width"):
            self.assertIn(needle, page)
        for banned in ("<script", "http", "src=", "HEARTHSTONE", "otterbrook"):  # no code, no network, no payees, no accounts
            self.assertNotIn(banned, page)


class TestRoutine(Base):
    def test_a_routine_stops_at_the_first_failed_step(self):
        import routine
        calls = []

        def runner(args):
            calls.append(args[0])
            return (2, "STOP: the card does not tie") if args[0] == "reconcile.py" else (0, "fine")

        done, failed = routine.run_steps(routine.steps_for("monthly", date(2026, 10, 22)), runner)
        self.assertEqual(failed[1], "Tie every statement to the ledger, to the cent")
        self.assertEqual(calls[-1], "reconcile.py")           # nothing ran after the failure
        self.assertNotIn("monthly.py", calls)

    def test_each_routine_includes_the_one_before_it(self):
        import routine
        w, m, q = (routine.steps_for(r, date(2026, 10, 22)) for r in ("weekly", "monthly", "quarterly"))
        self.assertEqual(m[:len(w)], w)
        self.assertEqual(q[:len(m)], m)
        self.assertEqual(routine.prev_month(date(2027, 1, 5)), "2026-12")

    def test_net_worth_uses_each_accounts_latest_balance(self):
        import networth
        rows = [{"as_of": "2026-07-31", "account": "bank", "amount": "100.00", "source": "s1", "confidence": "exact"},
                {"as_of": "2026-08-31", "account": "bank", "amount": "150.00", "source": "s2", "confidence": "exact"},
                {"as_of": "2026-10-22", "account": "loan", "amount": "-40.00", "source": "Sam", "confidence": "estimate"}]
        latest, total, est = networth.summarize(rows)
        self.assertEqual((total, est, len(latest)), (Decimal("110.00"), Decimal("-40.00"), 2))


class TestReturns(Base):
    def month(self, begin, change, end, start, end_date, base):
        return {"market_change": Decimal(change), "base": Decimal(base), "start": start,
                "statement": {"begin_value": Decimal(begin), "end": end_date, "end_value": Decimal(end)}}

    def test_with_no_flows_both_returns_are_the_plain_return(self):
        import returns
        m = [self.month("1000.00", "100.00", "1100.00", date(2026, 1, 1), date(2026, 1, 31), "1000.00")]
        self.assertEqual(returns.time_weighted(m), Decimal("0.1"))
        self.assertAlmostEqual(float(returns.money_weighted("a", [], m)), 0.1, places=4)

    def test_money_weighted_return_solves_for_the_dated_flows(self):
        import returns
        m = [self.month("1000.00", "150.00", "1650.00", date(2026, 1, 1), date(2026, 1, 31), "1250.00")]
        rows = [{"account": "a", "action": "CONTRIBUTION", "date": "2026-01-16", "amount": "500.00"}]
        r = float(returns.money_weighted("a", rows, m))
        tau = 15 / 30
        self.assertAlmostEqual(1000 * (1 + r) + 500 * (1 + r) ** (1 - tau), 1650, delta=0.05)

    def test_money_taken_out_is_followed_to_the_one_off_it_paid_for(self):
        import returns
        rows = [{"id": "t1", "account": "tidewell", "action": "WITHDRAWAL", "date": "2026-05-08", "amount": "-100.00", "pair_id": "o1",
                 "kind": "transfer", "category": "", "description": ""},
                {"id": "o1", "account": "otterbrook", "action": "", "date": "2026-05-08", "amount": "100.00", "pair_id": "t1",
                 "kind": "transfer", "category": "", "description": ""},
                {"id": "o2", "account": "otterbrook", "action": "", "date": "2026-05-11", "amount": "-60.00", "pair_id": "",
                 "kind": "spend", "category": "Remodel", "description": "CHECK"},
                {"id": "o3", "account": "otterbrook", "action": "", "date": "2026-12-11", "amount": "-60.00", "pair_id": "",
                 "kind": "spend", "category": "Remodel", "description": "LATER"}]
        item = returns.where_it_went(rows, "tidewell", {"Remodel"})[0]
        self.assertEqual([u["id"] for u in item["uses"]], ["o2"])   # the later one is outside the window


class TestEmergencyFund(Base):
    def test_targets_under_each_definition_and_how_far_checking_goes(self):
        import emergency_fund
        plan = [{"block": "committed", "line": "Rent", "amount": Decimal("-1000.00")},
                {"block": "committed", "line": "Dining", "amount": Decimal("-200.00")},
                {"block": "lumpy", "line": "Repairs", "amount": Decimal("-100.00")},
                {"block": "savings", "line": "Emergency fund", "amount": Decimal("-300.00")},
                {"block": "income", "line": "Pay", "amount": Decimal("3000.00")}]
        bal = [{"as_of": "2026-07-31", "account": "bank", "amount": "5000.00"},
               {"as_of": "2026-08-31", "account": "bank", "amount": "7800.00"}]
        r = emergency_fund.compute(plan, bal, "bank", ["Rent"])
        everything, essentials = r["rows"]
        self.assertEqual((everything["monthly"], everything["target"]), (Decimal("1300.00"), Decimal("7800.00")))  # savings are not expenses
        self.assertEqual((essentials["monthly"], essentials["target"]), (Decimal("1000.00"), Decimal("6000.00")))
        self.assertEqual(float(everything["checking_covers"]), 6.0)                 # uses the latest balance
        self.assertAlmostEqual(float(essentials["months_of_setaside"]), 20.0)
        self.assertEqual(emergency_fund.compute(plan, bal, "bank", ["Nope"])["missing"], ["Nope"])


class TestMortgageWhatIf(Base):
    def test_payment_payoff_and_the_break_even_sit_near_the_loan_rate(self):
        import mortgage_whatif as M
        pay = M.standard_payment(Decimal("340000.00"), "6.125", 360)
        self.assertEqual(pay, Decimal("2065.88"))
        n0, i0 = M.amortize(Decimal("340000.00"), "6.125", pay)
        self.assertEqual(n0, 360)                                    # the standard payment clears the loan on schedule
        nA, iA = M.amortize(Decimal("340000.00"), "6.125", pay, Decimal("500"))
        self.assertTrue(nA < n0 and iA < i0)
        be = float(M.break_even(Decimal("326000.00"), "6.125", pay, Decimal("500")))
        self.assertAlmostEqual(be, 0.06125, delta=0.002)             # paying down earns about the loan rate
        low, _ = M.compare(Decimal("326000.00"), "6.125", pay, Decimal("500"), "0.03")
        high, _ = M.compare(Decimal("326000.00"), "6.125", pay, Decimal("500"), "0.09")
        self.assertTrue(low < 0 < high)                              # below the break-even paying down wins, above it investing wins


if __name__ == "__main__":
    unittest.main()
