"""Step 5b: weekly four-factor stress testing under model_config_v1.yaml."""
import json, math, os
import numpy as np, pandas as pd, yaml
import statsmodels.api as sm

cfg = yaml.safe_load(open("config/model_config_v1.yaml"))
ST = cfg["stress"]; OUT = "results/step5"; os.makedirs(OUT, exist_ok=True)
adj = pd.read_csv("data/qc/adjclose.csv", index_col=0, parse_dates=True)
fac = pd.read_csv("data/qc/factors_raw.csv", index_col=0, parse_dates=True)
MLP = cfg["portfolios"]["PF1"]; PF = {k: cfg["portfolios"][k] for k in ("PF1", "PF2")}
T0 = pd.Timestamp(cfg["dates"]["T0"]); H0 = pd.Timestamp(cfg["data"]["history_start"])

# --- weekly endpoints (Fridays), last valid observation within 3 calendar days, no forward filling beyond that
ends = pd.date_range(H0 - pd.Timedelta(days=7), T0, freq="W-FRI")
def endpoint(s):
    s = s.dropna(); out = []
    for e in ends:
        prior = s.loc[:e]
        out.append(prior.iloc[-1] if len(prior) and (e - prior.index[-1]).days <= ST["max_endpoint_staleness_days"] else np.nan)
    return pd.Series(out, index=ends)
lv = {t: endpoint(adj[t]) for t in MLP + ["SPY", "HYG"]}
lv["OIL"] = endpoint(fac["DCOILWTICO"].where(fac["DCOILWTICO"] > 0)); lv["Y"] = endpoint(fac["DGS10"] / 100)
LV = pd.DataFrame(lv)
WR = LV[MLP].pct_change(fill_method=None)
F = pd.DataFrame({"market": LV["SPY"].pct_change(fill_method=None), "oil": LV["OIL"].pct_change(fill_method=None),
                  "rate": LV["Y"].diff(), "hyg": LV["HYG"].pct_change(fill_method=None)})
WR, F = WR.loc[H0:], F.loc[H0:]
assert F.index[-1] == T0


def calibrate(start, end):
    f = F.loc[start:end].dropna()
    g = sm.OLS(f["hyg"], sm.add_constant(f["market"])).fit(); gamma = g.params["market"]
    f = f.assign(credit=f["hyg"] - g.params["const"] - gamma * f["market"])
    X = sm.add_constant(f[["market", "oil", "rate", "credit"]])
    betas, diag = {}, []
    for t in MLP:
        d = pd.concat([WR[t], X], axis=1, join="inner").dropna()
        m = sm.OLS(d[t], d[X.columns]).fit()
        betas[t] = m.params[["market", "oil", "rate", "credit"]]
        diag.append({"ticker": t, "n_weeks": int(m.nobs), "r2": m.rsquared, **{f"b_{k}": v for k, v in m.params.items()},
                     **{f"se_{k}": v for k, v in m.bse.items()}})
    B = pd.DataFrame(betas).T
    port = {}
    for k, names in PF.items():
        w = pd.Series(1 / len(names), index=names)
        x = WR.loc[f.index, names]; mask = x.notna(); miss = (w * ~mask).sum(axis=1)
        wadj = mask.mul(w, axis=1).add(mask.mul(miss / mask.sum(axis=1), axis=0))
        pr = (x.fillna(0) * wadj).sum(axis=1)
        m = sm.OLS(pr, X).fit(cov_type="HAC", cov_kwds={"maxlags": ST["uncertainty"]["lags"]})
        port[k] = {"agg_beta": (B.loc[names].mul(w, axis=0)).sum(), "reg": m, "w": w, "weekly": pr}
    fc = f[["market", "oil", "rate", "credit"]].cov()
    return {"gamma": gamma, "alpha_hyg": g.params["const"], "B": B, "diag": pd.DataFrame(diag), "port": port,
            "fcov": fc, "f": f, "n_weeks": len(f)}

main = calibrate(ST["calibration"]["start"], ST["calibration"]["end"])
sens = calibrate(ST["calibration_sensitivity"]["start"], ST["calibration_sensitivity"]["end"])

f = main["f"]
worst = {"market": f["market"].min(), "oil_down": f["oil"].min(), "oil_up_p99": f["oil"].quantile(.99),
         "rate_up": f["rate"].max(), "rate_down": f["rate"].min(), "hyg": f["hyg"].min()}

def shock_vec(s, cal):
    spy, oil, dy, hyg = s
    return np.array([spy, oil, dy, hyg - cal["gamma"] * spy])

def multiple(s):
    spy, oil, dy, hyg = s; m = []
    if spy < 0: m.append(spy / worst["market"])
    if oil < 0: m.append(oil / worst["oil_down"])
    if oil > 0: m.append(oil / worst["oil_up_p99"])
    if dy > 0: m.append(dy / worst["rate_up"])
    if dy < 0: m.append(dy / worst["rate_down"])
    if hyg < 0: m.append(hyg / worst["hyg"])
    return max(m) if m else 0.0

scen = {**ST["scenarios_calibrated"], **ST["scenarios_severe_legacy"]}
rows = []
for name, s in scen.items():
    for k in PF:
        for label, cal in (("main", main), ("sensitivity_3y", sens)):
            x = shock_vec(s, cal); b = cal["port"][k]["agg_beta"].values
            ret = float(b @ x); reg = cal["port"][k]["reg"]
            V = reg.cov_params().loc[["market", "oil", "rate", "credit"], ["market", "oil", "rate", "credit"]].values
            se = math.sqrt(x @ V @ x)
            mult = multiple(s); r2 = reg.rsquared
            rows.append({"scenario": name, "set": "B (sensitivity)" if name.startswith("B") else "A/C (primary)",
                         "portfolio": k, "calibration": label, "SPY": s[0], "WTI": s[1], "dDGS10": s[2], "HYG": s[3],
                         "credit_orth_shock": x[3], "stress_return": ret, "loss": max(0.0, -ret),
                         "return_ci_low": ret - 1.96 * se, "return_ci_high": ret + 1.96 * se,
                         "shock_multiple": mult, "portfolio_R2": r2,
                         "status": "PROVISIONAL" if (mult > 1 + 1e-9 or r2 < 0.10) else "VALID"})
scen_df = pd.DataFrame(rows)

# factor contributions for the main calibration
contrib = []
for name, s in scen.items():
    for k in PF:
        x = shock_vec(s, main); b = main["port"][k]["agg_beta"]
        for i, fn in enumerate(["market", "oil", "rate", "credit"]):
            contrib.append({"scenario": name, "portfolio": k, "factor": fn, "beta": b[fn], "shock": x[i], "contribution": b[fn] * x[i]})
contrib = pd.DataFrame(contrib)

# historical replays: model vs actual, weekly compounding over the window (returns of weeks ending after start through end)
rep = []
for name, (a, b_) in ST["historical_replays"].items():
    wk = F.loc[pd.Timestamp(a) + pd.Timedelta(days=1):b_]
    for k in PF:
        cal = main; bb = cal["port"][k]["agg_beta"].values
        fx = np.column_stack([wk["market"], wk["oil"], wk["rate"], wk["hyg"] - cal["gamma"] * wk["market"]])
        ok = ~np.isnan(fx).any(axis=1)
        model = float(np.prod(1 + fx[ok] @ bb) - 1)
        actual = float(np.prod(1 + cal["port"][k]["weekly"].reindex(wk.index).fillna(0)) - 1)
        rep.append({"scenario": name, "start": a, "end": b_, "weeks": len(wk), "weeks_with_factors": int(ok.sum()),
                    "portfolio": k, "SPY_cum": float(np.prod(1 + wk["market"]) - 1), "WTI_cum": float(np.prod(1 + wk["oil"].fillna(0)) - 1),
                    "dDGS10_cum": float(wk["rate"].sum()), "HYG_cum": float(np.prod(1 + wk["hyg"]) - 1),
                    "model_loss": -model, "actual_loss": -actual, "gap_actual_minus_model": -actual + model})
rep = pd.DataFrame(rep)

# reverse stress
rev = []
for k in PF:
    b = main["port"][k]["agg_beta"].values; S = main["fcov"].values; L = cfg["stress"]["reverse_stress"]["loss"]
    x = -L * S @ b / (b @ S @ b); d = L / math.sqrt(b @ S @ b)
    hyg = x[3] + main["gamma"] * x[0]
    rev.append({"portfolio": k, "target_loss": L, "SPY": x[0], "WTI": x[1], "dDGS10": x[2], "credit_orth": x[3], "HYG_implied": hyg,
                "mahalanobis_distance": d, "SPY_vs_worst_week": x[0] / worst["market"], "WTI_vs_worst_week": x[1] / worst["oil_down"],
                "check_loss": -float(b @ x)})
rev = pd.DataFrame(rev)

# distribution stress (PF2 fixed payers); inputs are the PF2 names' distribution / TTM operating cash flow
src = pd.read_csv("data/qc/pf2_distribution_inputs.csv"); drow = []
thr = cfg["stress"]["distribution_stress"]["threshold"]
for t, dtype, pay in src.itertuples(index=False):
    rec = {"ticker": t, "distribution_type": dtype, "distribution_to_OCF": pay}
    if dtype == "Fixed":
        for s in cfg["stress"]["distribution_stress"]["ocf_shocks"]:
            rec[f"payout_OCF_{int(s*100)}pct"] = pay / (1 + s)
        rec["breakeven_OCF_decline"] = 1 - pay / thr
    drow.append(rec)
dist = pd.DataFrame(drow)

betas_tbl = main["B"].copy(); betas_tbl["subsector_in_PF2"] = [t in PF["PF2"] for t in betas_tbl.index]
diag = main["diag"]
port_b = pd.DataFrame({k: {**{f"agg_{f}": v for f, v in main["port"][k]["agg_beta"].items()},
                           **{f"reg_{f}": v for f, v in main["port"][k]["reg"].params.items()},
                           "reg_R2": main["port"][k]["reg"].rsquared, "n_weeks": int(main["port"][k]["reg"].nobs),
                           **{f"sens3y_agg_{f}": v for f, v in sens["port"][k]["agg_beta"].items()}} for k in PF})
for nm, df in (("scenarios", scen_df), ("contributions", contrib), ("replays", rep), ("reverse", rev), ("distribution", dist),
               ("security_betas", diag), ("portfolio_betas", port_b)):
    df.to_csv(f"{OUT}/stress_{nm}.csv", index=nm in ("portfolio_betas",))
json.dump({"gamma_hyg_on_spy": main["gamma"], "n_weeks": main["n_weeks"], "n_weeks_sens": sens["n_weeks"],
           "worst": worst, "factor_cov": main["fcov"].to_dict()}, open(f"{OUT}/stress_meta.json", "w"), indent=2, default=float)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print("weeks", main["n_weeks"], sens["n_weeks"], "gamma", round(main["gamma"], 3), {k: round(v, 4) for k, v in worst.items()})
print(port_b.round(3).to_string())
print(scen_df[scen_df.calibration == "main"][["scenario", "portfolio", "stress_return", "return_ci_low", "return_ci_high", "loss", "shock_multiple", "portfolio_R2", "status"]].round(4).to_string())
print(scen_df[scen_df.calibration != "main"][["scenario", "portfolio", "loss"]].round(4).to_string())
print(rep.round(4).to_string()); print(rev.round(4).to_string()); print(dist.round(3).to_string())
