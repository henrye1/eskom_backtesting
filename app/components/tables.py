"""DataTable components for the Streamlit dashboard."""

import pandas as pd
import streamlit as st

from lgd_model.scenario import ScenarioResult, generate_scenario_comparison_table


def render_scenario_table(scenarios: list[ScenarioResult]) -> None:
    """Render the scenario comparison table with the best row highlighted.

    Parameters
    ----------
    scenarios : list[ScenarioResult]
        Sorted scenario results (best first).
    """
    df = generate_scenario_comparison_table(scenarios)

    def highlight_best(row: pd.Series) -> list[str]:
        if row['Rank'] == 1:
            return ['background-color: #e8f5e9; font-weight: bold'] * len(row)
        return [''] * len(row)

    styled = df.style.apply(highlight_best, axis=1).format({
        'Mean Error (Bias)': '{:+.4f}',
        'Std Dev': '{:.4f}',
        'RMSE': '{:.4f}',
        'MAE': '{:.4f}',
        'Median AE': '{:.4f}',
        'Max |Error|': '{:.4f}',
        'IQR': '{:.4f}',
        'AIC Proxy': '{:.1f}',
        'Composite Score': '{:.4f}',
        'Latest LGD TID=0': '{:.4f}',
        'Latest Weighted LGD': '{:.4f}',
    })

    st.dataframe(styled, use_container_width=True, hide_index=True)
