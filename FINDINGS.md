# MLP Portfolio Market Risk Assessment: Summary of Findings

Author: Ginger Gao. Data through 2026-08-31; formation date T0 = 2026-06-12.
Baseline (PF1): 23 energy and natural-resource partnerships, equal-weighted.
Checked & Diversified (PF2): the 13 that pass the financial checks, equal-weighted, with no subsector above 40%.

Every figure can be traced to a file in `results/` or `deliverables/`.

## 1. Three main findings

1. **PF2 has slightly lower tail risk than PF1; the difference is significant but small.** Primary metric, one-day 97.5% ES: PF2 1.71%, PF1 1.88%, difference −0.17 pp, 95% block-bootstrap interval −0.27 to −0.02 pp. Differences in volatility and VaR are not significant.
2. **The primary model (historical simulation) is narrowly rejected in the 99% VaR backtest; filtered historical simulation (FHS) is not.** Over the 500 days before T0, HS 99% VaR was exceeded 10 times for each portfolio (5 expected, Kupiec p = 0.048); FHS was exceeded 5 times for each. Absolute risk levels should be read from FHS: ES of 2.63% for PF1 and 1.94% for PF2.
3. **The main risk is a simultaneous fall in US equities, oil and credit, and the linear stress model understates losses in real crises.** In scenario C1 the one-week loss is 18.9% for PF2 and 19.6% for PF1. Replaying February–March 2020, actual losses were 48.3% for PF2 and 53.1% for PF1, against model estimates of only 37.2% and 38.4%.

These results describe the risk of the holdings at formation. The screen used the same quarter's financial data, so they do not show that the selection rules caused the lower risk.

## 2. PF2 selection approach and holdings

PF2 keeps the partnerships from the 23-name universe that pass a set of financial checks. The checks cover, in general terms:

- a manual review for fundamental and governance concerns;
- debt and leverage considerations;
- the ability to service debt from earnings;
- the sustainability of distributions relative to cash generation;
- a cap on the weight of any single subsector, so that the result stays diversified.

Holdings (13): DMLP, ARLP, WES, UAN, HESM, MPLX, EPD, CQP, CAPL, GLP, WLKP, BSM, NRP. Five are midstream, 38.5% of the portfolio.

CQP and CAPL entered the list after the scope of the manual review was redefined. CAPL is the weakest of the 13.

## 3. Risk at formation (one day, % of portfolio value)

| Metric | PF1 | PF2 | Difference | 95% bootstrap interval |
|---|---|---|---|---|
| HS 97.5% ES (primary) | 1.88% | 1.71% | −0.17 pp | −0.27 to −0.02 pp |
| HS 99% VaR | 1.94% | 1.81% | −0.13 pp | −0.38 to +0.11 pp |
| HS 95% VaR | 1.37% | 1.21% | −0.16 pp | −0.38 to +0.15 pp |
| Annualized volatility | 12.4% | 11.8% | −0.6 pp | −1.4 to +0.2 pp |
| FHS 99% VaR | 2.54% | 1.82% | | |
| FHS 97.5% ES | 2.63% | 1.94% | | |
| EWMA 97.5% ES | 2.23% | 1.79% | | |
| HS 97.5% ES (500 days) | 2.83% | 2.72% | | |
| Stressed 99% VaR (2019-06 to 2020-06) | 15.9% | 13.6% | | |
| Stressed 97.5% ES | 14.9% | 13.2% | | |

- Over the 250-day window both portfolios have a beta to SPY close to zero. Oil prices swung sharply in the first half of 2026 and MLPs were negatively correlated with US equities (PF1 versus SPY: −0.19, against 0.41 to 0.62 in each year from 2019 to 2024).
- Against random equal-weighted 13-name portfolios: PF2's ES is at the 3rd percentile of all 1,144,066 combinations, and at the 5th percentile of the 312,851 that satisfy the 40% subsector cap.

## 4. Sources of risk (PF2, ES decomposition)

| Subsector | Weight | Share of portfolio ES |
|---|---|---|
| Midstream | 38.5% | 44.5% |
| Oil and gas royalties | 15.4% | 20.3% |
| Nitrogen fertilizer (UAN) | 7.7% | 15.8% |
| Coal and mineral resources | 15.4% | 10.7% |
| Fuel distribution | 15.4% | 10.1% |
| Petrochemicals (WLKP) | 7.7% | −1.5% |

- HESM contributes 16.3%, almost all of it from a single-day fall of 10.4% on 2025-09-19. This is single-name event risk.
- UAN's contribution comes from several falls (−8.5% on 2026-03-31, −5.4% on 2026-04-14).
- Limits: PF2's midstream weight is 38.5%, which is 96% of the 40% cap; PF1's is 47.8%, above the cap. VaR and ES for both portfolios use only 34–49% of the research limits.

## 5. Model validation

**99% VaR, 500 days before T0**

| Model | PF1 exceptions | PF2 exceptions | Kupiec p (PF1 / PF2) | Traffic light, last 250 days | Verdict |
|---|---|---|---|---|---|
| Historical simulation (primary) | 10 | 10 | 0.048 / 0.048 | Green / Green | Rejected |
| EWMA | 11 | 9 | 0.020 / 0.106 | Yellow / Green | Rejected for PF1; not rejected for PF2 |
| FHS | 5 | 5 | 1.000 / 1.000 | Green / Green | Not rejected |

- Exceptions cluster in early August 2024, late January 2025 and the April 2025 tariff shock.
- At the 95% level all three models pass (Kupiec p between 0.24 and 1.00).
- ES check: on days when losses exceeded the 97.5% VaR, PF2's average realized loss was 2.48% against an HS-predicted ES of 2.18%; for FHS the figures are 2.21% and 2.13%.
- Christoffersen independence test: p < 0.01 for every model at the 99% level, but the result is flagged as unreliable because there are too few exceptions. It is reported for reference and does not enter the decision rule.
- Out of sample (2026-06-15 to 2026-08-31, 54 days): HS 99% VaR was exceeded twice for each portfolio (0.54 expected, binomial p = 0.10). The sample is too short to conclude anything; the test's power is below 10%.

## 6. Stress testing

Weekly four-factor model (SPY, WTI, change in the 10-year yield, HYG orthogonalized to SPY), calibrated from 2019-03 to T0, 381 weeks.

| One-week scenario | PF1 | PF2 | Status |
|---|---|---|---|
| C1 Energy and credit crisis (SPY −15%, WTI −35%, −30 bp, HYG −10%) | −19.6% | −18.9% | Provisional |
| A5 Credit shock (HYG −10%) | −6.6% | −7.0% | Valid |
| A2 Oil price collapse (−35%) | −6.1% | −5.8% | Valid |
| A1 Equity selloff (−15%) | −5.6% | −4.8% | Provisional |
| A4 Rates up (+50 bp) | +2.1% | +2.4% | Provisional |
| A3 Oil price spike (+30%) | +5.2% | +5.0% | Provisional |
| C2 Oil price spike with falling equities | +1.3% | +1.5% | Provisional |
| B Severe shock from the original specification (including +200 bp) | −4.1% | −1.9% | Provisional (4.3x extrapolation) |

- When rates and oil rose, both portfolios gained over the sample (sensitivity of about +4.5 to rates and about +0.17 to oil). The real rate risk is a recession scenario.
- Calibrating on the last three years only, the equity sensitivity halves (to about 0.35) and the credit sensitivity rises to about 1.2; C1 stays near 19%.
- PF2 is slightly worse than PF1 only under the credit shock. In every scenario the difference between the two is within the 95% interval.

**Historical replays (losses shown as positive)**

| Period | Model PF1 / PF2 | Actual PF1 / PF2 |
|---|---|---|
| 2020-02-21 to 03-20 | 38.4% / 37.2% | 53.1% / 48.3% |
| 2022-03-11 to 04-08 | gain 3.8% / 3.8% | gain 9.9% / 10.0% |
| 2025-03-28 to 04-11 | 4.1% / 3.7% | 11.1% / 8.8% |
| 2026-02-13 to 03-13 | gain 7.8% / 7.6% | gain 2.7% / 2.8% |

- Reverse stress test: the most likely combination producing a 15% loss in one week is SPY about −13%, WTI about −33% and HYG about −6%, roughly 85% of the week ending 2020-03-20.
- Distribution sustainability: with a 10% fall in operating cash flow, CAPL's distribution coverage breaches the monitoring threshold (a 3.8% fall is enough). With a 20% fall, MPLX, CQP, WES and UAN breach it as well.

## 7. Limitations

- The screening rules were not tested historically; the conclusions are descriptive.
- The 250-day ES rests on about six observations, and the bootstrap cannot produce extreme losses that are absent from the window.
- The negative correlation between MLPs and US equities in 2026 may not persist.
- The linear stress model missed between a quarter and two thirds of actual losses in 2020 and 2025.
- The ICE high-yield spread series is only available from 2023-11, so HYG is used instead. Before MNR and TXO listed, their weights are spread equally across the other names.
- The out-of-sample period is only 54 days.

## 8. Monitoring recommendations

| Recommendation | Trigger for review |
|---|---|
| Use FHS as the primary VaR model, with HS as a comparison | Either model enters the yellow zone over the last 250 days |
| Track the C1 scenario against the 20% limit each month | Usage above 100% |
| Monitor high-yield spreads and the portfolio's credit sensitivity | Spreads widen by 100 bp within a month |
| Watch HESM and UAN | Either accounts for more than 15% of portfolio ES |
| Review CAPL's distribution coverage each quarter | Coverage breaches the monitoring threshold |
| Re-run the screen and recalibrate after each quarterly earnings season | The list of holdings changes |
| Extend out-of-sample monitoring before judging the models | At least 250 days |
