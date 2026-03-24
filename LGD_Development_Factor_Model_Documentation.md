# LGD Development Factor Model — Technical Documentation

**Model Type:** IFRS 9 Loss Given Default — Development Factor (Chain-Ladder)
**Framework:** Generic — applicable to any portfolio with a recovery triangle
**Reference Entity:** Eskom (Non-Metro Municipalities, Recognise Revenue basis)
**Author:** Anchor Point Risk (Pty) Ltd
**Document Date:** March 2026

---

## 1. Executive Summary

This document describes a generic Loss Given Default (LGD) development factor framework for estimating expected credit losses under IFRS 9. The framework constructs a recovery triangle from monthly default cohorts, applies the chain-ladder (development factor) methodology to project future recoveries, and discounts them at a configurable annual rate to arrive at a present-value LGD term structure indexed by months in default.

The framework is not specific to any particular portfolio or segment — it can be applied to any credit exposure that produces a recovery triangle (rows = default cohorts, columns = months-since-default, cells = outstanding balances). The reference implementation uses Eskom non-metro municipal receivable data (82 monthly cohorts, March 2019 to December 2025) as the validation dataset, producing LGD values ranging from approximately 29% at the point of default (TID 0) to near 100% for exposures in default for more than 40 months. A rolling-window backtest across 23 vintage periods confirms unbiased forecasts (mean residual = 0.70%) with moderate dispersion (σ = 9.4%). Residual normality is rejected by both Jarque-Bera and Chi-Square tests, indicating heavier-than-normal tails with implications for confidence interval construction.

---

## 2. Model Purpose and Scope

The framework serves two primary purposes. First, it provides a term structure of LGD estimates conditioned on the number of months an exposure has been in default, supporting the calculation of lifetime expected credit losses under IFRS 9 paragraph 5.5.3. Second, it provides a backtesting framework to validate that the development factor projections are consistent with subsequently observed recovery outcomes.

The development factor methodology is portfolio-agnostic — the same chain-ladder engine, vintage analysis, and backtesting framework apply regardless of the underlying asset class, provided the input data is structured as a recovery triangle. The framework does not incorporate forward-looking macroeconomic adjustments, downturn LGD overlays, or cure-rate analysis — these are addressed elsewhere in the IFRS 9 framework and can be applied as overlays to the development factor output.

---

## 3. Data Sources and Structure

### 3.1 Master Recovery Triangle

The foundation of the model is a recovery triangle. In the reference implementation this is stored in the "RR LGD TERM STRUCTURE ALL" sheet, but the framework accepts any workbook with the same columnar structure. Each row represents a default cohort (accounts that first entered default status in a particular calendar month), and the columns track the aggregate outstanding balance of that cohort at each subsequent month.

The key fields are as follows. **Period** is the calendar month of default. **TID** (Time in Default) represents the maximum number of months of observation available for that cohort — the oldest cohort has the highest TID and the most recent cohort has TID = 0. **EAD** is the Exposure at Default, equal to the outstanding balance at the point of default. **TID_0 through TID_N** record the outstanding balance at each month post-default. TID_0 equals the EAD by definition. As time progresses and recoveries occur, these balances decline. Cells are empty (NaN) beyond the cohort's available observation window.

### 3.2 Vintage Window Construction

The framework operates on rolling windows of the master data with a configurable window size (default 60 months). Each vintage window represents a set of consecutive default cohorts used to calibrate one LGD term structure. Crucially, within each vintage, each cohort's balance data is restricted to only those TID periods that would have been observable at the vintage date. A cohort that defaulted k months before the vintage end-date can observe at most k months of recovery data, regardless of how much subsequent data exists in the master.

---

## 4. Methodology

### 4.1 Overview

The methodology follows the actuarial chain-ladder approach adapted for credit risk. The five core steps are: (1) construct the observation-masked balance triangle for the vintage window, (2) compute aggregate recovery cash flows at each development period, (3) compute cumulative outstanding balance denominators, (4) build a discount factor matrix, and (5) derive the LGD term structure as one minus the sum of discounted incremental recovery rates.

### 4.2 Aggregate Recovery Calculation

For each development period transition from period n to n+1, the model computes the total recovery across all cohorts that have observations at both periods:

    Recovery(n) = Σᵢ Balance(i, n) − Σᵢ Balance(i, n+1)

where the summation runs over cohorts i that have a non-empty observation at period n+1. This difference captures the total cash received or write-down occurring between development periods n and n+1. The conditional summation ensures that only cohorts with complete paired observations contribute to the recovery estimate.

### 4.3 Cumulative Outstanding Balance

The cumulative outstanding balance forms a lower-triangular matrix. For development period row r and column c, the entry is:

    CumBal(r, c) = Σᵢ Balance(i, r)  [for cohorts with non-empty observation at c+1]

This denominator represents the total portfolio balance at development period r, restricted to cohorts that have sufficient history to observe period c+1. The matrix structure accounts for the progressively smaller number of cohorts available at longer development horizons.

### 4.4 Discount Factor Matrix

The discount factor matrix translates future recovery cash flows to present value. Each entry is computed as:

    DF(r, c) = 1 / (1 + rate)^((c + 1 − r) / 12)

where `rate` is the annual discount rate (15%) and the exponent converts the monthly time difference to an annual basis. The matrix is lower-triangular, with DF(r, r) representing a one-month discount and DF(r, c) for c > r representing progressively longer discounts.

The 15% discount rate is intended as a proxy for the effective interest rate on the underlying receivables. Under IFRS 9 paragraph B5.5.44, the discount rate should reflect the original effective interest rate of the financial instrument.

### 4.5 LGD Term Structure Derivation

The incremental recovery rate at each development period is the ratio of recovery to cumulative balance:

    RecoveryRate(t, c) = Recovery(c) / CumBal(t, c)

The LGD at time-in-default t is then:

    LGD(t) = 1 − Σ_c [ RecoveryRate(t, c) × DF(t, c) ]

where the summation runs over all development periods c ≥ t. This gives the present-value LGD conditional on the exposure currently being t months in default. At TID 0, the sum captures all future expected discounted recoveries. At higher TID values, fewer future recovery periods remain, and the LGD approaches 1.0.

### 4.6 EAD-Weighted Average

The overall EAD-weighted LGD is computed as the weighted average across cohorts:

    Weighted_LGD = Σᵢ (LGD(TIDᵢ) × EADᵢ) / Σᵢ EADᵢ

where TIDᵢ is the maximum observed time-in-default for cohort i and EADᵢ is its exposure at default. This produces a single summary statistic reflecting the current cohort composition.

---

## 5. Backtest Framework

### 5.1 Vintage Forecast vs Actual

The backtest compares each vintage's forecasted LGD term structure against the "actual" LGD that materialised in subsequent periods. The forecast LGD term structure represents the LGD term structure that is generated from historical default and loss data  up to that point. The reason for defining the LGDs at a point in time as forecast LGDs is that the last observed LGD terms structure for the observation period is kept constant for the entire backtesting period. the key objective is therefore to determine how the latest LGD represents future possible LGD term structure outcomes. The key obkective of this process isw to determine which historical period best represents future LGD term structure realisations. The actual LGD for vintage v at a given TID is obtained by reading the next vintage's (v+1) full LGD term structure at the same TID. The actual LGDs can therefore be seen as  forecast LGD term structures generated in the future back test period. The reason for defining them as actual is that the future LGD term structures are impacted by actual recovery data. This reflects the updated model estimate incorporating one additional month of observed recovery data.

The comparison is restricted to TID values where genuinely new information exists. For the oldest vintage (hindsight = 22 months), all TID values from 0 through 23 are compared. For each subsequent vintage, the starting TID shifts forward by one, reflecting that short-TID estimates are stable across adjacent vintages and comparing them would add noise rather than signal.

### 5.2 Residual Analysis

Residuals are defined as Actual − Forecast. A positive residual indicates the model underestimated LGD (was too optimistic about recoveries), while a negative residual indicates overestimation.

Across 276 non-null residuals, the model produces a mean error of 0.70% with a standard deviation of 9.4%. The near-zero mean confirms the model is approximately unbiased. The average forecast error by TID is also near zero across all term points, with no systematic over- or under-prediction at particular durations.

### 5.3 Confidence Intervals

## Backtest Confidence Intervals (SEM-based)

The backtest constructs confidence intervals around the cross-vintage mean LGD using the Standard Error of the Mean (SEM). The confidence level is user-configurable via the UI — it is never hardcoded into formulas.

### Setup

1. Accept the user's desired confidence percentile from the UI and store it in a designated input cell.
2. Compute the corresponding z-value using the inverse standard normal function (e.g. `NORM.S.INV(percentile)` in Excel, or `scipy.stats.norm.ppf(percentile)` in Python). For example, 75% → z ≈ 0.6745.

### Formulas

    Upper = MIN(1, Mean + z × StdDev × SQRT(N_steps / N_vintages))
    Lower = MAX(0, Mean − z × StdDev × SQRT(N_steps / N_vintages))

where:

- **Mean** = average of the cross-vintage LGD values from the LGD Term Structure Summary for a given term point column
- **StdDev** = standard deviation of the same cross-vintage LGD values
- **N_steps** = the term point index for that column (i.e. how many steps along the term structure). This increases across columns, causing the bands to widen for longer-horizon term points.
- **N_vintages** = total number of vintages in the dataset (derived dynamically from the data, not hardcoded)
- **z** = z-score corresponding to the user-selected confidence percentile, referenced from the UI input cell

### Key characteristics

- **Bands widen with term point**: The `SQRT(N_steps / N_vintages)` factor means the confidence interval grows as you move further along the term structure. Early term points have narrow bands; later term points have wider bands.
- **Variable across term points**: Band width differs across columns because Mean, StdDev, and N_steps all change per term point.
- **Staircase fill pattern**: Each vintage row only has values from its minimum available term point onward, determined by how many months of performance data that vintage has accumulated. Earlier term point columns are left blank for newer vintages. This creates a triangular or staircase shape — the oldest vintage fills the most columns, the newest vintage fills the fewest.

### Output layout

The output consists of two mirrored sections — upper bounds and lower bounds — each structured identically:

1. **Section header row**: A label summarising the parameters, e.g. `"UPPER BOUND ({pctl}th pctl) — SEM CI (z={z_value}, n={N_vintages})"`. All parameter values in the label should be dynamically derived, not typed manually.
2. **Column header row**: Term point periods (referenced from the term structure definition, not duplicated manually).
3. **Value rows**: One row per vintage, ordered oldest to newest. Each cell applies the upper or lower formula using the Mean, StdDev, and N_steps for that column. Cells for term points the vintage hasn't yet reached are left blank.

The lower bound section follows the same structure, substituting the lower bound formula.

### Implementation notes

- N_vintages, N_steps, term point ranges, and vintage counts must all be derived from the underlying data so the model adapts automatically when vintages are added or the observation window changes.
- The z-value must be a single cell reference so the user can change the confidence level and all bands update immediately.
- Mean and StdDev rows should reference the LGD Term Structure Summary data range dynamically (e.g. using OFFSET/COUNTA or structured references) rather than fixed cell addresses where possible.

### 5.4 Normality Tests

The Jarque-Bera test statistic of 13.3 exceeds the chi-squared critical value of 5.99 (α = 0.05, df = 2), rejecting the null hypothesis of normally distributed residuals. The Chi-Square goodness-of-fit test confirms this with a statistic of 262.3 against a critical value of 16.9.

The residual distribution exhibits approximate symmetry (skewness = 0.19) but is leptokurtic (excess kurtosis ≈ 1.0), indicating heavier tails than a normal distribution. This means extreme forecast errors occur more frequently than a Gaussian model would predict.

---

## 6. Spreadsheet Architecture and Audit Trail Export

### 6.1 Workbook Structure

The framework generates per-window audit trail workbooks that replicate the reference workbook structure. When new data is uploaded through the UI, these workbooks are regenerated automatically from the fresh analysis results. Each workbook contains:

**Master Data** ("RR LGD TERM STRUCTURE ALL") — the complete recovery triangle that all calculations reference.

**LGD Term Structure Summary** — one row per vintage with LGD values at each TID.

**Vintage Calculation Sheets** — one sheet per vintage, named "RR LGD TERM STRUCTURES (X-Y)" where X-Y denotes the cohort range. The number of sheets is determined dynamically by the number of vintages in the backtest set. Each vintage sheet contains seven computational blocks:

1. The observation-masked balance triangle (cohort metadata, EAD, MIN balance, balance values)
2. The weighted LGD and check row
3. Model parameters (interest rate, columns, rows, min)
4. Aggregate recovery vector
5. Cumulative balance matrix
6. Discount factor matrix
7. LGD component matrix (Recovery / CumBal x DF)

**LGD Backtest Summary** — forecast, actual, mean, upper CI, lower CI, residuals, and summary statistics.

### 6.2 Audit Trail Purpose

The full audit trail workbooks serve as the bridge between the UI and the underlying mathematics. Users can:

- Verify every intermediate calculation step per vintage
- Trace the LGD at any TID back through the component matrix to the raw recovery and balance data
- Compare workbook values cell-by-cell against the dashboard results
- Confirm that the observation mask correctly restricts data to the vintage date

The workbooks are generated on-the-fly from the same computation engine that powers the dashboard, so values always match exactly.

### 6.3 Download Options

The UI provides two audit trail download options:

- **Single window** — select any window size and download its full audit trail workbook
- **All windows (ZIP)** — download a ZIP file containing audit trail workbooks for all selected window sizes

These complement the existing summary exports (multi-scenario Excel, single-window summary, HTML dashboard).

### 6.4 Key Formulas

The recovery at development period n is computed as an array formula: `{=SUM(IF(col_{n+1}<>"", col_n)) - SUM(col_{n+1})}`, where the IF condition restricts the sum to cohorts with observations at the next period.

The cumulative balance denominator for row r, column c is: `{=SUM(IF(col_{c+1}<>"", col_r))}`, applying the same observation mask.

The discount factor is: `=1/(1+rate)^((col-row)/12)` where the rate is configurable (default 0.15).

The LGD at each TID is: `=1 - SUMPRODUCT(recovery_rates, discount_factors)`, where recovery rates are `=IFERROR(Recovery/CumBal, 0)`.

---

## 7. Key Findings and Recommendations

### 7.1 Model Performance

The development factor framework performs well on the reference dataset. The mean forecast error is near zero (0.7%), confirming absence of systematic bias. The standard deviation of 9.4% reflects moderate forecast uncertainty, which is expected given the heterogeneous nature of recovery behaviour across default cohorts.

### 7.2 Issues Identified

**LGD values exceeding 1.0**: The latest vintage produces LGD values above 100% at TID 42–49 (maximum 102.9%). This occurs because discounting penalises very late recoveries sufficiently to push cumulative discounted recovery below zero at the margin. A decision should be documented on whether to cap LGD at 1.0 or accept economic LGD > 1.

**Non-normal residuals**: The leptokurtic residual distribution means the normal-approximation confidence intervals understate tail risk. Consider replacing the z-based CI with empirical quantiles or a t-distribution with estimated degrees of freedom.

**Confidence interval formulation**: The `√(N − hindsight)` scaling produces dramatically wide bands for recent vintages. This is a heuristic rather than a standard statistical CI. Consider using bootstrap resampling or the standard error of the mean for more rigorous uncertainty quantification.

---

## 8. Glossary

**Chain-Ladder**: An actuarial technique for projecting the ultimate development of claims or losses from incomplete triangular data, using ratios of successive development period totals.

**Cohort**: A group of accounts that entered default status in the same calendar month.

**Development Factor**: The ratio of cumulative recoveries at successive development periods, used to project future recovery patterns from incomplete data.

**EAD (Exposure at Default)**: The outstanding balance at the point an account first enters default status.

**EIR (Effective Interest Rate)**: The rate that exactly discounts estimated future cash flows through the expected life of the financial instrument to its gross carrying amount.

**Hindsight**: The number of months of subsequent data available beyond a given vintage date, used to measure how much validation evidence exists.

**IFRS 9**: International Financial Reporting Standard 9 — Financial Instruments, which requires entities to recognise expected credit losses on financial assets.

**LGD (Loss Given Default)**: The proportion of exposure that is not recovered following default, expressed as a percentage of EAD.

**Recovery Triangle**: A matrix where rows represent default cohorts and columns represent months since default, with entries showing outstanding balances. The upper-right portion is empty because recent cohorts have not been observed long enough.

**TID (Time in Default)**: The number of months elapsed since an account entered default status.

**Vintage**: A specific rolling window of cohorts used to estimate the LGD term structure. Each vintage represents the information set available at a particular point in time.
