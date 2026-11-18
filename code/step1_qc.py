"""Step 1 quality check: parse raw Yahoo/FRED files into tidy panels and audit them.

Usage: python step1_qc.py <raw_dir> <out_dir>
"""
import json, re, sys
from pathlib import Path
import numpy as np
import pandas as pd

raw, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
MLP = ("DMLP ARLP WES UAN ET HESM MPLX SPH EPD CQP DKL GEL MMLP PAA USAC CAPL GLP SUN "
       "WLKP BSM MNR TXO NRP").split()
CUTOFF = pd.Timestamp("2026-11-03")  # drop the incomplete intraday bar of the download day
PF2 = "DMLP ARLP WES UAN HESM MPLX EPD CQP CAPL GLP WLKP BSM NRP".split()


def load_yahoo(path):
    res = json.loads(path.read_text(encoding="utf-8"))["chart"]["result"][0]
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True)
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    dates = ts.tz_convert(tz).tz_localize(None).normalize()
    q = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    df = pd.DataFrame({"close": q["close"], "adjclose": adj, "volume": q.get("volume")}, index=dates)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.loc[:CUTOFF]
    ev = res.get("events", {})
    div = pd.Series({pd.to_datetime(int(k), unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize(): v["amount"]
                     for k, v in ev.get("dividends", {}).items()}, dtype=float).sort_index()
    spl = ev.get("splits", {})
    return df, div, spl


def load_fred(series):
    csv, html = raw / f"{series}.csv", raw / f"{series}.html"
    if csv.exists():
        d = pd.read_csv(csv)
        d.columns = ["date", "value"]
        s = pd.Series(pd.to_numeric(d["value"], errors="coerce").values, index=pd.to_datetime(d["date"]))
    elif html.exists():
        pairs = re.findall(r"#(\d{4}-\d{2}-\d{2})\|\s*([\d.\-]+)", html.read_text(encoding="utf-8"))
        s = pd.Series({pd.Timestamp(a): float(b) if b != "." else np.nan for a, b in pairs})
    else:
        return None
    return s.sort_index().loc[:CUTOFF].rename(series)


prices, adjc, divs, rows = {}, {}, {}, []
tickers = [t for t in MLP + ["SPY", "HYG"] if (raw / f"{t}.json").exists()]
for t in tickers:
    df, div, spl = load_yahoo(raw / f"{t}.json")
    prices[t], adjc[t], divs[t] = df["close"], df["adjclose"], div
    rows.append({"ticker": t, "first_date": df.index.min().date(), "last_date": df.index.max().date(),
                 "n_rows": len(df), "missing_close": int(df["close"].isna().sum()),
                 "missing_adjclose": int(df["adjclose"].isna().sum()),
                 "nonpositive_close": int((df["close"] <= 0).sum()),
                 "n_dividends": len(div), "n_splits": len(spl), "in_PF2": t in PF2})
close, adj = pd.DataFrame(prices), pd.DataFrame(adjc)
cal = adj["SPY"].dropna().index  # SPY sessions = reference trading calendar
cov = pd.DataFrame(rows).set_index("ticker")

# coverage against the SPY calendar after each ticker's first observation
for t in tickers:
    s = adj[t].reindex(cal)
    live = s.loc[s.first_valid_index():]
    miss = live.isna()
    run = (miss != miss.shift()).cumsum()[miss]
    cov.loc[t, "sessions_since_first"] = len(live)
    cov.loc[t, "missing_sessions"] = int(miss.sum())
    cov.loc[t, "longest_gap_sessions"] = int(run.value_counts().max()) if miss.any() else 0
    cov.loc[t, "coverage_pct"] = round(100 * (1 - miss.mean()), 2)

ret = adj.reindex(cal).pct_change(fill_method=None)
ext = ret.stack().rename("ret").reset_index()
ext.columns = ["date", "ticker", "ret"]
ext = ext[ext["ret"].abs() > 0.15].sort_values("ret")

# dividend reconciliation: on ex-dates, adjusted return should equal (P_t + D)/P_{t-1} - 1 approximately
rec = []
for t in tickers:
    c = close[t].reindex(cal)
    for d, amt in divs[t].items():
        if d not in cal or cal.get_loc(d) == 0:
            continue
        prev = cal[cal.get_loc(d) - 1]
        if pd.isna(c.get(prev)) or pd.isna(c.get(d)):
            continue
        cash_ret = (c[d] + amt) / c[prev] - 1
        rec.append({"ticker": t, "ex_date": d.date(), "amount": amt, "adj_return": ret.loc[d, t],
                    "cash_return": cash_ret, "abs_diff": abs(ret.loc[d, t] - cash_ret)})
rec = pd.DataFrame(rec)

fred = {s: load_fred(s) for s in ["DCOILWTICO", "DGS10", "BAMLH0A0HYM2"]}
frow = []
for s, ser in fred.items():
    if ser is None:
        frow.append({"series": s, "status": "MISSING FILE"}); continue
    v = ser.dropna()
    frow.append({"series": s, "first_date": v.index.min().date(), "last_date": v.index.max().date(),
                 "n_obs": len(v), "n_blank_days": int(ser.isna().sum()), "min": v.min(), "max": v.max(),
                 "nonpositive": int((v <= 0).sum())})
fdf = pd.DataFrame(frow)

close.to_csv(out / "close.csv"); adj.to_csv(out / "adjclose.csv")
ret.to_csv(out / "daily_returns.csv")
pd.concat({k: v for k, v in fred.items() if v is not None}, axis=1).to_csv(out / "factors_raw.csv")
cov.to_csv(out / "coverage.csv"); ext.to_csv(out / "extreme_returns.csv", index=False)
rec.to_csv(out / "dividend_reconciliation.csv", index=False); fdf.to_csv(out / "fred_coverage.csv", index=False)

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 20)
print("CALENDAR", cal.min().date(), "to", cal.max().date(), len(cal), "SPY sessions")
print(cov.to_string())
print("\nFRED\n", fdf.to_string(index=False))
print(f"\nExtreme daily moves |r|>15%: {len(ext)}")
print(ext.head(12).to_string(index=False))
if len(rec):
    print(f"\nDividend events checked: {len(rec)}; max |adj - cash| return diff {rec.abs_diff.max():.2e}; "
          f">0.5%: {(rec.abs_diff > 0.005).sum()}")
