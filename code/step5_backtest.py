"""Step 5a: VaR backtests (pre-T0 hypothetical and out-of-sample) under model_config_v1.yaml."""
import hashlib, json, math, os
import numpy as np, pandas as pd, yaml
from scipy import stats

CFG = "config/model_config_v1.yaml"
cfg = yaml.safe_load(open(CFG)); HASH = hashlib.sha256(open(CFG, "rb").read()).hexdigest()
OUT = "results/step5"; os.makedirs(OUT, exist_ok=True)
R = pd.read_csv("results/step2/returns_from_2019.csv", index_col=0, parse_dates=True)
MLP = cfg["portfolios"]["PF1"]; PF = {k: cfg["portfolios"][k] for k in ("PF1", "PF2")}
VE = cfg["var_es"]; BT = cfg["backtest"]; LAM, SEED, WIN = VE["ewma"]["lambda"], VE["ewma"]["seed_days"], VE["hs"]["window"]
hist = R.loc[cfg["data"]["history_start"]:, MLP]
T0 = pd.Timestamp(cfg["dates"]["T0"])


def port_returns(ret, w):
    x = ret[w.index]; mask = x.notna(); miss = (w * ~mask).sum(axis=1); nav = mask.sum(axis=1)
    wadj = mask.mul(w, axis=1).add(mask.mul(miss / nav, axis=0))
    return (x.fillna(0) * wadj).sum(axis=1)

def q_loss(L, a): return float(np.sort(L)[math.ceil(a * len(L)) - 1])
def es(L, a):
    s = np.sort(L)[::-1]; q = len(L) * (1 - a); j = int(math.floor(q + 1e-12)); fr = q - j
    return float((s[:j].sum() + (fr * s[j] if fr > 1e-12 else 0)) / q)
def ewma_sig(r):
    r = np.asarray(r); v = np.var(r[:SEED], ddof=1); s = np.full(len(r) + 1, np.nan)
    for t in range(SEED, len(r)):
        s[t] = math.sqrt(v); v = LAM * v + (1 - LAM) * r[t] ** 2
    s[len(r)] = math.sqrt(v)
    return s  # s[t] forecasts r[t]; s[len] forecasts the next day
N = stats.norm
LEVELS = {"99": 0.99, "97.5": 0.975, "95": 0.95}


def forecasts(p_hist, t):
    """Forecasts for day index t of series p_hist (uses p_hist[:t] only)."""
    L = -p_hist[t - WIN:t]; s = ewma_sig(p_hist[:t]); sig_t = s[t]
    z = p_hist[t - WIN:t] / s[t - WIN:t]; Lf = -z * sig_t
    out = {}
    for k, a in LEVELS.items():
        out[f"HS_VaR{k}"] = q_loss(L, a); out[f"EWMA_VaR{k}"] = N.ppf(a) * sig_t; out[f"FHS_VaR{k}"] = q_loss(Lf, a)
    a = VE["es_confidence"]
    out["HS_ES"] = es(L, a); out["EWMA_ES"] = sig_t * N.pdf(N.ppf(a)) / (1 - a); out["FHS_ES"] = es(Lf, a)
    return out


rows = []
# ---- pre-T0 hypothetical backtest: constant T0 weights
pre = R.loc[BT["pre_T0"]["start"]:BT["pre_T0"]["end"]].index
assert len(pre) == BT["pre_T0"]["forecast_days"]
for k, names in PF.items():
    w = pd.Series(1 / len(names), index=names)
    p = port_returns(hist.loc[:T0], w); vals = p.values; idx = p.index
    for d in pre:
        t = idx.get_loc(d); f = forecasts(vals, t)
        rows.append({"period": "pre_T0", "portfolio": k, "date": d, "loss": -vals[t], **f})
# ---- out-of-sample: buy-and-hold drift from T0 equal weights
oos = R.loc[BT["oos"]["start"]:BT["oos"]["end"]].index
assert len(oos) == BT["oos"]["forecast_days"]
for k, names in PF.items():
    w = pd.Series(1 / len(names), index=names)
    for d in oos:
        p = port_returns(hist.loc[:d], w)            # revalue current (BOD) book over history incl. day d
        vals = p.values; t = len(vals) - 1
        f = forecasts(vals, t)
        actual = float((w * R.loc[d, names]).sum())
        rows.append({"period": "oos", "portfolio": k, "date": d, "loss": -actual, **f,
                     **{f"w_{n}": w[n] for n in names}})
        w = w * (1 + R.loc[d, names]); w = w / w.sum()   # drift to next BOD
bt = pd.DataFrame(rows)
bt.to_csv(f"{OUT}/backtest_daily.csv", index=False)


def kupiec(x, n, p):
    if x == 0: lr = -2 * n * math.log(1 - p)
    elif x == n: lr = -2 * n * math.log(p)
    else: lr = -2 * ((n - x) * math.log(1 - p) + x * math.log(p) - (n - x) * math.log(1 - x / n) - x * math.log(x / n))
    return lr, 1 - stats.chi2.cdf(lr, 1)

def christoffersen(h):
    h = np.asarray(h, int); a, b = h[:-1], h[1:]
    n00 = int(((a == 0) & (b == 0)).sum()); n01 = int(((a == 0) & (b == 1)).sum())
    n10 = int(((a == 1) & (b == 0)).sum()); n11 = int(((a == 1) & (b == 1)).sum())
    def ll(p, k0, k1): return (k0 * math.log(1 - p) if k0 else 0) + (k1 * math.log(p) if k1 else 0) if 0 < p < 1 else 0.0
    pi01 = n01 / (n00 + n01) if n00 + n01 else 0; pi11 = n11 / (n10 + n11) if n10 + n11 else 0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    lr = -2 * (ll(pi, n00 + n10, n01 + n11) - ll(pi01, n00, n01) - ll(pi11, n10, n11))
    reliable = min(n00, n01, n10, n11) >= BT["christoffersen_min_cell"]
    return lr, 1 - stats.chi2.cdf(lr, 1), (n00, n01, n10, n11), reliable

def light(x):
    g, y = BT["traffic_light"]["green"], BT["traffic_light"]["yellow"]
    return "GREEN" if x <= g[1] else ("YELLOW" if x <= y[1] else "RED")

summ = []
for (per, k), g in bt.groupby(["period", "portfolio"]):
    g = g.sort_values("date")
    for m in ("HS", "EWMA", "FHS"):
        for lev, a in (("99", .99), ("95", .95)):
            hits = (g["loss"] > g[f"{m}_VaR{lev}"]).astype(int).values; n, x = len(hits), int(hits.sum())
            lr, pk = kupiec(x, n, 1 - a); lri, pi_, cells, rel = christoffersen(hits)
            pb = stats.binomtest(x, n, 1 - a).pvalue
            rec = {"period": per, "portfolio": k, "model": m, "level": f"{lev}%", "n": n, "expected": n * (1 - a), "exceptions": x,
                   "exception_dates": ";".join(str(d.date()) for d in g["date"][hits == 1]),
                   "binomial_p": pb}
            if per == "pre_T0":
                rec.update({"kupiec_LR": lr, "kupiec_p": pk, "christoffersen_LR": lri, "christoffersen_p": pi_,
                            "transition_cells": str(cells), "christoffersen_reliable": rel})
                if lev == "99":
                    last = hits[-250:].sum(); rolling = max(hits[i - 250:i].sum() for i in range(250, n + 1))
                    rec.update({"traffic_light_last250": light(last), "exceptions_last250": int(last),
                                "max_rolling250_exceptions": int(rolling), "traffic_light_worst250": light(rolling)})
            summ.append(rec)
        # ES check on 97.5% exceedance days
        e = g["loss"] > g[f"{m}_VaR97.5"]
        summ.append({"period": per, "portfolio": k, "model": m, "level": "ES check (97.5%)", "n": len(g), "expected": len(g) * .025,
                     "exceptions": int(e.sum()), "avg_loss_on_exceedance": float(g.loc[e, "loss"].mean()) if e.any() else np.nan,
                     "avg_ES_forecast_on_exceedance": float(g.loc[e, f"{m}_ES"].mean()) if e.any() else np.nan})
summ = pd.DataFrame(summ); summ.to_csv(f"{OUT}/backtest_summary.csv", index=False)
json.dump({"config_sha256": HASH}, open(f"{OUT}/meta_bt.json", "w"))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 60)
cols = ["period", "portfolio", "model", "level", "n", "expected", "exceptions", "binomial_p", "kupiec_p", "christoffersen_p",
        "christoffersen_reliable", "exceptions_last250", "traffic_light_last250", "max_rolling250_exceptions", "traffic_light_worst250"]
print(summ[summ.level.isin(["99%", "95%"])][cols].round(3).to_string())
print(summ[summ.level.str.startswith("ES")][["period", "portfolio", "model", "exceptions", "avg_loss_on_exceedance", "avg_ES_forecast_on_exceedance"]].round(4).to_string())
print(summ[(summ.level == "99%")][["period", "portfolio", "model", "exception_dates"]].to_string())
