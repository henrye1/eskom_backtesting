"""Vintage analysis — rolling window LGD term structure estimation.

The vintage observation mask is the single most important correctness
constraint. Each cohort's data is restricted to what would have been
observable at the vintage date.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from lgd_model.config import ModelConfig
from lgd_model.core_engine import (
    compute_aggregate_recoveries,
    compute_cumulative_balances,
    compute_discount_matrix,
    compute_ead_weighted_lgd,
    compute_lgd_term_structure,
)
from lgd_model.data_loader import extract_balance_matrix


@dataclass
class VintageDetail:
    """Intermediate computation triangles for a single vintage.

    Stores the balance matrix (after observation mask), recoveries,
    cumulative balances, discount matrix, and per-cohort data so
    the user can inspect and verify against Excel workings.

    Attributes
    ----------
    balance_matrix : np.ndarray
        Shape (n_cohorts, n_periods). After observation mask applied.
    recoveries : np.ndarray
        Shape (n_periods,). Aggregate recovery vector.
    cum_bal : np.ndarray
        Shape (n_periods, n_periods). Cumulative balance matrix.
    discount_matrix : np.ndarray
        Shape (n_periods, n_periods). Discount factor matrix.
    cohort_eads : np.ndarray
        EAD per cohort in the window.
    adjusted_max_tids : np.ndarray
        Adjusted MAXIF per cohort (after offset).
    n_periods : int
        Number of TID periods in the computation.
    """

    balance_matrix: np.ndarray
    recoveries: np.ndarray
    cum_bal: np.ndarray
    discount_matrix: np.ndarray
    cohort_eads: np.ndarray
    adjusted_max_tids: np.ndarray
    n_periods: int


@dataclass
class VintageResult:
    """Result container for a single vintage window.

    Attributes
    ----------
    vintage_label : str
        Human-readable label, e.g. "(0-59)" or "Latest (0-59)".
    period : pd.Timestamp
        End-date of the vintage window.
    start_idx : int
        Index of first cohort in the window.
    end_idx : int
        Index one past the last cohort (exclusive).
    lgd_term_structure : np.ndarray
        LGD values by TID.
    weighted_lgd : float
        EAD-weighted LGD across cohorts in the window.
    n_cohorts : int
        Number of cohorts in the window.
    hindsight : int
        Number of backtest periods available for this vintage.
    detail : VintageDetail or None
        Intermediate computation triangles. Only populated when
        store_detail=True is passed to run_vintage_analysis.
    """

    vintage_label: str
    period: pd.Timestamp
    start_idx: int
    end_idx: int
    lgd_term_structure: np.ndarray
    weighted_lgd: float
    n_cohorts: int
    hindsight: int = 0
    detail: VintageDetail | None = None


def run_single_vintage(
    balance_matrix: np.ndarray,
    eads: np.ndarray,
    master_tids: np.ndarray,
    start_idx: int,
    end_idx: int,
    config: ModelConfig,
    store_detail: bool = False,
) -> tuple[np.ndarray, VintageDetail | None]:
    """Run the LGD model for a single vintage window.

    CRITICAL — Vintage Observation Mask: each cohort's data is restricted
    to what would have been observable at the vintage date. The offset is
    how many months before the latest data point this vintage sits.

    Parameters
    ----------
    balance_matrix : np.ndarray
        Full master balance matrix.
    eads : np.ndarray
        EAD values for all cohorts.
    master_tids : np.ndarray
        Maximum TID for each cohort in the master data.
    start_idx : int
        Start index of the vintage window.
    end_idx : int
        End index (exclusive) of the vintage window.
    config : ModelConfig
        Model configuration.
    store_detail : bool
        If True, return intermediate computation triangles.

    Returns
    -------
    tuple[np.ndarray, VintageDetail | None]
        LGD term structure (padded to max_tid + 1 with 1.0),
        and optional detail object.
    """
    n_total = balance_matrix.shape[0]
    window = balance_matrix[start_idx:end_idx, :].copy()
    if window.shape[1] > config.max_tid:
        window = window[:, :config.max_tid]
    n_periods = window.shape[1]

    # Apply the vintage observation mask
    offset = n_total - end_idx
    adjusted_max_tids = np.zeros(window.shape[0], dtype=int)
    for i in range(window.shape[0]):
        cohort_master_idx = start_idx + i
        adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
        adjusted_max_tids[i] = adjusted_max_tid
        if adjusted_max_tid < n_periods:
            window[i, max(0, adjusted_max_tid + 1):] = np.nan

    recoveries = compute_aggregate_recoveries(window, config.min_obs_window)
    cum_bal = compute_cumulative_balances(window, config.min_obs_window)
    discount_mat = compute_discount_matrix(config.discount_rate, n_periods)
    lgd = compute_lgd_term_structure(recoveries, cum_bal, discount_mat, config.lgd_cap)

    detail = None
    if store_detail:
        detail = VintageDetail(
            balance_matrix=window.copy(),
            recoveries=recoveries.copy(),
            cum_bal=cum_bal.copy(),
            discount_matrix=discount_mat.copy(),
            cohort_eads=eads[start_idx:end_idx].copy(),
            adjusted_max_tids=adjusted_max_tids.copy(),
            n_periods=n_periods,
        )

    # Pad to max_tid + 1 with 1.0 if shorter
    if len(lgd) < config.max_tid + 1:
        padded = np.ones(config.max_tid + 1)
        padded[:len(lgd)] = lgd
        lgd = padded

    return lgd, detail


def run_vintage_analysis(
    master_df: pd.DataFrame,
    config: ModelConfig,
    store_detail: bool = False,
) -> list[VintageResult]:
    """Run vintage analysis across all rolling windows.

    Slides a rolling window across the master triangle:
    - n_vintages = n_total - window_size + 1
    - Vintage v uses cohorts [v, v + window_size)

    Parameters
    ----------
    master_df : pd.DataFrame
        Master DataFrame from load_recovery_triangle.
    config : ModelConfig
        Model configuration.
    store_detail : bool
        If True, store intermediate triangles in each VintageResult.

    Returns
    -------
    list[VintageResult]
        One result per vintage window, ordered oldest to latest.
    """
    balance_matrix = extract_balance_matrix(master_df)
    eads = master_df['EAD'].values
    master_tids = master_df['TID'].values
    n_total = len(master_df)
    n_vintages = n_total - config.window_size + 1

    if n_vintages < 1:
        raise ValueError(
            f"Not enough cohorts ({n_total}) for window size {config.window_size}."
        )

    results: list[VintageResult] = []
    for v in range(n_vintages):
        start = v
        end = v + config.window_size

        oldest_offset = n_total - 1 - (end - 1)
        newest_offset = n_total - 1 - start
        label = f"({oldest_offset}-{newest_offset})"
        if v == n_vintages - 1:
            label = f"Latest ({oldest_offset}-{newest_offset})"

        period = master_df['Period'].iloc[end - 1]
        lgd, detail = run_single_vintage(
            balance_matrix, eads, master_tids, start, end, config,
            store_detail=store_detail,
        )

        window_eads = eads[start:end]
        window_balance = balance_matrix[start:end, :]
        cohort_max_tid = (~np.isnan(window_balance)).sum(axis=1) - 1
        cohort_lgds = np.array([lgd[min(t, len(lgd) - 1)] for t in cohort_max_tid])
        weighted = compute_ead_weighted_lgd(cohort_lgds, window_eads)

        hindsight = n_vintages - 1 - v

        results.append(VintageResult(
            vintage_label=label,
            period=period,
            start_idx=start,
            end_idx=end,
            lgd_term_structure=lgd,
            weighted_lgd=weighted,
            n_cohorts=end - start,
            hindsight=hindsight,
            detail=detail,
        ))

    return results
