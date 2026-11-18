"""Build the Step 2 workbook: every statistic is an Excel formula over the stored return window."""
import json
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L

S = "results/step2"
OUT = "deliverables/step2_baseline_stats.xlsx"
win = pd.read_csv(f"{S}/window_returns.csv", index_col=0, parse_dates=True)
sec = pd.read_csv(f"{S}/security_stats.csv", index_col=0)
port = pd.read_csv(f"{S}/portfolio_stats.csv", index_col=0)
meta = json.load(open(f"{S}/meta.json"))
MLP = list(sec.index)
PF2 = [t for t in MLP if sec.loc[t, "in_PF2"]]
N, NR = len(MLP), len(win)

AR = "Arial"
HDR_FILL = PatternFill("solid", fgColor="FF1F4E78")
def hdr(c):
    c.font = Font(name=AR, sz=10, b=True, color="FFFFFFFF"); c.fill = HDR_FILL
    c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
def f(c, color="FF000000", fmt=None, b=False):
    c.font = Font(name=AR, sz=10, color=color, b=b)
    if fmt: c.number_format = fmt
BLUE, BLACK, GREEN = "FF0000FF", "FF000000", "FF008000"

wb = openpyxl.Workbook()
rd = wb.active; rd.title = "README"
readme = [
    ("Purpose", "Step 2 baseline statistics for PF1 (23 names) and PF2 (13 names). All statistics are Excel formulas over the stored daily returns, so they can be audited cell by cell."),
    ("Formation date (T0)", f"{meta['T0']} close. Only returns up to and including T0 are used."),
    ("Estimation window", f"{meta['window_start']} to {meta['window_end']}, {meta['n']} trading days."),
    ("Returns", "Daily simple total returns from Yahoo Finance adjusted close (dividends reinvested). Source: pf2_raw_data.zip, downloaded 2026-11-04."),
    ("Weights", "Equal weight within each portfolio at T0: PF1 1/23 per name, PF2 1/13 per name. Membership flags on the Weights sheet are inputs."),
    ("Portfolio returns", "Fixed T0 weights applied to each historical day (current book revalued over the window), the standard basis for ex-ante risk."),
    ("Annualization", "Daily standard deviation x SQRT(252). Beta is OLS slope on SPY daily total return with intercept; 95% CI uses the t distribution."),
    ("Colors", "Blue = hardcoded input data; black = formulas; green = links to another sheet."),
    ("Check sheet", "Compares every formula result with an independent Python calculation. 'OK' means the absolute difference is below 1e-9."),
]
hdr(rd["A1"]); hdr(rd["B1"]); rd["A1"] = "Item"; rd["B1"] = "Detail"
for i, (a, b) in enumerate(readme, 2):
    rd.cell(i, 1, a); rd.cell(i, 2, b); f(rd.cell(i, 1), b=True); f(rd.cell(i, 2))
    rd.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="top")
rd.column_dimensions["A"].width = 22; rd.column_dimensions["B"].width = 110

# ---------------------------------------------------------------- Weights
ws = wb.create_sheet("Weights")
cols = ["Ticker", "Subsector", "PF1 member", "PF2 member", "PF1 weight", "PF2 weight"]
for j, h in enumerate(cols, 1): hdr(ws.cell(1, j, h))
for i, t in enumerate(MLP, 2):
    ws.cell(i, 1, t); ws.cell(i, 2, sec.loc[t, "subsector"]); ws.cell(i, 3, 1); ws.cell(i, 4, int(t in PF2))
    for j in (1, 2): f(ws.cell(i, j))
    for j in (3, 4): f(ws.cell(i, j), BLUE, "0")
    ws.cell(i, 5, f"=IF(C{i}=1,1/SUM($C$2:$C${N+1}),0)"); ws.cell(i, 6, f"=IF(D{i}=1,1/SUM($D$2:$D${N+1}),0)")
    for j in (5, 6): f(ws.cell(i, j), BLACK, "0.00%")
tr = N + 2
ws.cell(tr, 1, "Total"); f(ws.cell(tr, 1), b=True)
for j, col in ((3, "C"), (4, "D"), (5, "E"), (6, "F")):
    ws.cell(tr, j, f"=SUM({col}2:{col}{N+1})"); f(ws.cell(tr, j), BLACK, "0" if j < 5 else "0.00%", True)
# subsector table
subs = sorted(sec["subsector"].unique())
r0 = tr + 3
for j, h in enumerate(["Subsector", "PF1 weight", "PF2 weight", "PF1 names", "PF2 names"], 1): hdr(ws.cell(r0, j, h))
for k, s in enumerate(subs, r0 + 1):
    ws.cell(k, 1, s); f(ws.cell(k, 1))
    ws.cell(k, 2, f"=SUMIF($B$2:$B${N+1},A{k},$E$2:$E${N+1})")
    ws.cell(k, 3, f"=SUMIF($B$2:$B${N+1},A{k},$F$2:$F${N+1})")
    ws.cell(k, 4, f"=SUMIF($B$2:$B${N+1},A{k},$C$2:$C${N+1})")
    ws.cell(k, 5, f"=SUMIF($B$2:$B${N+1},A{k},$D$2:$D${N+1})")
    for j in (2, 3): f(ws.cell(k, j), BLACK, "0.0%")
    for j in (4, 5): f(ws.cell(k, j), BLACK, "0")
SUB_LAST = r0 + len(subs)
for c, wdt in zip("ABCDEF", (28, 28, 12, 12, 12, 12)): ws.column_dimensions[c].width = wdt
ws.freeze_panes = "B2"

# ---------------------------------------------------------------- Returns
rs = wb.create_sheet("Returns_250d")
names = MLP + ["SPY"]
hdr(rs.cell(1, 1, "Date"))
for j, t in enumerate(names, 2): hdr(rs.cell(1, j, t))
pf1c, pf2c = L(len(names) + 2), L(len(names) + 3)
hdr(rs.cell(1, len(names) + 2, "PF1")); hdr(rs.cell(1, len(names) + 3, "PF2"))
rs.cell(2, 1, "PF1 weight"); rs.cell(3, 1, "PF2 weight")
for j, t in enumerate(MLP, 2):
    i = MLP.index(t) + 2
    rs.cell(2, j, f"=Weights!E{i}"); rs.cell(3, j, f"=Weights!F{i}")
    f(rs.cell(2, j), GREEN, "0.00%"); f(rs.cell(3, j), GREEN, "0.00%")
f(rs.cell(2, 1), b=True); f(rs.cell(3, 1), b=True)
D0 = 5; D1 = D0 + NR - 1
lastmlp = L(N + 1)
for k, (d, row) in enumerate(win.iterrows()):
    r = D0 + k
    c = rs.cell(r, 1, d.to_pydatetime()); f(c, BLUE, "yyyy-mm-dd")
    for j, t in enumerate(names, 2):
        c = rs.cell(r, j, float(row[t])); f(c, BLUE, "0.000%")
    rs.cell(r, N + 3, f"=SUMPRODUCT($B$2:${lastmlp}$2,B{r}:{lastmlp}{r})")
    rs.cell(r, N + 4, f"=SUMPRODUCT($B$3:${lastmlp}$3,B{r}:{lastmlp}{r})")
    f(rs.cell(r, N + 3), BLACK, "0.000%"); f(rs.cell(r, N + 4), BLACK, "0.000%")
rs.column_dimensions["A"].width = 12
rs.freeze_panes = "B5"
SPYc = L(N + 2)
def rng(col): return f"Returns_250d!${col}${D0}:${col}${D1}"
X = rng(SPYc)

# ---------------------------------------------------------------- Security stats
st = wb.create_sheet("Security_stats")
h = ["Ticker", "Subsector", "In PF2", "Ann. volatility", "Beta vs SPY", "Beta std. error", "Beta 95% CI low",
     "Beta 95% CI high", "R-squared", "Worst day", "Best day", "N obs"]
for j, x in enumerate(h, 1): hdr(st.cell(1, j, x))
for i, t in enumerate(MLP, 2):
    Y = rng(L(MLP.index(t) + 2))
    st.cell(i, 1, f"=Weights!A{i}"); st.cell(i, 2, f"=Weights!B{i}"); st.cell(i, 3, f'=IF(Weights!D{i}=1,"Yes","No")')
    for j in (1, 2, 3): f(st.cell(i, j), GREEN)
    forms = {4: (f"=STDEV({Y})*SQRT(252)", "0.0%"), 5: (f"=SLOPE({Y},{X})", "0.00"),
             6: (f"=STEYX({Y},{X})/(STDEV({X})*SQRT(COUNT({X})-1))", "0.000"),
             7: (f"=E{i}-TINV(0.05,L{i}-2)*F{i}", "0.00"), 8: (f"=E{i}+TINV(0.05,L{i}-2)*F{i}", "0.00"),
             9: (f"=RSQ({Y},{X})", "0.000"), 10: (f"=MIN({Y})", "0.0%"), 11: (f"=MAX({Y})", "0.0%"),
             12: (f"=COUNT({Y})", "0")}
    for j, (fm, fmt) in forms.items():
        st.cell(i, j, fm); f(st.cell(i, j), BLACK, fmt)
SR = N + 3
st.cell(SR, 1, "SPY"); f(st.cell(SR, 1), b=True)
st.cell(SR, 4, f"=STDEV({X})*SQRT(252)"); f(st.cell(SR, 4), BLACK, "0.0%")
for c, wdt in zip("ABCDEFGHIJKL", (9, 26, 8, 12, 11, 11, 11, 11, 10, 10, 10, 8)): st.column_dimensions[c].width = wdt
st.freeze_panes = "B2"

# ---------------------------------------------------------------- Correlation
co = wb.create_sheet("Correlation")
hdr(co.cell(1, 1, "Ticker"))
for j, t in enumerate(MLP, 2):
    hdr(co.cell(1, j, t)); co.cell(j, 1, t); f(co.cell(j, 1), b=True)
for i, ti in enumerate(MLP, 2):
    for j, tj in enumerate(MLP, 2):
        c = co.cell(i, j, f"=CORREL({rng(L(MLP.index(ti) + 2))},{rng(L(MLP.index(tj) + 2))})"); f(c, BLACK, "0.00")
fc1, fc2 = N + 2, N + 3            # flag columns
fr1, fr2 = N + 2, N + 3            # flag rows
hdr(co.cell(1, fc1, "PF1 flag")); hdr(co.cell(1, fc2, "PF2 flag"))
co.cell(fr1, 1, "PF1 flag"); co.cell(fr2, 1, "PF2 flag"); f(co.cell(fr1, 1), b=True); f(co.cell(fr2, 1), b=True)
for k in range(N):
    co.cell(k + 2, fc1, f"=Weights!C{k+2}"); co.cell(k + 2, fc2, f"=Weights!D{k+2}")
    co.cell(fr1, k + 2, f"=Weights!C{k+2}"); co.cell(fr2, k + 2, f"=Weights!D{k+2}")
    for c in (co.cell(k + 2, fc1), co.cell(k + 2, fc2), co.cell(fr1, k + 2), co.cell(fr2, k + 2)): f(c, GREEN, "0")
M = f"Correlation!$B$2:${L(N+1)}${N+1}"
co.column_dimensions["A"].width = 10
for j in range(2, N + 4): co.column_dimensions[L(j)].width = 7
co.freeze_panes = "B2"
from openpyxl.formatting.rule import ColorScaleRule
co.conditional_formatting.add(f"B2:{L(N+1)}{N+1}", ColorScaleRule(start_type="num", start_value=-1, start_color="FF5B9BD5",
                              mid_type="num", mid_value=0, mid_color="FFFFFFFF", end_type="num", end_value=1, end_color="FFF8696B"))

# ---------------------------------------------------------------- Portfolio stats
ps = wb.create_sheet("Portfolio_stats")
for j, x in enumerate(["Metric", "PF1", "PF2", "PF2 - PF1", "Definition"], 1): hdr(ps.cell(1, j, x))
def pr(pf): return rng(pf1c if pf == "PF1" else pf2c)
W = {"PF1": f"Weights!$E$2:$E${N+1}", "PF2": f"Weights!$F$2:$F${N+1}"}
FLAG = {"PF1": (f"Correlation!${L(fc1)}$2:${L(fc1)}${N+1}", f"Correlation!$B${fr1}:${L(N+1)}${fr1}"),
        "PF2": (f"Correlation!${L(fc2)}$2:${L(fc2)}${N+1}", f"Correlation!$B${fr2}:${L(N+1)}${fr2}")}
VOL = f"Security_stats!$D$2:$D${N+1}"
DATES = f"Returns_250d!$A${D0}:$A${D1}"
metrics = [
    ("Number of holdings", lambda p, c: f"=COUNTIF({W[p]},\">0\")", "0", "Names with weight > 0"),
    ("Annualized volatility", lambda p, c: f"=STDEV({pr(p)})*SQRT(252)", "0.0%", "Daily std. dev. of portfolio return x SQRT(252)"),
    ("Beta vs SPY", lambda p, c: f"=SLOPE({pr(p)},{X})", "0.00", "OLS slope on SPY daily total return"),
    ("Beta std. error", lambda p, c: f"=STEYX({pr(p)},{X})/(STDEV({X})*SQRT(COUNT({X})-1))", "0.000", "Classical OLS standard error"),
    ("Beta 95% CI low", lambda p, c: f"={c}4-TINV(0.05,COUNT({X})-2)*{c}5", "0.00", "t distribution, n-2 df"),
    ("Beta 95% CI high", lambda p, c: f"={c}4+TINV(0.05,COUNT({X})-2)*{c}5", "0.00", "t distribution, n-2 df"),
    ("R-squared vs SPY", lambda p, c: f"=RSQ({pr(p)},{X})", "0.000", "Share of daily variance explained by SPY"),
    ("Average pairwise correlation", lambda p, c: f"=(SUMPRODUCT({M}*{FLAG[p][0]}*{FLAG[p][1]})-{c}2)/({c}2*({c}2-1))", "0.00", "Mean of off-diagonal correlations among holdings"),
    ("Weighted average stock volatility", lambda p, c: f"=SUMPRODUCT({W[p]},{VOL})", "0.0%", "Sum of weight x stand-alone volatility"),
    ("Diversification ratio", lambda p, c: f"={c}10/{c}3", "0.00", "Weighted average stock vol / portfolio vol"),
    ("Weight HHI", lambda p, c: f"=SUMSQ({W[p]})", "0.000", "Sum of squared weights"),
    ("Effective number of holdings", lambda p, c: f"=1/{c}12", "0.0", "1 / HHI"),
    ("Largest subsector weight", lambda p, c: f"=MAX(Weights!${'B' if p=='PF1' else 'C'}${r0+1}:${'B' if p=='PF1' else 'C'}${SUB_LAST})", "0.0%", "From the subsector table on the Weights sheet"),
    ("Worst day in window", lambda p, c: f"=MIN({pr(p)})", "0.00%", "Lowest daily portfolio return"),
    ("Date of worst day", lambda p, c: f"=INDEX({DATES},MATCH(MIN({pr(p)}),{pr(p)},0))", "yyyy-mm-dd", ""),
]
for i, (name, fn, fmt, dfn) in enumerate(metrics, 2):
    ps.cell(i, 1, name); f(ps.cell(i, 1), b=True)
    for j, (p, c) in enumerate((("PF1", "B"), ("PF2", "C")), 2):
        ps.cell(i, j, fn(p, c)); f(ps.cell(i, j), BLACK, fmt)
    if name not in ("Date of worst day",):
        ps.cell(i, 4, f"=C{i}-B{i}"); f(ps.cell(i, 4), BLACK, fmt)
    ps.cell(i, 5, dfn); f(ps.cell(i, 5))
k = len(metrics) + 3
ps.cell(k, 1, "SPY annualized volatility"); f(ps.cell(k, 1), b=True)
ps.cell(k, 2, f"=Security_stats!D{SR}"); f(ps.cell(k, 2), GREEN, "0.0%")
for c, wdt in zip("ABCDE", (32, 12, 12, 12, 52)): ps.column_dimensions[c].width = wdt
wb.move_sheet("Portfolio_stats", offset=-4)

# ---------------------------------------------------------------- Check vs Python
ck = wb.create_sheet("Check")
for j, x in enumerate(["Item", "Workbook formula", "Python reference (static)", "Abs. difference", "Status"], 1): hdr(ck.cell(1, j, x))
checks = []
pmap = {"Annualized volatility": "ann_vol", "Beta vs SPY": "beta", "R-squared vs SPY": "r2", "Average pairwise correlation": "avg_pair_corr",
        "Weighted average stock volatility": "wavg_stock_vol", "Diversification ratio": "div_ratio", "Weight HHI": "hhi", "Worst day in window": "worst_day"}
for i, (name, *_ ) in enumerate(metrics, 2):
    if name in pmap:
        for p, c in (("PF1", "B"), ("PF2", "C")):
            checks.append((f"{p} {name}", f"=Portfolio_stats!{c}{i}", float(port.loc[pmap[name], p])))
for i, t in enumerate(MLP, 2):
    checks.append((f"{t} volatility", f"=Security_stats!D{i}", float(sec.loc[t, "ann_vol"])))
    checks.append((f"{t} beta", f"=Security_stats!E{i}", float(sec.loc[t, "beta"])))
for r, (name, fm, val) in enumerate(checks, 2):
    ck.cell(r, 1, name); ck.cell(r, 2, fm); ck.cell(r, 3, val)
    ck.cell(r, 4, f"=ABS(B{r}-C{r})"); ck.cell(r, 5, f'=IF(D{r}<0.000000001,"OK","CHECK")')
    f(ck.cell(r, 1)); f(ck.cell(r, 2), GREEN, "0.000000"); f(ck.cell(r, 3), BLUE, "0.000000"); f(ck.cell(r, 4), BLACK, "0.0E+00"); f(ck.cell(r, 5))
last = len(checks) + 1
ck.cell(last + 2, 1, "Items checked"); ck.cell(last + 2, 2, f"=COUNTA(A2:A{last})")
ck.cell(last + 3, 1, "Items OK"); ck.cell(last + 3, 2, f'=COUNTIF(E2:E{last},"OK")')
for rr in (last + 2, last + 3): f(ck.cell(rr, 1), b=True); f(ck.cell(rr, 2), BLACK, "0", True)
for c, wdt in zip("ABCDE", (34, 18, 22, 14, 9)): ck.column_dimensions[c].width = wdt
ck.freeze_panes = "A2"

wb.save(OUT)
print("saved", OUT, "checks", len(checks))
