"""Multi-scenario runner and minimum observation window optimiser.

Key design: all scenarios use the same 60-cohort rolling window (window_size=60)
to produce the same 23 vintages. The min_obs_window parameter (12, 18, 24, ...)
controls how many cohorts are used per TID column in the chain-ladder
calculations — a sliding window that shifts backward for higher TIDs.
This decouples the forecast horizon from the calibration depth.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from lgd_model.backtest import BacktestResult, run_backtest
from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle
from lgd_model.vintage import VintageResult, run_vintage_analysis


@dataclass
class ScenarioResult:
    """Backtest metrics for a single window-size scenario.

    Attributes
    ----------
    window_size : int
        Window size in months (calibration data depth).
    n_vintages : int
        Number of vintages in the backtest.
    n_residuals : int
        Number of non-NaN residuals.
    mean_error : float
        Mean residual (bias).
    abs_mean_error : float
        Absolute value of mean residual.
    std_error : float
        Residual standard deviation.
    rmse : float
        Root mean squared error.
    mae : float
        Mean absolute error.
    median_ae : float
        Median absolute error.
    max_abs_error : float
        Worst single residual (absolute).
    iqr_error : float
        Inter-quartile range of residuals.
    jb_reject : bool
        Whether Jarque-Bera rejects normality.
    aic_proxy : float
        AIC-like information criterion proxy.
    composite_score : float
        Weighted composite for ranking (lower = better).
    latest_lgd_tid0 : float
        Latest vintage LGD at TID=0.
    latest_weighted_lgd : float
        Latest vintage EAD-weighted LGD.
    vintage_results : list[VintageResult]
        Full list of vintage results (aligned to reference window dates).
    backtest : BacktestResult
        Full backtest result.
    """

    window_size: int
    n_vintages: int
    n_residuals: int
    mean_error: float
    abs_mean_error: float
    std_error: float
    rmse: float
    mae: float
    median_ae: float
    max_abs_error: float
    iqr_error: float
    jb_reject: bool
    aic_proxy: float
    composite_score: float
    latest_lgd_tid0: float
    latest_weighted_lgd: float
    vintage_results: list[VintageResult]
    backtest: BacktestResult


def run_scenario(
    master_df: pd.DataFrame,
    window_size: int,
    base_config: ModelConfig,
    store_detail: bool = False,
    min_obs_window: int | None = None,
) -> ScenarioResult | None:
    """Run a single scenario and compute backtest metrics.

    All scenarios use window_size=base_config.window_size (60) for the
    rolling vintage window, producing the same 23 vintages. The
    min_obs_window parameter controls how many cohorts are used per TID
    column in the chain-ladder calculations.

    Parameters
    ----------
    master_df : pd.DataFrame
        Master DataFrame from load_recovery_triangle.
    window_size : int
        The min_obs_window label for this scenario (used for display
        and AIC penalty). The actual rolling window is always
        base_config.window_size.
    base_config : ModelConfig
        Base configuration (discount_rate, ci_percentile, max_tid, etc.).
    store_detail : bool
        If True, store intermediate triangles in each VintageResult.
    min_obs_window : int or None
        Minimum observation window per TID column. If None and
        window_size < base_config.window_size, uses window_size.

    Returns
    -------
    ScenarioResult or None
        None if insufficient data.
    """
    n_total = len(master_df)

    # Determine the effective min_obs_window
    effective_mow = min_obs_window
    if effective_mow is None and window_size < base_config.window_size:
        effective_mow = window_size
    # When window_size == base_config.window_size and no explicit mow, leave as None
    # (original behaviour: use all cohorts)

    # Always use the reference window_size for the rolling vintage window
    config = ModelConfig(
        discount_rate=base_config.discount_rate,
        window_size=base_config.window_size,
        max_tid=base_config.max_tid,
        lgd_cap=base_config.lgd_cap,
        ci_percentile=base_config.ci_percentile,
        min_obs_window=effective_mow,
    )

    if config.window_size > n_total:
        return None

    try:
        vr = run_vintage_analysis(master_df, config, store_detail=store_detail)
    except ValueError:
        return None

    if len(vr) < 3:
        return None

    bt = run_backtest(vr, config)
    flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]

    if len(flat) < 5:
        return None

    mean_err = float(np.mean(flat))
    std_err = float(np.std(flat, ddof=1))
    rmse = float(np.sqrt(np.mean(flat ** 2)))
    mae = float(np.mean(np.abs(flat)))
    median_ae = float(np.median(np.abs(flat)))
    max_abs = float(np.max(np.abs(flat)))
    q75, q25 = np.percentile(flat, [75, 25])
    iqr = float(q75 - q25)

    # AIC-like proxy — penalise by the min_obs_window (or window_size)
    n = len(flat)
    sse = float(np.sum(flat ** 2))
    k = window_size
    aic = n * np.log(max(sse / n, 1e-20)) + 2 * k

    # Composite score (lower = better)
    composite = (
        0.20 * abs(mean_err) / max(mae, 1e-10)
        + 0.35 * rmse
        + 0.25 * mae
        + 0.20 * (max_abs / max(std_err, 1e-10))
    )

    latest = vr[-1]

    return ScenarioResult(
        window_size=window_size,
        n_vintages=len(vr),
        n_residuals=len(flat),
        mean_error=mean_err,
        abs_mean_error=abs(mean_err),
        std_error=std_err,
        rmse=rmse,
        mae=mae,
        median_ae=median_ae,
        max_abs_error=max_abs,
        iqr_error=iqr,
        jb_reject=bt.normality_stats.get('jb_reject', True),
        aic_proxy=float(aic),
        composite_score=float(composite),
        latest_lgd_tid0=float(latest.lgd_term_structure[0]),
        latest_weighted_lgd=float(latest.weighted_lgd),
        vintage_results=vr,
        backtest=bt,
    )


def run_multi_scenario(
    filepath: str,
    window_sizes: list[int] | None = None,
    base_config: ModelConfig | None = None,
    verbose: bool = True,
    store_detail: bool = False,
) -> list[ScenarioResult]:
    """Run the model across multiple min-observation windows and rank them.

    All scenarios use the same 60-cohort rolling window (base_config.window_size)
    to produce the same set of vintages. The window_sizes parameter controls
    the min_obs_window per scenario — the number of cohorts used per TID
    column in the chain-ladder calculations.

    Parameters
    ----------
    filepath : str
        Path to the input workbook.
    window_sizes : list[int] or None
        Minimum observation windows to evaluate.
        Default: [12, 18, 24, 30, 36, 42, 48, 54, 60].
    base_config : ModelConfig or None
        Base configuration. Default: ModelConfig().
    verbose : bool
        Whether to print progress.
    store_detail : bool
        If True, store intermediate triangles in vintage results.

    Returns
    -------
    list[ScenarioResult]
        Sorted by composite_score ascending (best first).
    """
    if base_config is None:
        base_config = ModelConfig()
    if window_sizes is None:
        window_sizes = [12, 18, 24, 30, 36, 42, 48, 54, 60]

    if verbose:
        print("=" * 70)
        print("  MULTI-SCENARIO MIN-OBSERVATION WINDOW ANALYSIS")
        print("=" * 70)
        print(f"  Min-obs windows to test: {window_sizes}")
        print(f"  Vintage window: {base_config.window_size}m (fixed)")
        print(f"  Discount rate: {base_config.discount_rate:.1%}")
        print(f"  CI percentile: {base_config.ci_percentile:.0%}")

    master_df = load_recovery_triangle(filepath)
    n_total = len(master_df)
    ref_n_vintages = n_total - base_config.window_size + 1
    if verbose:
        print(f"  Total cohorts: {n_total}")
        print(f"  Backtest vintages: {ref_n_vintages}")
        print()

    scenarios: list[ScenarioResult] = []
    for ws in window_sizes:
        if verbose:
            print(f"  Min-obs {ws:>3}m: computing...", end='', flush=True)
        # ws == base_config.window_size → min_obs_window=None (use all cohorts)
        mow = ws if ws < base_config.window_size else None
        result = run_scenario(
            master_df, ws, base_config,
            store_detail=store_detail,
            min_obs_window=mow,
        )
        if result is not None:
            scenarios.append(result)
            if verbose:
                print(
                    f" {result.n_vintages} vintages, "
                    f"RMSE={result.rmse:.4f}, MAE={result.mae:.4f}, "
                    f"Bias={result.mean_error:+.4f}"
                )
        else:
            if verbose:
                print(" FAILED (insufficient data)")

    scenarios.sort(key=lambda s: s.composite_score)

    if verbose and scenarios:
        print()
        print("=" * 70)
        print("  MIN-OBS WINDOW RANKING (best to worst)")
        print("=" * 70)
        print(
            f"  {'Rank':>4} {'MinObs':>7} {'RMSE':>8} {'MAE':>8} "
            f"{'Bias':>8} {'MaxErr':>8} {'Score':>8} {'Vintages':>9}"
        )
        print(
            f"  {'----':>4} {'------':>7} {'------':>8} {'------':>8} "
            f"{'------':>8} {'------':>8} {'------':>8} {'--------':>9}"
        )
        for rank, s in enumerate(scenarios, 1):
            marker = " ***" if rank == 1 else ""
            print(
                f"  {rank:>4} {s.window_size:>5}m {s.rmse:>8.4f} {s.mae:>8.4f} "
                f"{s.mean_error:>+8.4f} {s.max_abs_error:>8.4f} "
                f"{s.composite_score:>8.4f} {s.n_vintages:>9}{marker}"
            )

        best = scenarios[0]
        print(f"\n  RECOMMENDATION: {best.window_size}-month min-obs window")
        print(f"    - Composite score: {best.composite_score:.4f}")
        print(f"    - RMSE: {best.rmse:.4f}")
        print(f"    - Mean bias: {best.mean_error:+.4f}")
        print(f"    - Latest LGD at TID 0: {best.latest_lgd_tid0:.4f}")
        print(f"    - Latest weighted LGD: {best.latest_weighted_lgd:.4f}")

    return scenarios


def generate_scenario_comparison_table(
    scenarios: list[ScenarioResult],
) -> pd.DataFrame:
    """Build a comparison table across all scenarios.

    Parameters
    ----------
    scenarios : list[ScenarioResult]
        Sorted scenario results.

    Returns
    -------
    pd.DataFrame
        Comparison table with one row per scenario.
    """
    rows = []
    for rank, s in enumerate(scenarios, 1):
        rows.append({
            'Rank': rank,
            'Window (months)': s.window_size,
            'Vintages': s.n_vintages,
            'Residuals': s.n_residuals,
            'Mean Error (Bias)': s.mean_error,
            'Std Dev': s.std_error,
            'RMSE': s.rmse,
            'MAE': s.mae,
            'Median AE': s.median_ae,
            'Max |Error|': s.max_abs_error,
            'IQR': s.iqr_error,
            'AIC Proxy': s.aic_proxy,
            'Composite Score': s.composite_score,
            'JB Reject Normality': s.jb_reject,
            'Latest LGD TID=0': s.latest_lgd_tid0,
            'Latest Weighted LGD': s.latest_weighted_lgd,
        })
    return pd.DataFrame(rows)
