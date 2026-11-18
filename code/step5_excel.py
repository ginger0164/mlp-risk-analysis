"""Step 5 verification workbook."""
import json
import numpy as np, pandas as pd, yaml, openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L

S = "results/step5"; OUT = "deliverables/step5_backtest_stress.xlsx"
cfg = yaml.safe_load(open("config/model_config_v1.yaml"))
H = json.load(open(f"{S}/meta_bt.json"))["config_sha256"]; sm = json.load(open(f"{S}/stress_meta.json"))
daily = pd.read_csv(f"{S}/backtest_daily.csv", parse_dates=["date"]); bsum = pd.read_csv(f"{S}/backtest_summary.csv")
scen = pd.read_csv(f"{S}/stress_scenarios.csv"); rep = pd.read_csv(f"{S}/stress_replays.csv")
rev = pd.read_csv(f"{S}/stress_reverse.csv"); dist = pd.read_csv(f"{S}/stress_distribution.csv")
sb = pd.read_csv(f"{S}/stress_security_betas.csv"); pb = pd.read_csv(f"{S}/stress_portfolio_betas.csv", index_col=0)

AR = "Arial"; BLUE, BLACK, GREEN = "FF0000FF", "FF000000", "FF008000"
def hdr(c, v=None):
    if v is not None: c.value = v
    c.font = Font(name=AR, sz=10, b=True, color="FFFFFFFF"); c.fill = PatternFill("solid", fgColor="FF1F4E78")
    c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
def f(c, color=BLACK, fmt=None, b=False):
    c.font = Font(name=AR, sz=10, color=color, b=b)
    if fmt: c.number_format = fmt
def table(ws, df, r0=1, fmts=None):
    for j, col in enumerate(df.columns, 1): hdr(ws.cell(r0, j), str(col))
    for i, row in enumerate(df.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, float) and np.isnan(v): v = None
            if hasattr(v, "item"): v = v.item()
            if isinstance(v, pd.Timestamp): v = v.to_pydatetime()
            c = ws.cell(i, j, v)
            f(c, BLUE if isinstance(v, (int, float)) and not isinstance(v, bool) else BLACK, (fmts or {}).get(df.columns[j - 1]))
    return r0 + len(df)
def widths(ws, d):
    for k, v in d.items(): ws.column_dimensions[k].width = v

wb = openpyxl.Workbook(); rd = wb.active; rd.title = "README"
info = [("Purpose", "Step 5: VaR backtests and stress tests for PF1 and PF2 under the frozen configuration."),
        ("Configuration", f"model_config_v1.yaml v{cfg['version']}, SHA-256 {H}"),
        ("Backtest periods", "Pre-T0 hypothetical: 2024-06-14 to 2026-06-12 (500 days, constant T0 weights). Out-of-sample: 2026-06-15 to 2026-08-31 (54 days, buy-and-hold from T0)."),
        ("Exception", "Day's loss strictly greater than that day's VaR forecast, made with data through the previous close."),
        ("Stress model", f"Weekly OLS per security on SPY, WTI, change in 10y yield (decimal) and credit (HYG residual on SPY, gamma = {sm['gamma_hyg_on_spy']:.3f}); {sm['n_weeks']} weeks, 2019-03-08 to 2026-06-12. Portfolio betas = T0 weights x security betas."),
        ("Sign convention", "Stress return < 0 is a loss. Rate shock +0.005 = +50bp."),
        ("Formula sheets", "Backtest_daily (exception flags and counts, Kupiec), Scenarios (stress returns from betas x shocks), Distribution_stress. The Check sheet compares them with Python."),
        ("Colors", "Blue = data or Python output; black = formulas; green = links to another sheet.")]
hdr(rd["A1"], "Item"); hdr(rd["B1"], "Detail")
for i, (a, b) in enumerate(info, 2):
    rd.cell(i, 1, a); rd.cell(i, 2, b); f(rd.cell(i, 1), b=True); f(rd.cell(i, 2)); rd.cell(i, 2).alignment = Alignment(wrap_text=True)
widths(rd, {"A": 18, "B": 130})

# ---- Backtest summary
bs = wb.create_sheet("Backtest_summary")
cols = ["period", "portfolio", "model", "level", "n", "expected", "exceptions", "binomial_p", "kupiec_p", "christoffersen_p",
        "christoffersen_reliable", "exceptions_last250", "traffic_light_last250", "max_rolling250_exceptions", "traffic_light_worst250", "exception_dates"]
x = bsum[bsum.level.isin(["99%", "95%"])][cols].copy()
def verdict(r):
    if r.period != "pre_T0" or r.level != "99%": return ""
    if r.kupiec_p >= 0.05 and r.traffic_light_last250 == "GREEN": return "Not rejected"
    if r.kupiec_p < 0.05: return "Rejected (Kupiec p < 0.05)"
    return "Needs review"
x["verdict_rule"] = x.apply(verdict, axis=1)
x = x.sort_values(["period", "level", "model", "portfolio"], ascending=[False, False, True, True])
e = table(bs, x, fmts={"expected": "0.00", "binomial_p": "0.000", "kupiec_p": "0.000", "christoffersen_p": "0.000"})
es = bsum[bsum.level.str.startswith("ES")][["period", "portfolio", "model", "exceptions", "avg_loss_on_exceedance", "avg_ES_forecast_on_exceedance"]].copy()
es.columns = ["period", "portfolio", "model", "97.5% VaR exceedances", "Avg actual loss on those days", "Avg ES forecast on those days"]
table(bs, es, r0=e + 3, fmts={"Avg actual loss on those days": "0.00%", "Avg ES forecast on those days": "0.00%"})
widths(bs, {**{L(j): 12 for j in range(1, 16)}, "P": 90, "Q": 26})

# ---- Backtest daily with formulas
bd = wb.create_sheet("Backtest_daily")
vcols = ["HS_VaR99", "EWMA_VaR99", "FHS_VaR99", "HS_VaR95", "EWMA_VaR95", "FHS_VaR95"]
head = ["period", "portfolio", "date", "loss"] + vcols + [f"hit_{c}" for c in vcols]
for j, h in enumerate(head, 1): hdr(bd.cell(1, j), h)
dd = daily.sort_values(["period", "portfolio", "date"], ascending=[False, True, True]).reset_index(drop=True)
for i, r in dd.iterrows():
    rr = i + 2
    vals = [r.period, r.portfolio, r.date.to_pydatetime(), r.loss] + [r[c] for c in vcols]
    for j, v in enumerate(vals, 1):
        c = bd.cell(rr, j, v); f(c, BLUE if j >= 3 else BLACK, "yyyy-mm-dd" if j == 3 else ("0.000%" if j >= 4 else None))
    for k in range(len(vcols)):
        c = bd.cell(rr, 11 + k, f"=IF($D{rr}>{L(5+k)}{rr},1,0)"); f(c, BLACK, "0")
NR = len(dd) + 1
bd.freeze_panes = "D2"; widths(bd, {"A": 8, "B": 9, "C": 11, **{L(j): 11 for j in range(4, 17)}})
# counts + Kupiec block
cs = wb.create_sheet("Backtest_counts")
hh = ["period", "portfolio", "model", "level", "n", "exceptions (COUNTIFS)", "p = 1 - level", "Kupiec LR", "Kupiec p", "Python exceptions", "Python Kupiec p"]
for j, h in enumerate(hh, 1): hdr(cs.cell(1, j), h)
r = 2
for per in ("pre_T0", "oos"):
    for pf in ("PF1", "PF2"):
        for m in ("HS", "EWMA", "FHS"):
            for lev in ("99", "95"):
                hit = L(11 + vcols.index(f"{m}_VaR{lev}"))
                cs.cell(r, 1, per); cs.cell(r, 2, pf); cs.cell(r, 3, m); cs.cell(r, 4, f"{lev}%")
                cs.cell(r, 5, f'=COUNTIFS(Backtest_daily!$A$2:$A${NR},A{r},Backtest_daily!$B$2:$B${NR},B{r})')
                cs.cell(r, 6, f'=SUMIFS(Backtest_daily!{hit}$2:{hit}${NR},Backtest_daily!$A$2:$A${NR},A{r},Backtest_daily!$B$2:$B${NR},B{r})')
                cs.cell(r, 7, 1 - int(lev) / 100)
                if per == "pre_T0":
                    cs.cell(r, 8, f"=-2*((E{r}-F{r})*LN(1-G{r})+F{r}*LN(G{r})-(E{r}-F{r})*LN(1-F{r}/E{r})-F{r}*LN(F{r}/E{r}))")
                    cs.cell(r, 9, f"=CHIDIST(H{r},1)")
                py = bsum[(bsum.period == per) & (bsum.portfolio == pf) & (bsum.model == m) & (bsum.level == f"{lev}%")].iloc[0]
                cs.cell(r, 10, int(py.exceptions)); cs.cell(r, 11, None if np.isnan(py.kupiec_p) else float(py.kupiec_p))
                for j in range(1, 5): f(cs.cell(r, j))
                f(cs.cell(r, 5), BLACK, "0"); f(cs.cell(r, 6), BLACK, "0"); f(cs.cell(r, 7), BLUE, "0.00")
                f(cs.cell(r, 8), BLACK, "0.000"); f(cs.cell(r, 9), BLACK, "0.000"); f(cs.cell(r, 10), BLUE, "0"); f(cs.cell(r, 11), BLUE, "0.000")
                r += 1
NC = r - 1
widths(cs, {L(j): 13 for j in range(1, 12)})

# ---- Scenarios (formulas)
sc = wb.create_sheet("Scenarios")
sc["A1"] = "Portfolio betas (main calibration)"; f(sc["A1"], b=True)
for j, h in enumerate(["Portfolio", "Market", "Oil", "Rate", "Credit", "Weekly R2"], 1): hdr(sc.cell(2, j), h)
for i, k in enumerate(("PF1", "PF2"), 3):
    sc.cell(i, 1, k); f(sc.cell(i, 1), b=True)
    for j, fn in enumerate(("market", "oil", "rate", "credit"), 2):
        sc.cell(i, j, float(pb.loc[f"agg_{fn}", k])); f(sc.cell(i, j), BLUE, "0.000")
    sc.cell(i, 6, float(pb.loc["reg_R2", k])); f(sc.cell(i, 6), BLUE, "0.000")
sc["A6"] = "gamma (HYG on SPY)"; sc["B6"] = sm["gamma_hyg_on_spy"]; f(sc["A6"], b=True); f(sc["B6"], BLUE, "0.000")
hh = ["Scenario", "Set", "SPY", "WTI", "dDGS10", "HYG", "Credit (orth.)", "PF1 return", "PF2 return", "PF2 - PF1",
      "PF1 CI low", "PF1 CI high", "PF2 CI low", "PF2 CI high", "Shock multiple", "Status", "PF1 return (3y calib.)", "PF2 return (3y calib.)"]
R0 = 8
for j, h in enumerate(hh, 1): hdr(sc.cell(R0, j), h)
main = scen[scen.calibration == "main"]; sens = scen[scen.calibration != "main"]
names = list(dict.fromkeys(main.scenario))
for i, nm in enumerate(names, R0 + 1):
    a = main[(main.scenario == nm) & (main.portfolio == "PF1")].iloc[0]; b = main[(main.scenario == nm) & (main.portfolio == "PF2")].iloc[0]
    sc.cell(i, 1, nm); sc.cell(i, 2, a.set); f(sc.cell(i, 1)); f(sc.cell(i, 2))
    for j, v in zip(range(3, 7), (a.SPY, a.WTI, a.dDGS10, a.HYG)):
        sc.cell(i, j, float(v)); f(sc.cell(i, j), BLUE, "0.0%" if j != 5 else "0.000")
    sc.cell(i, 7, f"=F{i}-$B$6*C{i}"); f(sc.cell(i, 7), BLACK, "0.0%")
    sc.cell(i, 8, f"=SUMPRODUCT($B$3:$E$3,C{i}:E{i}*1,0)" if False else f"=$B$3*C{i}+$C$3*D{i}+$D$3*E{i}+$E$3*G{i}")
    sc.cell(i, 9, f"=$B$4*C{i}+$C$4*D{i}+$D$4*E{i}+$E$4*G{i}")
    sc.cell(i, 10, f"=I{i}-H{i}")
    for j in (8, 9, 10): f(sc.cell(i, j), BLACK, "0.00%")
    for j, v in zip(range(11, 15), (a.return_ci_low, a.return_ci_high, b.return_ci_low, b.return_ci_high)):
        sc.cell(i, j, float(v)); f(sc.cell(i, j), BLUE, "0.00%")
    sc.cell(i, 15, float(a.shock_multiple)); f(sc.cell(i, 15), BLUE, "0.00")
    sc.cell(i, 16, a.status); f(sc.cell(i, 16))
    sa = sens[(sens.scenario == nm) & (sens.portfolio == "PF1")].iloc[0]; sbb = sens[(sens.scenario == nm) & (sens.portfolio == "PF2")].iloc[0]
    sc.cell(i, 17, float(sa.stress_return)); sc.cell(i, 18, float(sbb.stress_return))
    for j in (17, 18): f(sc.cell(i, j), BLUE, "0.00%")
SE = R0 + len(names)
sc.cell(SE + 2, 1, "Multiple = shock / largest weekly move in the calibration sample (oil spike vs 99th percentile). Status is PROVISIONAL when multiple > 1 or R2 < 0.10. CIs: Newey-West (4 lags) on the portfolio-level regression.")
f(sc.cell(SE + 2, 1))
widths(sc, {"A": 26, "B": 15, **{L(j): 10 for j in range(3, 16)}, "P": 13, "Q": 12, "R": 12})

# ---- Replays, reverse, distribution, betas
rp = wb.create_sheet("Historical_replays")
rr = rep[["scenario", "start", "end", "weeks", "portfolio", "SPY_cum", "WTI_cum", "dDGS10_cum", "HYG_cum", "model_loss", "actual_loss", "gap_actual_minus_model"]].copy()
rr.columns = ["Scenario", "Start (close)", "End (close)", "Weeks", "Portfolio", "SPY", "WTI", "10y change", "HYG", "Model loss", "Actual loss", "Actual - model"]
table(rp, rr, fmts={c: "0.0%" for c in ["SPY", "WTI", "HYG", "Model loss", "Actual loss", "Actual - model"]} | {"10y change": "0.000"})
rp.cell(len(rr) + 3, 1, "Negative loss = gain. Model loss = compounded weekly factor predictions with T0 betas; actual loss = T0 weights on actual weekly returns.")
f(rp.cell(len(rr) + 3, 1)); widths(rp, {"A": 20, "B": 12, "C": 12, **{L(j): 11 for j in range(4, 13)}})

rv = wb.create_sheet("Reverse_stress")
rvv = rev[["portfolio", "target_loss", "SPY", "WTI", "dDGS10", "credit_orth", "HYG_implied", "mahalanobis_distance", "SPY_vs_worst_week", "WTI_vs_worst_week"]].copy()
e = table(rv, rvv, fmts={"target_loss": "0%", "SPY": "0.0%", "WTI": "0.0%", "dDGS10": "0.0000", "credit_orth": "0.0%", "HYG_implied": "0.0%",
                         "mahalanobis_distance": "0.00", "SPY_vs_worst_week": "0.00", "WTI_vs_worst_week": "0.00"})
hdr(rv.cell(1, 11), "Loss check (formula)")
for i, k in ((2, "PF1"), (3, "PF2")):
    br = 3 if k == "PF1" else 4
    rv.cell(i, 11, f"=-(Scenarios!$B${br}*C{i}+Scenarios!$C${br}*D{i}+Scenarios!$D${br}*E{i}+Scenarios!$E${br}*F{i})"); f(rv.cell(i, 11), GREEN, "0.00%")
rv.cell(e + 2, 1, "Most likely one-week factor move (minimum Mahalanobis distance under the weekly factor covariance) that produces a 15% loss.")
f(rv.cell(e + 2, 1)); widths(rv, {L(j): 13 for j in range(1, 12)})

ds = wb.create_sheet("Distribution_stress")
for j, h in enumerate(["Ticker", "Distribution type", "Distribution / OCF", "OCF -10%", "OCF -20%", "Breach at -10%", "Breach at -20%", "Breakeven OCF decline"], 1): hdr(ds.cell(1, j), h)
ds["J1"] = "Threshold"; ds["K1"] = 0.8; f(ds["J1"], b=True); f(ds["K1"], BLUE, "0%")
for i, r in enumerate(dist.itertuples(index=False), 2):
    ds.cell(i, 1, r.ticker); ds.cell(i, 2, r.distribution_type); ds.cell(i, 3, float(r.distribution_to_OCF))
    f(ds.cell(i, 1)); f(ds.cell(i, 2)); f(ds.cell(i, 3), BLUE, "0.0%")
    if r.distribution_type == "Fixed":
        ds.cell(i, 4, f"=C{i}/(1-10%)"); ds.cell(i, 5, f"=C{i}/(1-20%)")
        ds.cell(i, 6, f'=IF(D{i}>$K$1,"Yes","No")'); ds.cell(i, 7, f'=IF(E{i}>$K$1,"Yes","No")'); ds.cell(i, 8, f"=1-C{i}/$K$1")
        for j, fm in ((4, "0.0%"), (5, "0.0%"), (6, None), (7, None), (8, "0.0%")): f(ds.cell(i, j), BLACK, fm)
    else:
        ds.cell(i, 4, "n/a: variable payer"); f(ds.cell(i, 4))
n = len(dist) + 1
ds.cell(n + 2, 1, "Breaches at -10%"); ds.cell(n + 2, 3, f'=COUNTIF(F2:F{n},"Yes")'); ds.cell(n + 3, 1, "Breaches at -20%"); ds.cell(n + 3, 3, f'=COUNTIF(G2:G{n},"Yes")')
for rr_ in (n + 2, n + 3): f(ds.cell(rr_, 1), b=True); f(ds.cell(rr_, 3), BLACK, "0", True)
ds.cell(n + 5, 1, "Source: MLP_MODEL_2026_Q2_cleaned_v2.xlsx, PFs column I (distribution / TTM OCF). Variable payers (DMLP, BSM) are exempt by the PF2 rule.")
f(ds.cell(n + 5, 1)); widths(ds, {"A": 10, "B": 16, **{L(j): 14 for j in range(3, 9)}, "J": 11})

sbt = wb.create_sheet("Security_betas")
sbx = sb[["ticker", "n_weeks", "r2", "b_market", "b_oil", "b_rate", "b_credit", "se_market", "se_oil", "se_rate", "se_credit"]]
table(sbt, sbx, fmts={c: "0.000" for c in sbx.columns[2:]})
widths(sbt, {L(j): 11 for j in range(1, 12)})

# ---- Check
ck = wb.create_sheet("Check")
for j, h in enumerate(["Item", "Workbook formula", "Python", "Abs. difference", "Status"], 1): hdr(ck.cell(1, j), h)
items = []
for r in range(2, NC + 1):
    items.append((f"=Backtest_counts!A{r}&\" \"&Backtest_counts!B{r}&\" \"&Backtest_counts!C{r}&\" \"&Backtest_counts!D{r}&\" exceptions\"", f"=Backtest_counts!F{r}", f"=Backtest_counts!J{r}"))
    if r - 2 < 12:  # pre_T0 rows have Kupiec
        items.append((f"=Backtest_counts!B{r}&\" \"&Backtest_counts!C{r}&\" \"&Backtest_counts!D{r}&\" Kupiec p\"", f"=Backtest_counts!I{r}", f"=Backtest_counts!K{r}"))
for i, nm in enumerate(names, R0 + 1):
    for col, k in (("H", "PF1"), ("I", "PF2")):
        v = main[(main.scenario == nm) & (main.portfolio == k)].iloc[0].stress_return
        items.append((f"{k} {nm} return", f"=Scenarios!{col}{i}", float(v)))
for i, k in ((2, "PF1"), (3, "PF2")):
    items.append((f"{k} reverse stress loss", f"=Reverse_stress!K{i}", 0.15))
for r, (a, b, c) in enumerate(items, 2):
    ck.cell(r, 1, a); ck.cell(r, 2, b); ck.cell(r, 3, c); ck.cell(r, 4, f"=ABS(B{r}-C{r})"); ck.cell(r, 5, f'=IF(D{r}<0.000001,"OK","CHECK")')
    f(ck.cell(r, 1)); f(ck.cell(r, 2), GREEN, "0.000000"); f(ck.cell(r, 3), BLUE if not str(c).startswith("=") else GREEN, "0.000000")
    f(ck.cell(r, 4), BLACK, "0.0E+00"); f(ck.cell(r, 5))
m = len(items) + 1
ck.cell(m + 2, 1, "Items checked"); ck.cell(m + 2, 2, f"=COUNTA(E2:E{m})"); ck.cell(m + 3, 1, "Items OK"); ck.cell(m + 3, 2, f'=COUNTIF(E2:E{m},"OK")')
for rr_ in (m + 2, m + 3): f(ck.cell(rr_, 1), b=True); f(ck.cell(rr_, 2), BLACK, "0", True)
widths(ck, {"A": 40, "B": 16, "C": 16, "D": 14, "E": 9})
wb.save(OUT); print("saved", len(items))
