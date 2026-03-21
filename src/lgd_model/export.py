"""Excel export functions for LGD model results."""

import numpy as np
import pandas as pd

from lgd_model.backtest import BacktestResult
from lgd_model.config import ModelConfig
from lgd_model.scenario import ScenarioResult, generate_scenario_comparison_table
from lgd_model.vintage import VintageResult


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
