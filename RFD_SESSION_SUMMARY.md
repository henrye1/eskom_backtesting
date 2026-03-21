# RFD — Eskom LGD Backtesting Project Session Summary
**Date**: 2026-03-20
**Client**: Anchor Point Risk (Pty) Ltd
**Entity**: Eskom — Non-Metro Municipal Debt

---

## 1. What Was Built

Refactored the validated monolithic script `lgd_development_factor_model.py` (1,178 lines) into a clean modular Python package with a Streamlit dashboard.

### Project Structure
```
eskom_backtesting/
├── CLAUDE.md                          # Project spec (source of truth)
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
├── app/
│   ├── streamlit_app.py   # Main Streamlit dashboard (single-page layout)
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

## 2. Key Design Decisions Made During Session

### 2.1 Window Alignment (Fixed)
**Problem**: Originally, each window size (12, 18, 24, ..., 60) produced its own number of vintages and its own independent backtest.
**Fix**: All windows now align to the **same 23 backtest dates** defined by the 60-month reference window. Smaller windows use fewer months of calibration data but forecast at the same dates. `max_tid` stays at 60 for all windows.
**File**: `src/lgd_model/scenario.py` lines 118-145

### 2.2 Confidence Interval Formula
**Final formula** (matching Excel cell `AA82`):
```
Upper[i, t] = MIN(1, Forecast[0, t] + z × Std[t] × √(step / total_steps))
Lower[i, t] = MAX(0, Forecast[0, t] - z × Std[t] × √(step / total_steps))
```
Where:
- `Forecast[0, t]` = first vintage's forecast at TID t (the reference forecast)
- `z` = NORM.S.INV(1 - α/2), user-selectable, default 90% CI
- `Std[t]` = cross-vintage std of forecast at TID t (ddof=1)
- `step` = position within the TID column (1, 2, 3, ... increasing down)
- `total_steps` = count of all values in that TID column = min(t, n_v - 1)
- Bounds WIDEN going down each column (more steps from forecast)
- Higher TIDs have more vintages in their column → different scaling

**Mean in CI blocks** = `Forecast[0, t]` (first row of forecast table), NOT cross-vintage nanmean.

**CI diagonal mask**: `start_tid = i + 1` for ALL vintages (no i=0 special case), unlike the Actual mask which has TID 0 for vintage 0.

**File**: `src/lgd_model/backtest.py` — `_compute_confidence_intervals()`, method `normal_sem`

### 2.3 Mean / Std Rows
- `Mean[t]` = `nanmean(forecast[:, t])` across all 23 vintages — matches Excel row 52
- `Std[t]` = `nanstd(forecast[:, t], ddof=1)` — matches Excel row 53
- These are the cross-vintage statistics used for CI computation

### 2.4 Backtest Diagonal Pattern (Unchanged from Source)
```python
for i in range(n_v - 1):
    hindsight = n_v - 1 - i
    source_idx = i + 1           # Actual from NEXT vintage
    start_tid = 0 if i == 0 else (n_v - hindsight)
    end_tid = n_v + 1            # NOT n_v — gives 276 residuals
```
- Actual[v0] = Forecast[v1] (verified to machine precision)
- 276 non-NaN residuals

### 2.5 Per-TID Backtesting (Not Per-Vintage)
The backtest analysis is done **column-wise** (per TID), not row-wise (per vintage). For each TID column, the forecast values across vintages approximate a stationary series. The per-TID blocks transpose column t from each matrix:
- Actual = `actual_matrix[:, t]` across vintages
- Mean = `Forecast[0, t]` (constant horizontal line)
- Upper/Lower = from the CI formula above (constant per vintage at this TID when using SEM, or varying with sqrt scaling)

### 2.6 Vintage Observation Mask (Unchanged — Critical)
```python
offset = n_total - end_idx
adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
if adjusted_max_tid < n_periods:
    window[i, max(0, adjusted_max_tid + 1):] = np.nan
```
This restricts each cohort to data observable at the vintage date.

---

## 3. Streamlit Dashboard Layout

Single-page scrollable layout (no tabs):

1. **KPI Cards** — Recommended Window, RMSE, MAE, Bias, LGD at TID=0
2. **Window Selector** — one dropdown controls all sections
3. **Backtest Summary Tables** (matching Excel `LGD Backtest Summary`):
   - FORECAST LGD BY VINTAGE
   - ACTUAL LGD BY VINTAGE (DIAGONAL)
   - Mean / Std Deviation
   - MEAN LGD BY VINTAGE (actual diagonal mask)
   - UPPER BOUND (CI diagonal mask, step/total scaling)
   - LOWER BOUND (CI diagonal mask)
   - DIFFERENCE (ACTUAL - FORECAST)
   - Normality Tests (JB, Chi-Square)
4. **Per-TID Backtest Blocks** — for each TID column:
   - Data table (Actual, Mean, Upper, Lower across vintages)
   - Chart with CI band, mean line, green/red markers, coverage %
   - Charts rendered 2 per row, compact (280px)
5. **Scenario Comparison** — all windows ranked by composite score
6. **Charts** — 10 Plotly charts (term structure, forecast vs actual, error by TID, etc.)
7. **Triangle Inspection** — per-vintage balance matrix, recovery, cumbal, discount, LGD
8. **Downloads** — Multi-scenario Excel, single-window Excel, HTML dashboard

### Sidebar Controls
- File uploader
- Window size checkboxes (12-60m)
- CI Method: `normal_sem` (default), standard_error, bootstrap, heuristic
- CI Level slider (0.10 - 0.99, default 0.90)
- z-score override input (auto-calculated, editable)
- Discount rate (default 0.15)
- LGD cap toggle
- Store triangle details toggle

---

## 4. Known Issues / Open Items

### 4.1 Data Version Mismatch
The Excel workbook `Munic_dashboard_LPU_1.xlsx` as read by the code has:
- 82 cohorts, 23 vintages (60m window)
- z=0.6745 in Excel header (50% CI)
- Forecast[0,0] = 0.225515, TID 23 upper starts at 54.5%

The user's current working version appears to have different data (upper at TID 23 starts at 57.5%, mean at ~52%). The **formulas are identical** but input data differs. When the user uploads their current workbook, values should match.

### 4.2 CI Level Default
- Code default: 90% CI (z ≈ 1.6449)
- Excel workbook header: "75th pctl -- SEM CI (z=0.6745, n=23)" = 50% CI
- User preference: 90% CI with z=1.64
- **User should set z-override to match their spreadsheet** when comparing

### 4.3 Not Yet Implemented
- README.md (user documentation)
- `notebooks/exploration.ipynb` placeholder
- Git repository initialization
- The `data/` directory convention (workbook currently in project root)

---

## 5. Commands

```bash
# Install
pip install -e ".[dev]"

# Run tests (49 tests)
python -m pytest tests/ -v

# Validate against Excel
python scripts/validate_against_excel.py Munic_dashboard_LPU_1.xlsx

# CLI analysis
python scripts/run_analysis.py Munic_dashboard_LPU_1.xlsx --windows 12,18,24,30,36,42,48,54,60

# Launch Streamlit dashboard
streamlit run app/streamlit_app.py
```

---

## 6. Files Modified Today (in order)

| File | Change |
|------|--------|
| `pyproject.toml` | Created — package config |
| `src/lgd_model/config.py` | ModelConfig with ci_z_override, default 90% CI |
| `src/lgd_model/data_loader.py` | load_recovery_triangle, extract_balance_matrix |
| `src/lgd_model/core_engine.py` | All chain-ladder math (unchanged from source) |
| `src/lgd_model/vintage.py` | VintageDetail added, run_single_vintage returns (lgd, detail) tuple |
| `src/lgd_model/statistics.py` | Normality tests |
| `src/lgd_model/backtest.py` | CI formula: Forecast[0,t] + z*Std*sqrt(step/total), coverage stats |
| `src/lgd_model/scenario.py` | max_tid=60 fixed, vintages aligned to reference window |
| `src/lgd_model/export.py` | Excel export |
| `src/lgd_model/dashboard.py` | HTML dashboard (10 charts) |
| `app/streamlit_app.py` | Single-page layout, z-override passthrough |
| `app/components/sidebar.py` | CI level slider, z-override input, percentile display |
| `app/components/backtest_tables.py` | Full backtest summary + per-TID CI blocks |
| `app/components/triangle_viewer.py` | Vintage triangle inspection |
| `tests/conftest.py` | Default config: normal_sem, 90% CI |
| `tests/test_backtest.py` | 7 tests |
| `tests/test_vintage.py` | 8 tests (including detail storage, hindsight) |
| `tests/test_scenario.py` | 6 tests (including aligned vintages) |
| `tests/test_validation.py` | 14 tests (machine precision checks) |

---

## 7. Resume Checklist for Next Session

1. **Verify CI against user's current workbook** — upload the latest xlsx and compare upper/lower bounds at TID 23
2. **Clarify CI level** — user wants 90% (z=1.64) but Excel has 50% (z=0.6745). Need to confirm which is the target for production
3. **Lower bound formula** — same as upper but subtracted: `Forecast[0,t] - z*Std*sqrt(step/total)`. Verify against Excel lower bound section
4. **Consider** whether the Mean/Std rows should use Forecast[0,:] or nanmean — currently Mean row = nanmean (matches Excel row 52), but CI blocks use Forecast[0,:] as the center
5. **Optional**: implement git init, README, data/ directory convention
6. **Optional**: add export of per-TID backtest tables to Excel
