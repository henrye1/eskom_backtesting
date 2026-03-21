"""Shared test fixtures for the LGD model test suite."""

import os
import sys

import pytest
import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle, extract_balance_matrix


# Path to test data
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
DEFAULT_WORKBOOK = os.path.join(DATA_DIR, 'Munic_dashboard_LPU_1.xlsx')

# Also check project root (where the xlsx lives currently)
ROOT_WORKBOOK = os.path.join(os.path.dirname(__file__), '..', 'Munic_dashboard_LPU_1.xlsx')


def _find_workbook() -> str:
    """Find the test workbook in either data/ or project root."""
    if os.path.exists(DEFAULT_WORKBOOK):
        return DEFAULT_WORKBOOK
    if os.path.exists(ROOT_WORKBOOK):
        return ROOT_WORKBOOK
    pytest.skip("Test workbook not found. Place Munic_dashboard_LPU_1.xlsx in data/ or project root.")


@pytest.fixture(scope="session")
def workbook_path() -> str:
    """Return path to the test workbook."""
    return _find_workbook()


@pytest.fixture(scope="session")
def master_df(workbook_path) -> pd.DataFrame:
    """Load the master recovery triangle DataFrame."""
    return load_recovery_triangle(workbook_path)


@pytest.fixture(scope="session")
def balance_matrix(master_df) -> np.ndarray:
    """Extract the balance matrix from the master DataFrame."""
    return extract_balance_matrix(master_df)


@pytest.fixture(scope="session")
def default_config() -> ModelConfig:
    """Return default model configuration (60m window, SEM scaled CI)."""
    return ModelConfig(
        discount_rate=0.15,
        window_size=60,
        max_tid=60,
        lgd_cap=None,
        ci_percentile=0.75,
    )
