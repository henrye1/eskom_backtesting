"""Core computational engine for LGD development factor model.

Contains the mathematical building blocks: aggregate recoveries,
cumulative balances, discount matrix, and LGD term structure.

WARNING: Do NOT modify the formulas — they have been validated to
machine precision against the client's Excel workbook.
"""

import numpy as np


def compute_aggregate_recoveries(balance_matrix: np.ndarray) -> np.ndarray:
    """Compute aggregate recoveries from the balance matrix.

    For transition n to n+1:
        Recovery(n) = SUM(Balance(i,n) for cohorts with obs at n+1)
                    - SUM(Balance(i,n+1) for same cohorts)

    Parameters
    ----------
    balance_matrix : np.ndarray
        Shape (n_cohorts, n_periods). NaN = unobserved.

    Returns
    -------
    np.ndarray
        Shape (n_periods,). Last period recovery = 0.
    """
    n_cohorts, n_periods = balance_matrix.shape
    recoveries = np.zeros(n_periods)
    for n in range(n_periods - 1):
        has_next = ~np.isnan(balance_matrix[:, n + 1])
        bal_n = np.where(has_next, np.nan_to_num(balance_matrix[:, n], nan=0.0), 0.0)
        bal_n1 = np.where(has_next, np.nan_to_num(balance_matrix[:, n + 1], nan=0.0), 0.0)
        recoveries[n] = bal_n.sum() - bal_n1.sum()
    return recoveries


def compute_cumulative_balances(balance_matrix: np.ndarray) -> np.ndarray:
    """Compute cumulative balance matrix.

    For row r, column c:
        CumBal(r, c) = SUM(Balance(i, r) for cohorts with obs at c+1)

    Special case: last column uses ~isnan(balance_matrix[:, c]) instead of c+1.

    Parameters
    ----------
    balance_matrix : np.ndarray
        Shape (n_cohorts, n_periods).

    Returns
    -------
    np.ndarray
        Shape (n_periods, n_periods).
    """
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
    """Compute the discount factor matrix.

    DF(r, c) = 1 / (1 + rate) ^ ((c + 1 - r) / 12)

    Note the c+1 (1-indexed column convention from spreadsheet).
    Monthly compounding with annual rate.

    Parameters
    ----------
    rate : float
        Annual discount rate.
    n_periods : int
        Number of periods.

    Returns
    -------
    np.ndarray
        Shape (n_periods, n_periods).
    """
    dm = np.zeros((n_periods, n_periods))
    for r in range(n_periods):
        for c in range(r, n_periods):
            dm[r, c] = 1.0 / (1.0 + rate) ** ((c + 1 - r) / 12.0)
    return dm


def compute_lgd_term_structure(
    recoveries: np.ndarray,
    cum_bal: np.ndarray,
    discount_matrix: np.ndarray,
    cap: float | None = None,
) -> np.ndarray:
    """Compute the LGD term structure from recoveries and cumulative balances.

    For each TID t:
        LGD(t) = 1 - SUM(Recovery(c)/CumBal(t,c) * DF(t,c), c in [t, n_periods))

    The final element LGD(n_periods) = 1.0 (no recovery data beyond triangle).

    Parameters
    ----------
    recoveries : np.ndarray
        Shape (n_periods,).
    cum_bal : np.ndarray
        Shape (n_periods, n_periods).
    discount_matrix : np.ndarray
        Shape (n_periods, n_periods).
    cap : float or None
        If set, clip LGD values to this maximum.

    Returns
    -------
    np.ndarray
        Shape (n_periods + 1,).
    """
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
    """Compute EAD-weighted average LGD.

    Parameters
    ----------
    lgd_per_cohort : np.ndarray
        LGD value per cohort.
    eads : np.ndarray
        Exposure at default per cohort.

    Returns
    -------
    float
        Weighted average LGD, or NaN if no valid data.
    """
    mask = ~np.isnan(lgd_per_cohort) & ~np.isnan(eads) & (eads > 0)
    if mask.sum() == 0:
        return np.nan
    return float(np.average(lgd_per_cohort[mask], weights=eads[mask]))
