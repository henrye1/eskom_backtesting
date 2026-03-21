"""KPI metric cards for the Streamlit dashboard."""

import streamlit as st

from lgd_model.scenario import ScenarioResult


def render_summary_cards(best: ScenarioResult) -> None:
    """Render KPI metric cards for the best scenario.

    Parameters
    ----------
    best : ScenarioResult
        The top-ranked scenario.
    """
    cols = st.columns(5)
    with cols[0]:
        st.metric("Recommended Window", f"{best.window_size}m")
    with cols[1]:
        st.metric("RMSE", f"{best.rmse:.4f}")
    with cols[2]:
        st.metric("MAE", f"{best.mae:.4f}")
    with cols[3]:
        st.metric("Bias", f"{best.mean_error:+.4f}")
    with cols[4]:
        st.metric("LGD at TID=0", f"{best.latest_lgd_tid0:.2%}")
