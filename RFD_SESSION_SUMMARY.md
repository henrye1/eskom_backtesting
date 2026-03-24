# RFD -- LGD Development Factor Backtesting Framework — Session Summary
**Date**: 2026-03-24 (updated)
**Client**: Anchor Point Risk (Pty) Ltd
**Framework**: Generic LGD Development Factor Backtesting (portfolio-agnostic)
**Reference Entity**: Eskom (Non-Metro Municipalities, RR basis)
**Repository**: https://github.com/henrye1/eskom_backtesting

---

## 1. What Was Built

Refactored the validated monolithic script `lgd_development_factor_model.py` (1,178 lines) into a clean modular Python package implementing a generic IFRS 9 LGD development factor backtesting framework. The framework is portfolio-agnostic — it applies to any credit exposure that produces a recovery triangle. The application provides both a Streamlit dashboard and a **FastAPI + React** architecture with a TypeScript frontend.

### Project Structure
```
eskom_backtesting/
├── CLAUDE.md                          # Project spec (source of truth)
├── PROJECT_REQUIREMENTS.md            # Formal requirements document
├── LGD_Development_Factor_Model_Documentation.md  # Technical documentation
├── pyproject.toml / requirements.txt  # Package config
├── src/lgd_model/
│   ├── config.py          # ModelConfig dataclass
│   ├── data_loader.py     # load_recovery_triangle, extract_balance_matrix
│   ├── core_engine.py     # Recovery, cumbal, discount, LGD computations
│   ├── vintage.py         # VintageResult, VintageDetail, run_vintage_analysis
│   ├── statistics.py      # Normality tests (JB, Chi-Square)
│   ├── backtest.py        # BacktestResult, run_backtest, CI methods
│   ├── scenario.py        # ScenarioResult, run_scenario, run_multi_scenario
│   ├── export.py          # Excel export functions
│   └── dashboard.py       # Plotly HTML dashboard (10 charts)
├── api/                             # ** NEW — FastAPI backend **
│   ├── main.py            # App factory, CORS, health check, config defaults
│   ├── models.py          # Pydantic request/response schemas
│   ├── routers/
│   │   ├── upload.py      # File upload endpoint
│   │   ├── analysis.py    # Run analysis, return JSON results
│   │   └── download.py    # Excel/HTML download endpoints
│   └── services/
│       ├── file_store.py  # Temporary file management with expiry
│       ├── job_manager.py # Background job execution
│       ├── chart_builder.py # Server-side Plotly chart config
│       └── serializers.py # NumPy/pandas to JSON serialization
├── frontend/                        # ** NEW — React + TypeScript **
│   ├── package.json       # Vite + React 19 + TanStack + Plotly
│   ├── src/
│   │   ├── App.tsx        # Main app component
│   │   ├── main.tsx       # Entry point
│   │   ├── plotly.d.ts    # Plotly ESM/CJS type declaration
│   │   ├── api/           # Axios API client
│   │   ├── store/         # Zustand state management
│   │   ├── pages/
│   │   │   └── Dashboard.tsx  # Main dashboard page
│   │   └── components/
│   │       ├── cards/     # KPI metric cards
│   │       ├── charts/    # Plotly chart components
│   │       ├── common/    # Shared UI components
│   │       ├── layout/    # Page layout components
│   │       └── tables/    # Data table components
│   └── vite.config.ts
├── app/                             # Legacy Streamlit dashboard
│   ├── streamlit_app.py   # Single-page layout
│   └── components/
│       ├── sidebar.py           # Parameter controls + z-score override
│       ├── summary_cards.py     # KPI metric cards
│       ├── charts.py            # 10 chart renderers
│       ├── tables.py            # Scenario comparison table
│       ├── backtest_tables.py   # Full backtest summary + per-TID CI blocks
│       └── triangle_viewer.py   # Balance/Recovery/CumBal/Discount inspection
├── tests/                 # 49 tests, all passing
├── scripts/
│   ├── run_analysis.py              # CLI entry point
│   └── validate_against_excel.py    # Regression test vs spreadsheet
└── Munic_dashboard_LPU_1.xlsx       # Input workbook
```

### Test Status
- **49/49 tests pass**
- Forecast[0,0] matches Excel to 8.3e-17
- Actual[0,0] matches to 4.2e-16
- 276 residuals exact match

---

## 2. Architecture Migration: Streamlit to FastAPI + React

### 2.1 Why the Migration

The original Streamlit dashboard was functional but limited in interactivity, layout control, and deployment flexibility. The project was migrated to a decoupled architecture:

- **FastAPI backend** (port 8001) serves the Python computation engine as a REST API
- **React frontend** (Vite dev server, port 5173) provides a modern interactive dashboard
- The core `src/lgd_model/` package remains unchanged -- only the presentation layer was replaced

### 2.2 FastAPI Backend

The API layer (`api/`) wraps the existing lgd_model package:

- `POST /api/upload` -- Upload Excel workbook, receive session ID
- `POST /api/analysis/run` -- Run multi-scenario analysis with configurable parameters
- `GET /api/analysis/results/{session_id}` -- Retrieve cached results as JSON
- `GET /api/download/{type}/{session_id}` -- Download Excel or HTML exports
- `GET /api/health` -- Health check
- `GET /api/config/defaults` -- Default parameter values

CORS is configured for the Vite dev server origin (`http://localhost:5173`).

### 2.3 React Frontend

Built with modern React 19 + TypeScript stack:

- **Plotly.js** for interactive charts (via react-plotly.js wrapper)
- **TanStack Query** for server state management and API response caching
- **TanStack Table** for sortable/filterable data tables
- **Zustand** for client-side state (selected window, parameters)
- **Tailwind CSS** for styling
- **Vite** for fast HMR development and production builds

### 2.4 Port 8001 Workaround

Port 8000 has a persistent zombie socket issue on Windows (the port remains bound after process termination). The backend runs on port 8001 as a workaround. The frontend Vite proxy is configured accordingly.

---

## 3. Key Design Decisions

### 3.1 Window Alignment (Unchanged from Original)
All windows align to the **same 23 backtest dates** defined by the 60-month reference window. Smaller windows use fewer months of calibration data but forecast at the same dates. `max_tid` stays at 60 for all windows.

### 3.2 CI Formula -- Updated to Documentation Spec

The CI formula has been updated to match the formal documentation:

```
Upper = MIN(1, Mean + z * StdDev * SQRT(N_steps / N_vintages))
Lower = MAX(0, Mean - z * StdDev * SQRT(N_steps / N_vintages))
```

Where:
- **Mean** = cross-vintage nanmean of forecast LGD at each TID
- **StdDev** = cross-vintage nanstd (ddof=1) of forecast LGD at each TID
- **N_steps** = term-point index (increases across columns, widening bands)
- **N_vintages** = total vintage count (derived dynamically from data)
- **z** = `NORM.S.INV(ci_percentile)`, user-configurable (default 75th pctl, z = 0.6745)

The implementation in `backtest.py` uses a per-cell variant with `scale = z * StdDev[t] * sqrt(H_i / t)` where H_i is per-vintage hindsight. Both produce widening bands; the per-cell variant additionally varies by vintage row for the staircase pattern.

### 3.3 Per-TID Backtesting (Not Per-Vintage)

Backtesting is performed **column-wise** (per TID), not row-wise (per vintage). For each TID column:
- Actual values across vintages form the test series
- Mean = forecast center (Forecast[0, t] or cross-vintage nanmean)
- Upper/Lower CI bands apply per TID column
- Coverage % computed per TID

### 3.4 Backtest Diagonal Pattern (Unchanged -- Critical)
```python
for i in range(n_v - 1):
    hindsight = n_v - 1 - i
    source_idx = i + 1           # Actual from NEXT vintage
    start_tid = 0 if i == 0 else (n_v - hindsight)
    end_tid = n_v + 1            # NOT n_v -- gives 276 residuals
```

### 3.5 Vintage Observation Mask (Unchanged -- Critical)
```python
offset = n_total - end_idx
adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
if adjusted_max_tid < n_periods:
    window[i, max(0, adjusted_max_tid + 1):] = np.nan
```

### 3.6 Plotly ESM/CJS Interop Fix

The `plotly.js-dist-min` package ships as CommonJS while the frontend uses ES modules (`"type": "module"` in package.json). This was resolved with:
- A custom TypeScript declaration file (`plotly.d.ts`) for module typing
- Lazy loading of Plotly components to avoid SSR/CJS import errors
- Chart factory pattern for consistent chart instantiation

---

## 4. Streamlit Dashboard Layout

The Streamlit dashboard is the primary interactive UI at `streamlit run app/streamlit_app.py`. Single-page scrollable layout with:

1. **KPI Cards** -- Recommended Window, RMSE, MAE, Bias, LGD at TID=0
2. **Window Selector** -- one dropdown controls all sections
3. **Backtest Summary Tables** (matching Excel `LGD Backtest Summary`)
4. **Per-TID Backtest Blocks** -- data table + CI band chart per TID
5. **Scenario Comparison** -- all windows ranked by composite score
6. **Charts** -- 10 Plotly charts
7. **Triangle Inspection** -- per-vintage balance matrix, recovery, cumbal, discount, LGD
8. **Downloads**:
   - **Full Audit Trail Workbooks** -- per-window workbook replicating the reference spreadsheet structure (balance triangles, recovery vectors, cumbal, discount, LGD components per vintage). Single-window or all-windows ZIP
   - **Summary Exports** -- Multi-scenario Excel, single-window Excel, HTML dashboard

All exports regenerate automatically from fresh analysis results when new data is uploaded.

---

## 5. Known Issues / Open Items

### 5.1 Plotly Chart Rendering (Open)
The React Plotly chart components need a final fix for the lazy-loading wrapper. The ESM/CJS interop workaround is in place (`plotly.d.ts` + lazy import) but some chart types may not render correctly on initial load.

### 5.2 Chart Factory Double-Nested Default Export (Open)
The chart factory module has a double-nested default export pattern that needs cleanup. This causes issues when importing chart components in certain contexts.

### 5.3 Port 8000 Zombie Socket (Workaround)
On Windows 11, port 8000 occasionally retains a zombie socket after process termination. Using port 8001 as the backend port avoids this issue. The Vite proxy configuration points to 8001.

### 5.4 Data Version Mismatch (Documented)
The Excel workbook `Munic_dashboard_LPU_1.xlsx` as read by the code has specific reference values (Forecast[0,0] = 0.225515, etc.). The user's current working version may have different input data. Formulas are identical; values will match when the same workbook is used.

### 5.5 CI Formula Reconciliation (To Reconcile)
The documentation specifies `sqrt(N_steps / N_vintages)` while the implementation uses a per-cell `sqrt(H_i / t)` variant. Both produce widening bands but differ in how they vary across vintages. The production formula should be reconciled to match the documentation exactly.

---

## 6. Commands

```bash
# Install Python package
pip install -e ".[dev]"

# Run tests (49 tests)
python -m pytest tests/ -v

# Validate against Excel
python scripts/validate_against_excel.py Munic_dashboard_LPU_1.xlsx

# CLI analysis
python scripts/run_analysis.py Munic_dashboard_LPU_1.xlsx --windows 12,18,24,30,36,42,48,54,60

# Start FastAPI backend (port 8001 -- avoids Windows zombie socket on 8000)
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# Start React frontend (dev)
cd frontend && npm install && npm run dev

# Build React frontend (production)
cd frontend && npm run build

# Legacy Streamlit dashboard
streamlit run app/streamlit_app.py
```

---

## 7. Files Modified / Created (Chronological)

### Phase 1: Core Package (Session 1)

| File | Change |
|------|--------|
| `pyproject.toml` | Created -- package config |
| `src/lgd_model/config.py` | ModelConfig with ci_percentile, default 75th pctl |
| `src/lgd_model/data_loader.py` | load_recovery_triangle, extract_balance_matrix |
| `src/lgd_model/core_engine.py` | All chain-ladder math (unchanged from source) |
| `src/lgd_model/vintage.py` | VintageDetail added, run_single_vintage returns (lgd, detail) tuple |
| `src/lgd_model/statistics.py` | Normality tests |
| `src/lgd_model/backtest.py` | CI formula: SEM-scaled with sqrt(N_steps/N_vintages), coverage stats |
| `src/lgd_model/scenario.py` | max_tid=60 fixed, vintages aligned to reference window |
| `src/lgd_model/export.py` | Excel export (summary + full audit trail workbooks) |
| `src/lgd_model/dashboard.py` | HTML dashboard (10 charts) |

### Phase 2: Streamlit Dashboard (Session 1)

| File | Change |
|------|--------|
| `app/streamlit_app.py` | Single-page layout, z-override passthrough |
| `app/components/sidebar.py` | CI level slider, z-override input, percentile display |
| `app/components/backtest_tables.py` | Full backtest summary + per-TID CI blocks |
| `app/components/triangle_viewer.py` | Vintage triangle inspection |

### Phase 3: FastAPI + React Migration (Session 2+)

| File | Change |
|------|--------|
| `api/main.py` | FastAPI app with CORS, routers, SPA serving |
| `api/models.py` | Pydantic schemas for API request/response |
| `api/routers/upload.py` | File upload endpoint |
| `api/routers/analysis.py` | Analysis runner endpoint |
| `api/routers/download.py` | Excel/HTML download endpoint |
| `api/services/file_store.py` | Temporary file storage with expiry cleanup |
| `api/services/job_manager.py` | Background job execution |
| `api/services/chart_builder.py` | Server-side chart configuration |
| `api/services/serializers.py` | NumPy to JSON serialization |
| `frontend/package.json` | React 19 + Vite + TanStack + Plotly + Tailwind |
| `frontend/src/App.tsx` | Main app component |
| `frontend/src/plotly.d.ts` | Plotly ESM/CJS type declaration |
| `frontend/src/pages/Dashboard.tsx` | Dashboard page |
| `frontend/src/components/` | Cards, charts, tables, layout components |
| `frontend/src/api/` | Axios API client |
| `frontend/src/store/` | Zustand state management |

### Phase 4: Documentation (Session 3)

| File | Change |
|------|--------|
| `PROJECT_REQUIREMENTS.md` | Formal project requirements document |
| `RFD_SESSION_SUMMARY.md` | Updated with FastAPI + React migration status |

### Phase 5: Full Audit Trail Export + Documentation Refresh (Session 4)

| File | Change |
|------|--------|
| `src/lgd_model/export.py` | Added `export_full_audit_workbook()` and `export_all_audit_workbooks_zip()` — generates per-window workbooks replicating reference spreadsheet structure with all intermediate calculations per vintage |
| `app/streamlit_app.py` | Added full audit trail download section (single-window + all-windows ZIP) to Downloads area |
| `LGD_Development_Factor_Model_Documentation.md` | Genericised framework (removed portfolio-specific language), added audit trail export section |
| `PROJECT_REQUIREMENTS.md` | Genericised scope, added FR-48a/b/c for audit trail export, updated output formats and acceptance criteria |
| `RFD_SESSION_SUMMARY.md` | Updated with audit trail export feature and documentation refresh |

**Key design decision**: The documentation now positions this as a generic development factor framework applicable to any recovery triangle, not specific to any portfolio or segment. Eskom non-metro municipal data is the reference validation dataset.

---

## 8. Resume Checklist for Next Session

1. **Fix Plotly chart rendering** -- resolve lazy-loading wrapper for all 10 chart types in the React frontend
2. **Clean up chart factory** -- fix double-nested default export pattern in chart component modules
3. **Reconcile CI formula** -- align `backtest.py` implementation with documentation spec (`sqrt(N_steps/N_vintages)` vs `sqrt(H_i/t)`)
4. **Verify CI against user's current workbook** -- upload latest xlsx and compare upper/lower bounds
5. **Push to GitHub** -- ensure https://github.com/henrye1/eskom_backtesting is up to date
6. **Optional**: Production build and deployment configuration
7. **Optional**: Add export of per-TID backtest tables to Excel download
