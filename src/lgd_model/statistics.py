"""Normality tests for backtest residuals (Jarque-Bera, Chi-Square GoF)."""

import numpy as np
from scipy import stats


def compute_normality_stats(residuals: np.ndarray) -> dict:
    """Compute normality test statistics on residuals.

    Tests performed:
    - Jarque-Bera: JB = (n/6) * (skew^2 + kurtosis^2/4), chi2 df=2
    - Chi-Square GoF: 12 bins from mu-3sigma to mu+3sigma, merge bins
      with expected < 5, df = valid_bins - 3

    Parameters
    ----------
    residuals : np.ndarray
        Flat array of residuals (NaN-free).

    Returns
    -------
    dict
        Dictionary with test statistics, p-values, and reject flags.
    """
    n = len(residuals)
    if n < 8:
        return {'n': n, 'error': 'Insufficient data for normality tests'}

    mu = np.mean(residuals)
    sigma = np.std(residuals, ddof=1)
    skew = stats.skew(residuals)
    kurt = stats.kurtosis(residuals)

    # Jarque-Bera test
    jb_stat = (n / 6.0) * (skew ** 2 + (kurt ** 2) / 4.0)
    jb_critical = stats.chi2.ppf(0.95, df=2)
    jb_pvalue = 1.0 - stats.chi2.cdf(jb_stat, df=2)

    # Chi-Square Goodness of Fit
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

    chi_sq_critical = (
        stats.chi2.ppf(0.95, df=max(chi_sq_df, 1)) if chi_sq_df > 0 else np.nan
    )

    return {
        'n': n,
        'mean': mu,
        'std': sigma,
        'skewness': skew,
        'excess_kurtosis': kurt,
        'jarque_bera_stat': jb_stat,
        'jb_pvalue': jb_pvalue,
        'jb_critical_005': jb_critical,
        'jb_reject': jb_stat > jb_critical,
        'chi_sq_stat': chi_sq_stat,
        'chi_sq_pvalue': chi_sq_pvalue,
        'chi_sq_critical_005': chi_sq_critical,
        'chi_sq_reject': (
            chi_sq_stat > chi_sq_critical if not np.isnan(chi_sq_stat) else None
        ),
        'chi_sq_df': chi_sq_df,
    }
