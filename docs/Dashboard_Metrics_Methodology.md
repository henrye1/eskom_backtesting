# Methodology Document — Dashboard Metrics, Interpretation, and Export Outputs

**Document Version:** 1.0
**Date:** 2026-03-31
**Prepared by:** Anchor Point Risk (Pty) Ltd
**Framework:** LGD Development Factor Backtesting Framework (IFRS 9)
**Reference Entity:** Eskom (Non-Metro Municipalities, RR basis)
**Status:** For Audit Review

---

## 1. Introduction

This document provides a detailed methodology description for every metric, chart, and export produced by the LGD Development Factor Backtesting Framework. It is structured to enable an auditor to:

1. Understand what each metric measures and why it is relevant under IFRS 9
2. Trace any metric from the dashboard or Excel output back to its mathematical definition
3. Verify the computation by reproducing it from the raw data
4. Interpret the results in the context of model validation

---

## 2. Data Foundation

### 2.1 Recovery Triangle

The input is a recovery triangle with the following structure:

- **Rows:** Monthly default cohorts (accounts entering default in a given calendar month)
- **Columns:** Months since default (TID 0, 1, 2, ..., N)
- **Cell values:** Aggregate outstanding balance of the cohort at that month post-default
- **NaN cells:** Periods not yet observed (cohort hasn't existed long enough)

The reference dataset contains 82 monthly cohorts (March 2019 to December 2025), producing a triangle with up to 82 TID columns. TID_0 equals the EAD (Exposure at Default) by definition.

### 2.2 Vintage Window Construction

A vintage is a rolling window of W consecutive cohorts (default W=60). For a dataset with N cohorts, there are N - W + 1 vintages. Each vintage produces one LGD term structure using data available up to the vintage end-date.

**Observation mask (critical):** Within each vintage, each cohort's balance data is restricted to what was observable at the vintage date. A cohort that defaulted k months before the vintage end-date can observe at most k months. This prevents "look-ahead bias" — using future data that was not available when the vintage was computed.

### 2.3 Min-Observation Window

The min-observation window (MOW) controls how many cohorts contribute per TID column in the chain-ladder calculations. At TID 0, the most recent MOW cohorts are used. At higher TIDs, the window slides backward to include older cohorts that have data at that TID. This is distinct from the vintage window size — all scenarios produce the same number of vintages.

---

## 3. Core Computation Methodology

### 3.1 Aggregate Recovery

For each development period transition n to n+1:

```
Recovery(n) = SUM[Balance(i, n)] - SUM[Balance(i, n+1)]
              for cohorts i with non-NaN observation at n+1
```

This captures the net cash recovered (or written down) between periods. Only cohorts with paired observations contribute.

**Export location:** Vintage calculation sheets, Recovery row (Excel formulas).

### 3.2 Cumulative Balance

For row r (starting TID) and column c (conditioning TID):

```
CumBal(r, c) = SUM[Balance(i, r)]
               for cohorts i with non-NaN observation at c+1
```

This denominator restricts the balance sum to cohorts with sufficient history. The matrix is lower-triangular.

**Export location:** Vintage calculation sheets, Cumulative Balance section (Excel formulas).

### 3.3 Discount Factor

```
DF(r, c) = 1 / (1 + rate)^((c + 1 - r) / 12)
```

The `c + 1` convention (1-indexed column) comes from the reference workbook. Monthly compounding with annual rate (default 15%).

**Export location:** Vintage calculation sheets, Discount Factor section (Excel formulas).

### 3.4 LGD Term Structure

For each TID t:

```
LGD(t) = 1 - SUM[Recovery(c) / CumBal(t, c) x DF(t, c)]  for c in [t, N)
```

The final element LGD(N) = 1.0 (no recovery data beyond the triangle).

**Monotonicity enforcement:** When enabled, LGD(t) = MAX(LGD(t), LGD(t-1)) ensures the term structure is non-decreasing.

**LGD cap:** When set (e.g. 1.0), all values are clipped: LGD(t) = MIN(LGD(t), cap).

**Export location:** Vintage calculation sheets, columns E/F (Excel formula: `=IFERROR(1-SUMPRODUCT(comp_range, disc_range), 1)` with optional MAX for monotonicity).

### 3.5 EAD-Weighted LGD

```
Weighted_LGD = SUM[LGD(TID_i) x EAD_i] / SUM[EAD_i]
```

where TID_i is each cohort's maximum observed TID and EAD_i is its exposure at default. Cohorts with NaN LGD or zero EAD are excluded.

**Export location:** Vintage calculation sheets, Weighted LGD cell (Excel formula: `=SUMPRODUCT(lgd_col, ead_col)/SUM(ead_col)`).

---

## 4. Backtest Methodology

### 4.1 Forecast and Actual Matrices

**Forecast matrix** (n_v x n_tid): Row i contains vintage i's LGD term structure — the model's prediction at the vintage date.

**Actual matrix** (n_v x n_tid): Populated via the diagonal backtest pattern. For vintage i, the "actual" LGD at TID t is read from vintage i+1's full LGD term structure at the same TID. This reflects the updated model estimate incorporating one additional month of observed recovery data.

**Diagonal pattern specifics:**
- Vintage i=0 (oldest, hindsight=n_v-1): actual from vintage 1 at TIDs 0 through n_v
- Vintage i>0: actual from vintage i+1 at TIDs (n_v - hindsight) through n_v
- end_tid = n_v + 1 (not n_v) — produces 276 residuals at 60-month window
- The last vintage has no actual (no subsequent vintage to compare against)

**Export location:** Backtest Summary sheet: FORECAST and ACTUAL sections; Single-window workbook: Forecast LGD and Actual LGD sheets.

### 4.2 Residual Matrix

```
Residual(i, t) = Actual(i, t) - Forecast(i, t)
```

| Sign | Interpretation | Provisioning Impact |
|------|---------------|-------------------|
| Positive (+) | Model underestimated LGD | Provisions potentially understated |
| Negative (-) | Model overestimated LGD | Provisions potentially overstated |

Non-NaN residuals at the 60-month window: 276.

**Export location:** Backtest Summary sheet: DIFFERENCE section (Excel formula: `=IF(ISBLANK(actual),"",actual-forecast)`); Single-window workbook: Residuals sheet.

---

## 5. Error Metrics Methodology

All metrics are computed on the flattened vector of non-NaN residuals.

### 5.1 Mean Error (Bias)

```
Bias = (1/n) x SUM[residual_i]
```

**Purpose:** Tests whether the model is systematically optimistic or conservative. An unbiased model has Bias ≈ 0.

**Reference value:** +0.0070 (slightly optimistic — model underestimates LGD by 0.70pp on average).

**Audit interpretation:** A statistically significant positive bias means the model underestimates losses. Test significance using a t-test: t = Bias / (std / sqrt(n)). At n=276, even a small bias can be statistically significant.

### 5.2 Standard Deviation

```
Std = sqrt[(1/(n-1)) x SUM[(residual_i - mean)^2]]
```

Uses Bessel's correction (ddof=1) for sample standard deviation.

**Reference value:** 0.0939

**Audit interpretation:** Represents the typical dispersion of forecast errors around the mean. Combined with the mean, defines a ±1 sigma band.

### 5.3 Root Mean Squared Error (RMSE)

```
RMSE = sqrt[(1/n) x SUM[residual_i^2]]
```

**Purpose:** Measures average error magnitude, penalising large errors quadratically. Decomposes as RMSE^2 = Bias^2 + Variance, so RMSE captures both systematic and random error.

**Reference value (60m):** 0.0940

**Audit interpretation:** If RMSE >> MAE, extreme errors dominate. If RMSE ≈ MAE, errors are uniformly distributed in magnitude.

### 5.4 Mean Absolute Error (MAE)

```
MAE = (1/n) x SUM[|residual_i|]
```

**Purpose:** Average absolute deviation. More robust to outliers than RMSE (linear vs quadratic penalty).

**Reference value (60m):** 0.0634

**Audit interpretation:** Represents the "typical" forecast miss in absolute terms. Always <= RMSE.

### 5.5 Median Absolute Error

```
Median_AE = median(|residual_i|)
```

**Purpose:** Most robust central tendency measure. Unaffected by any number of extreme values.

**Audit interpretation:** If Median_AE << MAE, the error distribution has a heavy right tail (a few very large errors pull the mean up).

### 5.6 Maximum Absolute Error

```
Max_AE = max(|residual_i|)
```

**Purpose:** Identifies the single worst forecast miss in the backtest.

**Audit interpretation:** Should be contextualised relative to std. A Max_AE > 3 x std indicates extreme tail events. The vintage and TID responsible for the maximum error should be investigated.

### 5.7 Inter-Quartile Range (IQR)

```
IQR = Q75 - Q25
```

**Purpose:** Width of the central 50% of residuals. Robust measure of spread that excludes tails.

**Audit interpretation:** A narrow IQR with a wide overall range indicates most forecasts are accurate but a few are very poor.

### 5.8 AIC Proxy

```
AIC = n x log(max(SSE/n, 1e-20)) + 2k
```

where SSE = SUM[residual_i^2] and k = min_obs_window size.

**Purpose:** Penalises model complexity (larger windows use more data, analogous to more parameters). Balances goodness-of-fit against overfitting.

**Audit interpretation:** Useful for comparing windows of different sizes. Lower AIC is preferred. The penalty term 2k discourages unnecessarily large windows.

### 5.9 Composite Score

```
Composite = 0.20 x |Bias| / max(MAE, 1e-10)      (Bias Ratio)
          + 0.35 x RMSE                             (Precision)
          + 0.25 x MAE                              (Average Error)
          + 0.20 x Max_AE / max(Std, 1e-10)         (Tail Severity)
```

**Purpose:** Single ranking metric combining four dimensions. Lower = better. Determines the recommended min-observation window.

**Component interpretation:**

| Component | Weight | What It Captures |
|-----------|--------|-----------------|
| Bias Ratio | 20% | Fraction of average error that is systematic. Value of 0 = purely random errors. Value of 1 = all error is bias. |
| RMSE | 35% | Overall forecast precision including tail sensitivity |
| MAE | 25% | Robust average error magnitude |
| Tail Severity | 20% | How extreme the worst error is relative to typical dispersion. High values indicate outlier vulnerability. |

**Export location:** Scenario Comparison table (both HTML dashboard and Excel).

---

## 6. Confidence Interval Methodology

### 6.1 Formula

For vintage i and TID t:

```
scale(i, t) = z x StdDev[t] x sqrt(H_i / min(t, n_v - 1))

Upper(i, t) = MIN(1.0, Forecast_oldest[t] + scale(i, t))
Lower(i, t) = MAX(0.0, Forecast_oldest[t] - scale(i, t))
```

Where:
- **z** = NORMSINV(ci_percentile), e.g. 0.6745 for 75th percentile
- **StdDev[t]** = column-wise standard deviation of the forecast matrix (ddof=1)
- **H_i** = i + 1 (hindsight: 1 for oldest vintage, n_v-1 for newest)
- **t** = TID number (1-indexed; TID 0 has no CI)
- **n_v - 1** = TID cap (e.g. 22 for 23 vintages)
- **Forecast_oldest** = forecast[0, :] (oldest vintage's LGD term structure)

### 6.2 Key Properties

| Property | Description |
|----------|-------------|
| Centre | Oldest vintage's forecast LGD (NOT the cross-vintage mean) |
| Staircase pattern | Vintage i has CI from TID = H_i = i+1 onwards |
| TID 0 exclusion | No CI at TID 0 for any vintage |
| Band widening | sqrt(H/t) causes bands to widen at longer horizons |
| Unique per cell | Each (vintage, TID) has a different CI value |
| Non-NaN cells | 275 (not 276 — TID 0 excluded) |
| Bounded | Upper capped at 1.0, Lower floored at 0.0 |

### 6.3 Coverage Statistics

```
Coverage(t) = count(Lower[i,t] <= Actual[i,t] <= Upper[i,t]) / count(valid pairs at TID t)
Overall_Coverage = total_within / total_valid across all TIDs
```

**Audit interpretation:** If the CI is well-calibrated, overall coverage should approximate the nominal percentile. Significant undercoverage suggests the CI bands are too narrow (possible due to non-normal residuals). Overcoverage suggests the bands are unnecessarily wide.

### 6.4 Average CI Vectors (for chart display)

```
Upper_vector[t] = nanmean(Upper_CI[:, t])
Lower_vector[t] = nanmean(Lower_CI[:, t])
```

These are averaged across vintages for Chart 4 (which needs a single CI line per TID).

**Export location:** Full CI matrices in Upper CI / Lower CI sheets; Average vectors in Chart 4; Summary coverage in Backtest Summary Statistics.

---

## 7. Normality Test Methodology

### 7.1 Jarque-Bera Test

```
JB = (n/6) x (S^2 + K^2/4)
```

Where S = skewness and K = excess kurtosis of the residuals.

- **H0:** Residuals are normally distributed
- **Distribution under H0:** Chi-squared with df=2
- **Critical value at alpha=0.05:** 5.991
- **Decision rule:** Reject H0 if JB > 5.991

**Reference result:** JB = 13.3, p < 0.05. **Reject normality.**

**Audit interpretation:** The residuals have heavier tails than a normal distribution (excess kurtosis ~1.0) with mild positive skewness (~0.19). This means extreme forecast errors occur more frequently than a Gaussian model predicts.

### 7.2 Chi-Square Goodness-of-Fit

- **Binning:** 12 equally-spaced bins from mu - 3*sigma to mu + 3*sigma
- **Boundary adjustment:** First bin extended to -infinity, last bin to +infinity
- **Expected frequencies:** Based on normal CDF evaluated at bin edges
- **Bin merging:** Bins with expected count < 5 are merged
- **Degrees of freedom:** (number of valid bins after merging) - 3
- **Decision rule:** Reject H0 if Chi-Sq > chi2_critical(alpha=0.05, df)

**Reference result:** Chi-Sq = 262.3, critical = 16.9. **Reject normality.**

**Audit interpretation:** Confirms the Jarque-Bera finding. The residual distribution departs significantly from normality, particularly in the tails.

### 7.3 QQ-Plot

The QQ-plot (Chart 10) provides visual confirmation:
- **X-axis:** Theoretical normal quantiles (using the residual mean and std)
- **Y-axis:** Observed sample quantiles (sorted residuals)
- **45-degree reference line:** Points on this line indicate perfect normality

**Interpretation:** Departures from the line in the tails indicate heavy tails (points curve away from the line). An S-shape indicates both tails are heavier than normal.

---

## 8. Dashboard Chart Methodology

### Chart 1: LGD Term Structure by Vintage

**Data source:** `vintage_results[i].lgd_term_structure` for up to 8 evenly-spaced vintages.

**Construction:** Each line plots LGD(t) for t = 0 to window_size. Vintages are sampled at regular intervals to avoid visual clutter.

**Interpretation guide:**
- Parallel lines = stable recovery behaviour over time
- Fan-out at long TIDs = increasing uncertainty at longer horizons (expected)
- Crossing lines = structural change in recovery patterns (investigate)
- Lines converging at LGD = 1.0 at max TID = normal (no more recoveries expected)

### Chart 2: Forecast vs Actual -- Oldest Vintage

**Data source:** `forecast_matrix[0, :]` and `actual_matrix[0, :]`

**Why oldest vintage:** It has the most hindsight (n_v - 1 months of subsequent data), giving the most complete actual LGD profile.

**Interpretation guide:**
- Close tracking = good model fit
- Persistent gap = systematic bias at those TIDs
- Gap widening at long TIDs = normal (more uncertainty at longer horizons)

### Chart 3: Average Forecast Error by TID

**Data source:** `avg_error_by_tid = nanmean(residual_matrix, axis=0)`

**Colour coding:** Red bars (positive) = model optimistic; Green bars (negative) = model conservative.

**Interpretation guide:**
- All bars near zero = unbiased across all term points (ideal)
- Systematic positive bars at long TIDs = model underestimates late-stage losses
- Single large bar at a specific TID = possible data anomaly at that development period

### Chart 4: Confidence Interval Bands

**Data source:** `upper_ci_vector`, `lower_ci_vector` (averaged across vintages), `mean_lgd`, and `actual_matrix[0, :]`.

**Interpretation guide:**
- Shaded area = uncertainty range at the given percentile
- Points outside the shaded area = model exceeded its uncertainty estimate
- Bands widen at long TIDs = expected from the sqrt scaling
- Very narrow bands = low cross-vintage variation (but may understate true uncertainty)

### Chart 5: Residual Distribution

**Data source:** Flattened non-NaN residual vector.

**Construction:** 30-bin histogram with a scaled normal PDF overlay using the residual mean and std.

**Title annotation:** JB test result (statistic value and reject/accept).

**Interpretation guide:**
- Bell-shaped centred near zero = well-behaved residuals
- Visible excess mass in tails beyond +/-2 sigma = heavy tails (explains JB rejection)
- Asymmetry = systematic directional bias

### Chart 6: Window Size Comparison

**Data source:** RMSE, MAE, and Bias for each tested scenario.

**Construction:** Three side-by-side bar subplots. Best-scoring window highlighted in green.

**Interpretation guide:**
- Short windows: potentially lower bias but higher variance (fewer cohorts per TID)
- Long windows: more stable but may include stale recovery patterns
- The "best" window minimises the composite score, not any single metric

### Chart 7: LGD Term Structure Comparison Across Windows

**Data source:** Latest vintage's LGD term structure for each tested window size.

**Construction:** Overlaid line charts; recommended window has a thicker line.

**Interpretation guide:**
- Convergent lines = LGD estimate is robust to window choice (strong result)
- Divergent lines at specific TIDs = sensitivity to calibration data (requires investigation)
- All lines converge to 1.0 at max TID = expected

### Chart 8: Residual Heatmap

**Data source:** `residual_matrix` (n_v x n_tid).

**Construction:** Plotly Heatmap with RdBu_r colorscale (red = positive error, blue = negative), centred at zero.

**Interpretation guide:**
- Random scatter (no visible pattern) = ideal (errors are unpredictable)
- Horizontal bands = a specific vintage consistently over/underestimates
- Vertical bands = a specific TID is systematically biased
- Diagonal patterns = time-varying recovery regime changes

### Chart 9: Vintage Weighted LGD Over Time

**Data source:** `vintage_results[i].weighted_lgd` plotted against `vintage_results[i].period`.

**Interpretation guide:**
- Flat trend = stable portfolio-level LGD (ideal for provisioning)
- Rising trend = deteriorating recovery performance (increasing loss severity)
- Step changes = large cohort entering/exiting the window or structural break
- Seasonal patterns = possible cyclicality in recovery processes

### Chart 10: QQ-Plot of Residuals

**Data source:** Sorted residuals vs theoretical normal quantiles (calculated using residual mean and std as parameters).

**Construction:** Scatter plot with 45-degree reference line.

**Interpretation guide:**
- Points on the line = residuals are normally distributed
- S-shaped departure = heavy tails (leptokurtic)
- J-shaped departure = skewed distribution
- Outlier points far from the line = extreme forecast errors

---

## 9. Export Audit Trail — Cell-Level Verification Guide

### 9.1 Verifying a Single LGD Value

To verify LGD at TID t for a specific vintage:

1. Open the vintage's calculation sheet (e.g. "RR LGD TERM STRUCTURES (0-59)")
2. Navigate to column F, row (LGD_R1 + t)
3. Click the cell — the formula bar shows: `=MAX(IFERROR(1-SUMPRODUCT(comp_range, disc_range), 1), prev_cell)`
4. Trace `comp_range` to the LGD Component section — each cell is `=IFERROR(Recovery/CumBal, 0)`
5. Trace `Recovery` to the Recovery row — formula: `=SUMPRODUCT((next_col<>"")*this_col) - SUM(next_col)`
6. Trace `CumBal` to the Cumulative Balance section — formula: `=SUMPRODUCT((cond_col<>"")*bal_col)`
7. All formulas reference the Balance Triangle (raw values) at the top of the sheet

### 9.2 Verifying a CI Value

1. Open the "LGD Backtest Summary" sheet
2. Navigate to the UPPER BOUND section, row for vintage i, column for TID t
3. Formula: `=MIN(1, fc_oldest + z * std * SQRT(h / MIN(t, cap)))`
4. Trace `fc_oldest` to the FORECAST section, row 1 (oldest vintage), same TID column
5. Trace `std` to the STD DEVIATION row, same TID column (`=STDEV(forecast_column)`)
6. Trace `z` and `cap` to the CI PARAMETERS row (reference cells)

### 9.3 Verifying a Residual

1. In the DIFFERENCE section: `=IF(ISBLANK(actual),"",actual-forecast)`
2. Trace `actual` to the ACTUAL section (same row, same column)
3. Trace `forecast` to the FORECAST section (same row, same column)

### 9.4 Cross-Checking Python vs Excel

Every vintage calculation sheet includes a "Python: X.XXXXXX" annotation next to the Weighted LGD cell. This allows auditors to confirm that the Excel formulas produce the same result as the Python engine. Any discrepancy indicates a formula error.

---

## 10. Known Limitations and Disclosures

| Item | Description | Impact | Mitigation |
|------|-------------|--------|------------|
| Non-normal residuals | JB and Chi-Sq both reject normality at 5% | z-based CI may understate tail risk | Disclose in audit report; consider empirical quantile CI as supplementary |
| LGD > 1.0 | Uncapped LGD exceeds 100% at TID 42-49 | Downstream systems may not handle >100% | Configurable cap available; recommend cap=1.0 with diagnostic flag |
| Workbook discount rate error | Reference workbook "Latest" sheet uses 0% instead of 15% | ~4.5pp LGD difference at TID 0 | Python implementation is correct; workbook has linking error |
| Heuristic CI scaling | sqrt(H/t) is empirically derived, not a standard statistical CI | Coverage may not match nominal percentile | Report actual coverage statistics alongside nominal |
| Small vintage count | 23 vintages at 60-month window | Limits power of statistical tests | Normality tests may lack power; consider as vintages grow |
| Monotone enforcement | Masks non-monotone dips in raw data | Potential data quality signals hidden | Can be toggled off for diagnostic purposes |

---

## 11. Glossary

| Term | Definition |
|------|-----------|
| **Bias** | Mean residual (Actual - Forecast). Positive = model optimistic. |
| **Chain-Ladder** | Actuarial method projecting loss development from triangular data using ratios of successive period totals. |
| **CI** | Confidence Interval — range within which the true value is expected to lie at a given probability. |
| **Cohort** | Group of accounts entering default in the same calendar month. |
| **Composite Score** | Weighted combination of bias ratio, RMSE, MAE, and tail severity used to rank window sizes. |
| **Coverage** | Fraction of actual values falling within the CI bounds. |
| **EAD** | Exposure at Default — outstanding balance at the point of default. |
| **EIR** | Effective Interest Rate — the rate used for discounting under IFRS 9 para B5.5.44. |
| **Hindsight** | Months of subsequent data beyond a vintage date, used for backtest validation. |
| **IQR** | Inter-Quartile Range — width of the central 50% of a distribution. |
| **JB** | Jarque-Bera test — tests whether sample skewness and kurtosis match a normal distribution. |
| **LGD** | Loss Given Default — proportion of exposure not recovered, as a percentage of EAD. |
| **MAE** | Mean Absolute Error — average of absolute residuals. |
| **Min-Observation Window** | Minimum number of cohorts per TID column in the chain-ladder calculation. |
| **Monotone** | Non-decreasing constraint: LGD(t) >= LGD(t-1). |
| **QQ-Plot** | Quantile-Quantile plot comparing sample distribution against a theoretical distribution. |
| **Recovery Triangle** | Matrix of outstanding balances by cohort (rows) and months-since-default (columns). |
| **Residual** | Actual LGD minus Forecast LGD at a given (vintage, TID) pair. |
| **RMSE** | Root Mean Squared Error — square root of mean squared residuals. |
| **TID** | Time in Default — months elapsed since default. |
| **Vintage** | A rolling window of cohorts used to calibrate one LGD term structure. |
| **Vintage Window** | Fixed number of consecutive cohorts (default 60) forming each vintage. |

---

## 12. Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Model Developer | | | |
| Model Validator | | | |
| Head of Risk | | | |
| External Auditor | | | |

---

*Document generated by the LGD Development Factor Backtesting Framework, version March 2026.*
