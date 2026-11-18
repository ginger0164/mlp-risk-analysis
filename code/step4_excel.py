"""Step 4 verification workbook: HS VaR/ES and component ES as Excel formulas; other models as Python tables."""
import json
import pandas as pd, numpy as np, yaml, openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as L

S = "results/step4"; OUT = "deliverables/step4_t0_risk_profile.xlsx"
cfg = yaml.safe_load(open("config/model_config_v1.yaml"))
meta = json.load(open(f"{S}/meta.json"))
summ = pd.read_csv(f"{S}/summary.csv", index_col=0)
dec = pd.read_csv(f"{S}/decomposition.csv"); sub = pd.read_csv(f"{S}/subsector_decomposition.csv")
bt = pd.read_csv(f"{S}/bootstrap.csv"); rp = pd.read_csv(f"{S}/random_portfolios.csv")
lim = pd.read_csv(f"{S}/limits.csv"); stz = pd.read_csv(f"{S}/stressed.csv", index_col=[0, 1])
R = pd.read_csv("results/step2/returns_from_2019.csv", index_col=0, parse_dates=True)
MLP = cfg["portfolios"]["PF1"]; PF2 = cfg["portfolios"]["PF2"]
win = R.loc[:cfg["dates"]["T0"], MLP].iloc[-250:]

AR = "Arial"; BLUE, BLACK, GREEN = "FF0000FF", "FF000000", "FF008000"
def hdr(c, v=None):
    if v is not None: c.value = v
    c.font = Font(name=AR, sz=10, b=True, color="FFFFFFFF"); c.fill = PatternFill("solid", fgColor="FF1F4E78")
    c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
def f(c, color=BLACK, fmt=None, b=False):
    c.font = Font(name=AR, sz=10, color=color, b=b)
    if fmt: c.number_format = fmt
def table(ws, df, r0=1, c0=1, fmts=None, color=BLUE):
    for j, col in enumerate(df.columns):
        hdr(ws.cell(r0, c0 + j), str(col))
    for i, row in enumerate(df.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row):
            v = None if (isinstance(v, float) and np.isnan(v)) else v
            c = ws.cell(i, c0 + j, v.item() if hasattr(v, "item") else v)
            f(c, color if isinstance(v, (int, float)) and not isinstance(v, bool) else BLACK, (fmts or {}).get(df.columns[j]))
    return r0 + len(df)
def widths(ws, w):
    for k, v in w.items(): ws.column_dimensions[k].width = v

wb = openpyxl.Workbook(); rd = wb.active; rd.title = "README"
rows = [("Purpose", "Step 4: market-risk profile of PF1 and PF2 at the formation date T0 = 2026-06-12, under the frozen configuration."),
        ("Configuration", f"model_config_v1.yaml v{cfg['version']}, SHA-256 {meta['config_sha256']}"),
        ("Units", "1-day losses as a share of portfolio value, positive = loss. Volatility annualized with SQRT(252)."),
        ("Primary metric", "Historical-simulation (HS) 97.5% ES on the 250 trading days 2025-06-16 to 2026-06-12."),
        ("What is formula-based", "HS_check and Component_ES recompute HS VaR, HS ES, volatility and component ES with Excel formulas from the stored returns; the Check sheet compares them with Python."),
        ("What is Python output", "EWMA, FHS, 500-day HS, stressed VaR, bootstrap and random-portfolio results (blue numbers) are static outputs of step4_risk.py (seed 42)."),
        ("Missing names", "Before MNR (2023-10-25) and TXO (2023-01-27) listed, their PF1 weight is spread equally across the other names; affects only the stressed window."),
        ("Colors", "Blue = hardcoded data or Python output; black = formulas; green = links to another sheet.")]
hdr(rd["A1"], "Item"); hdr(rd["B1"], "Detail")
for i, (a, b) in enumerate(rows, 2):
    rd.cell(i, 1, a); rd.cell(i, 2, b); f(rd.cell(i, 1), b=True); f(rd.cell(i, 2)); rd.cell(i, 2).alignment = Alignment(wrap_text=True)
widths(rd, {"A": 22, "B": 120})

# Summary
sm = wb.create_sheet("Summary")
order = ["HS ES 97.5%", "HS VaR 99%", "HS VaR 95%", "EWMA VaR 99%", "EWMA ES 97.5%", "FHS VaR 99%", "FHS ES 97.5%",
         "HS500 VaR 99%", "HS500 ES 97.5%", "Stressed VaR 99%", "Stressed ES 97.5%", "Ann. volatility (250d)",
         "Ann. volatility (LW)", "EWMA ann. volatility", "Worst day (250d)"]
model = {"HS": "Historical simulation, 250 days", "EWMA": "EWMA normal, lambda 0.94", "FHS": "Filtered HS, lambda 0.94",
         "HS500": "Historical simulation, 500 days", "Stressed": "HS on 2019-06-17 to 2020-06-11 (selected by max PF1 ES)",
         "Ann.": "250-day sample", "EWMA ann.": "EWMA forecast for 2026-06-15", "Worst": "250-day window"}
for j, h in enumerate(["Measure", "PF1", "PF2", "PF2 - PF1", "Model / window"], 1): hdr(sm.cell(1, j), h)
for i, k in enumerate(order, 2):
    sm.cell(i, 1, k); f(sm.cell(i, 1), b=True)
    for j, p in ((2, "PF1"), (3, "PF2")):
        sm.cell(i, j, float(summ.loc[k, p])); f(sm.cell(i, j), BLUE, "0.00%")
    sm.cell(i, 4, f"=C{i}-B{i}"); f(sm.cell(i, 4), BLACK, "+0.00%;-0.00%;0.00%")
    key = "EWMA ann." if k.startswith("EWMA ann") else ("Worst" if k.startswith("Worst") else ("Ann." if k.startswith("Ann") else k.split()[0]))
    sm.cell(i, 5, model[key]); f(sm.cell(i, 5))
sm.cell(len(order) + 3, 1, "ES tail days (PF2)"); sm.cell(len(order) + 3, 2, summ.loc["ES tail days", "PF2"])
sm.cell(len(order) + 4, 1, "ES tail days (PF1)"); sm.cell(len(order) + 4, 2, summ.loc["ES tail days", "PF1"])
for r in (len(order) + 3, len(order) + 4): f(sm.cell(r, 1), b=True); f(sm.cell(r, 2))
widths(sm, {"A": 26, "B": 12, "C": 12, "D": 12, "E": 56})

# HS_check
hs = wb.create_sheet("HS_check")
hdr(hs.cell(1, 1), "Date")
for j, t in enumerate(MLP, 2): hdr(hs.cell(1, j), t)
c1, c2, l1, l2, tw1, tw2 = (L(N) for N in range(25, 31))
for c, h in zip((c1, c2, l1, l2, tw1, tw2), ("PF1 return", "PF2 return", "PF1 loss", "PF2 loss", "PF1 ES tail weight", "PF2 ES tail weight")):
    hdr(hs[f"{c}1"], h)
hs["A2"] = "PF1 weight"; hs["A3"] = "PF2 weight"; f(hs["A2"], b=True); f(hs["A3"], b=True)
for j, t in enumerate(MLP, 2):
    hs.cell(2, j, f"=1/{len(MLP)}"); hs.cell(3, j, f"=1/{len(PF2)}" if t in PF2 else 0)
    f(hs.cell(2, j), BLUE, "0.00%"); f(hs.cell(3, j), BLUE, "0.00%")
D0, D1 = 5, 254; last = L(len(MLP) + 1)
for k, (d, row) in enumerate(win.iterrows()):
    r = D0 + k
    hs.cell(r, 1, d.to_pydatetime()); f(hs.cell(r, 1), BLUE, "yyyy-mm-dd")
    for j, t in enumerate(MLP, 2): hs.cell(r, j, float(row[t])); f(hs.cell(r, j), BLUE, "0.000%")
    hs[f"{c1}{r}"] = f"=SUMPRODUCT($B$2:${last}$2,B{r}:{last}{r})"; hs[f"{c2}{r}"] = f"=SUMPRODUCT($B$3:${last}$3,B{r}:{last}{r})"
    hs[f"{l1}{r}"] = f"=-{c1}{r}"; hs[f"{l2}{r}"] = f"=-{c2}{r}"
    for tw, lc in ((tw1, l1), (tw2, l2)):
        hs[f"{tw}{r}"] = f"=IF(RANK({lc}{r},${lc}${D0}:${lc}${D1},0)<=6,1,IF(RANK({lc}{r},${lc}${D0}:${lc}${D1},0)=7,0.25,0))/6.25"
    for c in (c1, c2, l1, l2): f(hs[f"{c}{r}"], BLACK, "0.000%")
    for c in (tw1, tw2): f(hs[f"{c}{r}"], BLACK, "0.000")
# results block to the right
rc = L(32); vc1, vc2 = L(33), L(34)
hdr(hs[f"{rc}1"], "HS result"); hdr(hs[f"{vc1}1"], "PF1"); hdr(hs[f"{vc2}1"], "PF2")
LR = {"PF1": f"${l1}${D0}:${l1}${D1}", "PF2": f"${l2}${D0}:${l2}${D1}"}
RR = {"PF1": f"${c1}${D0}:${c1}${D1}", "PF2": f"${c2}${D0}:${c2}${D1}"}
res_rows = [("99% VaR = 3rd largest loss", lambda p: f"=LARGE({LR[p]},3)"),
            ("95% VaR = 13th largest loss", lambda p: f"=LARGE({LR[p]},13)"),
            ("97.5% ES = mean of worst 6.25", lambda p: "=(" + "+".join(f"LARGE({LR[p]},{k})" for k in range(1, 7)) + f"+0.25*LARGE({LR[p]},7))/6.25"),
            ("97.5% ES via tail weights", lambda p: f"=SUMPRODUCT({LR[p]},${tw1 if p=='PF1' else tw2}${D0}:${tw1 if p=='PF1' else tw2}${D1})"),
            ("Annualized volatility", lambda p: f"=STDEV({RR[p]})*SQRT(252)"),
            ("Sum of tail weights (should be 1)", lambda p: f"=SUM(${tw1 if p=='PF1' else tw2}${D0}:${tw1 if p=='PF1' else tw2}${D1})")]
for i, (lab, fn) in enumerate(res_rows, 2):
    hs[f"{rc}{i}"] = lab; f(hs[f"{rc}{i}"], b=True)
    for col, p in ((vc1, "PF1"), (vc2, "PF2")):
        hs[f"{col}{i}"] = fn(p); f(hs[f"{col}{i}"], BLACK, "0.000" if "weights" in lab else "0.00%")
hs.column_dimensions["A"].width = 11; hs.column_dimensions[rc].width = 34
for c in (c1, c2, l1, l2, tw1, tw2, vc1, vc2): hs.column_dimensions[c].width = 11
hs.freeze_panes = "B5"

# Component_ES (formulas)
ce = wb.create_sheet("Component_ES")
cols = ["Ticker", "Subsector", "PF1 weight", "PF1 component ES", "PF1 ES share", "PF2 weight", "PF2 component ES", "PF2 ES share",
        "PF1 component vol (Python)", "PF2 component vol (Python)"]
for j, h in enumerate(cols, 1): hdr(ce.cell(1, j), h)
subs = dict(zip(dec.ticker, dec.subsector))
for i, t in enumerate(MLP, 2):
    col = L(MLP.index(t) + 2)
    ce.cell(i, 1, t); ce.cell(i, 2, subs[t]); f(ce.cell(i, 1)); f(ce.cell(i, 2))
    ce.cell(i, 3, f"=HS_check!{col}2"); ce.cell(i, 6, f"=HS_check!{col}3")
    for j in (3, 6): f(ce.cell(i, j), GREEN, "0.00%")
    ce.cell(i, 4, f"=C{i}*SUMPRODUCT(-HS_check!{col}${D0}:{col}${D1},HS_check!${tw1}${D0}:${tw1}${D1})")
    ce.cell(i, 7, f"=F{i}*SUMPRODUCT(-HS_check!{col}${D0}:{col}${D1},HS_check!${tw2}${D0}:${tw2}${D1})")
    ce.cell(i, 5, f"=D{i}/$D${len(MLP)+2}"); ce.cell(i, 8, f"=IF($G${len(MLP)+2}=0,0,G{i}/$G${len(MLP)+2})")
    for j in (4, 7): f(ce.cell(i, j), BLACK, "0.000%")
    for j in (5, 8): f(ce.cell(i, j), BLACK, "0.0%")
    for j, p in ((9, "PF1"), (10, "PF2")):
        v = dec[(dec.portfolio == p) & (dec.ticker == t)]["component_vol_ann"]
        ce.cell(i, j, float(v.iloc[0]) if len(v) else 0.0); f(ce.cell(i, j), BLUE, "0.00%")
tr = len(MLP) + 2
ce.cell(tr, 1, "Total"); f(ce.cell(tr, 1), b=True)
for j, colL in ((3, "C"), (4, "D"), (6, "F"), (7, "G"), (9, "I"), (10, "J")):
    ce.cell(tr, j, f"=SUM({colL}2:{colL}{tr-1})"); f(ce.cell(tr, j), BLACK, "0.000%" if j in (4, 7) else "0.00%", True)
# subsector table (formulas)
s0 = tr + 3
for j, h in enumerate(["Subsector", "PF1 weight", "PF1 ES share", "PF2 weight", "PF2 ES share"], 1): hdr(ce.cell(s0, j), h)
for k, s in enumerate(sorted(set(subs.values())), s0 + 1):
    ce.cell(k, 1, s); f(ce.cell(k, 1))
    for j, (wcol, scol) in ((2, ("C", None)), (3, ("E", None)), (4, ("F", None)), (5, ("H", None))):
        ce.cell(k, j, f"=SUMIF($B$2:$B${tr-1},A{k},{wcol[0]}$2:{wcol[0]}${tr-1})"); f(ce.cell(k, j), BLACK, "0.0%")
widths(ce, {"A": 10, "B": 26, "C": 11, "D": 13, "E": 11, "F": 11, "G": 13, "H": 11, "I": 14, "J": 14})
ce.freeze_panes = "B2"

# Bootstrap
bs = wb.create_sheet("Bootstrap")
btx = bt.copy()
btx.columns = ["Statistic", "PF1", "PF2", "PF2 - PF1", "PF1 CI low", "PF1 CI high", "PF2 CI low", "PF2 CI high",
               "Diff CI low", "Diff CI high", "Share of reps PF2 lower", "Verdict"]
btx["Statistic"] = btx["Statistic"].map({"vol": "Ann. volatility", "VaR99": "HS VaR 99%", "VaR95": "HS VaR 95%", "ES975": "HS ES 97.5% (primary)"})
pct = {c: "0.00%" for c in btx.columns[1:11]}; pct["Share of reps PF2 lower"] = "0.0%"
e = table(bs, btx, fmts=pct)
bs.cell(e + 2, 1, "Method: stationary block bootstrap of the 250 days, dates resampled jointly for all names, mean block 10 days, 5,000 reps, seed 42, 95% percentile intervals.")
bs.cell(e + 3, 1, "Rule: 'significantly lower' only if the whole difference interval is below 0.")
for r in (e + 2, e + 3): f(bs.cell(r, 1))
widths(bs, {"A": 22, **{L(j): 12 for j in range(2, 12)}, "L": 26})

# Random portfolios
rpx = rp.copy()
rpx.columns = ["Set", "Number of portfolios", "Metric", "PF2", "PF1", "5th pct", "Median", "95th pct", "PF2 percentile", "Share of set below PF1"]
rpx["PF2 percentile"] = rpx["PF2 percentile"] / 100
rps = wb.create_sheet("Random_13")
e = table(rps, rpx, fmts={**{c: "0.00%" for c in ["PF2", "PF1", "5th pct", "Median", "95th pct"]}, "PF2 percentile": "0.0%",
                          "Share of set below PF1": "0.0%", "Number of portfolios": "#,##0"})
rps.cell(e + 2, 1, "All equal-weight 13-name subsets of the 23-name universe, same 250-day window. 'PF2 percentile' = share of subsets with a lower value.")
rps.cell(e + 3, 1, "Capped set: subsets where no subsector exceeds 40% (at most 5 midstream names), the same diversification rule PF2 follows.")
for r in (e + 2, e + 3): f(rps.cell(r, 1))
widths(rps, {"A": 30, "B": 14, "C": 16, **{L(j): 11 for j in range(4, 11)}})

# Stressed + limits
sx = wb.create_sheet("Stressed_and_limits")
stx = stz.reset_index(); stx.columns = ["Window rule", "Portfolio", "Window start", "Window end", "HS VaR 99%", "HS ES 97.5%"]
e = table(sx, stx, fmts={"HS VaR 99%": "0.00%", "HS ES 97.5%": "0.00%"})
limx = lim.copy(); limx.columns = ["Portfolio", "Limit", "Value", "Limit value", "Utilization", "Status"]
table(sx, limx, r0=e + 3, fmts={"Value": "0.00%", "Limit value": "0.00%", "Utilization": "0%"})
widths(sx, {"A": 34, "B": 22, "C": 14, "D": 14, "E": 13, "F": 13})

# Check
ck = wb.create_sheet("Check")
for j, h in enumerate(["Item", "Excel formula", "Python", "Abs. difference", "Status"], 1): hdr(ck.cell(1, j), h)
items = []
for i, (lab, py) in enumerate([("99% VaR", "HS VaR 99%"), ("95% VaR", "HS VaR 95%"), ("97.5% ES", "HS ES 97.5%"),
                               ("97.5% ES (tail weights)", "HS ES 97.5%"), ("Annualized volatility", "Ann. volatility (250d)")], 2):
    for col, p in ((vc1, "PF1"), (vc2, "PF2")):
        items.append((f"{p} {lab}", f"=HS_check!{col}{i}", float(summ.loc[py, p])))
items.append(("PF1 component ES sum = ES", f"=Component_ES!D{tr}", float(summ.loc['HS ES 97.5%', 'PF1'])))
items.append(("PF2 component ES sum = ES", f"=Component_ES!G{tr}", float(summ.loc['HS ES 97.5%', 'PF2'])))
for t in PF2:
    i = MLP.index(t) + 2
    v = dec[(dec.portfolio == "PF2") & (dec.ticker == t)]["component_ES"].iloc[0]
    items.append((f"PF2 component ES {t}", f"=Component_ES!G{i}", float(v)))
for r, (a, fm, v) in enumerate(items, 2):
    ck.cell(r, 1, a); ck.cell(r, 2, fm); ck.cell(r, 3, v); ck.cell(r, 4, f"=ABS(B{r}-C{r})"); ck.cell(r, 5, f'=IF(D{r}<0.000000001,"OK","CHECK")')
    f(ck.cell(r, 1)); f(ck.cell(r, 2), GREEN, "0.000000"); f(ck.cell(r, 3), BLUE, "0.000000"); f(ck.cell(r, 4), BLACK, "0.0E+00"); f(ck.cell(r, 5))
n = len(items) + 1
ck.cell(n + 2, 1, "Items checked"); ck.cell(n + 2, 2, f"=COUNTA(A2:A{n})"); ck.cell(n + 3, 1, "Items OK"); ck.cell(n + 3, 2, f'=COUNTIF(E2:E{n},"OK")')
for r in (n + 2, n + 3): f(ck.cell(r, 1), b=True); f(ck.cell(r, 2), BLACK, "0", True)
widths(ck, {"A": 30, "B": 16, "C": 16, "D": 14, "E": 9})
wb.save(OUT); print("saved", OUT, len(items))
