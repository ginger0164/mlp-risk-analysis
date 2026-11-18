# MLP Portfolio Market Risk Assessment

Market risk assessment of two equal-weighted portfolios of US master limited partnerships (MLPs) in energy and natural resources:

- **Baseline (PF1):** 23 partnerships.
- **Checked & Diversified (PF2):** the 13 that pass a set of financial checks, with no subsector above 40%.

Author: Ginger Gao. Formation date T0 = 12 June 2026; data through 31 August 2026.

**Full findings:** [`FINDINGS.md`](FINDINGS.md)

> This project was carried out at **Hyde Park Alpha** and is published here with the firm's permission as a work sample. The firm's internal materials (its screening workbooks and the original project specification) have been removed; what remains is the methodology, the code, the market data and the results. Views and any errors are the author's own.
>
> Hypothetical pre-investment research on public market data. The portfolios are not actual holdings, and nothing here is investment advice.

## Question

Does screening the 23-name universe on leverage, interest coverage and distribution coverage, and capping subsector weights, produce a portfolio with lower tail risk at formation? And do the risk models used to answer that hold up in backtesting and stress testing?

## Main findings

1. **Lower tail risk, by a small margin.** One-day 97.5% expected shortfall (the primary metric) is 1.71% for PF2 against 1.88% for PF1: a difference of −0.17 pp, with a 95% block-bootstrap interval of −0.27 to −0.02 pp. Differences in volatility and VaR are not significant. PF2 ranks at the 5th percentile of ES among the 312,851 random 13-name portfolios that satisfy the same subsector cap.
2. **The primary VaR model is rejected; filtered historical simulation is not.** Over the 500 days before formation, historical-simulation 99% VaR was exceeded 10 times against 5 expected for both portfolios (Kupiec p = 0.048). Filtered historical simulation (FHS) was exceeded exactly 5 times. On FHS, formation-date ES is 2.63% for PF1 and 1.94% for PF2.
3. **The main exposure is a joint equity, energy and credit selloff, and the linear stress model understates crisis losses.** In that one-week scenario PF2 loses 18.9% and PF1 19.6%, close to the 20% research limit. Replaying February–March 2020, actual losses (48.3% and 53.1%) exceeded the model's estimates (37.2% and 38.4%).

These results describe the risk of the holdings at formation. The screens used the same quarter's financial data, so they do not show that the selection rules caused the lower risk.

### Formation-date risk (one day, % of portfolio value)

| Metric | PF1 | PF2 | Difference | 95% bootstrap interval |
|---|---|---|---|---|
| HS 97.5% ES (primary) | 1.88% | 1.71% | −0.17 pp | −0.27 to −0.02 pp |
| HS 99% VaR | 1.94% | 1.81% | −0.13 pp | −0.38 to +0.11 pp |
| HS 95% VaR | 1.37% | 1.21% | −0.16 pp | −0.38 to +0.15 pp |
| Annualized volatility | 12.4% | 11.8% | −0.6 pp | −1.4 to +0.2 pp |
| FHS 99% VaR | 2.54% | 1.82% | | |
| FHS 97.5% ES | 2.63% | 1.94% | | |
| Stressed 99% VaR (2019-06 to 2020-06) | 15.9% | 13.6% | | |

### 99% VaR backtest, 500 days before formation

| Model | Exceptions PF1 / PF2 (5 expected) | Kupiec p, PF1 / PF2 | Verdict |
|---|---|---|---|
| Historical simulation (primary) | 10 / 10 | 0.048 / 0.048 | Rejected |
| EWMA | 11 / 9 | 0.020 / 0.106 | Rejected for PF1 only |
| Filtered historical simulation | 5 / 5 | 1.000 / 1.000 | Not rejected |

Full results, including the ES decomposition by security and subsector, all stress scenarios, historical replays, reverse stress test and monitoring recommendations, are in [`FINDINGS.md`](FINDINGS.md).

## Method

| Step | What it does | Script |
|---|---|---|
| 1. Data QC | Builds price, return and factor panels from raw downloads; checks coverage, extreme returns and dividend reconciliation | `code/step1_qc.py` |
| 2. Baseline statistics | Security and portfolio statistics, correlations, T0 weights | `code/step2_calc.py` |
| 4. Formation-date risk | VaR and ES by historical simulation, FHS and EWMA; stressed VaR; Euler decomposition; block bootstrap of PF2 − PF1; comparison with random 13-name portfolios | `code/step4_risk.py` |
| 5a. Backtest | Kupiec, Christoffersen and traffic-light tests at 95% and 99% | `code/step5_backtest.py` |
| 5b. Stress test | Weekly four-factor model (SPY, WTI, change in 10-year yield, HYG orthogonalized to SPY); hypothetical scenarios, historical replays, reverse stress test | `code/step5_stress.py` |

All model parameters are fixed in the frozen configuration [`config/model_config_v1.yaml`](config/model_config_v1.yaml) (v1.0). The step 4 and step 5 results record the SHA-256 of the config they were run with.

**PF2 selection approach:** names from the 23-name universe that pass a manual review for fundamental and governance concerns and a set of financial checks covering debt and leverage, the ability to service debt, and the sustainability of distributions, subject to a cap on any single subsector.

**PF2 holdings:** DMLP, ARLP, WES, UAN, HESM, MPLX, EPD, CQP, CAPL, GLP, WLKP, BSM, NRP.

## Repository layout

| Path | Contents |
|---|---|
| `FINDINGS.md` | Full list of conclusions and key figures |
| `deliverables/` | Excel audit workbooks for steps 1, 2, 4 and 5 |
| `config/` | Frozen model configuration v1.0 |
| `code/` | Python scripts |
| `data/raw/` | Raw downloads from Yahoo Finance and FRED, with manifest |
| `data/qc/` | Cleaned prices, returns, factors and QC tables from step 1; distribution coverage of the PF2 names used by the stress test |
| `results/` | Outputs of steps 2, 4 and 5 (CSV, JSON) |
| `charts/` | Data behind the 99% VaR backtest chart |

## Reproduce

Requires Python 3.11+. Run from the repository root:

```bash
pip install -r requirements.txt
```

```bash
python code/step1_qc.py data/raw data/qc
python code/step2_calc.py
python code/step4_risk.py
python code/step5_backtest.py
python code/step5_stress.py
```

With the pinned package versions and random seed 42, these scripts reproduce the files in `data/qc/` and `results/` byte for byte.

Other scripts:

- `step2_excel.py`, `step4_excel.py`, `step5_excel.py` build the audit workbooks in `deliverables/`. They write formulas with openpyxl, so open and save each workbook once in Excel or LibreOffice to populate the calculated values.
- `fetch_pf2_data.py` downloads the raw data again. A fresh download will not match the stored files exactly, because adjusted prices change with later distributions.

## Data notes

- Prices come from Yahoo Finance; WTI, the 10-year Treasury yield and high-yield spreads come from FRED. Raw data was downloaded on 4 November 2026. All analysis uses data up to 31 August 2026, and risk estimates use data only up to T0.
- 19 file hashes in `data/raw/manifest.json` do not match the stored files, because the download script ran twice during market hours. The hashes of the files actually used are in `data/qc/received_manifest.csv`.
- `results/step4/random13.npz` (24 MB, the full random-portfolio distribution) is not stored; `step4_risk.py` regenerates it.
- The fundamentals used for screening came from the firm's internal workbooks, which are not included. The selection approach is described in general terms and the resulting PF2 list is given above; the screen itself cannot be re-run from this repository.

## Limitations

- The screening rules were not tested historically; the comparison is descriptive.
- A 250-day ES at 97.5% rests on about six observations, and the bootstrap cannot produce losses more extreme than those in the window.
- MLPs were negatively correlated with US equities in the first half of 2026 (PF1 versus SPY: −0.19, against 0.41 to 0.62 in 2019–2024). That regime may not persist.
- The linear stress model missed between a quarter and two thirds of actual losses in the 2020 and 2025 replays.
- The out-of-sample period is 54 trading days, too short to judge the models.
