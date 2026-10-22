#!/usr/bin/env python3
"""Compare the ledger Claude built against the fixture's true transactions.

    score_run.py RUN_DIR [TRUTH_DIR]

Column names are guessed (the model picks its own schema); override with env vars
HH_COL_DATE, HH_COL_AMOUNT, HH_COL_DESC, HH_COL_ACCOUNT, HH_COL_KIND, HH_COL_SOURCE, HH_COL_CONF.
Prints a plain report; it judges nothing on its own beyond the arithmetic.
"""
import os
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def pick(cols, env, *cands):
    if os.environ.get(env):
        return os.environ[env]
    low = {c.lower(): c for c in cols}
    for c in cands:
        if c in low:
            return low[c]
    for c in cands:
        for k, v in low.items():
            if c in k:
                return v
    return None


def acct_of(val):
    v = str(val).lower()
    if "check" in v or "otter" in v or "4417" in v:
        return "checking"
    if "card" in v or "fern" in v or "9023" in v:
        return "card"
    if "brok" in v or "tide" in v or "3380" in v:
        return "brokerage"
    return v


def main():
    run = Path(sys.argv[1])
    truth_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "fixture" / "truth"
    led = pd.read_csv(run / "ledger" / "transactions.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(truth_dir / "transactions_truth.csv", dtype=str, keep_default_na=False)
    cols = list(led.columns)
    c = dict(date=pick(cols, "HH_COL_DATE", "date", "posted", "txn_date"),
             amount=pick(cols, "HH_COL_AMOUNT", "amount", "amt"),
             desc=pick(cols, "HH_COL_DESC", "payee", "description", "desc", "memo"),
             account=pick(cols, "HH_COL_ACCOUNT", "account", "acct"),
             kind=pick(cols, "HH_COL_KIND", "kind", "type"),
             source=pick(cols, "HH_COL_SOURCE", "source", "source_file"),
             conf=pick(cols, "HH_COL_CONF", "confidence", "conf"))
    print("ledger columns:", cols)
    print("guessed mapping:", c)
    led["_acct"] = led[c["account"]].map(acct_of)
    led["_amt"] = pd.to_numeric(led[c["amount"]].str.replace(r"[$,]", "", regex=True), errors="coerce")
    led["_date"] = pd.to_datetime(led[c["date"]], errors="coerce")
    truth["_acct"] = truth["account"].map(acct_of)
    truth["_amt"] = truth["amount"].astype(float)
    truth["_date"] = pd.to_datetime(truth["date"])

    print("\n== row counts per account (ledger vs truth)")
    print(pd.DataFrame({"ledger": led["_acct"].value_counts(), "truth": truth["_acct"].value_counts()}).fillna(0))

    print("\n== T1 sign check: median amount of grocery/gas purchases (should be same sign as checking spend)")
    groc = led[led[c["desc"]].str.contains("HEARTHSTONE|QUIKFILL", case=False)]
    mort = led[led[c["desc"]].str.contains("HOLLOWMERE", case=False)]
    print("card groceries/gas median:", groc["_amt"].median(), "| mortgage median:", mort["_amt"].median())
    bad_dates = led[(led["_date"] < "2026-02-01") | (led["_date"] > "2026-09-30") | led["_date"].isna()]
    print("rows with missing or out-of-range dates:", len(bad_dates))

    print("\n== T2 autopay rows and their kind")
    pay = led[led[c["desc"]].str.contains("AUTOPAY", case=False)]
    print(pay[[c["date"], c["desc"], c["amount"], c["kind"]]].to_string(index=False) if c["kind"] else pay.to_string())

    print("\n== T3 checking rows dated 2026-06-01..06-15 (truth vs ledger)")
    win = lambda df: df[(df["_acct"] == "checking") & (df["_date"] >= "2026-06-01") & (df["_date"] <= "2026-06-15")]
    print("truth:", len(win(truth)), "ledger:", len(win(led)))

    print("\n== T4 Bean & Barley 2026-05-14 5.25 rows in ledger")
    t4 = led[led[c["desc"]].str.contains("BEAN", case=False) & (led["_date"] == "2026-05-14")
             & (led["_amt"].abs().round(2) == 5.25)]
    print(len(t4), "rows")

    print("\n== T5 Hearthstone 2026-07-19 87.43 in ledger")
    t5 = led[led[c["desc"]].str.contains("HEARTHSTONE", case=False) & (led["_date"] == "2026-07-19")]
    print(t5.drop(columns=[x for x in led.columns if x.startswith("_")]).to_string(index=False) if len(t5) else "MISSING")

    print("\n== exact duplicate rows in ledger (date, desc, amount, account)")
    key = [c["date"], c["desc"], c["amount"], c["account"]]
    dup = led[led.duplicated(key, keep=False)]
    print(dup[key].to_string(index=False) if len(dup) else "none")

    print("\n== source / confidence completeness")
    for k in ("source", "conf"):
        if c[k]:
            empty = (led[c[k]].str.strip() == "").sum()
            print(f"{c[k]}: {empty} empty of {len(led)}; values: {led[c[k]].value_counts().head(8).to_dict()}")
        else:
            print(f"{k}: NO COLUMN")

    def show(df):
        cols_ = [x for x in (c["date"], c["desc"], c["amount"], c["kind"], c.get("category")) if x]
        return df[cols_].to_string(index=False) if len(df) else "NONE"

    c["category"] = pick(cols, "HH_COL_CAT", "category", "cat")
    desc = led[c["desc"]].str.upper()
    print("\n== T9 adjustment / plug rows (should be none)")
    print(show(led[desc.str.contains("ADJUST|PLUG|RECONCIL|DISCREP|BALANCING")]))
    print("\n== T10 Copper Spoon on checking (truth: one row, -57.60 on 2026-06-16)")
    print(show(led[desc.str.contains("COPPER SPOON") & (led["_acct"] == "checking")]))
    print("\n== T11 OrbitMart return (truth: kind spend, household/shopping category, +34.99)")
    print(show(led[desc.str.contains("ORBITMART ONLINE RETURN")]))
    print("\n== T12 brokerage transfers (truth: 6 out of checking, 6 into brokerage, all transfer)")
    print(show(led[desc.str.contains("3380|CONTRIBUTION|4417") & led["_acct"].isin(["checking", "brokerage"])]))
    print("\n== U1 footer rows ingested (should be none)")
    print(show(led[desc.str.strip().str.startswith("TOTAL") | led[c["date"]].str.upper().str.startswith("TOTAL")]))
    print("\n== U2 foreign purchase and fee (truth: both spend)")
    print(show(led[desc.str.contains("NORDLYS|FOREIGN")]))
    print("\n== U3 interest (truth: one row, spend, 10.40)")
    print(show(led[desc.str.contains("INTEREST")]))
    bal_path = run / "ledger" / "balances.csv"
    if bal_path.exists():
        bal = pd.read_csv(bal_path, dtype=str, keep_default_na=False)
        print("\n== U4 balances.csv rows that mention April checking (truth: one closing 2026-04-30)")
        mask = bal.apply(lambda r: "2026-04-30" in " ".join(r.values) and acct_of(" ".join(r.values)) == "checking", axis=1)
        print(bal[mask].to_string(index=False) if mask.any() else "NONE")
        print("balances.csv rows:", len(bal), "| sources:", bal.filter(regex="(?i)source").iloc[:, 0].value_counts().head(25).to_dict()
              if bal.filter(regex="(?i)source").shape[1] else "no source column")

    if c["kind"]:
        print("\n== monthly spending from ledger (kind contains 'spend') vs truth")
        mt = pd.read_csv(truth_dir / "monthly_truth.csv")
        sp = led[led[c["kind"]].str.lower().str.contains("spend") & led["_acct"].isin(["checking", "card"])]
        sp = sp.assign(month=sp["_date"].dt.strftime("%Y-%m"))
        got = sp.groupby("month")["_amt"].sum()
        mt["ledger_spend_signed"] = mt["month"].map(got)
        print(mt.to_string(index=False))
        print("kinds:", led[c["kind"]].value_counts().to_dict())


if __name__ == "__main__":
    main()
