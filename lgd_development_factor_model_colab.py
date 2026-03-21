"""
LGD Development Factor Model — Eskom Municipal Debt
====================================================
IFRS 9 Loss Given Default estimation using development factors (chain-ladder).

Replicates the logic in Munic_dashboard_LPU_1.xlsx and provides a parameterised,
deployable Python implementation with:
  - Dynamic historical window size selection (12, 18, 24, … 60 months)
  - Multi-scenario runner with statistical window optimisation
  - Interactive HTML dashboards with comprehensive charts

Author : Anchor Point Risk (Pty) Ltd
Date   : 2026-03-20
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from scipy import stats
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """All tuneable parameters in one place."""
    discount_rate: float = 0.15
    window_size: int = 60
    max_tid: int = 60
    lgd_cap: Optional[float] = None
    ci_z_score: float = 1.0
    ci_n_vintages: int = 23
    ci_method: str = 'bootstrap'
    ci_level: float = 0.50
    ci_bootstrap_samples: int = 10000


# ──────────────────────────────────────────────────────────────────────────────
# 1. Data Loading
# ──────────────────────────────────────────────────────────────────────────────

def load_recovery_triangle(filepath: str,
                           sheet_name: str = 'RR LGD TERM STRUCTURE ALL'
                           ) -> pd.DataFrame:
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
    df.columns = [c.strip() for c in df.columns]
    rename_map = {'DEFAULT YEAR': 'DEFAULT_YEAR', 'DEFAULT MONTH': 'DEFAULT_MONTH'}
    df.rename(columns=rename_map, inplace=True)
    tid_cols = [c for c in df.columns if c.startswith('TID_')]
    meta_cols = ['Period', 'MAXIF', 'DEFAULT_YEAR', 'DEFAULT_MONTH', 'TID', 'EAD']
    return df[meta_cols + tid_cols].copy()


def extract_balance_matrix(df: pd.DataFrame) -> np.ndarray:
    tid_cols = [c for c in df.columns if c.startswith('TID_')]
    return df[tid_cols].values.astype(float)


# ──────────────────────────────────────────────────────────────────────────────
# 2. Core Model Engine
# ──────────────────────────────────────────────────────────────────────────────

def compute_aggregate_recoveries(balance_matrix: np.ndarray) -> np.ndarray:
    n_cohorts, n_periods = balance_matrix.shape
    recoveries = np.zeros(n_periods)
    for n in range(n_periods - 1):
        has_next = ~np.isnan(balance_matrix[:, n + 1])
        bal_n = np.where(has_next, np.nan_to_num(balance_matrix[:, n], nan=0.0), 0.0)
        bal_n1 = np.where(has_next, np.nan_to_num(balance_matrix[:, n + 1], nan=0.0), 0.0)
        recoveries[n] = bal_n.sum() - bal_n1.sum()
    return recoveries


def compute_cumulative_balances(balance_matrix: np.ndarray) -> np.ndarray:
    n_cohorts, n_periods = balance_matrix.shape
    cum_bal = np.full((n_periods, n_periods), np.nan)
    for r in range(n_periods):
        for c in range(r, n_periods):
            if c + 1 < n_periods:
                has_obs = ~np.isnan(balance_matrix[:, c + 1])
            else:
                has_obs = ~np.isnan(balance_matrix[:, c])
            bal_r = np.where(has_obs, np.nan_to_num(balance_matrix[:, r], nan=0.0), 0.0)
            cum_bal[r, c] = bal_r.sum()
    return cum_bal


def compute_discount_matrix(rate: float, n_periods: int) -> np.ndarray:
    dm = np.zeros((n_periods, n_periods))
    for r in range(n_periods):
        for c in range(r, n_periods):
            dm[r, c] = 1.0 / (1.0 + rate) ** ((c + 1 - r) / 12.0)
    return dm


def compute_lgd_term_structure(recoveries: np.ndarray,
                               cum_bal: np.ndarray,
                               discount_matrix: np.ndarray,
                               cap: Optional[float] = None) -> np.ndarray:
    n_periods = len(recoveries)
    lgd = np.ones(n_periods + 1)
    for t in range(n_periods):
        discounted_recovery = 0.0
        for c in range(t, n_periods):
            if cum_bal[t, c] != 0 and not np.isnan(cum_bal[t, c]):
                rr = recoveries[c] / cum_bal[t, c]
                discounted_recovery += rr * discount_matrix[t, c]
        lgd[t] = 1.0 - discounted_recovery
    if cap is not None:
        lgd = np.clip(lgd, None, cap)
    return lgd


def compute_ead_weighted_lgd(lgd_per_cohort: np.ndarray, eads: np.ndarray) -> float:
    mask = ~np.isnan(lgd_per_cohort) & ~np.isnan(eads) & (eads > 0)
    if mask.sum() == 0:
        return np.nan
    return np.average(lgd_per_cohort[mask], weights=eads[mask])


# ──────────────────────────────────────────────────────────────────────────────
# 3. Vintage Analysis
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class VintageResult:
    vintage_label: str
    period: pd.Timestamp
    start_idx: int
    end_idx: int
    lgd_term_structure: np.ndarray
    weighted_lgd: float
    n_cohorts: int


def run_single_vintage(balance_matrix: np.ndarray,
                       eads: np.ndarray,
                       master_tids: np.ndarray,
                       start_idx: int,
                       end_idx: int,
                       config: ModelConfig) -> np.ndarray:
    n_total = balance_matrix.shape[0]
    window = balance_matrix[start_idx:end_idx, :].copy()
    if window.shape[1] > config.max_tid:
        window = window[:, :config.max_tid]
    n_periods = window.shape[1]
    offset = n_total - end_idx
    for i in range(window.shape[0]):
        cohort_master_idx = start_idx + i
        adjusted_max_tid = int(master_tids[cohort_master_idx]) - offset
        if adjusted_max_tid < n_periods:
            window[i, max(0, adjusted_max_tid + 1):] = np.nan
    recoveries = compute_aggregate_recoveries(window)
    cum_bal = compute_cumulative_balances(window)
    discount_matrix = compute_discount_matrix(config.discount_rate, n_periods)
    lgd = compute_lgd_term_structure(recoveries, cum_bal, discount_matrix, config.lgd_cap)
    if len(lgd) < config.max_tid + 1:
        padded = np.ones(config.max_tid + 1)
        padded[:len(lgd)] = lgd
        lgd = padded
    return lgd


def run_vintage_analysis(master_df: pd.DataFrame,
                         config: ModelConfig) -> list[VintageResult]:
    balance_matrix = extract_balance_matrix(master_df)
    eads = master_df['EAD'].values
    master_tids = master_df['TID'].values
    n_total = len(master_df)
    n_vintages = n_total - config.window_size + 1
    if n_vintages < 1:
        raise ValueError(f"Not enough cohorts ({n_total}) for window size {config.window_size}.")
    results = []
    for v in range(n_vintages):
        start = v
        end = v + config.window_size
        oldest_offset = n_total - 1 - (end - 1)
        newest_offset = n_total - 1 - start
        label = f"({oldest_offset}-{newest_offset})"
        if v == n_vintages - 1:
            label = f"Latest ({oldest_offset}-{newest_offset})"
        period = master_df['Period'].iloc[end - 1]
        lgd = run_single_vintage(balance_matrix, eads, master_tids, start, end, config)
        window_eads = eads[start:end]
        window_balance = balance_matrix[start:end, :]
        cohort_max_tid = (~np.isnan(window_balance)).sum(axis=1) - 1
        cohort_lgds = np.array([lgd[min(t, len(lgd) - 1)] for t in cohort_max_tid])
        weighted = compute_ead_weighted_lgd(cohort_lgds, window_eads)
        results.append(VintageResult(
            vintage_label=label, period=period, start_idx=start, end_idx=end,
            lgd_term_structure=lgd, weighted_lgd=weighted, n_cohorts=end - start,
        ))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# 4. Backtest Framework
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    forecast_matrix: np.ndarray
    actual_matrix: np.ndarray
    residual_matrix: np.ndarray
    mean_lgd: np.ndarray
    std_lgd: np.ndarray
    upper_ci: np.ndarray
    lower_ci: np.ndarray
    avg_error_by_tid: np.ndarray
    normality_stats: dict
    vintage_labels: list[str]
    periods: list
    ci_method: str = 'heuristic'


def _compute_confidence_intervals(forecast, mean_lgd, std_lgd, n_v, n_tid, config):
    method = config.ci_method.lower()
    alpha = 1.0 - config.ci_level
    upper_ci = np.full((n_v, n_tid), np.nan)
    lower_ci = np.full((n_v, n_tid), np.nan)

    if method == 'heuristic':
        for i in range(n_v):
            hindsight = n_v - 1 - i
            scale = config.ci_z_score * std_lgd * np.sqrt(max(n_v - hindsight, 1))
            upper_ci[i, :] = np.minimum(1.0, mean_lgd + scale)
            lower_ci[i, :] = np.maximum(0.0, mean_lgd - scale)
    elif method == 'standard_error':
        for i in range(n_v):
            for t in range(n_tid):
                col_data = forecast[:, t]
                n_obs = np.sum(~np.isnan(col_data))
                if n_obs < 2:
                    continue
                df = n_obs - 1
                se = std_lgd[t] / np.sqrt(n_obs)
                t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=df)
                upper_ci[i, t] = min(1.0, mean_lgd[t] + t_crit * se)
                lower_ci[i, t] = max(0.0, mean_lgd[t] - t_crit * se)
    elif method == 'bootstrap':
        rng = np.random.default_rng(seed=42)
        n_boot = config.ci_bootstrap_samples
        lower_q = alpha / 2.0
        upper_q = 1.0 - alpha / 2.0
        boot_lower = np.full(n_tid, np.nan)
        boot_upper = np.full(n_tid, np.nan)
        for t in range(n_tid):
            col = forecast[:, t]
            valid = col[~np.isnan(col)]
            if len(valid) < 2:
                continue
            boot_means = np.array([
                rng.choice(valid, size=len(valid), replace=True).mean()
                for _ in range(n_boot)
            ])
            boot_lower[t] = np.percentile(boot_means, lower_q * 100)
            boot_upper[t] = np.percentile(boot_means, upper_q * 100)
        for i in range(n_v):
            upper_ci[i, :] = np.minimum(1.0, boot_upper)
            lower_ci[i, :] = np.maximum(0.0, boot_lower)
    else:
        raise ValueError(f"Unknown ci_method '{config.ci_method}'.")
    return upper_ci, lower_ci


def run_backtest(vintage_results: list[VintageResult],
                 config: ModelConfig) -> BacktestResult:
    n_v = len(vintage_results)
    n_tid = config.max_tid + 1
    forecast = np.full((n_v, n_tid), np.nan)
    actual = np.full((n_v, n_tid), np.nan)
    for i, vr in enumerate(vintage_results):
        forecast[i, :len(vr.lgd_term_structure)] = vr.lgd_term_structure[:n_tid]
    for i in range(n_v - 1):
        hindsight = n_v - 1 - i
        source_idx = i + 1
        source_lgd = vintage_results[source_idx].lgd_term_structure
        start_tid = 0 if i == 0 else (n_v - hindsight)
        end_tid = n_v + 1
        for t in range(start_tid, min(end_tid, n_tid)):
            if t < len(source_lgd):
                actual[i, t] = source_lgd[t]
    residuals = actual - forecast
    mean_lgd = np.nanmean(forecast, axis=0)
    std_lgd = np.nanstd(forecast, axis=0, ddof=1)
    upper_ci, lower_ci = _compute_confidence_intervals(
        forecast, mean_lgd, std_lgd, n_v, n_tid, config
    )
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        avg_error_by_tid = np.nanmean(residuals, axis=0)
    flat_residuals = residuals[~np.isnan(residuals)]
    normality_stats = compute_normality_stats(flat_residuals)
    return BacktestResult(
        forecast_matrix=forecast, actual_matrix=actual, residual_matrix=residuals,
        mean_lgd=mean_lgd, std_lgd=std_lgd, upper_ci=upper_ci, lower_ci=lower_ci,
        avg_error_by_tid=avg_error_by_tid, normality_stats=normality_stats,
        vintage_labels=[vr.vintage_label for vr in vintage_results],
        periods=[vr.period for vr in vintage_results], ci_method=config.ci_method,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 5. Statistical Tests
# ──────────────────────────────────────────────────────────────────────────────

def compute_normality_stats(residuals: np.ndarray) -> dict:
    n = len(residuals)
    if n < 8:
        return {'n': n, 'error': 'Insufficient data for normality tests'}
    mu = np.mean(residuals)
    sigma = np.std(residuals, ddof=1)
    skew = stats.skew(residuals)
    kurt = stats.kurtosis(residuals)
    jb_stat = (n / 6.0) * (skew ** 2 + (kurt ** 2) / 4.0)
    jb_critical = stats.chi2.ppf(0.95, df=2)
    jb_pvalue = 1.0 - stats.chi2.cdf(jb_stat, df=2)
    n_bins = 12
    bin_edges = np.linspace(mu - 3 * sigma, mu + 3 * sigma, n_bins + 1)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf
    observed, _ = np.histogram(residuals, bins=bin_edges)
    expected_probs = np.diff(stats.norm.cdf(bin_edges, loc=mu, scale=sigma))
    expected = expected_probs * n
    valid = expected >= 5
    if valid.sum() < 3:
        chi_sq_stat, chi_sq_pvalue, chi_sq_df = np.nan, np.nan, 0
    else:
        chi_sq_stat = np.sum((observed[valid] - expected[valid]) ** 2 / expected[valid])
        chi_sq_df = valid.sum() - 3
        chi_sq_pvalue = 1.0 - stats.chi2.cdf(chi_sq_stat, df=max(chi_sq_df, 1))
    chi_sq_critical = stats.chi2.ppf(0.95, df=max(chi_sq_df, 1)) if chi_sq_df > 0 else np.nan
    return {
        'n': n, 'mean': mu, 'std': sigma, 'skewness': skew,
        'excess_kurtosis': kurt, 'jarque_bera_stat': jb_stat,
        'jb_pvalue': jb_pvalue, 'jb_critical_005': jb_critical,
        'jb_reject': jb_stat > jb_critical,
        'chi_sq_stat': chi_sq_stat, 'chi_sq_pvalue': chi_sq_pvalue,
        'chi_sq_critical_005': chi_sq_critical,
        'chi_sq_reject': chi_sq_stat > chi_sq_critical if not np.isnan(chi_sq_stat) else None,
        'chi_sq_df': chi_sq_df,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 6. Multi-Scenario Runner & Window Optimiser
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    """Backtest metrics for a single window-size scenario."""
    window_size: int
    n_vintages: int
    n_residuals: int
    mean_error: float           # Mean residual (bias)
    abs_mean_error: float       # |mean residual| — absolute bias
    std_error: float            # Residual std dev
    rmse: float                 # Root mean squared error
    mae: float                  # Mean absolute error
    median_ae: float            # Median absolute error
    max_abs_error: float        # Worst single residual
    iqr_error: float            # Inter-quartile range of residuals
    jb_reject: bool             # Jarque-Bera rejects normality?
    aic_proxy: float            # AIC-like information criterion proxy
    composite_score: float      # Weighted composite for ranking
    latest_lgd_tid0: float      # Latest vintage LGD at TID=0
    latest_weighted_lgd: float  # Latest vintage EAD-weighted LGD
    vintage_results: list       # Full VintageResult list
    backtest: BacktestResult    # Full BacktestResult


def run_scenario(master_df: pd.DataFrame,
                 window_size: int,
                 base_config: ModelConfig) -> Optional[ScenarioResult]:
    """Run a single window-size scenario and compute backtest metrics."""
    n_total = len(master_df)
    if window_size > n_total:
        return None

    config = ModelConfig(
        discount_rate=base_config.discount_rate,
        window_size=window_size,
        max_tid=min(window_size, base_config.max_tid),
        lgd_cap=base_config.lgd_cap,
        ci_z_score=base_config.ci_z_score,
        ci_n_vintages=n_total - window_size + 1,
        ci_method=base_config.ci_method,
        ci_level=base_config.ci_level,
        ci_bootstrap_samples=base_config.ci_bootstrap_samples,
    )

    try:
        vr = run_vintage_analysis(master_df, config)
    except ValueError:
        return None

    if len(vr) < 3:
        return None

    bt = run_backtest(vr, config)
    flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]

    if len(flat) < 5:
        return None

    mean_err = np.mean(flat)
    std_err = np.std(flat, ddof=1)
    rmse = np.sqrt(np.mean(flat ** 2))
    mae = np.mean(np.abs(flat))
    median_ae = np.median(np.abs(flat))
    max_abs = np.max(np.abs(flat))
    q75, q25 = np.percentile(flat, [75, 25])
    iqr = q75 - q25

    # AIC-like proxy: penalise models with fewer parameters (shorter windows
    # have fewer development factors estimated, but we use window_size as a
    # rough degrees-of-freedom proxy)
    n = len(flat)
    sse = np.sum(flat ** 2)
    k = window_size  # proxy for model complexity
    aic = n * np.log(max(sse / n, 1e-20)) + 2 * k

    # Composite score: lower is better
    # Weights chosen to balance bias, precision, and tail behaviour
    composite = (
        0.20 * abs(mean_err) / max(mae, 1e-10)    # Bias relative to MAE
        + 0.35 * rmse                                # Precision
        + 0.25 * mae                                 # Average absolute error
        + 0.20 * (max_abs / max(std_err, 1e-10))    # Tail severity
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
        aic_proxy=aic,
        composite_score=composite,
        latest_lgd_tid0=latest.lgd_term_structure[0],
        latest_weighted_lgd=latest.weighted_lgd,
        vintage_results=vr,
        backtest=bt,
    )


def run_multi_scenario(filepath: str,
                       window_sizes: list[int] = None,
                       base_config: ModelConfig = None,
                       verbose: bool = True) -> list[ScenarioResult]:
    """
    Run the model across multiple window sizes and rank them.

    Parameters
    ----------
    filepath : str
        Path to the input workbook.
    window_sizes : list of int
        Window sizes to evaluate. Default: [12, 18, 24, 30, 36, 42, 48, 54, 60].
    base_config : ModelConfig
        Base configuration (discount_rate, ci_method, etc.).
    verbose : bool

    Returns
    -------
    scenarios : list of ScenarioResult, sorted by composite_score (best first)
    """
    if base_config is None:
        base_config = ModelConfig()
    if window_sizes is None:
        window_sizes = [12, 18, 24, 30, 36, 42, 48, 54, 60]

    if verbose:
        print("=" * 70)
        print("  MULTI-SCENARIO WINDOW SIZE ANALYSIS")
        print("=" * 70)
        print(f"  Window sizes to test: {window_sizes}")
        print(f"  Discount rate: {base_config.discount_rate:.1%}")
        print(f"  CI method: {base_config.ci_method}")
        print(f"  CI level: {base_config.ci_level:.0%}")

    master_df = load_recovery_triangle(filepath)
    n_total = len(master_df)
    if verbose:
        print(f"  Total cohorts: {n_total}")
        print()

    scenarios = []
    for ws in window_sizes:
        if ws > n_total:
            if verbose:
                print(f"  Window {ws:>3}m: SKIPPED (exceeds {n_total} cohorts)")
            continue
        if verbose:
            print(f"  Window {ws:>3}m: computing...", end='', flush=True)
        result = run_scenario(master_df, ws, base_config)
        if result is not None:
            scenarios.append(result)
            if verbose:
                print(f" {result.n_vintages} vintages, "
                      f"RMSE={result.rmse:.4f}, MAE={result.mae:.4f}, "
                      f"Bias={result.mean_error:+.4f}")
        else:
            if verbose:
                print(" FAILED (insufficient data)")

    scenarios.sort(key=lambda s: s.composite_score)

    if verbose and scenarios:
        print()
        print("=" * 70)
        print("  WINDOW SIZE RANKING (best to worst)")
        print("=" * 70)
        print(f"  {'Rank':>4} {'Window':>7} {'RMSE':>8} {'MAE':>8} "
              f"{'Bias':>8} {'MaxErr':>8} {'Score':>8} {'Vintages':>9}")
        print(f"  {'----':>4} {'------':>7} {'------':>8} {'------':>8} "
              f"{'------':>8} {'------':>8} {'------':>8} {'--------':>9}")
        for rank, s in enumerate(scenarios, 1):
            marker = " ***" if rank == 1 else ""
            print(f"  {rank:>4} {s.window_size:>5}m {s.rmse:>8.4f} {s.mae:>8.4f} "
                  f"{s.mean_error:>+8.4f} {s.max_abs_error:>8.4f} "
                  f"{s.composite_score:>8.4f} {s.n_vintages:>9}{marker}")

        best = scenarios[0]
        print(f"\n  RECOMMENDATION: {best.window_size}-month window")
        print(f"    - Composite score: {best.composite_score:.4f}")
        print(f"    - RMSE: {best.rmse:.4f}")
        print(f"    - Mean bias: {best.mean_error:+.4f}")
        print(f"    - Latest LGD at TID 0: {best.latest_lgd_tid0:.4f}")
        print(f"    - Latest weighted LGD: {best.latest_weighted_lgd:.4f}")

    return scenarios


def generate_scenario_comparison_table(scenarios: list[ScenarioResult]) -> pd.DataFrame:
    """Build a comparison table across all scenarios."""
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


# ──────────────────────────────────────────────────────────────────────────────
# 7. Dashboard & Visualisation
# ──────────────────────────────────────────────────────────────────────────────

def generate_dashboard(scenarios: list[ScenarioResult],
                       output_path: str = 'LGD_Dashboard.html',
                       selected_window: int = None):
    """
    Generate a comprehensive interactive HTML dashboard using Plotly.

    Charts included:
      1. LGD Term Structure by Vintage (selected window)
      2. Forecast vs Actual — oldest vintage
      3. Average Forecast Error by TID
      4. Confidence Interval Bands (selected window)
      5. Residual Distribution (histogram)
      6. Window Size Comparison: RMSE / MAE / Bias
      7. LGD Term Structure Comparison across window sizes
      8. Residual Heatmap (selected window)
      9. Vintage Weighted LGD over Time
     10. QQ-Plot of Residuals

    Parameters
    ----------
    scenarios : list of ScenarioResult
    output_path : str
    selected_window : int or None
        Window size for detailed charts. If None, uses the best (rank 1).
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px

    if not scenarios:
        print("No scenarios to plot.")
        return

    if selected_window is None:
        sel = scenarios[0]
    else:
        sel = next((s for s in scenarios if s.window_size == selected_window), scenarios[0])

    bt = sel.backtest
    vr = sel.vintage_results

    # Colour palette
    BLUE = '#1f77b4'
    ORANGE = '#ff7f0e'
    GREEN = '#2ca02c'
    RED = '#d62728'
    PURPLE = '#9467bd'
    GREY = '#7f7f7f'

    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>LGD Development Factor Model — Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
  h1 {{ color: #333; border-bottom: 3px solid {BLUE}; padding-bottom: 10px; }}
  h2 {{ color: #555; margin-top: 40px; }}
  .chart-container {{ background: white; padding: 20px; margin: 20px 0;
       border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .summary-box {{ background: white; padding: 20px; margin: 20px 0;
       border-radius: 8px; border-left: 4px solid {BLUE};
       box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
  .metric-value {{ font-size: 24px; font-weight: bold; color: {BLUE}; }}
  .metric-label {{ font-size: 12px; color: #888; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
  th {{ background: {BLUE}; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  .best {{ background: #e8f5e9 !important; font-weight: bold; }}
</style></head><body>
<h1>LGD Development Factor Model — Dashboard</h1>
<p>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} |
   Entity: Eskom Municipal Debt (Non-Metro) |
   Discount Rate: {sel.backtest.normality_stats.get('n', 0)} residuals analysed</p>
""")

    # ── Summary Box ──
    best = scenarios[0]
    html_parts.append(f"""
<div class="summary-box">
<h2 style="margin-top:0">Recommended Window: {best.window_size} months</h2>
<div class="metric"><div class="metric-value">{best.rmse:.4f}</div><div class="metric-label">RMSE</div></div>
<div class="metric"><div class="metric-value">{best.mae:.4f}</div><div class="metric-label">MAE</div></div>
<div class="metric"><div class="metric-value">{best.mean_error:+.4f}</div><div class="metric-label">Mean Bias</div></div>
<div class="metric"><div class="metric-value">{best.latest_lgd_tid0:.2%}</div><div class="metric-label">LGD at TID=0</div></div>
<div class="metric"><div class="metric-value">{best.latest_weighted_lgd:.2%}</div><div class="metric-label">Wtd LGD</div></div>
<div class="metric"><div class="metric-value">{best.n_vintages}</div><div class="metric-label">Vintages</div></div>
</div>
""")

    # ── Scenario Comparison Table ──
    html_parts.append('<div class="chart-container"><h2>Window Size Comparison</h2><table>')
    html_parts.append('<tr><th>Rank</th><th>Window</th><th>Vintages</th><th>Residuals</th>'
                      '<th>RMSE</th><th>MAE</th><th>Bias</th><th>Max |Err|</th>'
                      '<th>Score</th><th>LGD TID=0</th></tr>')
    for rank, s in enumerate(scenarios, 1):
        cls = ' class="best"' if rank == 1 else ''
        html_parts.append(
            f'<tr{cls}><td>{rank}</td><td>{s.window_size}m</td><td>{s.n_vintages}</td>'
            f'<td>{s.n_residuals}</td><td>{s.rmse:.4f}</td><td>{s.mae:.4f}</td>'
            f'<td>{s.mean_error:+.4f}</td><td>{s.max_abs_error:.4f}</td>'
            f'<td>{s.composite_score:.4f}</td><td>{s.latest_lgd_tid0:.4f}</td></tr>'
        )
    html_parts.append('</table></div>')

    chart_id = 0

    def add_chart(fig, title=""):
        nonlocal chart_id
        chart_id += 1
        div_id = f"chart_{chart_id}"
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=30, t=50, b=50),
            height=500,
            title=dict(text=title, font=dict(size=16)),
        )
        html_parts.append(f'<div class="chart-container"><div id="{div_id}"></div></div>')
        html_parts.append(f'<script>Plotly.newPlot("{div_id}", '
                          f'{fig.to_json()}.data, {fig.to_json()}.layout, '
                          f'{{responsive: true}});</script>')

    def add_chart_json(fig, title=""):
        nonlocal chart_id
        chart_id += 1
        div_id = f"chart_{chart_id}"
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=30, t=50, b=50),
            height=500,
            title=dict(text=title, font=dict(size=16)),
        )
        fig_json = fig.to_json()
        html_parts.append(f'<div class="chart-container"><div id="{div_id}"></div></div>')
        html_parts.append(f'<script>(function(){{ var fig={fig_json}; '
                          f'Plotly.newPlot("{div_id}", fig.data, fig.layout, '
                          f'{{responsive: true}}); }})();</script>')

    # ── Chart 1: LGD Term Structure by Vintage ──
    fig1 = go.Figure()
    n_show = min(len(vr), 8)
    step = max(1, len(vr) // n_show)
    indices = list(range(0, len(vr), step))
    if len(vr) - 1 not in indices:
        indices.append(len(vr) - 1)
    colors = px.colors.qualitative.Set2
    for idx, vi in enumerate(indices):
        v = vr[vi]
        max_t = min(sel.window_size + 1, len(v.lgd_term_structure))
        tids = list(range(max_t))
        fig1.add_trace(go.Scatter(
            x=tids, y=v.lgd_term_structure[:max_t].tolist(),
            mode='lines', name=v.vintage_label,
            line=dict(color=colors[idx % len(colors)]),
        ))
    fig1.update_xaxes(title_text='Time in Default (months)')
    fig1.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig1, f'LGD Term Structure by Vintage ({sel.window_size}m window)')

    # ── Chart 2: Forecast vs Actual — oldest vintage ──
    fig2 = go.Figure()
    n_tid = bt.forecast_matrix.shape[1]
    fc_oldest = bt.forecast_matrix[0, :]
    ac_oldest = bt.actual_matrix[0, :]
    valid_mask = ~np.isnan(ac_oldest)
    tids_all = np.arange(n_tid)
    fig2.add_trace(go.Scatter(
        x=tids_all.tolist(), y=fc_oldest.tolist(),
        mode='lines', name='Forecast', line=dict(color=BLUE, width=2),
    ))
    fig2.add_trace(go.Scatter(
        x=tids_all[valid_mask].tolist(), y=ac_oldest[valid_mask].tolist(),
        mode='lines+markers', name='Actual',
        line=dict(color=ORANGE, width=2), marker=dict(size=4),
    ))
    fig2.update_xaxes(title_text='Time in Default (months)')
    fig2.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig2, f'Forecast vs Actual — Oldest Vintage ({bt.vintage_labels[0]})')

    # ── Chart 3: Average Forecast Error by TID ──
    fig3 = go.Figure()
    avg_err = bt.avg_error_by_tid
    valid_tids = ~np.isnan(avg_err)
    colors_bar = [RED if v > 0 else GREEN for v in avg_err[valid_tids]]
    fig3.add_trace(go.Bar(
        x=tids_all[valid_tids].tolist(), y=avg_err[valid_tids].tolist(),
        marker_color=colors_bar, name='Avg Error',
    ))
    fig3.add_hline(y=0, line_dash='dash', line_color='black')
    fig3.update_xaxes(title_text='Time in Default (months)')
    fig3.update_yaxes(title_text='Average Forecast Error', tickformat='.2%')
    add_chart_json(fig3, f'Average Forecast Error by TID ({sel.window_size}m window)')

    # ── Chart 4: Confidence Interval Bands ──
    fig4 = go.Figure()
    mean_lgd = bt.mean_lgd
    upper_ci_0 = bt.upper_ci[0, :]
    lower_ci_0 = bt.lower_ci[0, :]
    valid_ci = ~np.isnan(upper_ci_0)
    t_valid = tids_all[valid_ci]
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=upper_ci_0[valid_ci].tolist(),
        mode='lines', name=f'Upper CI ({bt.ci_method})',
        line=dict(color=BLUE, width=1, dash='dash'),
    ))
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=lower_ci_0[valid_ci].tolist(),
        mode='lines', name=f'Lower CI ({bt.ci_method})',
        line=dict(color=BLUE, width=1, dash='dash'),
        fill='tonexty', fillcolor='rgba(31,119,180,0.1)',
    ))
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=mean_lgd[valid_ci].tolist(),
        mode='lines', name='Mean LGD',
        line=dict(color=BLUE, width=2),
    ))
    # Overlay actuals for oldest vintage
    ac_v = bt.actual_matrix[0, :]
    ac_valid = ~np.isnan(ac_v)
    fig4.add_trace(go.Scatter(
        x=tids_all[ac_valid].tolist(), y=ac_v[ac_valid].tolist(),
        mode='markers', name='Actual (oldest vintage)',
        marker=dict(color=ORANGE, size=5),
    ))
    fig4.update_xaxes(title_text='Time in Default (months)')
    fig4.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig4, f'Confidence Interval — {bt.ci_method.title()} ({sel.window_size}m)')

    # ── Chart 5: Residual Distribution ──
    flat_r = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
    fig5 = go.Figure()
    fig5.add_trace(go.Histogram(
        x=flat_r.tolist(), nbinsx=30,
        marker_color=BLUE, opacity=0.7, name='Residuals',
    ))
    ns = bt.normality_stats
    if 'mean' in ns and 'std' in ns:
        x_norm = np.linspace(flat_r.min(), flat_r.max(), 100)
        y_norm = stats.norm.pdf(x_norm, ns['mean'], ns['std'])
        bin_width = (flat_r.max() - flat_r.min()) / 30
        y_norm_scaled = y_norm * len(flat_r) * bin_width
        fig5.add_trace(go.Scatter(
            x=x_norm.tolist(), y=y_norm_scaled.tolist(),
            mode='lines', name='Normal fit',
            line=dict(color=RED, width=2, dash='dash'),
        ))
    fig5.update_xaxes(title_text='Residual (Actual − Forecast)')
    fig5.update_yaxes(title_text='Frequency')
    jb_text = f"JB={ns.get('jarque_bera_stat', 0):.1f}, " \
              f"Reject={'Yes' if ns.get('jb_reject') else 'No'}"
    add_chart_json(fig5, f'Residual Distribution ({sel.window_size}m) — {jb_text}')

    # ── Chart 6: Window Size Comparison (multi-metric bar chart) ──
    fig6 = make_subplots(rows=1, cols=3,
                         subplot_titles=('RMSE', 'MAE', 'Mean Bias'))
    ws_labels = [str(s.window_size) for s in scenarios]
    rmses = [s.rmse for s in scenarios]
    maes = [s.mae for s in scenarios]
    biases = [s.mean_error for s in scenarios]
    best_ws = str(scenarios[0].window_size) if scenarios else ''
    rmse_colors = [GREEN if w == best_ws else BLUE for w in ws_labels]
    mae_colors = [GREEN if w == best_ws else ORANGE for w in ws_labels]
    bias_colors = [GREEN if w == best_ws else PURPLE for w in ws_labels]
    fig6.add_trace(go.Bar(x=ws_labels, y=rmses, marker_color=rmse_colors, name='RMSE',
                          showlegend=False), row=1, col=1)
    fig6.add_trace(go.Bar(x=ws_labels, y=maes, marker_color=mae_colors, name='MAE',
                          showlegend=False), row=1, col=2)
    fig6.add_trace(go.Bar(x=ws_labels, y=biases, marker_color=bias_colors, name='Bias',
                          showlegend=False), row=1, col=3)
    fig6.update_xaxes(title_text='Window (months)')
    fig6.update_layout(height=400)
    add_chart_json(fig6, 'Error Metrics by Window Size')

    # ── Chart 7: LGD Term Structure Comparison across windows ──
    fig7 = go.Figure()
    for s in scenarios:
        latest_v = s.vintage_results[-1]
        max_t = min(s.window_size + 1, len(latest_v.lgd_term_structure))
        tids_s = list(range(max_t))
        fig7.add_trace(go.Scatter(
            x=tids_s, y=latest_v.lgd_term_structure[:max_t].tolist(),
            mode='lines', name=f'{s.window_size}m',
            line=dict(width=2 if s.window_size == best.window_size else 1),
        ))
    fig7.update_xaxes(title_text='Time in Default (months)')
    fig7.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig7, 'Latest Vintage LGD — Comparison Across Window Sizes')

    # ── Chart 8: Residual Heatmap ──
    fig8 = go.Figure()
    resid = bt.residual_matrix.copy()
    max_show = min(n_tid, sel.window_size + 1)
    resid_show = resid[:, :max_show]
    fig8.add_trace(go.Heatmap(
        z=resid_show.tolist(),
        x=[str(t) for t in range(max_show)],
        y=bt.vintage_labels,
        colorscale='RdBu_r', zmid=0,
        colorbar=dict(title='Residual'),
    ))
    fig8.update_xaxes(title_text='TID')
    fig8.update_yaxes(title_text='Vintage', autorange='reversed')
    add_chart_json(fig8, f'Residual Heatmap ({sel.window_size}m window)')

    # ── Chart 9: Vintage Weighted LGD over Time ──
    fig9 = go.Figure()
    periods = [v.period for v in vr]
    wlgds = [v.weighted_lgd for v in vr]
    fig9.add_trace(go.Scatter(
        x=[p.strftime('%Y-%m') if hasattr(p, 'strftime') else str(p) for p in periods],
        y=wlgds, mode='lines+markers', name='Weighted LGD',
        line=dict(color=BLUE, width=2), marker=dict(size=5),
    ))
    fig9.update_xaxes(title_text='Vintage Period')
    fig9.update_yaxes(title_text='EAD-Weighted LGD', tickformat='.0%')
    add_chart_json(fig9, f'EAD-Weighted LGD Over Time ({sel.window_size}m window)')

    # ── Chart 10: QQ Plot ──
    fig10 = go.Figure()
    sorted_r = np.sort(flat_r)
    n_r = len(sorted_r)
    theoretical_q = stats.norm.ppf((np.arange(1, n_r + 1) - 0.5) / n_r,
                                    loc=ns.get('mean', 0), scale=ns.get('std', 1))
    fig10.add_trace(go.Scatter(
        x=theoretical_q.tolist(), y=sorted_r.tolist(),
        mode='markers', name='Residuals',
        marker=dict(color=BLUE, size=4, opacity=0.6),
    ))
    min_v = min(theoretical_q.min(), sorted_r.min())
    max_v = max(theoretical_q.max(), sorted_r.max())
    fig10.add_trace(go.Scatter(
        x=[min_v, max_v], y=[min_v, max_v],
        mode='lines', name='45° line',
        line=dict(color=RED, dash='dash'),
    ))
    fig10.update_xaxes(title_text='Theoretical Quantiles (Normal)')
    fig10.update_yaxes(title_text='Sample Quantiles')
    add_chart_json(fig10, 'QQ-Plot of Residuals — Normality Check')

    # ── Close HTML ──
    html_parts.append("""
<div class="summary-box">
<h2 style="margin-top:0">Methodology Notes</h2>
<p><strong>Composite Score</strong> weights: 20% bias ratio, 35% RMSE, 25% MAE, 20% tail severity. Lower is better.</p>
<p><strong>Confidence Intervals</strong>: Three methods available — heuristic (spreadsheet original),
t-distribution standard error, and non-parametric bootstrap (recommended when normality is rejected).</p>
<p><strong>Residual</strong> = Actual − Forecast. Positive → model underestimated LGD (too optimistic).</p>
</div>
</body></html>""")

    html_content = '\n'.join(html_parts)
    with open(output_path, 'w') as f:
        f.write(html_content)
    print(f"\n  Dashboard saved to: {output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# 8. Reporting & Export
# ──────────────────────────────────────────────────────────────────────────────

def print_lgd_term_structure(lgd, label="LGD Term Structure"):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  {'TID':>4}  {'LGD':>10}  {'Recovery Rate':>14}")
    print(f"  {'----':>4}  {'----------':>10}  {'--------------':>14}")
    for t, v in enumerate(lgd):
        print(f"  {t:>4}  {v:>10.6f}  {1.0-v:>14.6f}")


def print_backtest_summary(bt: BacktestResult):
    print(f"\n{'='*60}")
    print(f"  BACKTEST SUMMARY")
    print(f"{'='*60}")
    ns = bt.normality_stats
    print(f"\n  Residual Statistics:")
    print(f"    N                     : {ns['n']}")
    print(f"    Mean                  : {ns['mean']:.6f}")
    print(f"    Std Deviation         : {ns['std']:.6f}")
    print(f"    Skewness              : {ns['skewness']:.6f}")
    print(f"    Excess Kurtosis       : {ns['excess_kurtosis']:.6f}")
    print(f"\n  Jarque-Bera Test:")
    print(f"    Statistic             : {ns['jarque_bera_stat']:.4f}")
    print(f"    Critical (a=0.05)     : {ns['jb_critical_005']:.4f}")
    print(f"    Reject normality?     : {'YES' if ns['jb_reject'] else 'NO'}")
    if not np.isnan(ns.get('chi_sq_stat', np.nan)):
        print(f"\n  Chi-Square GoF:")
        print(f"    Statistic             : {ns['chi_sq_stat']:.4f}")
        print(f"    Critical (a=0.05)     : {ns['chi_sq_critical_005']:.4f}")
        print(f"    Reject normality?     : {'YES' if ns['chi_sq_reject'] else 'NO'}")
    print(f"\n  CI Method: {bt.ci_method}")


def generate_summary_dataframe(vintage_results, config):
    rows = []
    for vr in vintage_results:
        row = {'Vintage': vr.vintage_label, 'Period': vr.period}
        for t in range(config.max_tid + 1):
            row[t] = vr.lgd_term_structure[t] if t < len(vr.lgd_term_structure) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def export_results_to_excel(vintage_results, bt, config, output_path):
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        summary_df = generate_summary_dataframe(vintage_results, config)
        summary_df.to_excel(writer, sheet_name='LGD Term Structure Summary', index=False)
        forecast_df = pd.DataFrame(
            bt.forecast_matrix,
            columns=[f'TID_{t}' for t in range(bt.forecast_matrix.shape[1])],
            index=bt.vintage_labels)
        forecast_df.insert(0, 'Period', bt.periods)
        forecast_df.to_excel(writer, sheet_name='Forecast LGD')
        actual_df = pd.DataFrame(
            bt.actual_matrix,
            columns=[f'TID_{t}' for t in range(bt.actual_matrix.shape[1])],
            index=bt.vintage_labels)
        actual_df.insert(0, 'Period', bt.periods)
        actual_df.to_excel(writer, sheet_name='Actual LGD')
        resid_df = pd.DataFrame(
            bt.residual_matrix,
            columns=[f'TID_{t}' for t in range(bt.residual_matrix.shape[1])],
            index=bt.vintage_labels)
        resid_df.insert(0, 'Period', bt.periods)
        resid_df.to_excel(writer, sheet_name='Residuals')
        stats_data = {
            'Metric': ['N', 'Mean', 'Std Dev', 'Skewness', 'Excess Kurtosis',
                        'JB Stat', 'JB Critical', 'JB Reject',
                        'Chi-Sq Stat', 'Chi-Sq Critical', 'Chi-Sq Reject', 'CI Method'],
            'Value': [
                bt.normality_stats['n'], bt.normality_stats['mean'],
                bt.normality_stats['std'], bt.normality_stats['skewness'],
                bt.normality_stats['excess_kurtosis'],
                bt.normality_stats['jarque_bera_stat'],
                bt.normality_stats['jb_critical_005'], bt.normality_stats['jb_reject'],
                bt.normality_stats.get('chi_sq_stat', np.nan),
                bt.normality_stats.get('chi_sq_critical_005', np.nan),
                bt.normality_stats.get('chi_sq_reject', None), bt.ci_method,
            ]}
        pd.DataFrame(stats_data).to_excel(writer, sheet_name='Normality Tests', index=False)
        upper_df = pd.DataFrame(
            bt.upper_ci,
            columns=[f'TID_{t}' for t in range(bt.upper_ci.shape[1])],
            index=bt.vintage_labels)
        upper_df.insert(0, 'Period', bt.periods)
        upper_df.to_excel(writer, sheet_name=f'Upper CI ({bt.ci_method})')
        lower_df = pd.DataFrame(
            bt.lower_ci,
            columns=[f'TID_{t}' for t in range(bt.lower_ci.shape[1])],
            index=bt.vintage_labels)
        lower_df.insert(0, 'Period', bt.periods)
        lower_df.to_excel(writer, sheet_name=f'Lower CI ({bt.ci_method})')
    print(f"\n  Results exported to: {output_path}")


def export_multi_scenario_excel(scenarios: list[ScenarioResult],
                                output_path: str = 'LGD_Multi_Scenario_Output.xlsx'):
    """Export all scenario results to a comprehensive Excel workbook."""
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        comp_df = generate_scenario_comparison_table(scenarios)
        comp_df.to_excel(writer, sheet_name='Scenario Comparison', index=False)

        for s in scenarios:
            ws = s.window_size
            bt = s.backtest
            # Forecast
            fc_df = pd.DataFrame(
                bt.forecast_matrix,
                columns=[f'TID_{t}' for t in range(bt.forecast_matrix.shape[1])],
                index=bt.vintage_labels)
            fc_df.insert(0, 'Period', bt.periods)
            fc_df.to_excel(writer, sheet_name=f'{ws}m Forecast')
            # Residuals
            res_df = pd.DataFrame(
                bt.residual_matrix,
                columns=[f'TID_{t}' for t in range(bt.residual_matrix.shape[1])],
                index=bt.vintage_labels)
            res_df.insert(0, 'Period', bt.periods)
            res_df.to_excel(writer, sheet_name=f'{ws}m Residuals')
            # Latest LGD term structure
            latest = s.vintage_results[-1]
            lgd_df = pd.DataFrame({
                'TID': range(len(latest.lgd_term_structure)),
                'LGD': latest.lgd_term_structure,
                'Recovery': 1.0 - latest.lgd_term_structure,
            })
            lgd_df.to_excel(writer, sheet_name=f'{ws}m LGD Term', index=False)

    print(f"\n  Multi-scenario results exported to: {output_path}")


# ──────────────────────────────────────────────────────────────────────────────
# 9. Main Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(filepath: str,
                      config: Optional[ModelConfig] = None,
                      output_path: Optional[str] = None,
                      verbose: bool = True) -> tuple[list[VintageResult], BacktestResult]:
    if config is None:
        config = ModelConfig()
    if verbose:
        print("LGD Development Factor Model")
        print(f"  Discount rate  : {config.discount_rate:.1%}")
        print(f"  Window size    : {config.window_size}")
        print(f"  Max TID        : {config.max_tid}")
        print(f"  LGD cap        : {config.lgd_cap}")
        print(f"  CI method      : {config.ci_method}")
        print(f"  CI level       : {config.ci_level:.0%}")
    if verbose:
        print("\n[1/4] Loading recovery triangle...")
    master_df = load_recovery_triangle(filepath)
    if verbose:
        print(f"  Loaded {len(master_df)} cohorts, "
              f"{master_df['Period'].min().strftime('%Y-%m')} to "
              f"{master_df['Period'].max().strftime('%Y-%m')}")
    if verbose:
        print("\n[2/4] Running vintage analysis...")
    vintage_results = run_vintage_analysis(master_df, config)
    if verbose:
        print(f"  Computed {len(vintage_results)} vintage windows")
    latest = vintage_results[-1]
    if verbose:
        print(f"\n  Latest vintage: {latest.vintage_label}")
        print(f"  Weighted LGD   : {latest.weighted_lgd:.6f}")
        print_lgd_term_structure(latest.lgd_term_structure[:21],
                                 f"Latest Vintage LGD Term Structure (TID 0-20)")
    if verbose:
        print("\n[3/4] Running backtest...")
    bt = run_backtest(vintage_results, config)
    if verbose:
        print_backtest_summary(bt)
    if output_path:
        if verbose:
            print("\n[4/4] Exporting results...")
        export_results_to_excel(vintage_results, bt, config, output_path)
    return vintage_results, bt


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import os

    input_file = sys.argv[1] if len(sys.argv) > 1 else 'Munic_dashboard_LPU_1.xlsx'
    output_dir = os.path.dirname(os.path.abspath(input_file)) or '.'

    # ── Configuration ──
    # Change these parameters to control the analysis:
    WINDOW_SIZES = [12, 18, 24, 30, 36, 42, 48, 54, 60]
    CI_METHOD = 'bootstrap'     # 'heuristic' | 'standard_error' | 'bootstrap'
    CI_LEVEL = 0.50             # 0.50 = 50% CI (25th/75th percentiles)
    DISCOUNT_RATE = 0.15        # 15% annual
    LGD_CAP = None              # Set to 1.0 to cap LGD at 100%

    base_config = ModelConfig(
        discount_rate=DISCOUNT_RATE,
        window_size=60,         # Default; overridden per scenario
        max_tid=60,
        lgd_cap=LGD_CAP,
        ci_method=CI_METHOD,
        ci_level=CI_LEVEL,
    )

    # ── Run multi-scenario analysis ──
    scenarios = run_multi_scenario(
        filepath=input_file,
        window_sizes=WINDOW_SIZES,
        base_config=base_config,
        verbose=True,
    )

    if scenarios:
        # ── Export Excel with all scenarios ──
        xlsx_path = os.path.join(output_dir, 'LGD_Multi_Scenario_Output.xlsx')
        export_multi_scenario_excel(scenarios, xlsx_path)

        # ── Generate interactive dashboard ──
        dash_path = os.path.join(output_dir, 'LGD_Dashboard.html')
        generate_dashboard(scenarios, output_path=dash_path)

        # ── Also run the single best-window pipeline for backward compatibility ──
        best_ws = scenarios[0].window_size
        best_config = ModelConfig(
            discount_rate=DISCOUNT_RATE,
            window_size=best_ws,
            max_tid=min(best_ws, 60),
            lgd_cap=LGD_CAP,
            ci_method=CI_METHOD,
            ci_level=CI_LEVEL,
        )
        single_xlsx = os.path.join(output_dir, 'LGD_Model_Output.xlsx')
        print(f"\n\n{'='*70}")
        print(f"  DETAILED OUTPUT FOR BEST WINDOW ({best_ws} months)")
        print(f"{'='*70}")
        run_full_pipeline(input_file, best_config, single_xlsx, verbose=True)
