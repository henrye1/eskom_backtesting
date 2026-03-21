"""Configuration dataclass for the LGD Development Factor Model."""

from dataclasses import dataclass


@dataclass
class ModelConfig:
    """All tuneable parameters in one place.

    Parameters
    ----------
    discount_rate : float
        Annual discount rate (EIR proxy). Default 0.15 (15%).
    window_size : int
        Rolling window of cohorts per vintage. Default 60.
    max_tid : int
        Maximum time-in-default periods. Default 60.
    lgd_cap : float or None
        Set to 1.0 to cap LGD at 100%; None = uncapped.
    ci_percentile : float
        Confidence percentile for SEM CI bands (e.g. 0.75 → z ≈ 0.6745).
        The z-value is derived dynamically via norm.ppf(ci_percentile).
        Default 0.75 (75th percentile).
    """

    discount_rate: float = 0.15
    window_size: int = 60
    max_tid: int = 60
    lgd_cap: float | None = None
    ci_percentile: float = 0.75
