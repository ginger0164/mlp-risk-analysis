"""Step 4: T0 risk profile for PF1/PF2 under the frozen model_config_v1.yaml."""
import hashlib, itertools, json, math, os
import numpy as np, pandas as pd, yaml
from sklearn.covariance import LedoitWolf

CFG_PATH = "config/model_config_v1.yaml"
cfg = yaml.safe_load(open(CFG_PATH))
CFG_HASH = hashlib.sha256(open(CFG_PATH, "rb").read()).hexdigest()
assert cfg["version"] == "1.0"
OUT = "results/step4"; os.makedirs(OUT, exist_ok=True)

R = pd.read_csv("results/step2/returns_from_2019.csv", index_col=0, parse_dates=True)
T0 = pd.Timestamp(cfg["dates"]["T0"])
PF = {k: cfg["portfolios"][k] for k in ("PF1", "PF2")}
MLP = PF["PF1"]
SUB = {"DMLP": "Oil and gas royalties", "BSM": "Oil and gas royalties", "ARLP": "Coal and mineral resources",
       "NRP": "Coal and mineral resources", "UAN": "Nitrogen fertilizers", "WLKP": "Petrochemicals",
       "SPH": "Fuel distribution", "GLP": "Fuel distribution", "CAPL": "Fuel distribution",
       "SUN": "Fuel distribution", "MNR": "Oil and gas production", "TXO": "Oil and gas production"}
SUB.update({t: "Midstream" for t in "WES ET HESM MPLX EPD CQP DKL GEL MMLP PAA USAC".split()})
VE = cfg["var_es"]; A99, A95 = VE["var_confidence"]; AES = VE["es_confidence"]

hist = R.loc[cfg["data"]["history_start"]:T0, MLP]
W = {k: pd.Series(1 / len(v), index=v) for k, v in PF.items()}


def port_returns(ret, w):
    """Constant weights; a missing name's weight is spread equally over names with data that day."""
    x = ret[w.index]
    mask = x.notna()
    miss = (w * ~mask).sum(axis=1)
    navail = mask.sum(axis=1)
    wadj = mask.mul(w, axis=1).add(mask.mul(miss / navail, axis=0))
    return (x.fillna(0) * wadj).sum(axis=1)


def hs_var(L, a):
    return float(np.sort(L)[math.ceil(a * len(L)) - 1])


def hs_es(L, a):
    s = np.sort(L)[::-1]; q = len(L) * (1 - a); j = int(math.floor(q + 1e-12)); fr = q - j
    return float((s[:j].sum() + (fr * s[j] if fr > 1e-12 else 0)) / q)


def tail_weights(L, a):
    """Weights per observation in the ES tail (sum = 1)."""
    n = len(L); q = n * (1 - a); order = np.argsort(-L); w = np.zeros(n)
    j = int(math.floor(q + 1e-12)); w[order[:j]] = 1
    if q - j > 1e-12: w[order[j]] = q - j
    return w / q


def ewma_sigma(r, lam, seed):
    """sigma[t] = forecast for day t using data through t-1; returns series and next-day forecast."""
    r = np.asarray(r); var = np.var(r[:seed], ddof=1); sig = np.full(len(r), np.nan)
    for t in range(seed, len(r)):
        sig[t] = math.sqrt(var); var = lam * var + (1 - lam) * r[t] ** 2
    return sig, math.sqrt(var)


from statistics import NormalDist
N01 = NormalDist()
res, pr_hist = {}, {}
for k, w in W.items():
    p = port_returns(hist, w); pr_hist[k] = p
    win = p.iloc[-VE["hs"]["window"]:]; L = -win.values
    win500 = p.iloc[-VE["hs_robustness_window"]:]; L5 = -win500.values
    sig, sig_next = ewma_sigma(p.values, VE["ewma"]["lambda"], VE["ewma"]["seed_days"])
    z = (p.values / sig)[-VE["fhs"]["window"]:]; Lf = -z * sig_next
    zq = N01.inv_cdf(A99); zes = N01.inv_cdf(AES)
    res[k] = {
        "HS VaR 99%": hs_var(L, A99), "HS VaR 95%": hs_var(L, A95), "HS ES 97.5%": hs_es(L, AES),
        "EWMA VaR 99%": zq * sig_next, "EWMA VaR 95%": N01.inv_cdf(A95) * sig_next,
        "EWMA ES 97.5%": sig_next * N01.pdf(zes) / (1 - AES),
        "FHS VaR 99%": hs_var(Lf, A99), "FHS VaR 95%": hs_var(Lf, A95), "FHS ES 97.5%": hs_es(Lf, AES),
        "HS500 VaR 99%": hs_var(L5, A99), "HS500 ES 97.5%": hs_es(L5, AES),
        "Ann. volatility (250d)": win.std(ddof=1) * np.sqrt(252), "EWMA ann. volatility": sig_next * np.sqrt(252),
        "Worst day (250d)": -L.max(),
    }
    assert win.index[-1] == T0 and win.index[0] == pd.Timestamp("2025-06-16")

# stressed window: rolling 250-day windows, select max PF1 HS ES
roll = {}
for k in W:
    p = pr_hist[k]
    roll[k] = pd.Series([hs_es(-p.values[i - 250:i], AES) for i in range(250, len(p) + 1)], index=p.index[249:])
end1 = roll["PF1"].idxmax(); end2 = roll["PF2"].idxmax()
def window_ending(p, end): i = p.index.get_loc(end); return p.iloc[i - 249:i + 1]
stress = {}
for label, end in (("Selected by PF1 (applied to both)", end1), ("PF2 own worst window", end2)):
    for k in W:
        wv = window_ending(pr_hist[k], end); Ls = -wv.values
        stress[(label, k)] = {"window_start": str(wv.index[0].date()), "window_end": str(wv.index[-1].date()),
                              "HS VaR 99%": hs_var(Ls, A99), "HS ES 97.5%": hs_es(Ls, AES)}
for k in W:
    res[k]["Stressed VaR 99%"] = stress[("Selected by PF1 (applied to both)", k)]["HS VaR 99%"]
    res[k]["Stressed ES 97.5%"] = stress[("Selected by PF1 (applied to both)", k)]["HS ES 97.5%"]

# decomposition
X250 = hist.iloc[-250:]
assert X250.notna().all().all()
dec = []
for k, w in W.items():
    x = X250[w.index]; S = x.cov().values; LWc = LedoitWolf().fit(x.values).covariance_
    wv = w.values; sp = math.sqrt(wv @ S @ wv); sl = math.sqrt(wv @ LWc @ wv)
    cvol = wv * (S @ wv) / sp; cvol_lw = wv * (LWc @ wv) / sl
    pr = x.values @ wv; tw = tail_weights(-pr, AES)
    ces = wv * (-(x.values * tw[:, None]).sum(axis=0))
    assert abs(ces.sum() - res[k]["HS ES 97.5%"]) < 1e-12 and abs(cvol.sum() - sp) < 1e-12
    for i, t in enumerate(w.index):
        dec.append({"portfolio": k, "ticker": t, "subsector": SUB[t], "weight": wv[i],
                    "component_vol_ann": cvol[i] * np.sqrt(252), "vol_share": cvol[i] / sp,
                    "component_vol_LW_ann": cvol_lw[i] * np.sqrt(252),
                    "component_ES": ces[i], "ES_share": ces[i] / ces.sum()})
    res[k]["Ann. volatility (LW)"] = sl * np.sqrt(252)
    res[k]["ES tail days"] = ", ".join(str(d.date()) for d in x.index[np.argsort(-tw)[:7]])
dec = pd.DataFrame(dec)
subdec = dec.groupby(["portfolio", "subsector"])[["weight", "component_vol_ann", "vol_share", "component_ES", "ES_share"]].sum().reset_index()

# stationary block bootstrap of the 250-day window, dates resampled jointly
B = cfg["comparison"]["bootstrap"]; rng = np.random.default_rng(B["seed"])
n = 250; pnew = 1 / B["mean_block_days"]
P = np.column_stack([X250[W[k].index].values @ W[k].values for k in ("PF1", "PF2")])
stats_names = ["vol", "VaR99", "VaR95", "ES975"]
def st(v):
    L = -v
    return [v.std(ddof=1) * np.sqrt(252), hs_var(L, A99), hs_var(L, A95), hs_es(L, AES)]
boot = np.empty((B["reps"], 2, 4))
for b in range(B["reps"]):
    idx = np.empty(n, dtype=int); idx[0] = rng.integers(n)
    newblk = rng.random(n) < pnew; starts = rng.integers(n, size=n)
    for t in range(1, n):
        idx[t] = starts[t] if newblk[t] else (idx[t - 1] + 1) % n
    boot[b, 0] = st(P[idx, 0]); boot[b, 1] = st(P[idx, 1])
point = np.array([st(P[:, 0]), st(P[:, 1])])
lo, hi = (1 - B["ci"]) / 2, 1 - (1 - B["ci"]) / 2
bt = []
for j, s in enumerate(stats_names):
    d = boot[:, 1, j] - boot[:, 0, j]
    bt.append({"statistic": s, "PF1": point[0, j], "PF2": point[1, j], "PF2_minus_PF1": point[1, j] - point[0, j],
               "PF1_ci_low": np.quantile(boot[:, 0, j], lo), "PF1_ci_high": np.quantile(boot[:, 0, j], hi),
               "PF2_ci_low": np.quantile(boot[:, 1, j], lo), "PF2_ci_high": np.quantile(boot[:, 1, j], hi),
               "diff_ci_low": np.quantile(d, lo), "diff_ci_high": np.quantile(d, hi),
               "share_reps_PF2_lower": float((d < 0).mean())})
bt = pd.DataFrame(bt)
bt["verdict"] = np.where(bt.diff_ci_high < 0, "PF2 significantly lower",
                np.where(bt.diff_ci_low > 0, "PF2 significantly higher", "No significant difference"))

# random 13-name equal-weight portfolios
Xw = X250[MLP].values.astype(np.float64)
mid = np.array([SUB[t] == "Midstream" for t in MLP])
combos = np.array(list(itertools.combinations(range(23), 13)), dtype=np.int8)
vols, v99s, ess, cap = [], [], [], []
for chunk in np.array_split(combos, 40):
    A = np.zeros((len(chunk), 23)); np.put_along_axis(A, chunk.astype(np.int64), 1.0, axis=1); A /= 13
    Pm = A @ Xw.T; Lm = -Pm
    top = -np.sort(-np.partition(Lm, -13, axis=1)[:, -13:], axis=1)  # 13 largest losses, descending
    vols.append(Pm.std(axis=1, ddof=1) * np.sqrt(252)); v99s.append(top[:, 2])
    ess.append((top[:, :6].sum(axis=1) + 0.25 * top[:, 6]) / 6.25); cap.append(mid[chunk].sum(axis=1) <= 5)
vols, v99s, ess, cap = map(np.concatenate, (vols, v99s, ess, cap))
pf2_idx = tuple(sorted(MLP.index(t) for t in PF["PF2"]))
pos = np.where((combos == np.array(pf2_idx, dtype=np.int8)).all(axis=1))[0][0]
assert abs(ess[pos] - res["PF2"]["HS ES 97.5%"]) < 1e-12
rp = []
for label, m in (("All 13-name subsets", np.ones(len(combos), bool)), ("Subsets with subsector cap 40%", cap)):
    for s, arr, val in (("Ann. volatility", vols, res["PF2"]["Ann. volatility (250d)"]), ("HS VaR 99%", v99s, res["PF2"]["HS VaR 99%"]),
                        ("HS ES 97.5%", ess, res["PF2"]["HS ES 97.5%"])):
        a = arr[m]
        rp.append({"set": label, "n_portfolios": int(m.sum()), "metric": s, "PF2": val,
                   "PF1": res["PF1"]["Ann. volatility (250d)" if s == "Ann. volatility" else s],
                   "p5": np.quantile(a, .05), "median": np.median(a), "p95": np.quantile(a, .95),
                   "PF2_percentile": float((a < val).mean() * 100), "share_lower_than_PF1": float((a < (res['PF1']['Ann. volatility (250d)'] if s == 'Ann. volatility' else res['PF1'][s])).mean())})
rp = pd.DataFrame(rp)
hist_rp = {"vol": vols.tolist()[:0]}  # placeholder, distributions saved below
np.savez_compressed(f"{OUT}/random13.npz", vol=vols, var99=v99s, es=ess, cap=cap)

# limits
L = cfg["limits"]; lim = []
for k in W:
    subw = pd.Series(W[k].values, index=W[k].index).groupby(SUB).sum().max()
    for name, val, limv in (("HS VaR 99%", res[k]["HS VaR 99%"], L["hs_var_99"]), ("HS ES 97.5%", res[k]["HS ES 97.5%"], L["hs_es_975"]),
                            ("Single-name weight", W[k].max(), L["single_name_weight"]), ("Subsector weight", subw, L["subsector_weight"])):
        u = val / limv
        lim.append({"portfolio": k, "limit": name, "value": val, "limit_value": limv, "utilization": u,
                    "status": "GREEN" if u < L["amber_from_utilization"] else ("AMBER" if u <= 1 else "RED")})
lim = pd.DataFrame(lim)

summary = pd.DataFrame(res).T if False else pd.DataFrame(res)
summary.to_csv(f"{OUT}/summary.csv"); dec.to_csv(f"{OUT}/decomposition.csv", index=False)
subdec.to_csv(f"{OUT}/subsector_decomposition.csv", index=False); bt.to_csv(f"{OUT}/bootstrap.csv", index=False)
rp.to_csv(f"{OUT}/random_portfolios.csv", index=False); lim.to_csv(f"{OUT}/limits.csv", index=False)
pd.DataFrame(stress).T.to_csv(f"{OUT}/stressed.csv")
pd.DataFrame({"PF1": pr_hist["PF1"], "PF2": pr_hist["PF2"]}).to_csv(f"{OUT}/portfolio_returns_hist.csv")
json.dump({"config_sha256": CFG_HASH, "n_combos": int(len(combos)), "n_capped": int(cap.sum()),
           "stress_end_PF1": str(end1.date()), "stress_end_PF2": str(end2.date())}, open(f"{OUT}/meta.json", "w"), indent=2)

pd.set_option("display.width", 230); pd.set_option("display.max_columns", 20)
print("config", CFG_HASH[:12]); print(summary.to_string())
print(pd.DataFrame(stress).T.to_string())
print(bt.round(5).to_string())
print(rp.round(4).to_string())
print(subdec.round(4).to_string())
print(lim.round(3).to_string())
