"""Triangle viewer — inspect intermediate computation matrices per vintage.

Displays the same data as the Excel vintage calculation sheets:
1. Balance matrix (after observation mask)
2. Aggregate recovery vector
3. Cumulative balance matrix
4. Discount factor matrix
5. LGD term structure
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from lgd_model.scenario import ScenarioResult
from lgd_model.vintage import VintageDetail, VintageResult


def _format_matrix_df(
    matrix: np.ndarray,
    row_labels: list[str] | None = None,
    col_prefix: str = 'TID',
) -> pd.DataFrame:
    """Convert a 2D numpy matrix to a labelled DataFrame for display."""
    n_rows, n_cols = matrix.shape
    col_labels = [f"{col_prefix} {c}" for c in range(n_cols)]
    df = pd.DataFrame(matrix, columns=col_labels)
    if row_labels is not None:
        df.insert(0, 'Row', row_labels)
    return df


def render_triangle_viewer(scenario: ScenarioResult) -> None:
    """Render the triangle inspection panel for a selected vintage.

    Parameters
    ----------
    scenario : ScenarioResult
        Must have been computed with store_detail=True.
    """
    vr_list = scenario.vintage_results

    # Check if detail is available
    has_detail = any(v.detail is not None for v in vr_list)
    if not has_detail:
        st.warning(
            "Triangle detail not available. Re-run analysis to enable "
            "triangle inspection (this uses more memory)."
        )
        return

    st.subheader(f"Vintage Triangle Inspection — {scenario.window_size}m Window")

    # Vintage selector
    vintage_options = {v.vintage_label: i for i, v in enumerate(vr_list)}
    selected_label = st.selectbox(
        "Select vintage to inspect",
        options=list(vintage_options.keys()),
        index=len(vintage_options) - 1,  # Default to Latest
    )
    idx = vintage_options[selected_label]
    vr = vr_list[idx]
    detail = vr.detail

    if detail is None:
        st.warning("No detail stored for this vintage.")
        return

    n_periods = detail.n_periods
    n_cohorts = detail.balance_matrix.shape[0]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Cohorts", n_cohorts)
    with col2:
        st.metric("Periods", n_periods)
    with col3:
        st.metric("LGD at TID 0", f"{vr.lgd_term_structure[0]:.4f}")
    with col4:
        st.metric("Weighted LGD", f"{vr.weighted_lgd:.4f}")

    tabs = st.tabs([
        "Balance Matrix",
        "Recovery",
        "Cumulative Balance",
        "Discount Matrix",
        "LGD Term Structure",
    ])

    # Tab 1: Balance Matrix (after observation mask)
    with tabs[0]:
        st.markdown(f"**Balance Matrix** — {n_cohorts} cohorts x {n_periods} periods")
        st.caption("NaN = data not available at this vintage date (observation mask applied)")

        # Build cohort info table
        bm = detail.balance_matrix
        cohort_info = pd.DataFrame({
            'Cohort': range(n_cohorts),
            'Adj MAXIF': detail.adjusted_max_tids,
            'EAD': detail.cohort_eads,
        })

        # Show balance matrix with cohort labels
        bm_df = pd.DataFrame(
            bm,
            columns=[f"TID_{c}" for c in range(n_periods)],
        )
        bm_df.insert(0, 'EAD', detail.cohort_eads)
        bm_df.insert(0, 'Adj MAXIF', detail.adjusted_max_tids)
        bm_df.insert(0, 'Cohort', range(n_cohorts))

        st.dataframe(
            bm_df.style.format(
                {c: '{:,.2f}' for c in bm_df.columns if c.startswith('TID_')},
                na_rep='',
            ).format({'EAD': '{:,.2f}'}),
            use_container_width=True,
            hide_index=True,
            height=min(35 * n_cohorts + 50, 500),
        )

    # Tab 2: Aggregate Recovery vector
    with tabs[1]:
        st.markdown(f"**Aggregate Recovery Vector** — {n_periods} periods")
        rec_df = pd.DataFrame({
            'TID': range(n_periods),
            'Recovery': detail.recoveries,
        })
        st.dataframe(
            rec_df.style.format({'Recovery': '{:,.4f}'}),
            use_container_width=True,
            hide_index=True,
        )

    # Tab 3: Cumulative Balance matrix
    with tabs[2]:
        st.markdown(f"**Cumulative Balance Matrix** — {n_periods} x {n_periods}")
        cb_df = _format_matrix_df(detail.cum_bal, row_labels=[str(r) for r in range(n_periods)])
        st.dataframe(
            cb_df.style.format(
                {c: '{:,.2f}' for c in cb_df.columns if c.startswith('TID')},
                na_rep='',
            ),
            use_container_width=True,
            hide_index=True,
            height=min(35 * n_periods + 50, 500),
        )

    # Tab 4: Discount Factor matrix
    with tabs[3]:
        st.markdown(f"**Discount Factor Matrix** — rate={scenario.backtest.normality_stats.get('n', 0) and '15%'}")
        dm_df = _format_matrix_df(detail.discount_matrix, row_labels=[str(r) for r in range(n_periods)])
        st.dataframe(
            dm_df.style.format(
                {c: '{:.6f}' for c in dm_df.columns if c.startswith('TID')},
                na_rep='',
            ),
            use_container_width=True,
            hide_index=True,
            height=min(35 * n_periods + 50, 500),
        )

    # Tab 5: LGD Term Structure
    with tabs[4]:
        st.markdown("**LGD Term Structure**")
        max_show = min(len(vr.lgd_term_structure), n_periods + 1)
        lgd_df = pd.DataFrame({
            'TID': range(max_show),
            'LGD': vr.lgd_term_structure[:max_show],
            'Recovery Rate': 1.0 - vr.lgd_term_structure[:max_show],
        })
        st.dataframe(
            lgd_df.style.format({'LGD': '{:.6f}', 'Recovery Rate': '{:.6f}'}),
            use_container_width=True,
            hide_index=True,
        )
