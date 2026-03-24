"""Data loading utilities for the municipal RR LGD recovery triangle.

Handles the simplified data format with columns:
    PERIOD, EAD, 0, 1, 2, ..., N

Derives the missing metadata (MAXIF, DEFAULT_YEAR, DEFAULT_MONTH, TID)
and normalises column names to match the pipeline's expected format:
    Period, MAXIF, DEFAULT_YEAR, DEFAULT_MONTH, TID, EAD, TID_0 .. TID_N
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def load_recovery_triangle(
    filepath: str,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """Load the master recovery triangle from the Excel workbook.

    Supports two data formats:

    **New format** (simplified):
        Columns: PERIOD, EAD, 0, 1, 2, ..., N
        Missing metadata is derived automatically.

    **Old format** (original Eskom):
        Columns: Period, MAXIF, DEFAULT YEAR, DEFAULT MONTH, TID, EAD,
        TID_0 .. TID_N

    Parameters
    ----------
    filepath : str
        Path to the input workbook (.xlsx).
    sheet_name : str or int
        Sheet name or index. Default 0 (first sheet).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: Period, MAXIF, DEFAULT_YEAR, DEFAULT_MONTH,
        TID, EAD, TID_0 .. TID_N.
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
    df.columns = [str(c).strip() for c in df.columns]

    # Detect format by checking for the PERIOD column (new format)
    # vs Period column (old format)
    col_upper = {c.upper(): c for c in df.columns}

    if 'PERIOD' in col_upper and 'MAXIF' not in col_upper:
        return _load_new_format(df, col_upper)
    else:
        return _load_old_format(df)


def _load_new_format(df: pd.DataFrame, col_upper: dict) -> pd.DataFrame:
    """Load simplified format: PERIOD, EAD, 0, 1, 2, ..., N."""

    period_col = col_upper['PERIOD']
    ead_col = col_upper.get('EAD', col_upper.get('Ead', 'EAD'))

    # Identify balance columns (numeric column names)
    balance_col_names = []
    for c in df.columns:
        if c in (period_col, ead_col):
            continue
        try:
            int(c)
            balance_col_names.append(c)
        except (ValueError, TypeError):
            continue

    # Sort balance columns numerically
    balance_col_names.sort(key=lambda c: int(c))

    # Extract balance matrix
    balance = df[balance_col_names].values.astype(float)
    n_cohorts = len(df)

    # Derive MAXIF: count of non-NaN balance values per row
    maxif = np.sum(~np.isnan(balance), axis=1).astype(int)

    # Derive TID: index of last non-NaN balance column per row
    tid = np.zeros(n_cohorts, dtype=int)
    for i in range(n_cohorts):
        non_nan_idx = np.where(~np.isnan(balance[i, :]))[0]
        tid[i] = int(non_nan_idx[-1]) if len(non_nan_idx) > 0 else 0

    # Derive DEFAULT_YEAR and DEFAULT_MONTH from PERIOD
    periods = pd.to_datetime(df[period_col])
    default_year = periods.dt.year.values
    default_month = periods.dt.month.values

    # Build normalised DataFrame using pd.concat to avoid fragmentation
    meta = pd.DataFrame({
        'Period': periods,
        'MAXIF': maxif,
        'DEFAULT_YEAR': default_year,
        'DEFAULT_MONTH': default_month,
        'TID': tid,
        'EAD': df[ead_col].values.astype(float),
    })

    # Rename balance columns: 0 -> TID_0, 1 -> TID_1, ...
    bal_df = df[balance_col_names].copy()
    bal_df.columns = [f'TID_{bc}' for bc in balance_col_names]
    bal_df = bal_df.astype(float)

    result = pd.concat([meta, bal_df], axis=1)
    return result


def _load_old_format(df: pd.DataFrame) -> pd.DataFrame:
    """Load original Eskom format with all metadata columns."""
    rename_map = {'DEFAULT YEAR': 'DEFAULT_YEAR', 'DEFAULT MONTH': 'DEFAULT_MONTH'}
    df.rename(columns=rename_map, inplace=True)
    tid_cols = [c for c in df.columns if c.startswith('TID_')]
    meta_cols = ['Period', 'MAXIF', 'DEFAULT_YEAR', 'DEFAULT_MONTH', 'TID', 'EAD']
    return df[meta_cols + tid_cols].copy()


def extract_balance_matrix(df: pd.DataFrame) -> np.ndarray:
    """Extract the TID columns as a float ndarray.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame returned by ``load_recovery_triangle``.

    Returns
    -------
    np.ndarray
        Balance matrix of shape (n_cohorts, n_periods).
    """
    tid_cols = [c for c in df.columns if c.startswith('TID_')]
    return df[tid_cols].values.astype(float)
