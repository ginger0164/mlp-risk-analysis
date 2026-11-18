"""Step 2: returns, T0 weights and baseline risk statistics (Python reference values)."""
import json
import numpy as np, pandas as pd
from scipy import stats

Q = "data/qc"
OUT = "results/step2"
HIST_START, T0, WINDOW = "2019-03-01", pd.Timestamp("2026-06-12"), 250
MLP = ("DMLP ARLP WES UAN ET HESM MPLX SPH EPD CQP DKL GEL MMLP PAA USAC CAPL GLP SUN "
       "WLKP BSM MNR TXO NRP").split()
PF2 = "DMLP ARLP WES UAN HESM MPLX EPD CQP CAPL GLP WLKP BSM NRP".split()
SUB = {"DMLP": "Oil and gas royalties", "BSM": "Oil and gas royalties", "ARLP": "Coal and mineral resources",
       "NRP": "Coal and mineral resources", "UAN": "Nitrogen fertilizers", "WLKP": "Petrochemicals",
       "SPH": "Fuel distribution", "GLP": "Fuel distribution", "CAPL": "Fuel distribution",
       "SUN": "Fuel distribution", "MNR": "Oil and gas production", "TXO": "Oil and gas production"}
for t in "WES ET HESM MPLX EPD CQP DKL GEL MMLP PAA USAC".split():
    SUB[t] = "Midstream"

import os; os.makedirs(OUT, exist_ok=True)
adj = pd.read_csv(f"{Q}/adjclose.csv", index_col=0, parse_dates=True)
ret = adj.pct_change(fill_method=None).loc[HIST_START:]
ret.to_csv(f"{OUT}/returns_from_2019.csv")

win = ret.loc[:T0].iloc[-WINDOW:]
assert win.index[-1] == T0 and win[MLP + ["SPY"]].notna().all().all()
w = pd.DataFrame(0.0, index=MLP, columns=["PF1", "PF2"])
w["PF1"] = 1 / len(MLP); w.loc[PF2, "PF2"] = 1 / len(PF2)

spy = win["SPY"]
def ols(y):
    r = stats.linregress(spy, y); n = len(y)
    tc = stats.t.ppf(0.975, n - 2)
    return dict(beta=r.slope, beta_se=r.stderr, beta_lo=r.slope - tc * r.stderr, beta_hi=r.slope + tc * r.stderr, r2=r.rvalue ** 2)

sec = []
for t in MLP:
    y = win[t]
    sec.append(dict(ticker=t, subsector=SUB[t], in_PF2=t in PF2, ann_vol=y.std(ddof=1) * np.sqrt(252),
                    worst_day=y.min(), best_day=y.max(), **ols(y)))
sec = pd.DataFrame(sec).set_index("ticker")

corr = win[MLP].corr()
port = {}
for pf in ["PF1", "PF2"]:
    names = w.index[w[pf] > 0]
    pr = win[MLP] @ w[pf]
    c = corr.loc[names, names].values; n = len(names)
    vol = pr.std(ddof=1) * np.sqrt(252)
    wavg = (w.loc[names, pf] * sec.loc[names, "ann_vol"]).sum()
    port[pf] = dict(n=n, ann_vol=vol, **ols(pr), hhi=(w[pf] ** 2).sum(), eff_n=1 / (w[pf] ** 2).sum(),
                    avg_pair_corr=(c.sum() - n) / (n * (n - 1)), wavg_stock_vol=wavg, div_ratio=wavg / vol,
                    worst_day=pr.min(), worst_day_date=str(pr.idxmin().date()),
                    max_subsector_weight=w[pf].groupby(pd.Series(SUB)).sum().max())
port = pd.DataFrame(port)
subw = w.groupby(pd.Series(SUB)).sum()
spy_vol = spy.std(ddof=1) * np.sqrt(252)

# robustness: 500-day window volatility
win500 = ret.loc[:T0].iloc[-500:]
vol500 = {pf: (win500[MLP] @ w[pf]).std(ddof=1) * np.sqrt(252) for pf in ["PF1", "PF2"]}

pd.set_option("display.width", 220)
print("window", win.index[0].date(), win.index[-1].date(), len(win), "| SPY vol", round(spy_vol, 4))
print(sec.round(4).sort_values("ann_vol").to_string())
print(port.to_string())
print(subw.round(4).to_string())
print("500d vol", {k: round(v, 4) for k, v in vol500.items()}, "window500 start", win500.index[0].date())
sec.to_csv(f"{OUT}/security_stats.csv"); port.to_csv(f"{OUT}/portfolio_stats.csv"); corr.to_csv(f"{OUT}/corr.csv")
w.to_csv(f"{OUT}/weights_T0.csv"); win.to_csv(f"{OUT}/window_returns.csv")
json.dump({"T0": str(T0.date()), "window_start": str(win.index[0].date()), "window_end": str(win.index[-1].date()),
           "n": len(win), "spy_vol": spy_vol, "vol500": vol500}, open(f"{OUT}/meta.json", "w"), indent=2)
