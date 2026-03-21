"""Data loading utilities for the recovery triangle workbook."""

import numpy as np
import pandas as pd


def load_recovery_triangle(
    filepath: str,
    sheet_name: str = 'RR LGD TERM STRUCTURE ALL',
) -> pd.DataFrame:
    """Load the master recovery triangle from the Excel workbook.

    Parameters
    ----------
    filepath : str
        Path to the input workbook (e.g. Munic_dashboard_LPU_1.xlsx).
    sheet_name : str
        Sheet name containing the master recovery data.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: Period, MAXIF, DEFAULT_YEAR, DEFAULT_MONTH,
        TID, EAD, TID_0 .. TID_N.
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name, header=0)
    df.columns = [c.strip() for c in df.columns]
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
