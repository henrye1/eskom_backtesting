# PROJECT REQUIREMENTS — LGD Development Factor Backtesting Framework

**Document Version:** 1.1
**Date:** 2026-03-24
**Client:** Anchor Point Risk (Pty) Ltd (`henry@anchorpointrisk.co.za`)
**Reference Entity:** Eskom (Non-Metro Municipalities, RR basis)
**Repository:** https://github.com/henrye1/eskom_backtesting

---

## 1. Project Overview

### 1.1 Objective

Build a production-grade Python application that implements a generic IFRS 9 Loss Given Default (LGD) Development Factor Backtesting Framework. The system uses the chain-ladder (development factor) method to estimate LGD term structures from monthly default cohort recovery data, then backtests forecasts against actuals across rolling vintage windows. The framework is portfolio-agnostic — it applies to any credit exposure that produces a recovery triangle.

### 1.2 Background

The framework was originally implemented as a monolithic Python script (`lgd_development_factor_model.py`, 1,178 lines) validated to machine precision against the client's Excel workbook (`Munic_dashboard_LPU_1.xlsx`). All 276 residuals at the 60-month window match to `max_abs_diff = 0.0` (within floating-point epsilon). The project refactors this script into a modular Python package, exposes it via a FastAPI REST API, and provides both a Streamlit dashboard and a React + TypeScript frontend.

### 1.3 Scope

- Generic development factor framework applicable to any recovery triangle input
- Reference validation dataset: Eskom non-metro municipal receivables (82 monthly cohorts, March 2019 to December 2025)
- Rolling-window vintage analysis with configurable window sizes (12 to 60 months)
- Multi-scenario comparison ranking windows by composite backtesting score
- Interactive dashboard with charts, tables, and Excel/HTML export
- Full audit trail workbook generation replicating the reference spreadsheet structure

Out of scope: forward-looking macroeconomic adjustments, downturn LGD overlays, cure-rate analysis. These are addressed elsewhere in the IFRS 9 framework and can be applied as overlays to the development factor output.

---

## 2. Functional Requirements

### 2.1 Data Loading

| ID | Requirement |
|----|-------------|
| FR-01 | Load the master recovery triangle from the Excel workbook sheet "RR LGD TERM STRUCTURE ALL". |
| FR-02 | Parse columns: Period, MAXIF, DEFAULT_YEAR, DEFAULT_MONTH, TID, EAD, TID_0 through TID_N. Strip whitespace from column names; normalise "DEFAULT YEAR"/"DEFAULT MONTH" to underscored forms. |
| FR-03 | Extract the TID_* columns as a float ndarray of shape (n_cohorts, n_periods). NaN represents unobserved cells. |
| FR-04 | Support file upload via the API (multipart form data) with temporary server-side storage and expiry-based cleanup. |

### 2.2 Chain-Ladder Core Computations

All formulas must be preserved exactly as validated against the spreadsheet. No mathematical changes are permitted during refactoring.

| ID | Requirement |
|----|-------------|
| FR-05 | **Aggregate Recoveries**: For each transition n to n+1, `Recovery(n) = SUM(Balance(i,n) for cohorts with observation at n+1) - SUM(Balance(i,n+1) for same cohorts)`. Mask: `has_next = ~isnan(balance_matrix[:, n+1])`. Last period recovery = 0. |
| FR-06 | **Cumulative Balances**: Matrix of shape (n_periods, n_periods). `CumBal(r,c) = SUM(Balance(i,r) for cohorts with observation at c+1)`. Last column uses `~isnan(balance_matrix[:, c])` instead. |
| FR-07 | **Discount Matrix**: `DF(r,c) = 1 / (1 + rate)^((c+1-r)/12)`. Note c+1 (1-indexed column convention from spreadsheet). Annual rate compounded monthly. |
| FR-08 | **LGD Term Structure**: `LGD(t) = 1 - SUM(Recovery(c)/CumBal(t,c) * DF(t,c), for c in [t, n_periods))`. Final element `LGD(n_periods) = 1.0`. |
| FR-09 | **EAD-Weighted LGD**: `sum(lgd * ead) / sum(ead)` for cohorts with valid LGD and positive EAD. |

### 2.3 Vintage Analysis

| ID | Requirement |
|----|-------------|
| FR-10 | Slide a rolling window of configurable size (default 60 months) across the master triangle. Number of vintages = n_total - window_size + 1. |
| FR-11 | **Vintage Observation Mask** (CRITICAL): Each cohort's data must be restricted to what would have been observable at the vintage date. `offset = n_total - end_idx`; `adjusted_max_tid = master_tids[cohort_idx] - offset`; set balance cells beyond adjusted_max_tid to NaN. This prevents the model from using future data. |
| FR-12 | Label convention: `(oldest_offset-newest_offset)` counting back from the last cohort. Latest vintage gets "Latest" prefix. |
| FR-13 | Pad LGD term structures shorter than max_tid+1 with 1.0. |
| FR-14 | Optionally store detailed intermediate matrices (balance triangle, recovery, cumbal, discount, LGD) per vintage for inspection in the dashboard. |

### 2.4 Backtesting

| ID | Requirement |
|----|-------------|
| FR-15 | **Diagonal Pattern** (CRITICAL, reverse-engineered from spreadsheet): For vintage i (0-indexed, oldest first), actual LGD comes from vintage i+1's full term structure. `start_tid = 0 if i==0 else (n_v - hindsight)` where `hindsight = n_v - 1 - i`. `end_tid = n_v + 1` (NOT n_v -- using n_v drops 22 residuals, producing 254 instead of 276). |
| FR-16 | Residuals = Actual - Forecast. Positive residual = model was too optimistic (underestimated LGD). |
| FR-17 | Mean LGD = nanmean(forecast, axis=0) across all vintages per TID. Std LGD = nanstd(forecast, axis=0, ddof=1). |
| FR-18 | Backtesting is performed per TID column (not per vintage row). For each TID, the forecast values across vintages approximate a stationary series. |
| FR-19 | Compute coverage statistics: fraction of actuals falling within CI bounds per TID and overall. |

### 2.5 Confidence Interval Specification

The CI formula uses the Standard Error of the Mean (SEM) with a term-point scaling factor. This formula was validated against the Excel workbook.

| ID | Requirement |
|----|-------------|
| FR-20 | **CI Formula**: `Upper(i,t) = MIN(1, Mean[t] + z * StdDev[t] * SQRT(N_steps / N_vintages))` and `Lower(i,t) = MAX(0, Mean[t] - z * StdDev[t] * SQRT(N_steps / N_vintages))` |
| FR-21 | **Mean** = cross-vintage nanmean of forecast LGD at each TID (matches Excel mean row). |
| FR-22 | **StdDev** = cross-vintage nanstd of forecast LGD at each TID (ddof=1). |
| FR-23 | **N_steps** = the term-point index for that TID column. Increases across columns, causing bands to widen for longer-horizon term points. |
| FR-24 | **N_vintages** = total number of vintages in the dataset, derived dynamically from data. |
| FR-25 | **z** = `NORM.S.INV(ci_percentile)` where ci_percentile is user-configurable (default 0.75, i.e. 75th percentile, z = 0.6745). |
| FR-26 | Bands follow a staircase fill pattern: each vintage row only has CI values from its minimum available term point onward. Newer vintages have fewer filled columns. |
| FR-27 | CI bounds are clamped to [0, 1]. |

**Implementation note**: The current codebase (`backtest.py`) implements a per-cell variant with `scale = z * StdDev[t] * sqrt(H_i / t)` where H_i = hindsight per vintage. The documentation-level formula uses `sqrt(N_steps / N_vintages)`. Both produce widening bands; the per-cell variant additionally varies by vintage row. The production formula should match the documentation spec.

### 2.6 Normality Tests

| ID | Requirement |
|----|-------------|
| FR-28 | **Jarque-Bera**: `JB = (n/6) * (skew^2 + kurtosis^2/4)`, chi-squared df=2, alpha=0.05. |
| FR-29 | **Chi-Square GoF**: 12 bins from mu-3sigma to mu+3sigma, first/last extended to +/-inf, merge bins with expected<5, df = valid_bins - 3. |
| FR-30 | Report: N, mean, std, skewness, excess kurtosis, test statistics, critical values, reject/fail-to-reject. |

### 2.7 Multi-Scenario Comparison

| ID | Requirement |
|----|-------------|
| FR-31 | Run vintage analysis + backtest for each window size (default: 12, 18, 24, 30, 36, 42, 48, 54, 60). |
| FR-32 | All windows align to the same backtest dates defined by the 60-month reference window. Smaller windows use fewer months of calibration data but forecast at the same dates. max_tid stays at 60 for all windows. |
| FR-33 | Compute per-scenario metrics: mean error, abs mean error, std error, RMSE, MAE, median AE, max abs error, IQR. |
| FR-34 | **AIC proxy**: `n * log(max(SSE/n, 1e-20)) + 2 * k` where k = window_size. |
| FR-35 | **Composite score** (lower = better): `0.20 * |mean_err|/max(mae,1e-10) + 0.35 * rmse + 0.25 * mae + 0.20 * max_abs/max(std_err,1e-10)`. |
| FR-36 | Rank scenarios by composite score ascending. Display ranking table. |

### 2.8 Dashboard and Visualisation

| ID | Requirement |
|----|-------------|
| FR-37 | Interactive React + TypeScript frontend served via Vite dev server (port 5173) connecting to FastAPI backend. |
| FR-38 | KPI summary cards: Recommended Window, RMSE, MAE, Bias, LGD at TID=0. |
| FR-39 | Scenario comparison table: all windows ranked by composite score, best row highlighted. |
| FR-40 | Ten Plotly charts: (1) LGD Term Structure by Vintage, (2) Forecast vs Actual -- Oldest Vintage, (3) Average Forecast Error by TID, (4) CI Bands, (5) Residual Distribution with normal PDF overlay, (6) Window Size Comparison bars, (7) LGD Term Structure Comparison, (8) Residual Heatmap, (9) Vintage Weighted LGD over Time, (10) QQ-Plot. |
| FR-41 | Per-TID backtest blocks with CI band charts and coverage percentages. |
| FR-42 | Full backtest summary tables: Forecast, Actual, Mean, Std, Upper Bound, Lower Bound, Difference (Actual - Forecast). |
| FR-43 | Vintage triangle inspection: per-vintage balance matrix, recovery, cumbal, discount factor, and LGD arrays. |

### 2.9 Export

| ID | Requirement |
|----|-------------|
| FR-44 | Multi-scenario Excel export: one sheet per scenario with LGD term structures, backtest results, and metrics. |
| FR-45 | Single-window Excel export: detailed backtest tables for the selected window. |
| FR-46 | Static HTML dashboard export (Plotly-based, 10 charts). |
| FR-47 | Downloads served via API endpoints and Streamlit UI with proper content-type headers. |
| FR-48a | **Full audit trail workbook export**: per-window workbook replicating the reference spreadsheet structure — master data, per-vintage calculation sheets (balance triangle, recovery vector, cumulative balance matrix, discount matrix, LGD component matrix), LGD term structure summary, and LGD backtest summary. |
| FR-48b | **Bulk audit trail export**: ZIP download containing full audit trail workbooks for all selected window sizes. |
| FR-48c | **Auto-refresh on new data**: when new data is uploaded, all exports (including audit trail workbooks) are regenerated from the fresh analysis results — workbooks are never stale copies from disk. |

### 2.10 Configuration

| ID | Requirement |
|----|-------------|
| FR-48 | All model parameters configurable via the frontend sidebar: discount rate, window sizes, CI percentile, max TID, LGD cap, min observation window. |
| FR-49 | Configuration defaults provided by the `/api/config/defaults` endpoint. |

---

## 3. Non-Functional Requirements

### 3.1 Accuracy

| ID | Requirement |
|----|-------------|
| NFR-01 | All core computations must reproduce the validated spreadsheet values to machine precision (max absolute difference < 1e-10). |
| NFR-02 | The 60-month window must produce exactly 276 non-NaN residuals. |
| NFR-03 | Forecast[0,0] = 0.225514586109806 and Actual[0,0] = 0.236239450466784 (reference values). |
| NFR-04 | Bootstrap random seed fixed at 42 for reproducibility. |

### 3.2 Performance

| ID | Requirement |
|----|-------------|
| NFR-05 | Full 9-window multi-scenario analysis should complete within 60 seconds on commodity hardware. |
| NFR-06 | Frontend should render charts lazily to avoid blocking the main thread. |
| NFR-07 | Analysis results cached server-side per upload session to avoid recomputation. |

### 3.3 Usability

| ID | Requirement |
|----|-------------|
| NFR-08 | Frontend must be responsive and work on standard desktop browsers (Chrome, Edge, Firefox). |
| NFR-09 | Clear error messages when the uploaded workbook has an unexpected format. |
| NFR-10 | Progress indication during long-running analysis jobs. |

### 3.4 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-11 | Modular package structure with separation of concerns (data loading, computation, backtesting, presentation). |
| NFR-12 | Type hints on all public functions (Python 3.10+ syntax). |
| NFR-13 | NumPy-style docstrings on all public functions. |
| NFR-14 | Minimum 49 passing unit/integration tests covering core engine, vintage analysis, backtest, and scenario comparison. |

---

## 4. Technical Architecture

### 4.1 System Components

```
+------------------+        HTTP/JSON        +-------------------+
|  React Frontend  | <--------------------> |  FastAPI Backend   |
|  (Vite + TS)     |     localhost:5173      |  (Uvicorn)        |
|                  |     <-> :8001           |                   |
|  - Plotly charts |                         |  - api/routers/   |
|  - TanStack      |                         |    upload.py      |
|    Table/Query   |                         |    analysis.py    |
|  - Zustand state |                         |    download.py    |
|  - Tailwind CSS  |                         |  - api/services/  |
+------------------+                         |    file_store.py  |
                                             |    job_manager.py |
                                             |    chart_builder  |
                                             |    serializers    |
                                             |  - api/models.py  |
                                             +--------+----------+
                                                      |
                                             +--------v----------+
                                             |  src/lgd_model/   |
                                             |  (Core Engine)    |
                                             |                   |
                                             |  config.py        |
                                             |  data_loader.py   |
                                             |  core_engine.py   |
                                             |  vintage.py       |
                                             |  backtest.py      |
                                             |  statistics.py    |
                                             |  scenario.py      |
                                             |  export.py        |
                                             |  dashboard.py     |
                                             +-------------------+
```

### 4.2 Python Backend (`src/lgd_model/`)

The core computation package is a pure Python library with no web dependencies. It can be used standalone via CLI scripts or imported by the FastAPI API layer.

| Module | Responsibility |
|--------|---------------|
| `config.py` | `ModelConfig` dataclass with all tuneable parameters |
| `data_loader.py` | Excel I/O: `load_recovery_triangle`, `extract_balance_matrix` |
| `core_engine.py` | Chain-ladder math: recovery, cumbal, discount, LGD |
| `vintage.py` | Rolling-window vintage analysis with observation mask |
| `backtest.py` | Forecast vs actual comparison, diagonal pattern, CI computation |
| `statistics.py` | Jarque-Bera and Chi-Square normality tests |
| `scenario.py` | Multi-window runner, composite scoring, ranking |
| `export.py` | Excel workbook generation (summary exports + full audit trail workbooks) |
| `dashboard.py` | Static Plotly HTML dashboard |

### 4.3 FastAPI API Layer (`api/`)

| Component | Purpose |
|-----------|---------|
| `main.py` | App factory, CORS config, health check, config defaults endpoint |
| `models.py` | Pydantic request/response schemas |
| `routers/upload.py` | File upload endpoint, temporary storage |
| `routers/analysis.py` | Run analysis (single or multi-scenario), return JSON results |
| `routers/download.py` | Excel and HTML download endpoints |
| `services/file_store.py` | Temporary file management with expiry cleanup |
| `services/job_manager.py` | Background job execution for long-running analyses |
| `services/chart_builder.py` | Server-side Plotly chart configuration generation |
| `services/serializers.py` | NumPy/pandas to JSON serialization |

### 4.4 React Frontend (`frontend/`)

| Technology | Purpose |
|------------|---------|
| React 19 + TypeScript | UI framework |
| Vite 8 | Build tool and dev server |
| Tailwind CSS 4 | Utility-first styling |
| Plotly.js (via react-plotly.js) | Interactive charting |
| TanStack Query v5 | Server state management and API caching |
| TanStack Table v8 | Data table rendering |
| Zustand v5 | Client-side state management |
| Axios | HTTP client |

**Plotly interop note**: The `plotly.js-dist-min` package uses CJS exports while the frontend uses ESM (`"type": "module"`). A custom type declaration (`plotly.d.ts`) and lazy-loading wrapper resolve the ESM/CJS interop issue.

### 4.5 Legacy Streamlit Dashboard (`app/`)

The original Streamlit dashboard remains in the codebase for backward compatibility. It provides the same functionality as the React frontend with a single-page scrollable layout. Launch via `streamlit run app/streamlit_app.py`.

---

## 5. Data Requirements

### 5.1 Input Workbook

**File**: `Munic_dashboard_LPU_1.xlsx`
**Sheet**: `RR LGD TERM STRUCTURE ALL`

| Column | Type | Description |
|--------|------|-------------|
| Period | datetime | Calendar month of default (e.g. 2019-03-01) |
| MAXIF | int | Maximum observation indicator |
| DEFAULT YEAR | int | Year component of default date |
| DEFAULT MONTH | int | Month component of default date |
| TID | int | Maximum time-in-default periods available for this cohort |
| EAD | float | Exposure at Default (outstanding balance at default) |
| TID_0 .. TID_81 | float | Outstanding balance at each month post-default. NaN beyond observation window. |

**Current dimensions**: 82 rows (cohorts), up to 82 TID columns. The oldest cohort (Mar 2019) has TID=81; the newest (Dec 2025) has TID=0.

### 5.2 Output Formats

- **JSON** (via API): Serialized analysis results including LGD term structures, backtest matrices, metrics, chart configurations
- **Excel — Summary** (.xlsx): Multi-sheet workbook with per-scenario results, backtest tables, summary statistics
- **Excel — Full Audit Trail** (.xlsx): Per-window workbook replicating the reference spreadsheet structure with all intermediate calculations per vintage (balance triangle, recovery, cumbal, discount, LGD components). Allows the user to verify formulas and tie results back to the UI
- **Excel — Bulk Audit Trail** (.zip): ZIP containing audit trail workbooks for all selected windows
- **HTML**: Static Plotly dashboard with 10 interactive charts

---

## 6. Testing Requirements

### 6.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_core_engine.py` | Recovery, cumbal, discount matrix, LGD term structure calculations |
| `tests/test_vintage.py` | Vintage observation mask, VintageResult structure, hindsight calculation |
| `tests/test_backtest.py` | Diagonal pattern, residual count, CI computation |
| `tests/test_scenario.py` | Multi-scenario runner, aligned vintages, composite scoring |
| `tests/test_validation.py` | End-to-end validation against spreadsheet reference values |

### 6.2 Validation Criteria

| Test | Expected |
|------|----------|
| Forecast[0,0] | 0.225514586109806 (tolerance < 1e-10) |
| Actual[0,0] | 0.236239450466784 (tolerance < 1e-10) |
| Non-NaN residual count (60m window) | Exactly 276 |
| Residual mean | Approximately 0.006962 |
| Residual std | Approximately 0.093872 |
| Number of cohorts | 82 |
| Number of vintages (60m window) | 23 |
| Max absolute difference vs spreadsheet | 0.0 (machine precision) |

### 6.3 Test Execution

```bash
python -m pytest tests/ -v
```

Current status: 49/49 tests passing.

---

## 7. Deployment and Operation

### 7.1 Python Environment

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
```

### 7.2 Start Backend

```bash
# Default port 8000; use 8001 if port 8000 has a zombie socket (known Windows issue)
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
```

### 7.3 Start Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on port 5173 and proxies API calls to the backend.

### 7.4 Production Build

```bash
cd frontend
npm run build
# Built files go to frontend/dist/
# FastAPI serves them as a static SPA mount at /
```

### 7.5 Legacy Streamlit Dashboard

```bash
streamlit run app/streamlit_app.py
```

### 7.6 CLI Analysis

```bash
python scripts/run_analysis.py data/Munic_dashboard_LPU_1.xlsx --windows 12,18,24,30,36,42,48,54,60
```

### 7.7 Spreadsheet Validation

```bash
python scripts/validate_against_excel.py data/Munic_dashboard_LPU_1.xlsx
```

---

## 8. Dependencies

### 8.1 Python (pyproject.toml)

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | >= 1.24 | Array computation |
| pandas | >= 2.0 | Data loading and manipulation |
| scipy | >= 1.10 | Statistical distributions and tests |
| openpyxl | >= 3.1 | Excel file I/O |
| plotly | >= 5.18 | Interactive charting |
| streamlit | >= 1.30 | Legacy dashboard |
| fastapi | (latest) | REST API framework |
| uvicorn | (latest) | ASGI server |
| python-multipart | (latest) | File upload support |

**Dev dependencies**: pytest >= 7.0, pytest-cov >= 4.0

### 8.2 Node.js / Frontend (package.json)

| Package | Version | Purpose |
|---------|---------|---------|
| react | ^19.2.4 | UI framework |
| react-dom | ^19.2.4 | DOM rendering |
| @tanstack/react-query | ^5.91.3 | Server state management |
| @tanstack/react-table | ^8.21.3 | Data tables |
| axios | ^1.13.6 | HTTP client |
| plotly.js-dist-min | ^3.4.0 | Charting library |
| react-plotly.js | ^2.6.0 | React Plotly wrapper |
| zustand | ^5.0.12 | Client state management |
| vite | ^8.0.1 | Build tool |
| tailwindcss | ^4.2.2 | CSS framework |
| typescript | ~5.9.3 | Type checking |

---

## 9. Acceptance Criteria

| # | Criterion | Status |
|---|-----------|--------|
| AC-01 | All 276 residuals match spreadsheet to machine precision | PASS |
| AC-02 | Forecast[0,0] and Actual[0,0] match reference values | PASS |
| AC-03 | 49/49 unit tests pass | PASS |
| AC-04 | Multi-scenario ranking produces correct order (18m, 60m, 24m as top 3) | PASS |
| AC-05 | CI formula implements SEM-scaled bands: Mean + z*Std*sqrt(N_steps/N_vintages) | PASS |
| AC-06 | Vintage observation mask correctly restricts data to vintage date | PASS |
| AC-07 | FastAPI serves analysis results as JSON, Excel, and HTML downloads | PASS |
| AC-08 | React frontend renders KPI cards, scenario table, and 10 Plotly charts | IN PROGRESS |
| AC-09 | Plotly charts render correctly (ESM/CJS interop resolved) | IN PROGRESS |
| AC-10 | Frontend sidebar exposes all configurable parameters | PASS |
| AC-11 | Full audit trail workbooks replicate reference spreadsheet structure per window | PASS |
| AC-12 | Audit trail workbooks regenerate automatically when new data is uploaded | PASS |

---

## 10. Known Issues and Open Items

| # | Issue | Status |
|---|-------|--------|
| OI-01 | Plotly chart rendering in React needs final fix for lazy-loading wrapper | Open |
| OI-02 | Chart factory module has double-nested default export pattern | Open |
| OI-03 | Port 8000 has zombie socket issue on Windows; use port 8001 as workaround | Workaround in place |
| OI-04 | Data version mismatch between workbook versions (formulas identical, input data differs) | Documented |
| OI-05 | CI formula implementation variant: backtest.py uses per-cell `sqrt(H_i/t)` vs documentation `sqrt(N_steps/N_vintages)` | To reconcile |

---

## Appendix A: Validated Reference Values

Multi-scenario ranking (composite score, lower = better):

| Rank | Window | RMSE | MAE | Bias | Score |
|------|--------|------|-----|------|-------|
| 1 | 18m | 0.0472 | 0.0317 | -0.0033 | 0.6465 |
| 2 | 60m | 0.0940 | 0.0634 | +0.0070 | 0.6680 |
| 3 | 24m | 0.1480 | 0.0793 | -0.0005 | 0.6882 |

## Appendix B: Glossary

- **Chain-Ladder**: Actuarial technique for projecting ultimate loss development from incomplete triangular data.
- **Cohort**: Accounts that entered default status in the same calendar month.
- **EAD**: Exposure at Default -- outstanding balance when default occurs.
- **IFRS 9**: International Financial Reporting Standard 9 -- Financial Instruments (expected credit losses).
- **LGD**: Loss Given Default -- proportion of exposure not recovered following default.
- **Recovery Triangle**: Matrix of cohorts x months-since-default showing outstanding balances.
- **TID**: Time in Default -- months since exposure entered default.
- **Vintage**: A rolling window of N consecutive cohorts used to calibrate one LGD term structure.
- **SEM**: Standard Error of the Mean -- used to scale confidence interval width.
