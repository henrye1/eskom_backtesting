"""Tests for multi-scenario runner."""

import pytest

from lgd_model.config import ModelConfig
from lgd_model.scenario import run_scenario, generate_scenario_comparison_table


class TestRunScenario:
    def test_60m_window(self, master_df, default_config):
        """60m scenario should produce valid results."""
        result = run_scenario(master_df, 60, default_config)
        assert result is not None
        assert result.window_size == 60
        assert result.n_vintages == 23
        assert result.n_residuals == 276

    def test_18m_window(self, master_df, default_config):
        """18m window should produce valid results."""
        result = run_scenario(master_df, 18, default_config)
        assert result is not None
        assert result.window_size == 18

    def test_impossible_window_returns_none(self, master_df, default_config):
        """Window larger than data should return None."""
        result = run_scenario(master_df, 200, default_config)
        assert result is None

    def test_composite_score_positive(self, master_df, default_config):
        """Composite score should be a positive number."""
        result = run_scenario(master_df, 60, default_config)
        assert result.composite_score > 0

    def test_aligned_vintages(self, master_df, default_config):
        """All window sizes should produce the same number of aligned vintages."""
        r18 = run_scenario(master_df, 18, default_config)
        r60 = run_scenario(master_df, 60, default_config)
        assert r18.n_vintages == r60.n_vintages == 23


class TestGenerateScenarioComparisonTable:
    def test_table_shape(self, master_df, default_config):
        """Comparison table should have correct number of rows."""
        results = []
        for ws in [18, 60]:
            r = run_scenario(master_df, ws, default_config)
            if r:
                results.append(r)
        results.sort(key=lambda s: s.composite_score)
        df = generate_scenario_comparison_table(results)
        assert len(df) == 2
        assert 'Rank' in df.columns
        assert 'RMSE' in df.columns
