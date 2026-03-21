# CLAUDE.md — Eskom LGD Backtesting Project

## Project Overview

Build a production-grade Python project that implements an **IFRS 9 LGD (Loss Given Default) Development Factor Model** for Eskom municipal debt. The model uses the **chain-ladder method** to estimate LGD term structures from monthly default cohort recovery data, then backtests forecasts against actuals across rolling vintage windows.

The project must be refactored from a validated monolithic script (`lgd_development_factor_model.py`, 1,178 lines) into a clean, modular, testable Python package with a Streamlit dashboard frontend.

**Client**: Anchor Point Risk (Pty) Ltd (`henry@anchorpointrisk.co.za`)
**Entity**: Eskom — Non-Metro Municipal Debt

---

## Source of Truth

The monolithic script `lgd_development_factor_model.py` (located alongside this file in the `Eskom Backtest` folder) has been **validated to machine precision** against the client's Excel workbook `Munic_dashboard_LPU_1.xlsx`. All 276 residuals at the 60-month window match to `max_abs_diff = 0.0000000000`. Do NOT alter the core computational logic — only refactor the structure.

The input workbook `Munic_dashboard_LPU_1.xlsx` contains:
- **Sheet `RR LGD TERM STRUCTURE ALL`**: Master recovery triangle — 82 monthly default cohorts (Mar 2019 to Dec 2025), columns `Period`, `MAXIF`, `DEFAULT YEAR`, `DEFAULT MONTH`, `TID`, `EAD`, `TID_0` through `TID_81`
- 23 vintage calculation sheets (e.g., `RR LGD TERM STRUCTURES  (0-59)`)
- `LGD Term Structure Summary` and `LGD Backtest Summary` sheets with charts

---

## Target Project Structure

```
eskom_backtesting/
├── CLAUDE.md                     # This file
├── README.md                     # User-facing documentation
├── pyproject.toml                # Project metadata & dependencies
├── requirements.txt              # Pinned dependencies
├── .gitignore
├── data/
│   └── Munic_dashboard_LPU_1.xlsx   # Input workbook (gitignored)
├── src/
│   └── lgd_model/
│       ├── __init__.py
│       ├── config.py             # ModelConfig dataclass
│       ├── data_loader.py        # load_recovery_triangle, extract_balance_matrix
│       ├── core_engine.py        # Recovery, cumbal, discount, LGD computations
│       ├── vintage.py            # VintageResult, run_single_vintage, run_vintage_analysis
│       ├── backtest.py           # BacktestResult, run_backtest, CI methods
│       ├── statistics.py         # Normality tests (JB, Chi-Square)
│       ├── scenario.py           # ScenarioResult, run_scenario, run_multi_scenario
│       ├── export.py             # Excel export functions
│       └── dashboard.py          # Plotly chart generation (static HTML)
├── app/
│   ├── streamlit_app.py          # Main Streamlit dashboard
│   └── components/
│       ├── sidebar.py            # Parameter controls
│       ├── summary_cards.py      # KPI metric cards
│       ├── charts.py             # Chart rendering components
│       └── tables.py             # DataTable components
├── tests/
│   ├── conftest.py               # Shared fixtures (load test data)
│   ├── test_core_engine.py       # Unit tests for recovery, cumbal, discount, LGD
│   ├── test_vintage.py           # Tests for vintage mask and analysis
│   ├── test_backtest.py          # Tests for diagonal pattern, residuals
│   ├── test_scenario.py          # Tests for multi-scenario runner
│   └── test_validation.py        # End-to-end validation against spreadsheet values
├── notebooks/
│   └── exploration.ipynb         # For ad-hoc analysis
└── scripts/
    ├── run_analysis.py           # CLI entry point
    └── validate_against_excel.py # Regression test vs spreadsheet
```

---

## Module Specifications

### 1. `config.py` — Configuration

```python
@dataclass
class ModelConfig:
    discount_rate: float = 0.15          # Annual discount rate (EIR proxy)
    window_size: int = 60                # Rolling window of cohorts per vintage
    max_tid: int = 60                    # Maximum time-in-default periods
    lgd_cap: Optional[float] = None      # Set to 1.0 to cap LGD; None = uncapped
    ci_z_score: float = 1.0              # z for heuristic CI
    ci_n_vintages: int = 23              # Total vintages in backtest
    ci_method: str = 'bootstrap'         # 'heuristic' | 'standard_error' | 'bootstrap'
    ci_level: float = 0.50               # CI coverage (0.50 = 25th/75th percentiles)
    ci_bootstrap_samples: int = 10000    # Number of bootstrap resamples
```

### 2. `data_loader.py` — Data Loading

Two functions:
- `load_recovery_triangle(filepath, sheet_name='RR LGD TERM STRUCTURE ALL')` — Reads the master sheet. Returns DataFrame with columns: `Period`, `MAXIF`, `DEFAULT_YEAR`, `DEFAULT_MONTH`, `TID`, `EAD`, `TID_0` .. `TID_N`. Must strip whitespace from column names and rename `DEFAULT YEAR` / `DEFAULT MONTH` to underscored versions.
- `extract_balance_matrix(df)` — Extracts the `TID_*` columns as a float ndarray of shape `(n_cohorts, n_periods)`.

### 3. `core_engine.py` — Core Computations

These are the mathematical building blocks. **Every formula must be preserved exactly.**

#### `compute_aggregate_recoveries(balance_matrix) -> ndarray`
For transition n to n+1:
```
Recovery(n) = SUM(Balance(i, n) for cohorts with observation at n+1)
            - SUM(Balance(i, n+1) for same cohorts)
```
The mask `has_next = ~isnan(balance_matrix[:, n+1])` restricts to cohorts with valid data at the next period. Last period recovery = 0.

#### `compute_cumulative_balances(balance_matrix) -> ndarray`
Returns shape `(n_periods, n_periods)`. For row r, column c:
```
CumBal(r, c) = SUM(Balance(i, r) for cohorts with observation at c+1)
```
Special case: last column uses `~isnan(balance_matrix[:, c])` instead of `c+1`.

#### `compute_discount_matrix(rate, n_periods) -> ndarray`
```
DF(r, c) = 1 / (1 + rate) ^ ((c + 1 - r) / 12)
```
Note the `c + 1` (1-indexed column convention from spreadsheet). Monthly compounding with annual rate.

#### `compute_lgd_term_structure(recoveries, cum_bal, discount_matrix, cap=None) -> ndarray`
Returns shape `(n_periods + 1,)`. For each TID t:
```
LGD(t) = 1 - SUM(Recovery(c) / CumBal(t, c) * DF(t, c), for c in [t, n_periods))
```
The final element `LGD(n_periods) = 1.0` (no recovery data beyond the triangle).

#### `compute_ead_weighted_lgd(lgd_per_cohort, eads) -> float`
Weighted average: `sum(lgd * ead) / sum(ead)` for cohorts with valid LGD and positive EAD.

### 4. `vintage.py` — Vintage Analysis

#### `VintageResult` dataclass
Fields: `vintage_label`, `period`, `start_idx`, `end_idx`, `lgd_term_structure`, `weighted_lgd`, `n_cohorts`.

#### `run_single_vintage(balance_matrix, eads, master_tids, start_idx, end_idx, config) -> ndarray`

**CRITICAL — Vintage Observation Mask**: Each cohort's data must be restricted to what would have been observable at the vintage date.

```python
offset = n_total - end_idx
for i in range(window.shape[0]):
    cohort_master_idx = start_idx + i
    adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
    if adjusted_max_tid < n_periods:
        window[i, max(0, adjusted_max_tid + 1):] = np.nan
```

Without this mask, the model uses "future" data that wasn't available at the vintage date, producing wrong cumulative balances. This was the hardest bug to find (took extensive debugging). The offset is how many months before the latest data point this vintage sits.

Then compute: recoveries -> cumbal -> discount_matrix -> lgd_term_structure. Pad to `max_tid + 1` with 1.0 if needed.

#### `run_vintage_analysis(master_df, config) -> list[VintageResult]`

Slides a rolling window across the master triangle:
- `n_vintages = n_total - window_size + 1`
- Vintage v uses cohorts `[v, v + window_size)`
- Label convention: `(oldest_offset-newest_offset)` where offsets count back from the last cohort. The last vintage gets prefix `Latest`.

### 5. `backtest.py` — Backtest Framework

#### `BacktestResult` dataclass
Fields: `forecast_matrix`, `actual_matrix`, `residual_matrix`, `mean_lgd`, `std_lgd`, `upper_ci`, `lower_ci`, `avg_error_by_tid`, `normality_stats`, `vintage_labels`, `periods`, `ci_method`.

#### Backtest Diagonal Pattern

**CRITICAL — This pattern was reverse-engineered from the spreadsheet and empirically verified across all 22 vintages.**

```python
for i in range(n_v - 1):
    hindsight = n_v - 1 - i
    source_idx = i + 1           # Actual comes from the NEXT vintage
    source_lgd = vintage_results[source_idx].lgd_term_structure
    start_tid = 0 if i == 0 else (n_v - hindsight)
    end_tid = n_v + 1            # Exclusive upper bound
    for t in range(start_tid, min(end_tid, n_tid)):
        if t < len(source_lgd):
            actual[i, t] = source_lgd[t]
```

Explanation:
- Vintage i=0 (oldest, hindsight=22): gets actual from vintage 1 at ALL TIDs 0 through n_v
- Vintage i=1 (hindsight=21): gets actual from vintage 2 starting at TID 2
- Generally: `start_tid = n_v - hindsight` for i > 0
- The actual LGD comes from the next vintage's full term structure (not a diagonal read of specific TIDs)
- `end_tid = n_v + 1` (NOT `n_v`) — this was a bug that caused 254 vs 276 residual count mismatch

`residuals = actual - forecast`
`mean_lgd = nanmean(forecast, axis=0)`
`std_lgd = nanstd(forecast, axis=0, ddof=1)`

#### Confidence Interval Computation

There is only one CI method: **Binomial CI with vintage × term-point scaling**. There is no method selector in the UI — this is the only approach used.

**Formula** — validated against Excel workbook to machine precision (0.00 diff across all 275 CI cells):

```python
from scipy.stats import norm

z = norm.ppf(config.ci_percentile)  # e.g. 0.95 → z ≈ 1.6449
forecast_oldest = forecast[0, :]    # Oldest vintage's LGD term structure (center of CI)
std_lgd = nanstd(forecast, axis=0, ddof=1)  # Column std across ALL vintages
tid_cap = n_v - 1                   # TID denominator cap (e.g. 22 for 23 vintages)

upper_ci = full((n_v, n_tid), NaN)
lower_ci = full((n_v, n_tid), NaN)

for i in range(n_v - 1):            # Last vintage has no CI
    h = i + 1                        # Hindsight: 1 for oldest, n_v-1 for newest
    start_t = h                      # CI starts at TID = H (staircase pattern)
    for t in range(start_t, n_tid):
        tid_d = min(t, tid_cap)      # TID denominator, 1-indexed, capped
        if tid_d == 0:
            continue
        scale = z * std_lgd[t] * sqrt(h / tid_d)
        upper_ci[i, t] = min(1.0, forecast_oldest[t] + scale)
        lower_ci[i, t] = max(0.0, forecast_oldest[t] - scale)
```

Key properties:
- **Center**: `forecast[0, :]` — the oldest vintage's forecast LGD (NOT the column mean)
- **Hindsight H**: `i + 1` where i=0 is oldest. H=1 for oldest, H=n_v-1 for newest
- **TID denominator**: TID number (1-indexed), capped at n_v-1. TID 0 has NO CI
- **Staircase**: vintage i has CI from TID = H = i+1 onwards
- **Each (vintage, TID) cell gets a UNIQUE value** — CI is NOT constant within columns
- **275 non-NaN CI cells** (not 276 — TID 0 has no CI for any vintage)
- **ci_percentile** is user-configurable (slider in UI). z is derived via `norm.ppf(ci_percentile)`
- **There is no CI method selector** in the UI — this is the sole method

Average upper/lower vectors (for charts needing a single CI line per TID) are computed as `nanmean(upper_ci, axis=0)` and `nanmean(lower_ci, axis=0)`.

**Known workbook discrepancy**: The Excel workbook's `RR LGD TERM STRUCTURES ` sheet (no suffix) uses discount_rate=0.0 instead of 0.15 for the Latest vintage, causing its LGD at TID 0 to be 0.2464 vs 0.2919 (Python, using correct 15% rate). This propagates a ~0.003 difference in std_lgd and ~0.6% max CI value difference. The Python code is correct; the workbook has a linking error. The `(0-59)` sheet with 15% rate matches Python to machine precision.

### 6. `statistics.py` — Normality Tests

`compute_normality_stats(residuals) -> dict`:
- N, mean, std (ddof=1), skewness, excess kurtosis
- **Jarque-Bera**: `JB = (n/6) * (skew^2 + kurtosis^2/4)`, chi2 df=2, critical at alpha=0.05
- **Chi-Square GoF**: 12 bins from mu-3sigma to mu+3sigma (first/last extended to +/-inf), merge bins with expected<5, df = valid_bins - 3

### 7. `scenario.py` — Multi-Scenario Runner

#### `ScenarioResult` dataclass
Fields: `window_size`, `n_vintages`, `n_residuals`, `mean_error`, `abs_mean_error`, `std_error`, `rmse`, `mae`, `median_ae`, `max_abs_error`, `iqr_error`, `jb_reject`, `aic_proxy`, `composite_score`, `latest_lgd_tid0`, `latest_weighted_lgd`, `vintage_results`, `backtest`.

#### `run_scenario(master_df, window_size, base_config) -> ScenarioResult`
For a given window_size:
- Set `max_tid = min(window_size, base_config.max_tid)`
- Set `ci_n_vintages = n_total - window_size + 1`
- Run vintage analysis + backtest
- Compute metrics on flat residuals: mean, std, rmse, mae, median_ae, max_abs, IQR
- **AIC proxy**: `n * log(max(SSE/n, 1e-20)) + 2 * k` where k = window_size
- **Composite score** (lower = better):
  ```
  0.20 * |mean_err| / max(mae, 1e-10)   # Bias ratio
  + 0.35 * rmse                           # Precision
  + 0.25 * mae                            # Average absolute error
  + 0.20 * max_abs / max(std_err, 1e-10)  # Tail severity
  ```

#### `run_multi_scenario(filepath, window_sizes, base_config, verbose) -> list[ScenarioResult]`
Default windows: `[12, 18, 24, 30, 36, 42, 48, 54, 60]`. Sort results by composite_score ascending (best first). Print ranking table when verbose.

### 8. `dashboard.py` — Chart Generation

Generate an interactive HTML dashboard using Plotly with 10 charts:

1. **LGD Term Structure by Vintage** — Line chart, up to 8 representative vintages for selected window
2. **Forecast vs Actual — Oldest Vintage** — Two-line overlay
3. **Average Forecast Error by TID** — Bar chart, red=positive/green=negative, horizontal line at 0
4. **Confidence Interval Bands** — Shaded area with mean line + actual scatter for oldest vintage
5. **Residual Distribution** — Histogram with normal PDF overlay, show JB test result in title
6. **Window Size Comparison** — 3 side-by-side bar subplots (RMSE, MAE, Bias), best window highlighted green
7. **LGD Term Structure Comparison** — All window sizes overlaid, best window gets thicker line
8. **Residual Heatmap** — Plotly Heatmap, vintages on y-axis, TID on x-axis, RdBu_r colorscale centered at 0
9. **Vintage Weighted LGD over Time** — Line + markers
10. **QQ-Plot** — Sample vs theoretical quantiles with 45-degree reference line

Include: summary box with recommended window + KPI metrics, scenario comparison HTML table with best row highlighted green, methodology notes footer.

### 9. Streamlit Dashboard (`app/streamlit_app.py`)

Build an interactive Streamlit app that replaces the static HTML dashboard. The sidebar should expose all configurable parameters:

**Sidebar Controls:**
- File uploader for the Excel workbook
- Multi-select for window sizes (checkboxes for 12, 18, 24, 30, 36, 42, 48, 54, 60)
- Dropdown: CI method (heuristic / standard_error / bootstrap)
- Slider: CI level (0.50 to 0.99)
- Number input: Discount rate (default 0.15)
- Checkbox: LGD cap at 1.0
- "Run Analysis" button

**Main Area:**
- Top: KPI cards (Recommended Window, RMSE, MAE, Bias, LGD at TID=0)
- Scenario comparison table (sortable, best row highlighted)
- Tabbed charts: all 10 charts from the static dashboard, rendered with `st.plotly_chart`
- Download buttons for: Multi-Scenario Excel, Single-Window Excel, HTML Dashboard
- Expander: Normality test details, residual statistics

**Caching:**
- Use `@st.cache_data` on `load_recovery_triangle` (keyed on file hash)
- Use `@st.cache_data` on `run_multi_scenario` (keyed on config params)

---

## Validated Reference Values

Use these for regression tests. All from the 60-month window, bootstrap CI, 50% level, 15% discount rate.

| Metric | Value |
|--------|-------|
| Number of cohorts | 82 |
| Number of vintages (60m window) | 23 |
| Number of non-NaN residuals | 276 |
| Forecast[0, 0] (oldest vintage, TID 0) | 0.225514586109806 |
| Actual[0, 0] | 0.236239450466784 |
| Residual mean | 0.006962 |
| Residual std | 0.093872 |
| JB statistic | (rejects normality) |
| Chi-Sq | (rejects normality) |

Multi-scenario ranking (composite score, lower = better):

| Rank | Window | RMSE | MAE | Bias | Score |
|------|--------|------|-----|------|-------|
| 1 | 18m | 0.0472 | 0.0317 | -0.0033 | 0.6465 |
| 2 | 60m | 0.0940 | 0.0634 | +0.0070 | 0.6680 |
| 3 | 24m | 0.1480 | 0.0793 | -0.0005 | 0.6882 |

---

## Dependencies

```
numpy>=1.24
pandas>=2.0
scipy>=1.10
openpyxl>=3.1
plotly>=5.18
streamlit>=1.30
```

---

## Development Commands

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run validation against spreadsheet
python scripts/validate_against_excel.py data/Munic_dashboard_LPU_1.xlsx

# Run CLI analysis
python scripts/run_analysis.py data/Munic_dashboard_LPU_1.xlsx --windows 12,18,24,30,36,42,48,54,60

# Launch Streamlit dashboard
streamlit run app/streamlit_app.py
```

---

## Implementation Rules

1. **DO NOT change the core math** — the formulas in core_engine.py, vintage.py (especially the observation mask), and backtest.py (especially the diagonal pattern) have been validated to machine precision against the spreadsheet. Refactor structure only.

2. **Preserve the vintage observation mask exactly** — the `offset = n_total - end_idx` then `adjusted_max_tid = master_tids[i] - offset` logic is the single most important correctness constraint. Getting this wrong produces subtly incorrect cumulative balances.

3. **Preserve the backtest diagonal pattern exactly** — `start_tid = 0 if i == 0 else (n_v - hindsight)` and `end_tid = n_v + 1`. Changing `end_tid` to `n_v` drops 22 residuals (254 instead of 276).

4. **Bootstrap seed must be 42** — for reproducibility.

5. **Type hints everywhere** — use Python 3.10+ syntax (`list[int]`, `dict[str, float]`, `X | None`).

6. **Docstrings on all public functions** — NumPy-style.

7. **Tests must validate against the reference values** above to catch any regression.

8. **Use `warnings.catch_warnings()` + `simplefilter('ignore', RuntimeWarning)`** around `np.nanmean` on the residual matrix (some TID columns are all-NaN for shorter windows).

---

## Build Order

1. Create project structure with `pyproject.toml` and dependencies
2. Implement `config.py` (simple dataclass, copy from source)
3. Implement `data_loader.py` + `test_data_loader.py`
4. Implement `core_engine.py` + `test_core_engine.py`
5. Implement `vintage.py` + `test_vintage.py`
6. Implement `statistics.py`
7. Implement `backtest.py` + `test_backtest.py`
8. Implement `scenario.py` + `test_scenario.py`
9. Implement `export.py`
10. Implement `dashboard.py` (static HTML)
11. Build Streamlit app (`app/`)
12. Write `scripts/run_analysis.py` CLI
13. Write `scripts/validate_against_excel.py`
14. Run full test suite and validate all 276 residuals match
15. Write README.md

---

## Key Domain Knowledge

- **IFRS 9**: International Financial Reporting Standard for Expected Credit Losses. LGD is one of three parameters (with PD and EAD) in the ECL formula.
- **Development Factors / Chain-Ladder**: Actuarial technique borrowed from insurance reserving. Estimates how losses develop over time by looking at historical patterns across cohorts.
- **Recovery Triangle**: Matrix where rows = default cohorts (monthly), columns = months-since-default. Cell = outstanding balance. Upper-right is NaN (cohort hasn't been observed that long yet).
- **Vintage Window**: A rolling window of N consecutive monthly cohorts used to calibrate the model. Each window position produces one LGD term structure.
- **Backtest**: Compare the LGD forecast from vintage V against the "actual" LGD observed when more data becomes available (from vintage V+1). The diagonal pattern tracks how forecasts held up over time.
- **Time in Default (TID)**: Months since the exposure entered default status. TID=0 means freshly defaulted.
- **EAD**: Exposure at Default — the outstanding balance when default occurs.
