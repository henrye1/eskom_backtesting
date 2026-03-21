"""Backtest framework — compare vintage forecasts against actuals.

The diagonal pattern was reverse-engineered from the spreadsheet and
empirically verified across all 22 vintages. Do NOT modify the
start_tid / end_tid logic.
"""

import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from lgd_model.config import ModelConfig
from lgd_model.statistics import compute_normality_stats
from lgd_model.vintage import VintageResult


@dataclass
class BacktestResult:
    """Container for backtest outputs.

    Attributes
    ----------
    forecast_matrix : np.ndarray
        Shape (n_vintages, n_tid). Forecast LGD per vintage per TID.
    actual_matrix : np.ndarray
        Shape (n_vintages, n_tid). Actual LGD from next vintage.
    residual_matrix : np.ndarray
        actual - forecast.
    mean_lgd : np.ndarray
        Mean forecast LGD across vintages, per TID (1D, length n_tid).
    std_lgd : np.ndarray
        Std dev of forecast LGD across vintages, per TID (ddof=1).
    upper_ci : np.ndarray
        Upper CI bound. Shape (n_v, n_tid) with diagonal NaN mask.
    lower_ci : np.ndarray
        Lower CI bound. Shape (n_v, n_tid) with diagonal NaN mask.
    mean_matrix : np.ndarray
        Mean LGD replicated per vintage with diagonal NaN mask.
        Shape (n_v, n_tid). Matches Excel "MEAN LGD BY VINTAGE" section.
    upper_ci_vector : np.ndarray
        Global upper CI per TID (1D, length n_tid). NaN where < 2 obs.
    lower_ci_vector : np.ndarray
        Global lower CI per TID (1D, length n_tid). NaN where < 2 obs.
    avg_error_by_tid : np.ndarray
        Mean residual per TID.
    normality_stats : dict
        Normality test results on flat residuals.
    vintage_labels : list[str]
        Labels for each vintage.
    periods : list
        Period dates for each vintage.
    ci_percentile : float
        Confidence percentile used (e.g. 0.75 for 75th percentile).
    z_score : float
        z-score derived from ci_percentile via norm.ppf.
    coverage_by_tid : np.ndarray
        Coverage percentage per TID — fraction of actuals within CI.
    overall_coverage : float
        Overall coverage across all non-NaN actual/CI pairs.
    """

    forecast_matrix: np.ndarray
    actual_matrix: np.ndarray
    residual_matrix: np.ndarray
    mean_lgd: np.ndarray
    std_lgd: np.ndarray
    upper_ci: np.ndarray
    lower_ci: np.ndarray
    mean_matrix: np.ndarray
    upper_ci_vector: np.ndarray
    lower_ci_vector: np.ndarray
    avg_error_by_tid: np.ndarray
    normality_stats: dict
    vintage_labels: list[str]
    periods: list
    ci_percentile: float = 0.75
    z_score: float = 0.6745
    coverage_by_tid: np.ndarray = field(default_factory=lambda: np.array([]))
    overall_coverage: float = 0.0


def _compute_confidence_intervals(
    forecast: np.ndarray,
    actual: np.ndarray,
    mean_lgd: np.ndarray,
    std_lgd: np.ndarray,
    n_v: int,
    n_tid: int,
    config: ModelConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, np.ndarray, float]:
    """Compute Binomial CI with vintage × term-point scaling.

    Formula per (vintage i, TID t) — validated against Excel workbook:
        scale(i, t) = z × StdDev[t] × √(H_i / t)
        Upper(i, t) = MIN(1, Forecast_oldest[t] + scale(i, t))
        Lower(i, t) = MAX(0, Forecast_oldest[t] − scale(i, t))

    where:
        H_i  = i + 1              (hindsight: 1 for oldest, n_v-1 for newest)
        t    = TID number          (1-indexed; TID 0 has no CI, TID cap at n_v-1)
        z    = NORMSINV(ci_percentile)
        Forecast_oldest = forecast[0, :] (oldest vintage's LGD term structure)
        StdDev = column std (ddof=1) across all vintage forecasts

    Staircase: vintage i has CI from TID = H_i onwards (matching actual diagonal).
    Each (vintage, TID) cell gets a unique value.

    The upper/lower vectors represent the AVERAGE across vintages at each
    TID (used for charts that need a single CI line).

    Returns
    -------
    tuple of:
        upper_ci (n_v, n_tid) — with diagonal mask, unique per cell
        lower_ci (n_v, n_tid) — with diagonal mask, unique per cell
        mean_matrix (n_v, n_tid) — mean replicated with diagonal mask
        upper_ci_vector (n_tid,) — average upper per TID (for charts)
        lower_ci_vector (n_tid,) — average lower per TID (for charts)
        z_score — z value used
        coverage_by_tid (n_tid,) — coverage % per TID
        overall_coverage — overall coverage %
    """
    z_score = round(stats.norm.ppf(config.ci_percentile), 4)

    upper_ci = np.full((n_v, n_tid), np.nan)
    lower_ci = np.full((n_v, n_tid), np.nan)
    mean_matrix = np.full((n_v, n_tid), np.nan)

    has_actual = ~np.isnan(actual)

    # Center of CI = oldest vintage's forecast (row 3 in Excel)
    forecast_oldest = forecast[0, :]

    # Mean matrix: broadcast mean_lgd with actual diagonal mask
    for i in range(n_v):
        for t in range(n_tid):
            if has_actual[i, t]:
                mean_matrix[i, t] = mean_lgd[t]

    # TID denominator: 1-indexed TID, capped at n_v - 1
    # TID 0 → no CI; TID 1..n_v-2 → t; TID n_v-1 onwards → n_v - 1
    tid_cap = n_v - 1  # e.g. 22 for 23 vintages

    # Compute upper/lower per (vintage, TID) — unique for every cell
    # Staircase: vintage i starts at TID = H_i = i + 1
    for i in range(n_v - 1):
        h = i + 1  # hindsight: 1 for oldest, n_v-1 for newest
        start_t = h  # CI starts at TID = hindsight
        for t in range(start_t, n_tid):
            if np.isnan(std_lgd[t]) or np.isnan(forecast_oldest[t]):
                continue
            tid_d = min(t, tid_cap)  # TID denominator, capped
            if tid_d == 0:
                continue
            scale = z_score * std_lgd[t] * np.sqrt(h / tid_d)
            upper_ci[i, t] = min(1.0, forecast_oldest[t] + scale)
            lower_ci[i, t] = max(0.0, forecast_oldest[t] - scale)

    # Compute average upper/lower vectors per TID (for chart CI lines)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        upper_vec = np.nanmean(upper_ci, axis=0)
        lower_vec = np.nanmean(lower_ci, axis=0)
    # Where no vintages contributed, keep NaN
    all_nan_cols = np.all(np.isnan(upper_ci), axis=0)
    upper_vec[all_nan_cols] = np.nan
    lower_vec[all_nan_cols] = np.nan

    # Compute coverage statistics
    coverage_by_tid = np.full(n_tid, np.nan)
    total_within = 0
    total_valid = 0
    for t in range(n_tid):
        actual_col = actual[:, t]
        valid_mask = ~np.isnan(actual_col) & ~np.isnan(upper_ci[:, t]) & ~np.isnan(lower_ci[:, t])
        if valid_mask.sum() == 0:
            continue
        actuals_t = actual_col[valid_mask]
        uppers_t = upper_ci[valid_mask, t]
        lowers_t = lower_ci[valid_mask, t]
        within = np.sum((actuals_t >= lowers_t) & (actuals_t <= uppers_t))
        coverage_by_tid[t] = within / len(actuals_t)
        total_within += within
        total_valid += len(actuals_t)

    overall_coverage = total_within / total_valid if total_valid > 0 else 0.0

    return (
        upper_ci, lower_ci, mean_matrix,
        upper_vec, lower_vec, z_score,
        coverage_by_tid, overall_coverage,
    )


def run_backtest(
    vintage_results: list[VintageResult],
    config: ModelConfig,
) -> BacktestResult:
    """Run the backtest — compare forecast vs actual across vintages.

    The diagonal pattern assigns actuals from the NEXT vintage's term
    structure to the current vintage:
    - Vintage i=0 (oldest): actual from vintage 1 at TIDs 0..n_v
    - Vintage i>0: actual from vintage i+1 at TIDs (n_v-hindsight)..n_v+1
    - end_tid = n_v + 1 (NOT n_v) — critical for correct residual count

    Parameters
    ----------
    vintage_results : list[VintageResult]
        Results from run_vintage_analysis.
    config : ModelConfig
        Model configuration.

    Returns
    -------
    BacktestResult
        Complete backtest results including residuals, CI, and coverage.
    """
    n_v = len(vintage_results)
    n_tid = config.max_tid + 1

    forecast = np.full((n_v, n_tid), np.nan)
    actual = np.full((n_v, n_tid), np.nan)

    # Fill forecast matrix
    for i, vr in enumerate(vintage_results):
        forecast[i, :len(vr.lgd_term_structure)] = vr.lgd_term_structure[:n_tid]

    # Fill actual matrix using the diagonal pattern
    for i in range(n_v - 1):
        hindsight = n_v - 1 - i
        source_idx = i + 1
        source_lgd = vintage_results[source_idx].lgd_term_structure
        start_tid = 0 if i == 0 else (n_v - hindsight)
        end_tid = n_v + 1  # NOT n_v — this gives 276 residuals, not 254
        for t in range(start_tid, min(end_tid, n_tid)):
            if t < len(source_lgd):
                actual[i, t] = source_lgd[t]

    residuals = actual - forecast

    mean_lgd = np.nanmean(forecast, axis=0)
    std_lgd = np.nanstd(forecast, axis=0, ddof=1)

    (
        upper_ci, lower_ci, mean_matrix,
        upper_ci_vector, lower_ci_vector, z_score,
        coverage_by_tid, overall_coverage,
    ) = _compute_confidence_intervals(
        forecast, actual, mean_lgd, std_lgd, n_v, n_tid, config
    )

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        avg_error_by_tid = np.nanmean(residuals, axis=0)

    flat_residuals = residuals[~np.isnan(residuals)]
    normality_stats = compute_normality_stats(flat_residuals)

    return BacktestResult(
        forecast_matrix=forecast,
        actual_matrix=actual,
        residual_matrix=residuals,
        mean_lgd=mean_lgd,
        std_lgd=std_lgd,
        upper_ci=upper_ci,
        lower_ci=lower_ci,
        mean_matrix=mean_matrix,
        upper_ci_vector=upper_ci_vector,
        lower_ci_vector=lower_ci_vector,
        avg_error_by_tid=avg_error_by_tid,
        normality_stats=normality_stats,
        vintage_labels=[vr.vintage_label for vr in vintage_results],
        periods=[vr.period for vr in vintage_results],
        ci_percentile=config.ci_percentile,
        z_score=z_score,
        coverage_by_tid=coverage_by_tid,
        overall_coverage=overall_coverage,
    )
