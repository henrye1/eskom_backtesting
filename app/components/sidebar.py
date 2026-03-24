"""Sidebar parameter controls for the Streamlit dashboard."""

from scipy import stats
import streamlit as st


def render_sidebar() -> dict:
    """Render the sidebar and return user-selected parameters.

    Returns
    -------
    dict
        Keys: uploaded_file, window_sizes, ci_percentile,
        discount_rate, lgd_cap, store_detail.
    """
    st.sidebar.header("Model Parameters")

    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel Workbook",
        type=["xlsx"],
        help="Upload Munic_dashboard_LPU_1.xlsx or compatible workbook.",
    )

    st.sidebar.subheader("Min Observation Windows")
    st.sidebar.caption(
        "Minimum cohorts per TID column in chain-ladder. "
        "All scenarios use 60-cohort vintages."
    )
    all_windows = [12, 18, 24, 30, 36, 42, 48, 54, 60]
    window_sizes = []
    cols = st.sidebar.columns(3)
    for i, ws in enumerate(all_windows):
        with cols[i % 3]:
            if st.checkbox(f"{ws}m", value=True, key=f"ws_{ws}"):
                window_sizes.append(ws)

    st.sidebar.subheader("Confidence Intervals")

    ci_percentile = st.sidebar.slider(
        "CI Percentile",
        min_value=0.50,
        max_value=0.99,
        value=0.75,
        step=0.01,
        help="Confidence percentile for SEM bands. z is derived via norm.ppf.",
    )

    z_display = round(stats.norm.ppf(ci_percentile), 4)
    st.sidebar.caption(
        f"z = {z_display} | Bands widen with term point via √(N_steps / N_vintages)"
    )

    st.sidebar.subheader("Model Settings")
    discount_rate = st.sidebar.number_input(
        "Discount Rate (annual)",
        min_value=0.0,
        max_value=1.0,
        value=0.15,
        step=0.01,
        format="%.2f",
    )

    lgd_cap = st.sidebar.checkbox("Cap LGD at 1.0", value=False)

    store_detail = st.sidebar.checkbox(
        "Store triangle details (for inspection)",
        value=True,
        help="Enable to inspect balance matrices, recovery vectors, etc. per vintage.",
    )

    return {
        'uploaded_file': uploaded_file,
        'window_sizes': window_sizes,
        'ci_percentile': ci_percentile,
        'discount_rate': discount_rate,
        'lgd_cap': 1.0 if lgd_cap else None,
        'store_detail': store_detail,
    }
