"""Excel export functions for LGD model results.

Includes three export levels:
1. Summary exports (export_results_to_excel, export_multi_scenario_excel)
2. Full audit trail workbooks (export_full_audit_workbook) — replicates
   the reference workbook structure with all intermediate calculations
   per vintage so the user can verify formulas and tie back to the UI.
"""

import io
import zipfile

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from lgd_model.backtest import BacktestResult
from lgd_model.config import ModelConfig
from lgd_model.core_engine import (
    compute_aggregate_recoveries,
    compute_cumulative_balances,
    compute_discount_matrix,
    compute_ead_weighted_lgd,
    compute_lgd_term_structure,
)
from lgd_model.data_loader import extract_balance_matrix
from lgd_model.scenario import ScenarioResult, generate_scenario_comparison_table
from lgd_model.vintage import VintageResult

# ── Formatting constants for audit trail workbooks ───────────────────
_HDR_FILL = PatternFill('solid', fgColor='2E75B6')
_HDR_FONT = Font(name='Arial', bold=True, color='FFFFFF', size=9)
_SECTION_FONT = Font(name='Arial', bold=True, size=10, color='2E75B6')
_LABEL_FONT = Font(name='Arial', bold=True, size=9)
_DATA_FONT = Font(name='Arial', size=9)
_PARAM_FONT = Font(name='Arial', bold=True, size=9, color='333333')
_THIN_BORDER = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9'),
)
_PCT_FMT = '0.0000%'
_NUM_FMT = '#,##0.00'
_DATE_FMT = 'YYYY-MM-DD'


def generate_summary_dataframe(
    vintage_results: list[VintageResult],
    config: ModelConfig,
) -> pd.DataFrame:
    """Build a summary DataFrame of LGD term structures by vintage.

    Parameters
    ----------
    vintage_results : list[VintageResult]
        Vintage analysis results.
    config : ModelConfig
        Model configuration.

    Returns
    -------
    pd.DataFrame
        One row per vintage, columns = TID values.
    """
    rows = []
    for vr in vintage_results:
        row: dict = {'Vintage': vr.vintage_label, 'Period': vr.period}
        for t in range(config.max_tid + 1):
            row[t] = (
                vr.lgd_term_structure[t]
                if t < len(vr.lgd_term_structure)
                else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows)


def export_results_to_excel(
    vintage_results: list[VintageResult],
    bt: BacktestResult,
    config: ModelConfig,
    output_path: str,
) -> None:
    """Export single-window results to an Excel workbook.

    Parameters
    ----------
    vintage_results : list[VintageResult]
        Vintage analysis results.
    bt : BacktestResult
        Backtest results.
    config : ModelConfig
        Model configuration.
    output_path : str
        Path for the output Excel file.
    """
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        summary_df = generate_summary_dataframe(vintage_results, config)
        summary_df.to_excel(writer, sheet_name='LGD Term Structure Summary', index=False)

        forecast_df = pd.DataFrame(
            bt.forecast_matrix,
            columns=[f'TID_{t}' for t in range(bt.forecast_matrix.shape[1])],
            index=bt.vintage_labels,
        )
        forecast_df.insert(0, 'Period', bt.periods)
        forecast_df.to_excel(writer, sheet_name='Forecast LGD')

        actual_df = pd.DataFrame(
            bt.actual_matrix,
            columns=[f'TID_{t}' for t in range(bt.actual_matrix.shape[1])],
            index=bt.vintage_labels,
        )
        actual_df.insert(0, 'Period', bt.periods)
        actual_df.to_excel(writer, sheet_name='Actual LGD')

        resid_df = pd.DataFrame(
            bt.residual_matrix,
            columns=[f'TID_{t}' for t in range(bt.residual_matrix.shape[1])],
            index=bt.vintage_labels,
        )
        resid_df.insert(0, 'Period', bt.periods)
        resid_df.to_excel(writer, sheet_name='Residuals')

        stats_data = {
            'Metric': [
                'N', 'Mean', 'Std Dev', 'Skewness', 'Excess Kurtosis',
                'JB Stat', 'JB Critical', 'JB Reject',
                'Chi-Sq Stat', 'Chi-Sq Critical', 'Chi-Sq Reject', 'CI Method',
            ],
            'Value': [
                bt.normality_stats['n'],
                bt.normality_stats['mean'],
                bt.normality_stats['std'],
                bt.normality_stats['skewness'],
                bt.normality_stats['excess_kurtosis'],
                bt.normality_stats['jarque_bera_stat'],
                bt.normality_stats['jb_critical_005'],
                bt.normality_stats['jb_reject'],
                bt.normality_stats.get('chi_sq_stat', np.nan),
                bt.normality_stats.get('chi_sq_critical_005', np.nan),
                bt.normality_stats.get('chi_sq_reject', None),
                'sem_scaled',
            ],
        }
        pd.DataFrame(stats_data).to_excel(
            writer, sheet_name='Normality Tests', index=False
        )

        upper_df = pd.DataFrame(
            bt.upper_ci,
            columns=[f'TID_{t}' for t in range(bt.upper_ci.shape[1])],
            index=bt.vintage_labels,
        )
        upper_df.insert(0, 'Period', bt.periods)
        upper_df.to_excel(writer, sheet_name='Upper CI (SEM Scaled)')

        lower_df = pd.DataFrame(
            bt.lower_ci,
            columns=[f'TID_{t}' for t in range(bt.lower_ci.shape[1])],
            index=bt.vintage_labels,
        )
        lower_df.insert(0, 'Period', bt.periods)
        lower_df.to_excel(writer, sheet_name='Lower CI (SEM Scaled)')

    print(f"\n  Results exported to: {output_path}")


def export_multi_scenario_excel(
    scenarios: list[ScenarioResult],
    output_path: str = 'LGD_Multi_Scenario_Output.xlsx',
) -> None:
    """Export all scenario results to a comprehensive Excel workbook.

    Parameters
    ----------
    scenarios : list[ScenarioResult]
        Sorted scenario results.
    output_path : str
        Path for the output Excel file.
    """
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        comp_df = generate_scenario_comparison_table(scenarios)
        comp_df.to_excel(writer, sheet_name='Scenario Comparison', index=False)

        for s in scenarios:
            ws = s.window_size
            bt = s.backtest

            fc_df = pd.DataFrame(
                bt.forecast_matrix,
                columns=[f'TID_{t}' for t in range(bt.forecast_matrix.shape[1])],
                index=bt.vintage_labels,
            )
            fc_df.insert(0, 'Period', bt.periods)
            fc_df.to_excel(writer, sheet_name=f'{ws}m Forecast')

            res_df = pd.DataFrame(
                bt.residual_matrix,
                columns=[f'TID_{t}' for t in range(bt.residual_matrix.shape[1])],
                index=bt.vintage_labels,
            )
            res_df.insert(0, 'Period', bt.periods)
            res_df.to_excel(writer, sheet_name=f'{ws}m Residuals')

            latest = s.vintage_results[-1]
            lgd_df = pd.DataFrame({
                'TID': range(len(latest.lgd_term_structure)),
                'LGD': latest.lgd_term_structure,
                'Recovery': 1.0 - latest.lgd_term_structure,
            })
            lgd_df.to_excel(writer, sheet_name=f'{ws}m LGD Term', index=False)

    print(f"\n  Multi-scenario results exported to: {output_path}")


# ═══════════════════════════════════════════════════════════════════════
# Full Audit Trail Workbook Export
# ═══════════════════════════════════════════════════════════════════════


def _style_hdr(cell):
    cell.font = _HDR_FONT
    cell.fill = _HDR_FILL
    cell.alignment = Alignment(horizontal='center')
    cell.border = _THIN_BORDER


def _style_data(cell, fmt=None):
    cell.font = _DATA_FONT
    cell.border = _THIN_BORDER
    cell.alignment = Alignment(horizontal='center')
    if fmt:
        cell.number_format = fmt


def _write_val(ws, row, col, val, fmt=None, font=None):
    cell = ws.cell(row=row, column=col, value=val)
    cell.font = font or _DATA_FONT
    cell.border = _THIN_BORDER
    cell.alignment = Alignment(horizontal='center')
    if fmt:
        cell.number_format = fmt
    return cell


def _write_vintage_calc_sheet(
    wb, vintage_label, balance_window, eads_window,
    master_tids_window, n_periods, config,
    recoveries, cum_bal, discount_mat, lgd_ts,
    weighted_lgd, cohort_indices,
):
    """Write a single vintage calculation sheet with full audit trail.

    Layout matches the reference workbook:
    - Cols A-D: Cohort index, max TID, LGD, EAD
    - Col F: TID index
    - Col G: MIN balance
    - Col H onwards: Balance triangle
    - Recovery vector, cumulative balance matrix, discount matrix,
      LGD component matrix
    """
    sheet_label = vintage_label.replace("Latest ", "")
    sheet_name = f'RR LGD TERM STRUCTURES  ({sheet_label})'
    if len(sheet_name) > 31:
        sheet_name = sheet_name[:31]

    ws = wb.create_sheet(sheet_name)
    n_cohorts = balance_window.shape[0]

    # ── Row 1: Header ──
    _write_val(ws, 1, 3, 'LGD TERM STRUCTURES', font=_SECTION_FONT)
    _write_val(ws, 1, 7, 'MIN', font=_LABEL_FONT)
    for t in range(n_periods + 1):
        _write_val(ws, 1, 8 + t, t, font=_HDR_FONT)
        ws.cell(row=1, column=8 + t).fill = _HDR_FILL

    # ── Rows 2..(n_cohorts+1): Balance triangle with cohort metadata ──
    for i in range(n_cohorts):
        r = 2 + i
        _write_val(ws, r, 1, int(cohort_indices[i]))
        max_tid = int(master_tids_window[i])
        _write_val(ws, r, 2, max_tid)
        _write_val(
            ws, r, 3,
            float(lgd_ts[min(i, len(lgd_ts) - 1)]) if i < len(lgd_ts) else 1.0,
            fmt=_PCT_FMT,
        )
        _write_val(ws, r, 4, float(eads_window[i]), fmt=_NUM_FMT)
        _write_val(ws, r, 6, i)

        row_vals = balance_window[i, :]
        valid_vals = row_vals[~np.isnan(row_vals)]
        if len(valid_vals) > 0:
            _write_val(ws, r, 7, float(np.min(valid_vals)), fmt=_NUM_FMT)

        for t in range(n_periods):
            val = balance_window[i, t]
            cell = ws.cell(row=r, column=8 + t)
            cell.value = None if np.isnan(val) else float(val)
            _style_data(cell, _NUM_FMT)

    # ── Weighted LGD + Check row ──
    check_row = 2 + n_cohorts + 2
    _write_val(ws, check_row, 1, 'Weighted', font=_LABEL_FONT)
    _write_val(ws, check_row, 3, float(weighted_lgd), fmt=_PCT_FMT)
    _write_val(ws, check_row, 7, 'Check', font=_LABEL_FONT)
    for t in range(min(n_periods + 1, len(lgd_ts))):
        _write_val(ws, check_row, 8 + t, float(lgd_ts[t]), fmt=_PCT_FMT)

    # ── Parameters block ──
    param_row = check_row + 2
    _write_val(ws, param_row, 7, 'Interest Rate', font=_PARAM_FONT)
    _write_val(ws, param_row, 8, config.discount_rate)
    _write_val(ws, param_row + 1, 7, 'Columns', font=_PARAM_FONT)
    _write_val(ws, param_row + 1, 8, n_periods)
    _write_val(ws, param_row + 2, 7, 'Rows', font=_PARAM_FONT)
    _write_val(ws, param_row + 2, 8, n_cohorts)
    _write_val(ws, param_row + 3, 7, 'Min', font=_PARAM_FONT)
    _write_val(ws, param_row + 3, 8, 0)

    # ── Recovery vector ──
    recov_row = param_row + 5
    _write_val(ws, recov_row, 7, 'Recovery', font=_SECTION_FONT)
    for t in range(n_periods):
        _write_val(ws, recov_row, 8 + t, float(recoveries[t]), fmt=_NUM_FMT)

    # ── Cumulative Balance matrix ──
    cumbal_row = recov_row + 2
    for t_row in range(n_periods + 1):
        _write_val(ws, cumbal_row + t_row, 7, t_row)
        for t_col in range(n_periods):
            if t_row < cum_bal.shape[0] and t_col < cum_bal.shape[1]:
                val = cum_bal[t_row, t_col]
                cell = ws.cell(row=cumbal_row + t_row, column=8 + t_col)
                cell.value = None if (np.isnan(val) or t_col < t_row) else float(val)
                _style_data(cell, _NUM_FMT)

    # ── Discount matrix ──
    disc_row = cumbal_row + n_periods + 3
    for t in range(n_periods + 1):
        _write_val(ws, disc_row - 1, 8 + t, t)
    for t_row in range(n_periods + 1):
        _write_val(ws, disc_row + t_row, 7, t_row)
        for t_col in range(n_periods):
            if t_row < discount_mat.shape[0] and t_col < discount_mat.shape[1]:
                val = discount_mat[t_row, t_col]
                cell = ws.cell(row=disc_row + t_row, column=8 + t_col)
                cell.value = None if t_col < t_row else float(val)
                _style_data(cell, '0.000000')

    # ── LGD component matrix (Recovery[c] / CumBal[t,c] * DF[t,c]) ──
    lgd_comp_row = disc_row + n_periods + 3
    for t_row in range(n_periods + 1):
        _write_val(ws, lgd_comp_row + t_row, 7, t_row)
        for t_col in range(n_periods):
            cell = ws.cell(row=lgd_comp_row + t_row, column=8 + t_col)
            if t_col < t_row:
                cell.value = None
            elif (t_row < cum_bal.shape[0] and t_col < cum_bal.shape[1]
                  and not np.isnan(cum_bal[t_row, t_col])
                  and cum_bal[t_row, t_col] != 0
                  and t_col < len(recoveries)
                  and t_row < discount_mat.shape[0]
                  and t_col < discount_mat.shape[1]):
                comp = (recoveries[t_col] / cum_bal[t_row, t_col]) * discount_mat[t_row, t_col]
                cell.value = float(comp)
            else:
                cell.value = None
            _style_data(cell, _PCT_FMT)

    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 6
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 14
    ws.column_dimensions['F'].width = 6
    ws.column_dimensions['G'].width = 14
    return ws


def _write_backtest_section(ws, start_row, title, vintage_labels, periods,
                            hindsights, matrix, n_tid):
    """Write a labelled backtest matrix section."""
    ws.cell(row=start_row, column=1, value=title).font = _SECTION_FONT
    hdr_row = start_row + 1
    _write_val(ws, hdr_row, 1, 'Vintage', font=_HDR_FONT)
    ws.cell(row=hdr_row, column=1).fill = _HDR_FILL
    _write_val(ws, hdr_row, 2, 'Period', font=_HDR_FONT)
    ws.cell(row=hdr_row, column=2).fill = _HDR_FILL
    _write_val(ws, hdr_row, 3, 'Hindsight', font=_HDR_FONT)
    ws.cell(row=hdr_row, column=3).fill = _HDR_FILL
    for t in range(n_tid):
        cell = ws.cell(row=hdr_row, column=4 + t, value=t)
        _style_hdr(cell)

    n_v = len(vintage_labels)
    for i in range(n_v):
        r = hdr_row + 1 + i
        _write_val(ws, r, 1, vintage_labels[i])
        period_val = periods[i]
        if hasattr(period_val, 'to_pydatetime'):
            period_val = period_val.to_pydatetime()
        _write_val(ws, r, 2, period_val, fmt=_DATE_FMT)
        _write_val(ws, r, 3, hindsights[i])
        for t in range(min(n_tid, matrix.shape[1])):
            val = matrix[i, t]
            cell = ws.cell(row=r, column=4 + t)
            cell.value = None if np.isnan(val) else float(val)
            _style_data(cell, _PCT_FMT)

    return hdr_row + 1 + n_v + 1


def _write_master_data_sheet(wb, master_df: pd.DataFrame):
    """Write the RR LGD TERM STRUCTURE ALL sheet from the loaded DataFrame.

    Preserves all columns and formatting so the user can trace back to
    the source data.
    """
    ws = wb.create_sheet('RR LGD TERM STRUCTURE ALL')

    # Header row
    for col_idx, col_name in enumerate(master_df.columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        _style_hdr(cell)

    # Data rows
    for row_idx, (_, row) in enumerate(master_df.iterrows(), start=2):
        for col_idx, col_name in enumerate(master_df.columns, start=1):
            val = row[col_name]
            cell = ws.cell(row=row_idx, column=col_idx)
            if pd.isna(val):
                cell.value = None
            elif isinstance(val, (np.floating, float)):
                cell.value = float(val)
            elif isinstance(val, (np.integer, int)):
                cell.value = int(val)
            else:
                cell.value = val
            _style_data(cell)

    ws.column_dimensions['A'].width = 14
    return ws


def export_full_audit_workbook(
    master_df: pd.DataFrame,
    scenario: ScenarioResult,
    config: ModelConfig,
    output_path: str | None = None,
) -> bytes:
    """Generate a full audit trail workbook for a single window scenario.

    Replicates the reference workbook structure so the user can verify
    every intermediate calculation (balance triangle, recovery vector,
    cumulative balances, discount matrix, LGD component matrix) and
    tie results back to the UI.

    Parameters
    ----------
    master_df : pd.DataFrame
        Master DataFrame from load_recovery_triangle.
    scenario : ScenarioResult
        Scenario result with vintage_results populated.
    config : ModelConfig
        Model configuration used for this scenario.
    output_path : str or None
        If provided, saves to disk. Always returns bytes.

    Returns
    -------
    bytes
        The workbook as bytes (for Streamlit download).
    """
    balance_matrix = extract_balance_matrix(master_df)
    eads = master_df['EAD'].values.astype(float)
    master_tids = master_df['TID'].values.astype(float)
    n_total = len(master_df)

    vr_list = scenario.vintage_results
    bt = scenario.backtest
    n_v = len(vr_list)
    n_tid = config.max_tid + 1

    wb = Workbook()
    wb.remove(wb.active)

    # 1. Master data sheet
    _write_master_data_sheet(wb, master_df)

    # 2. LGD Term Structure Summary
    ws_sum = wb.create_sheet('LGD Term Structure Summary')
    _write_val(ws_sum, 1, 1, 'Vintage', font=_HDR_FONT)
    ws_sum.cell(1, 1).fill = _HDR_FILL
    _write_val(ws_sum, 1, 2, 'Period', font=_HDR_FONT)
    ws_sum.cell(1, 2).fill = _HDR_FILL
    for t in range(n_tid):
        cell = ws_sum.cell(row=1, column=3 + t, value=t)
        _style_hdr(cell)
    for i, v in enumerate(vr_list):
        r = 2 + i
        _write_val(ws_sum, r, 1, v.vintage_label)
        period_val = v.period
        if hasattr(period_val, 'to_pydatetime'):
            period_val = period_val.to_pydatetime()
        _write_val(ws_sum, r, 2, period_val, fmt=_DATE_FMT)
        for t in range(min(n_tid, len(v.lgd_term_structure))):
            _write_val(ws_sum, r, 3 + t, float(v.lgd_term_structure[t]), fmt=_PCT_FMT)
    ws_sum.column_dimensions['A'].width = 18
    ws_sum.column_dimensions['B'].width = 12

    # 3. Individual vintage calculation sheets (full audit trail)
    for vi, v in enumerate(vr_list):
        start_idx = v.start_idx
        end_idx = v.end_idx
        n_periods = min(config.max_tid, balance_matrix.shape[1])

        window = balance_matrix[start_idx:end_idx, :n_periods].copy()
        eads_window = eads[start_idx:end_idx].copy()
        tids_window = master_tids[start_idx:end_idx].copy()

        # Apply the observation mask
        offset = n_total - end_idx
        for i in range(window.shape[0]):
            cohort_master_idx = start_idx + i
            adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
            if adjusted_max_tid < n_periods:
                window[i, max(0, adjusted_max_tid + 1):] = np.nan

        # Compute intermediates
        recoveries = compute_aggregate_recoveries(window)
        cum_bal = compute_cumulative_balances(window)
        discount_mat = compute_discount_matrix(config.discount_rate, n_periods)
        lgd_ts = compute_lgd_term_structure(
            recoveries, cum_bal, discount_mat, cap=config.lgd_cap,
        )

        # Weighted LGD
        cohort_lgds = np.full(window.shape[0], np.nan)
        for ci in range(window.shape[0]):
            row_valid = ~np.isnan(window[ci, :])
            if row_valid.any():
                first_valid = np.where(row_valid)[0][0]
                if first_valid < len(lgd_ts):
                    cohort_lgds[ci] = lgd_ts[first_valid]
        weighted_lgd = compute_ead_weighted_lgd(cohort_lgds, eads_window)

        cohort_indices = np.arange(start_idx, end_idx)

        # Pad lgd_ts to max_tid+1 with 1.0
        if len(lgd_ts) < n_tid:
            lgd_ts = np.concatenate([lgd_ts, np.ones(n_tid - len(lgd_ts))])

        _write_vintage_calc_sheet(
            wb, v.vintage_label, window, eads_window, tids_window,
            n_periods, config, recoveries, cum_bal, discount_mat,
            lgd_ts, weighted_lgd, cohort_indices,
        )

    # 4. LGD Backtest Summary
    ws_bt = wb.create_sheet('LGD Backtest Summary')
    vintage_labels = bt.vintage_labels
    periods = bt.periods
    hindsights = list(range(n_v, 0, -1))

    row = _write_backtest_section(
        ws_bt, 1, 'FORECAST LGD BY VINTAGE',
        vintage_labels, periods, hindsights, bt.forecast_matrix, n_tid,
    )
    row = _write_backtest_section(
        ws_bt, row, 'ACTUAL LGD BY VINTAGE (DIAGONAL)',
        vintage_labels, periods, hindsights, bt.actual_matrix, n_tid,
    )

    # Mean matrix
    mean_matrix = np.full_like(bt.forecast_matrix, np.nan)
    for i in range(n_v):
        for t in range(n_tid):
            if not np.isnan(bt.actual_matrix[i, t]):
                mean_matrix[i, t] = bt.mean_lgd[t]
    row = _write_backtest_section(
        ws_bt, row, 'MEAN LGD BY VINTAGE',
        vintage_labels, periods, hindsights, mean_matrix, n_tid,
    )

    # Upper CI
    z_score = bt.z_score
    ci_pctl = bt.ci_percentile
    ws_bt.cell(row=row, column=3, value=z_score).font = _DATA_FONT
    ws_bt.cell(row=row, column=5, value=1).font = _DATA_FONT
    row = _write_backtest_section(
        ws_bt, row,
        f'UPPER BOUND ({ci_pctl*100:.0f}th pctl) \u2014 Binomial CI',
        vintage_labels, periods, hindsights, bt.upper_ci, n_tid,
    )

    # Lower CI
    ws_bt.cell(row=row, column=3, value=-z_score).font = _DATA_FONT
    row = _write_backtest_section(
        ws_bt, row,
        f'LOWER BOUND ({(1-ci_pctl)*100:.0f}th pctl) \u2014 Binomial CI',
        vintage_labels, periods, hindsights, bt.lower_ci, n_tid,
    )

    # Residuals
    row = _write_backtest_section(
        ws_bt, row, 'DIFFERENCE (ACTUAL - FORECAST)',
        vintage_labels, periods, hindsights, bt.residual_matrix, n_tid,
    )

    # Summary stats
    row += 1
    ws_bt.cell(row=row, column=1, value='BACKTEST SUMMARY STATISTICS').font = _SECTION_FONT
    row += 1
    stats = [
        ('Window Size (months)', scenario.window_size),
        ('Number of Vintages', n_v),
        ('Number of Residuals', scenario.n_residuals),
        ('Discount Rate', config.discount_rate),
        ('CI Percentile', ci_pctl),
        ('z-score', z_score),
        ('', ''),
        ('Mean Error (Bias)', scenario.mean_error),
        ('Std Dev of Errors', scenario.std_error),
        ('RMSE', scenario.rmse),
        ('MAE', scenario.mae),
        ('Median AE', scenario.median_ae),
        ('Max |Error|', scenario.max_abs_error),
        ('IQR', scenario.iqr_error),
        ('Composite Score', scenario.composite_score),
        ('', ''),
        ('JB Rejects Normality', scenario.jb_reject),
        ('Overall CI Coverage', bt.overall_coverage),
        ('Latest LGD at TID=0', scenario.latest_lgd_tid0),
        ('Latest Weighted LGD', scenario.latest_weighted_lgd),
    ]
    for label, val in stats:
        _write_val(ws_bt, row, 1, label, font=_LABEL_FONT)
        cell = _write_val(ws_bt, row, 2, val)
        if isinstance(val, float) and abs(val) < 2:
            cell.number_format = '0.000000'
        row += 1

    ws_bt.column_dimensions['A'].width = 22
    ws_bt.column_dimensions['B'].width = 14
    ws_bt.column_dimensions['C'].width = 12

    # Serialize to bytes
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    workbook_bytes = buf.getvalue()

    if output_path is not None:
        with open(output_path, 'wb') as f:
            f.write(workbook_bytes)

    return workbook_bytes


def export_all_audit_workbooks_zip(
    master_df: pd.DataFrame,
    scenarios: list[ScenarioResult],
    config: ModelConfig,
) -> bytes:
    """Generate a ZIP containing full audit trail workbooks for all scenarios.

    Parameters
    ----------
    master_df : pd.DataFrame
        Master DataFrame from load_recovery_triangle.
    scenarios : list[ScenarioResult]
        All scenario results.
    config : ModelConfig
        Base model configuration.

    Returns
    -------
    bytes
        ZIP file as bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for s in scenarios:
            ws = s.window_size
            cfg = ModelConfig(
                discount_rate=config.discount_rate,
                window_size=config.window_size,
                max_tid=config.max_tid,
                lgd_cap=config.lgd_cap,
                ci_percentile=config.ci_percentile,
                min_obs_window=config.min_obs_window,
            )
            wb_bytes = export_full_audit_workbook(master_df, s, cfg)
            zf.writestr(f'Munic_dashboard_LPU_1_{ws}m.xlsx', wb_bytes)
    buf.seek(0)
    return buf.getvalue()
