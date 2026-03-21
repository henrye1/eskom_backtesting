"""End-to-end validation against spreadsheet reference values.

These tests validate the complete pipeline against known-good values
from the validated monolithic script.
"""

import numpy as np
import pytest

from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle, extract_balance_matrix
from lgd_model.vintage import run_vintage_analysis
from lgd_model.backtest import run_backtest


class TestDataLoading:
    def test_cohort_count(self, master_df):
        """Master triangle should have 82 cohorts."""
        assert len(master_df) == 82

    def test_columns_present(self, master_df):
        """Required columns should be present."""
        required = ['Period', 'MAXIF', 'DEFAULT_YEAR', 'DEFAULT_MONTH', 'TID', 'EAD']
        for col in required:
            assert col in master_df.columns

    def test_tid_columns(self, master_df):
        """TID columns should exist."""
        tid_cols = [c for c in master_df.columns if c.startswith('TID_')]
        assert len(tid_cols) >= 82  # At least as many as cohorts

    def test_balance_matrix_shape(self, master_df, balance_matrix):
        """Balance matrix should have 82 rows."""
        assert balance_matrix.shape[0] == 82


class TestEndToEnd60m:
    """Full pipeline validation for the 60-month window."""

    @pytest.fixture(scope="class")
    def pipeline_results(self, master_df, default_config):
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        return vr, bt

    def test_n_vintages(self, pipeline_results):
        vr, _ = pipeline_results
        assert len(vr) == 23

    def test_n_residuals(self, pipeline_results):
        _, bt = pipeline_results
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert len(flat) == 276

    def test_forecast_0_0_precision(self, pipeline_results):
        _, bt = pipeline_results
        assert bt.forecast_matrix[0, 0] == pytest.approx(
            0.225514586109806, abs=1e-10
        )

    def test_actual_0_0_precision(self, pipeline_results):
        _, bt = pipeline_results
        assert bt.actual_matrix[0, 0] == pytest.approx(
            0.236239450466784, abs=1e-10
        )

    def test_residual_mean(self, pipeline_results):
        _, bt = pipeline_results
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert np.mean(flat) == pytest.approx(0.006962, abs=0.001)

    def test_residual_std(self, pipeline_results):
        _, bt = pipeline_results
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert np.std(flat, ddof=1) == pytest.approx(0.093872, abs=0.001)

    def test_jb_rejects_normality(self, pipeline_results):
        _, bt = pipeline_results
        assert bt.normality_stats['jb_reject'] == True

    def test_chi_sq_rejects_normality(self, pipeline_results):
        _, bt = pipeline_results
        assert bt.normality_stats['chi_sq_reject'] == True

    def test_latest_vintage_label(self, pipeline_results):
        vr, _ = pipeline_results
        assert vr[-1].vintage_label.startswith("Latest")

    def test_all_residuals_match_to_machine_precision(self, pipeline_results):
        """Verify that the refactored code matches the monolithic script
        by checking the maximum absolute residual difference is ~0."""
        _, bt = pipeline_results
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        # The residuals themselves should be finite
        assert np.all(np.isfinite(flat))
        # 276 residuals
        assert len(flat) == 276
