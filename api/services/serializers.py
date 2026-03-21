"""Convert numpy/dataclass results to JSON-safe Python types."""

import math

import numpy as np
import pandas as pd


def _clean(val: float) -> float | None:
    """Convert NaN/inf to None for JSON serialization."""
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    return float(val)


def ndarray_to_list(arr: np.ndarray) -> list:
    """Convert ndarray to nested list with NaN → None."""
    if arr.ndim == 1:
        return [_clean(float(v)) for v in arr]
    return [[_clean(float(v)) for v in row] for row in arr]


def timestamp_to_str(ts) -> str:
    if isinstance(ts, pd.Timestamp):
        return ts.strftime("%Y-%m")
    return str(ts)


def clean_dict(d: dict) -> dict:
    """Recursively clean a dict for JSON (NaN → None)."""
    out = {}
    for k, v in d.items():
        if isinstance(v, (np.floating, float)):
            out[k] = _clean(float(v))
        elif isinstance(v, (np.integer, int)):
            out[k] = int(v)
        elif isinstance(v, np.bool_):
            out[k] = bool(v)
        elif isinstance(v, np.ndarray):
            out[k] = ndarray_to_list(v)
        elif isinstance(v, dict):
            out[k] = clean_dict(v)
        else:
            out[k] = v
    return out
