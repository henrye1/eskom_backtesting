"""Regression test: validate model output against the spreadsheet reference values.

Usage:
    python scripts/validate_against_excel.py data/Munic_dashboard_LPU_1.xlsx
"""

import os
import sys

import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle
from lgd_model.vintage import run_vintage_analysis
from lgd_model.backtest import run_backtest


def main() -> None:
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'data/Munic_dashboard_LPU_1.xlsx'

    print("=" * 60)
    print("  VALIDATION AGAINST SPREADSHEET REFERENCE VALUES")
    print("=" * 60)

    config = ModelConfig(
        discount_rate=0.15,
        window_size=60,
        max_tid=60,
        lgd_cap=None,
        ci_percentile=0.75,
    )

    print("\n  Loading data...")
    master_df = load_recovery_triangle(filepath)
    n_cohorts = len(master_df)
    print(f"  Cohorts: {n_cohorts}")
    assert n_cohorts == 82, f"Expected 82 cohorts, got {n_cohorts}"

    print("  Running vintage analysis...")
    vr = run_vintage_analysis(master_df, config)
    n_vintages = len(vr)
    print(f"  Vintages: {n_vintages}")
    assert n_vintages == 23, f"Expected 23 vintages, got {n_vintages}"

    print("  Running backtest...")
    bt = run_backtest(vr, config)

    flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
    n_residuals = len(flat)
    print(f"  Non-NaN residuals: {n_residuals}")
    assert n_residuals == 276, f"Expected 276 residuals, got {n_residuals}"

    # Reference values
    ref_forecast_0_0 = 0.225514586109806
    ref_actual_0_0 = 0.236239450466784

    fc_0_0 = bt.forecast_matrix[0, 0]
    ac_0_0 = bt.actual_matrix[0, 0]

    print(f"\n  Forecast[0,0]: {fc_0_0:.15f}")
    print(f"  Reference:     {ref_forecast_0_0:.15f}")
    print(f"  Diff:          {abs(fc_0_0 - ref_forecast_0_0):.2e}")

    print(f"\n  Actual[0,0]:   {ac_0_0:.15f}")
    print(f"  Reference:     {ref_actual_0_0:.15f}")
    print(f"  Diff:          {abs(ac_0_0 - ref_actual_0_0):.2e}")

    # Residual statistics
    resid_mean = np.mean(flat)
    resid_std = np.std(flat, ddof=1)
    print(f"\n  Residual mean: {resid_mean:.6f} (reference: 0.006962)")
    print(f"  Residual std:  {resid_std:.6f} (reference: 0.093872)")

    # Assertions with tolerance
    tol = 1e-10
    assert abs(fc_0_0 - ref_forecast_0_0) < tol, \
        f"Forecast[0,0] mismatch: {fc_0_0} vs {ref_forecast_0_0}"
    assert abs(ac_0_0 - ref_actual_0_0) < tol, \
        f"Actual[0,0] mismatch: {ac_0_0} vs {ref_actual_0_0}"
    assert abs(resid_mean - 0.006962) < 0.001, \
        f"Residual mean mismatch: {resid_mean}"
    assert abs(resid_std - 0.093872) < 0.001, \
        f"Residual std mismatch: {resid_std}"

    # JB rejects normality
    assert bt.normality_stats['jb_reject'], "Expected JB to reject normality"

    print("\n" + "=" * 60)
    print("  ALL VALIDATION CHECKS PASSED")
    print("=" * 60)


if __name__ == '__main__':
    main()
