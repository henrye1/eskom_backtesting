"""Tests for vintage analysis — observation mask and rolling window."""

import numpy as np
import pytest

from lgd_model.config import ModelConfig
from lgd_model.vintage import run_single_vintage, run_vintage_analysis


class TestRunSingleVintage:
    def test_output_length(self, balance_matrix, master_df, default_config):
        """LGD term structure should have max_tid + 1 elements."""
        eads = master_df['EAD'].values
        tids = master_df['TID'].values
        lgd, detail = run_single_vintage(
            balance_matrix, eads, tids,
            start_idx=0, end_idx=60,
            config=default_config,
        )
        assert len(lgd) == default_config.max_tid + 1

    def test_lgd_bounded(self, balance_matrix, master_df, default_config):
        """LGD values should be real numbers (not all NaN)."""
        eads = master_df['EAD'].values
        tids = master_df['TID'].values
        lgd, detail = run_single_vintage(
            balance_matrix, eads, tids,
            start_idx=0, end_idx=60,
            config=default_config,
        )
        assert not np.all(np.isnan(lgd))
        assert lgd[-1] == pytest.approx(1.0)

    def test_detail_stored(self, balance_matrix, master_df, default_config):
        """When store_detail=True, detail should be populated."""
        eads = master_df['EAD'].values
        tids = master_df['TID'].values
        lgd, detail = run_single_vintage(
            balance_matrix, eads, tids,
            start_idx=0, end_idx=60,
            config=default_config,
            store_detail=True,
        )
        assert detail is not None
        assert detail.balance_matrix.shape[0] == 60
        assert detail.recoveries.shape[0] == detail.n_periods


class TestRunVintageAnalysis:
    def test_n_vintages_60m(self, master_df, default_config):
        """60-month window on 82 cohorts should give 23 vintages."""
        results = run_vintage_analysis(master_df, default_config)
        assert len(results) == 23

    def test_latest_label(self, master_df, default_config):
        """Last vintage should have 'Latest' prefix."""
        results = run_vintage_analysis(master_df, default_config)
        assert results[-1].vintage_label.startswith("Latest")

    def test_cohort_count(self, master_df, default_config):
        """Each vintage should have window_size cohorts."""
        results = run_vintage_analysis(master_df, default_config)
        for vr in results:
            assert vr.n_cohorts == default_config.window_size

    def test_hindsight_values(self, master_df, default_config):
        """Hindsight should go from n_vintages-1 down to 0."""
        results = run_vintage_analysis(master_df, default_config)
        assert results[0].hindsight == len(results) - 1
        assert results[-1].hindsight == 0

    def test_insufficient_cohorts_raises(self, master_df):
        """Window larger than data should raise ValueError."""
        config = ModelConfig(window_size=200)
        with pytest.raises(ValueError, match="Not enough cohorts"):
            run_vintage_analysis(master_df, config)
