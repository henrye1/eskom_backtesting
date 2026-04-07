# Dashboard Metrics and Export Requirements Document

**Document Version:** 1.0
**Date:** 2026-03-31
**Client:** Anchor Point Risk (Pty) Ltd
**Framework:** LGD Development Factor Backtesting Framework (IFRS 9)
**Reference Entity:** Eskom (Non-Metro Municipalities, RR basis)

---

## 1. Purpose

This document specifies the metrics, outputs, and interpretations produced by the LGD Development Factor Backtesting Framework across its three export channels:

1. **Interactive HTML Dashboard** (Plotly, 10 charts + summary tables)
2. **Single-Window Excel Workbook** (value-based summary)
3. **Full Audit Trail Excel Workbook** (live Excel formulas replicating all intermediate calculations)

The intended audience is the internal audit team responsible for model validation under IFRS 9 paragraph 5.5.

---

## 2. Configurable Parameters

All outputs are generated from a common parameter set. Auditors should confirm these match the approved model configuration.

| Parameter | Default | Description |
|-----------|---------|-------------|
| Discount Rate | 15% (annual) | EIR proxy applied via monthly compounding: DF = 1/(1+rate)^((c+1-r)/12) |
| Vintage Window Size | 60 months | Number of consecutive default cohorts per rolling vintage window |
| Min Observation Window | Variable (12-60) | Minimum cohorts per TID column in chain-ladder calculations; controls calibration depth |
| Max TID | 60 | Maximum months-in-default modelled |
| CI Percentile | 75% | Confidence percentile for CI bands; z derived via NORMSINV(percentile) |
| LGD Cap | None (uncapped) | Optional cap at 1.0; when None, LGD may exceed 100% for deeply discounted late recoveries |
| Monotone LGD | True | Enforces LGD(t) >= LGD(t-1) so the term structure never dips below a previous period |

---

## 3. Summary KPI Metrics (HTML Dashboard Header + Streamlit Cards)

These six headline metrics appear in the dashboard summary box and Streamlit KPI cards. They describe the **recommended (best-scoring) scenario**.

### 3.1 RMSE (Root Mean Squared Error)

- **Definition:** sqrt(mean(residual^2)) across all non-NaN residuals
- **Interpretation:** Measures the average magnitude of forecast errors, penalising large errors more heavily than MAE. Lower values indicate better precision.
- **Audit use:** Primary precision metric. Compare across window sizes to assess calibration stability.

### 3.2 MAE (Mean Absolute Error)

- **Definition:** mean(|residual|) across all non-NaN residuals
- **Interpretation:** Average absolute deviation of forecast from actual LGD. More robust to outliers than RMSE.
- **Audit use:** Cross-check against RMSE. If RMSE >> MAE, extreme errors are present.

### 3.3 Mean Bias

- **Definition:** mean(Actual - Forecast) across all non-NaN residuals
- **Sign convention:** Positive = model underestimates LGD (too optimistic); Negative = model overestimates LGD (too conservative)
- **Interpretation:** Near-zero indicates the model is unbiased on average. Persistent positive bias means provisions may be understated.
- **Audit use:** Critical for regulatory compliance. A statistically significant positive bias requires management action.

### 3.4 LGD at TID=0

- **Definition:** The latest vintage's LGD term structure value at Time in Default = 0
- **Interpretation:** The model's current best estimate of LGD at the point of default. This is the starting point for ECL calculations on newly defaulted exposures.
- **Audit use:** Track over time for stability. Large shifts between reporting periods require explanation.

### 3.5 Weighted LGD

- **Definition:** EAD-weighted average LGD across all cohorts in the latest vintage: sum(LGD_i x EAD_i) / sum(EAD_i)
- **Interpretation:** The portfolio-level LGD accounting for the size distribution of defaulted exposures. Larger exposures contribute more to the weighted average.
- **Audit use:** Primary input for portfolio-level ECL. Compare against regulatory benchmarks.

### 3.6 Number of Vintages

- **Definition:** n_total - window_size + 1 (e.g. 82 - 60 + 1 = 23)
- **Interpretation:** The number of overlapping rolling windows available for backtesting. More vintages provide more residual observations for statistical testing.
- **Audit use:** Confirms data sufficiency. Fewer than 10 vintages limits the power of normality and bias tests.

---

## 4. Scenario Comparison Table

The multi-scenario comparison table ranks all tested min-observation windows. One row per scenario, sorted by composite score ascending (best first).

### 4.1 Columns

| Column | Definition | Interpretation |
|--------|-----------|----------------|
| Rank | Position by composite score (1 = best) | Recommended window is Rank 1 |
| Window (months) | Min-observation window size | Controls how many cohorts contribute per TID column |
| Vintages | Number of vintage windows | Always the same across scenarios (determined by the fixed 60-month vintage window) |
| Residuals | Count of non-NaN (Actual - Forecast) cells | More residuals = more statistical power |
| Mean Error (Bias) | mean(residuals) | + = optimistic, - = conservative |
| Std Dev | std(residuals, ddof=1) | Dispersion of forecast errors |
| RMSE | sqrt(mean(residuals^2)) | Precision metric (error scale) |
| MAE | mean(\|residuals\|) | Robust precision metric |
| Median AE | median(\|residuals\|) | Resistant to outliers |
| Max \|Error\| | max(\|residuals\|) | Worst single-period forecast miss |
| IQR | Q75 - Q25 of residuals | Central spread (robust) |
| AIC Proxy | n x log(SSE/n) + 2k | Information criterion; k = window size as complexity penalty |
| Composite Score | Weighted combination (see 4.2) | Ranking metric; lower = better |
| JB Reject Normality | True/False | Whether Jarque-Bera rejects at 5% |
| Latest LGD TID=0 | Latest vintage's LGD at t=0 | Current point-of-default LGD estimate |
| Latest Weighted LGD | Latest vintage's EAD-weighted LGD | Current portfolio-level estimate |

### 4.2 Composite Score Formula

```
Composite = 0.20 x |mean_error| / max(MAE, 1e-10)    -- Bias ratio
          + 0.35 x RMSE                                -- Precision
          + 0.25 x MAE                                 -- Average error
          + 0.20 x max_abs_error / max(std_error, 1e-10)  -- Tail severity
```

**Interpretation:** Balances four dimensions:
- **Bias ratio (20%):** How much of the average error is systematic vs random
- **RMSE (35%):** Dominant precision measure
- **MAE (25%):** Robust average error
- **Tail severity (20%):** How extreme the worst error is relative to typical dispersion

**Audit use:** The composite score determines the recommended window. Auditors should verify that the weights align with the institution's risk appetite. A model with low RMSE but high tail severity may still be unacceptable.

---

## 5. HTML Dashboard Charts (10 Charts)

### Chart 1: LGD Term Structure by Vintage

- **Content:** Line chart showing LGD(t) for up to 8 representative vintages at the selected window size
- **X-axis:** Time in Default (months), 0 to window_size
- **Y-axis:** LGD (percentage)
- **Interpretation:** Reveals how the term structure shape evolves across vintages. Parallel shifts indicate systematic changes in recovery behaviour. Fan-outs indicate increasing uncertainty at longer horizons. Crossing lines may signal structural breaks in recovery patterns.
- **Audit use:** Visual inspection for stability. Term structures should be broadly similar across vintages if the model assumptions are stable.

### Chart 2: Forecast vs Actual -- Oldest Vintage

- **Content:** Two-line overlay comparing the oldest vintage's forecast LGD against actual LGD (from the next vintage)
- **X-axis:** Time in Default (months)
- **Y-axis:** LGD (percentage)
- **Interpretation:** The oldest vintage has the most hindsight (22 months for 23 vintages). Close tracking between forecast and actual validates the model's predictive power. Persistent divergence at specific TIDs indicates systematic model weakness at those horizons.
- **Audit use:** Primary visual validation. The gap between lines is the residual at each TID.

### Chart 3: Average Forecast Error by TID

- **Content:** Bar chart of mean(Actual - Forecast) at each TID across all vintages
- **Colour coding:** Red bars = positive error (model optimistic); Green bars = negative error (model conservative)
- **X-axis:** Time in Default (months)
- **Y-axis:** Average forecast error (percentage)
- **Interpretation:** Bars clustered near zero indicate unbiased forecasting across all horizons. Systematic positive bars at long TIDs would indicate the model consistently underestimates losses at longer durations.
- **Audit use:** Checks for term-point-specific bias. Regulatory expectation is no systematic pattern.

### Chart 4: Confidence Interval Bands

- **Content:** Shaded area showing upper/lower CI around the mean LGD, with actual data points for the oldest vintage overlaid
- **Formula:** Upper = MIN(1, Forecast_oldest[t] + z x StdDev[t] x sqrt(H/t)); Lower = MAX(0, ...)
- **X-axis:** Time in Default (months)
- **Y-axis:** LGD (percentage)
- **Interpretation:** Bands widen at longer horizons due to the sqrt(H/t) scaling factor. Actuals falling outside the bands indicate the model's uncertainty estimate is too narrow.
- **Audit use:** Coverage analysis. The overall coverage rate (fraction of actuals within bounds) is reported in the backtest summary. Expected coverage depends on the percentile chosen.

### Chart 5: Residual Distribution

- **Content:** Histogram of all non-NaN residuals with a fitted normal PDF overlay
- **Title annotation:** Jarque-Bera test result (JB statistic and reject/accept)
- **X-axis:** Residual value (Actual - Forecast)
- **Y-axis:** Frequency
- **Interpretation:** A bell-shaped histogram centred near zero indicates well-behaved residuals. Heavy tails (visible as excess mass beyond +/-2 sigma) explain why JB rejects normality. Skewness shifts the distribution asymmetrically.
- **Audit use:** Validates the distributional assumptions underlying the CI construction. Non-normal residuals mean z-based CIs may understate tail risk.

### Chart 6: Window Size Comparison (RMSE / MAE / Bias)

- **Content:** Three side-by-side bar subplots comparing all tested window sizes
- **Highlighting:** Best-scoring window shown in green
- **X-axis:** Window size (months)
- **Y-axis:** Metric value
- **Interpretation:** Reveals the bias-variance trade-off. Shorter windows may have lower bias but higher variance (noisier). Longer windows are more stable but may introduce stale data. The optimal window balances all three.
- **Audit use:** Justification for the selected window size. Auditors should confirm the recommended window is not an outlier driven by a single metric.

### Chart 7: LGD Term Structure Comparison Across Windows

- **Content:** Overlaid line charts of the latest vintage's LGD term structure for every tested window size
- **Highlighting:** Best-scoring window's line is thicker
- **X-axis:** Time in Default (months)
- **Y-axis:** LGD (percentage)
- **Interpretation:** Shows sensitivity of the LGD estimate to the calibration window. Convergent lines indicate robustness. Divergent lines at specific TIDs indicate sensitivity to the data window.
- **Audit use:** Sensitivity analysis. Large divergence at policy-relevant TIDs (e.g. TID 0, TID 12, TID 24) should be flagged.

### Chart 8: Residual Heatmap

- **Content:** 2D heatmap with vintages on the Y-axis, TID on the X-axis, cells coloured by residual value
- **Colour scale:** RdBu_r (red = positive/optimistic error, blue = negative/conservative error), centred at zero
- **Interpretation:** Reveals spatio-temporal patterns in forecast errors. A consistent red band at high TIDs across all vintages indicates systematic under-estimation at long horizons. Diagonal streaks may indicate time-varying recovery regimes.
- **Audit use:** Pattern detection. Random scatter (no visible structure) is the ideal outcome. Structured patterns warrant investigation.

### Chart 9: Vintage Weighted LGD Over Time

- **Content:** Line chart with markers showing EAD-weighted LGD for each vintage, ordered chronologically
- **X-axis:** Vintage period (date)
- **Y-axis:** EAD-weighted LGD (percentage)
- **Interpretation:** Trend over time in the portfolio-level loss estimate. Rising trend indicates deteriorating recovery performance; declining trend indicates improving recoveries.
- **Audit use:** Monitors model output stability. Sharp movements require explanation (e.g. large cohort entering/exiting the window, structural change in recovery process).

### Chart 10: QQ-Plot of Residuals

- **Content:** Sample quantiles vs theoretical normal quantiles with a 45-degree reference line
- **X-axis:** Theoretical quantiles (Normal distribution)
- **Y-axis:** Sample quantiles (observed residuals)
- **Interpretation:** Points lying on the 45-degree line indicate the residuals follow a normal distribution. Deviations in the tails (S-shape or banana shape) indicate heavy tails or skewness. The heavier the tail deviation, the more the normal-based CI underestimates extreme error probabilities.
- **Audit use:** Complementary to JB test. Provides visual evidence of where the distribution departs from normality.

---

## 6. Excel Export: Single-Window Summary Workbook

### 6.1 Sheet: LGD Term Structure Summary

- **Content:** One row per vintage, columns for TID 0 through TID 60
- **Values:** LGD percentage at each term point
- **Audit use:** Master reference for all vintage LGD estimates. Cross-reference against the HTML dashboard Chart 1.

### 6.2 Sheet: Forecast LGD

- **Content:** Forecast LGD matrix (n_vintages x n_tid)
- **Values:** Each cell is the vintage's LGD term structure value at that TID
- **Audit use:** The "predicted" side of the backtest comparison.

### 6.3 Sheet: Actual LGD

- **Content:** Actual LGD matrix populated via the diagonal backtest pattern
- **Values:** Actual LGD from the next vintage (v+1) for each vintage v
- **Note:** The last vintage has no actual (no v+1 to compare against)
- **Audit use:** The "observed" side of the backtest comparison.

### 6.4 Sheet: Residuals

- **Content:** Actual - Forecast matrix
- **Sign convention:** Positive = model was too optimistic; Negative = model was too conservative
- **Audit use:** Source data for all error metrics. Sum of non-NaN cells should equal 276 (at 60-month window).

### 6.5 Sheet: Normality Tests

| Metric | Description | Audit Interpretation |
|--------|-------------|---------------------|
| N | Count of non-NaN residuals | Data sufficiency check |
| Mean | Mean residual | Near-zero = unbiased |
| Std Dev | Standard deviation (ddof=1) | Scale of forecast uncertainty |
| Skewness | Third standardised moment | 0 = symmetric; >0 = right tail; <0 = left tail |
| Excess Kurtosis | Fourth standardised moment minus 3 | 0 = normal; >0 = heavy tails; <0 = light tails |
| JB Stat | Jarque-Bera test statistic: (n/6)(S^2 + K^2/4) | Compared against chi2(df=2) critical value |
| JB Critical | Chi-squared critical at alpha=0.05, df=2 (5.991) | Fixed threshold |
| JB Reject | True if JB Stat > JB Critical | If True, residuals are non-normal |
| Chi-Sq Stat | Chi-Square GoF statistic (12 bins, mu +/- 3sigma) | Compared against chi2(df=valid_bins-3) |
| Chi-Sq Critical | Chi-squared critical at alpha=0.05 | Depends on df after merging low-count bins |
| Chi-Sq Reject | True if Chi-Sq Stat > Chi-Sq Critical | If True, residuals do not fit a normal distribution |

### 6.6 Sheet: Upper CI (SEM Scaled) / Lower CI (SEM Scaled)

- **Content:** Full (n_vintages x n_tid) CI matrices
- **Formula:** Upper(i,t) = MIN(1, Forecast_oldest[t] + z x StdDev[t] x sqrt(H_i / min(t, n_v-1)))
- **Staircase pattern:** Vintage i has CI values from TID = i+1 onwards; TID 0 has no CI for any vintage
- **275 non-NaN cells** (not 276 -- TID 0 excluded from CI)
- **Audit use:** Verify CI coverage (% of actuals within bounds). Compare against the nominal percentile.

---

## 7. Excel Export: Full Audit Trail Workbook (Live Formulas)

This workbook replicates the reference spreadsheet structure with **live Excel formulas** so auditors can click any cell and trace calculations to the raw data.

### 7.1 Sheet: RR LGD TERM STRUCTURE ALL

- **Content:** Complete master recovery triangle (values)
- **Purpose:** Source data for all calculations; all vintage sheets reference back to this data

### 7.2 Sheet: LGD Term Structure Summary

- **Content:** One row per vintage with LGD values (values, not formulas)
- **Purpose:** Quick-reference overview for all vintage term structures

### 7.3 Vintage Calculation Sheets (one per vintage)

Named "RR LGD TERM STRUCTURES (X-Y)" where X-Y is the cohort offset range. Each sheet contains seven computational blocks with **live formulas**:

| Block | Content | Formula Pattern | Audit Verification |
|-------|---------|----------------|--------------------|
| Balance Triangle | Observation-masked balance data | Values (after mask) | Verify NaN cells match vintage date restriction |
| MIN Column | Minimum balance per cohort | =MIN(row_range) | Cross-check against source data |
| Recovery Vector | Aggregate recovery per TID transition | =SUMPRODUCT((col_{n+1}<>"") * col_n) - SUM(col_{n+1}) | Verify recovery = bal_n - bal_{n+1} for qualifying cohorts |
| Cumulative Balance | Balance denominator matrix | =SUMPRODUCT((cond_col<>"") * bal_col) | Lower-triangular; verify condition column is c+1 |
| Discount Matrix | Present value factors | =1/(1+rate)^((col_hdr - row_lbl)/12) | Verify rate = 15%, monthly compounding |
| LGD Component | Recovery rate per (TID, period) | =IFERROR(Recovery/CumBal, 0) | Should be between 0 and 1 for valid cells |
| LGD Term Structure | Final LGD by TID (columns E/F) | =IFERROR(1-SUMPRODUCT(comp, disc), 1) with monotonicity | Verify LGD(t) >= LGD(t-1) when monotone=True |
| Weighted LGD | EAD-weighted portfolio LGD | =SUMPRODUCT(lgd_col, ead_col)/SUM(ead_col) | Cross-check against Python value printed in cell |

### 7.4 Sheet: LGD Backtest Summary

Contains eight sections with live formulas:

| Section | Rows | Content | Formula Type |
|---------|------|---------|--------------|
| FORECAST LGD BY VINTAGE | n_v rows | Vintage forecast term structures | Values |
| ACTUAL LGD BY VINTAGE | n_v rows | Diagonal-pattern actuals | Values |
| MEAN / STD DEVIATION | 2 rows | Cross-vintage statistics | =AVERAGE(fc_col), =STDEV(fc_col) |
| MEAN LGD BY VINTAGE | n_v rows | Mean replicated where actual exists | =IF(ISBLANK(actual),"",mean) |
| CI PARAMETERS | 1 row | z-score, percentile, TID cap | Values (reference cells) |
| UPPER BOUND | n_v rows | Upper CI per (vintage, TID) | =MIN(1, fc_oldest + z * std * SQRT(h/MIN(t,cap))) |
| LOWER BOUND | n_v rows | Lower CI per (vintage, TID) | =MAX(0, fc_oldest - z * std * SQRT(h/MIN(t,cap))) |
| DIFFERENCE | n_v rows | Residuals | =IF(ISBLANK(actual),"",actual-forecast) |
| SUMMARY STATISTICS | 20 rows | All backtest metrics | Values (computed by Python engine) |

### 7.5 Backtest Summary Statistics Block

| Statistic | Value Type | Audit Interpretation |
|-----------|-----------|---------------------|
| Window Size (months) | Integer | Calibration depth for this scenario |
| Number of Vintages | Integer | Rolling windows available |
| Number of Residuals | Integer | Non-NaN comparison points (expect 276 at 60m) |
| Discount Rate | Percentage | Must match approved EIR proxy |
| CI Percentile | Decimal | User-selected confidence level |
| z-score | Decimal | = NORMSINV(CI Percentile) |
| Mean Error (Bias) | Decimal | + optimistic / - conservative |
| Std Dev of Errors | Decimal | Dispersion of residuals |
| RMSE | Decimal | sqrt(mean(residuals^2)) |
| MAE | Decimal | mean(\|residuals\|) |
| Median AE | Decimal | Robust central error |
| Max \|Error\| | Decimal | Worst single observation |
| IQR | Decimal | Q75 - Q25 of residuals |
| Composite Score | Decimal | Ranking metric (lower = better) |
| JB Rejects Normality | Boolean | True = residuals are non-normal |
| Overall CI Coverage | Percentage | Fraction of actuals within CI bounds |
| Latest LGD at TID=0 | Decimal | Current point-of-default estimate |
| Latest Weighted LGD | Decimal | Current portfolio-level estimate |

---

## 8. Excel Export: Multi-Scenario Workbook

### 8.1 Sheet: Scenario Comparison

- Full ranking table with all metrics from Section 4.1
- Best row highlighted (Rank 1)

### 8.2 Per-Scenario Sheets (for each window size)

- **{W}m Forecast:** Forecast LGD matrix
- **{W}m Residuals:** Residual matrix
- **{W}m LGD Term:** Latest vintage term structure with columns TID, LGD, Recovery (= 1 - LGD)

---

## 9. Traceability Matrix

| Dashboard Element | Excel Sheet | Metric | Formula Reference |
|-------------------|-------------|--------|-------------------|
| KPI Card: RMSE | Backtest Summary: Summary Stats | sqrt(mean(residuals^2)) | Scenario Comparison: RMSE column |
| KPI Card: MAE | Backtest Summary: Summary Stats | mean(\|residuals\|) | Scenario Comparison: MAE column |
| KPI Card: Mean Bias | Backtest Summary: Summary Stats | mean(residuals) | Scenario Comparison: Mean Error column |
| KPI Card: LGD at TID=0 | LGD Term Structure Summary: last row, TID_0 | Latest vintage LGD(0) | Scenario Comparison: Latest LGD TID=0 |
| KPI Card: Wtd LGD | Vintage sheet: Weighted LGD cell | SUMPRODUCT(lgd,ead)/SUM(ead) | Scenario Comparison: Latest Weighted LGD |
| Chart 1 | LGD Term Structure Summary | All vintages term structures | Vintage calc sheets: Column F |
| Chart 2 | Forecast LGD + Actual LGD | Oldest vintage row | Backtest Summary: rows 1 of Forecast/Actual |
| Chart 3 | Residuals sheet | Column means | Backtest Summary: DIFFERENCE section |
| Chart 4 | Upper CI + Lower CI sheets | Full CI matrices | Backtest Summary: UPPER/LOWER sections |
| Chart 5 | Normality Tests sheet | JB stat, mean, std | Backtest Summary: Summary Stats |
| Chart 8 | Residuals sheet | Full matrix | Backtest Summary: DIFFERENCE section |
| Chart 9 | LGD Term Structure Summary | Weighted LGD per vintage | Vintage sheets: Weighted LGD cell |

---

## 10. Approval

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Model Developer | | | |
| Model Validator | | | |
| Head of Risk | | | |

---

*Document generated by the LGD Development Factor Backtesting Framework, version March 2026.*
