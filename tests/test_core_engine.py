"""Unit tests for core_engine.py — recovery, cumbal, discount, LGD computations."""

import numpy as np
import pytest

from lgd_model.core_engine import (
    compute_aggregate_recoveries,
    compute_cumulative_balances,
    compute_discount_matrix,
    compute_ead_weighted_lgd,
    compute_lgd_term_structure,
)


class TestComputeAggregateRecoveries:
    def test_simple_triangle(self):
        """Test with a simple 2x3 balance matrix."""
        bm = np.array([
            [100.0, 80.0, 60.0],
            [200.0, 150.0, np.nan],
        ])
        rec = compute_aggregate_recoveries(bm)
        assert rec.shape == (3,)
        # Period 0->1: cohorts with obs at 1 = both; rec = (100+200)-(80+150) = 70
        assert rec[0] == pytest.approx(70.0)
        # Period 1->2: cohort 0 has obs at 2, cohort 1 doesn't; rec = 80-60 = 20
        assert rec[1] == pytest.approx(20.0)
        # Last period = 0
        assert rec[2] == pytest.approx(0.0)

    def test_all_nan_next(self):
        """If no cohort has observation at n+1, recovery = 0."""
        bm = np.array([
            [100.0, np.nan],
            [200.0, np.nan],
        ])
        rec = compute_aggregate_recoveries(bm)
        assert rec[0] == pytest.approx(0.0)


class TestComputeCumulativeBalances:
    def test_shape(self):
        bm = np.array([
            [100.0, 80.0, 60.0],
            [200.0, 150.0, np.nan],
        ])
        cb = compute_cumulative_balances(bm)
        assert cb.shape == (3, 3)

    def test_diagonal_values(self):
        """Diagonal CumBal(r,r) should sum balance at r for cohorts with obs at r+1."""
        bm = np.array([
            [100.0, 80.0, 60.0],
            [200.0, 150.0, np.nan],
        ])
        cb = compute_cumulative_balances(bm)
        # CumBal(0,0): cohorts with obs at 1 = both; sum of bal at 0 = 300
        assert cb[0, 0] == pytest.approx(300.0)


class TestComputeDiscountMatrix:
    def test_identity_at_zero_rate(self):
        dm = compute_discount_matrix(0.0, 3)
        assert dm.shape == (3, 3)
        # All factors should be 1.0 at zero rate
        for r in range(3):
            for c in range(r, 3):
                assert dm[r, c] == pytest.approx(1.0)

    def test_positive_rate_decreasing(self):
        dm = compute_discount_matrix(0.15, 5)
        # df(0,0) > df(0,1) > df(0,2) etc.
        for c in range(4):
            assert dm[0, c] > dm[0, c + 1]

    def test_formula(self):
        rate = 0.15
        dm = compute_discount_matrix(rate, 3)
        expected = 1.0 / (1.0 + rate) ** ((2 + 1 - 1) / 12.0)
        assert dm[1, 2] == pytest.approx(expected)


class TestComputeLgdTermStructure:
    def test_last_element_is_one(self):
        rec = np.array([0.5, 0.3, 0.0])
        cb = np.full((3, 3), 100.0)
        dm = compute_discount_matrix(0.15, 3)
        lgd = compute_lgd_term_structure(rec, cb, dm)
        assert lgd[-1] == pytest.approx(1.0)

    def test_shape(self):
        n = 5
        rec = np.zeros(n)
        cb = np.full((n, n), 100.0)
        dm = compute_discount_matrix(0.15, n)
        lgd = compute_lgd_term_structure(rec, cb, dm)
        assert lgd.shape == (n + 1,)

    def test_cap(self):
        rec = np.array([-10.0])  # Negative recovery -> LGD > 1
        cb = np.full((1, 1), 100.0)
        dm = compute_discount_matrix(0.15, 1)
        lgd = compute_lgd_term_structure(rec, cb, dm, cap=1.0)
        assert all(v <= 1.0 for v in lgd)


class TestComputeEadWeightedLgd:
    def test_simple_average(self):
        lgds = np.array([0.3, 0.5])
        eads = np.array([100.0, 100.0])
        result = compute_ead_weighted_lgd(lgds, eads)
        assert result == pytest.approx(0.4)

    def test_weighted(self):
        lgds = np.array([0.3, 0.5])
        eads = np.array([300.0, 100.0])
        result = compute_ead_weighted_lgd(lgds, eads)
        expected = (0.3 * 300 + 0.5 * 100) / 400
        assert result == pytest.approx(expected)

    def test_nan_handling(self):
        lgds = np.array([0.3, np.nan])
        eads = np.array([100.0, 100.0])
        result = compute_ead_weighted_lgd(lgds, eads)
        assert result == pytest.approx(0.3)

    def test_all_nan_returns_nan(self):
        lgds = np.array([np.nan, np.nan])
        eads = np.array([100.0, 100.0])
        result = compute_ead_weighted_lgd(lgds, eads)
        assert np.isnan(result)
