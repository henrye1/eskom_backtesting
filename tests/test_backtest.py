"""Tests for the backtest framework — diagonal pattern, residuals."""

import numpy as np
import pytest

from lgd_model.backtest import run_backtest
from lgd_model.vintage import run_vintage_analysis


class TestRunBacktest:
    def test_residual_count_276(self, master_df, default_config):
        """The 60m window should produce exactly 276 non-NaN residuals."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert len(flat) == 276

    def test_forecast_0_0(self, master_df, default_config):
        """Forecast[0,0] should match reference value."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        expected = 0.225514586109806
        assert bt.forecast_matrix[0, 0] == pytest.approx(expected, abs=1e-10)

    def test_actual_0_0(self, master_df, default_config):
        """Actual[0,0] should match reference value."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        expected = 0.236239450466784
        assert bt.actual_matrix[0, 0] == pytest.approx(expected, abs=1e-10)

    def test_residual_mean(self, master_df, default_config):
        """Residual mean should be approximately 0.006962."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert np.mean(flat) == pytest.approx(0.006962, abs=0.001)

    def test_residual_std(self, master_df, default_config):
        """Residual std should be approximately 0.093872."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        assert np.std(flat, ddof=1) == pytest.approx(0.093872, abs=0.001)

    def test_matrix_shapes(self, master_df, default_config):
        """Forecast, actual, residual matrices should have correct shapes."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        n_v = len(vr)
        n_tid = default_config.max_tid + 1
        assert bt.forecast_matrix.shape == (n_v, n_tid)
        assert bt.actual_matrix.shape == (n_v, n_tid)
        assert bt.residual_matrix.shape == (n_v, n_tid)

    def test_normality_rejects(self, master_df, default_config):
        """Jarque-Bera should reject normality for 60m window."""
        vr = run_vintage_analysis(master_df, default_config)
        bt = run_backtest(vr, default_config)
        assert bt.normality_stats['jb_reject'] == True
