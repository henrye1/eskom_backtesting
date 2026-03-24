"""Triangle viewer — inspect intermediate computation matrices per vintage.

Displays the same data as the Excel vintage calculation sheets:
1. Balance matrix (after observation mask)
2. Aggregate recovery vector
3. Cumulative balance matrix
4. Discount factor matrix
5. LGD term structure
"""

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

    # ── Normalize toggle (shared across Balance, Recovery, CumBal tabs) ──
    show_pct = st.checkbox(
        "Show as % of EAD (normalised)",
        value=True,
        help="Divide balances by aggregate EAD so TID_0 ≈ 1.0. "
             "Uncheck to see raw Rand amounts.",
    )
    total_ead = float(np.nansum(detail.cohort_eads))

    # Tab 1: Balance Matrix (after observation mask)
    with tabs[0]:
        bm = detail.balance_matrix

        if show_pct:
            st.markdown(f"**Balance Matrix (% of EAD)** — {n_cohorts} cohorts x {n_periods} periods")
            st.caption("Each row divided by its own EAD. TID_0 = 1.0 (100%). NaN = unobserved.")
            eads_col = detail.cohort_eads.copy()
            eads_col[eads_col == 0] = np.nan
            bm_display = bm / eads_col[:, None]
            fmt_tid = {c: '{:.5f}' for c in [f"TID_{c}" for c in range(n_periods)]}
        else:
            st.markdown(f"**Balance Matrix (Rand)** — {n_cohorts} cohorts x {n_periods} periods")
            st.caption("NaN = data not available at this vintage date (observation mask applied)")
            bm_display = bm
            fmt_tid = {c: '{:,.2f}' for c in [f"TID_{c}" for c in range(n_periods)]}

        bm_df = pd.DataFrame(
            bm_display,
            columns=[f"TID_{c}" for c in range(n_periods)],
        )
        bm_df.insert(0, 'EAD', detail.cohort_eads)
        bm_df.insert(0, 'Adj MAXIF', detail.adjusted_max_tids)
        bm_df.insert(0, 'Cohort', range(n_cohorts))

        st.dataframe(
            bm_df.style.format(fmt_tid, na_rep='').format({'EAD': '{:,.2f}'}),
            use_container_width=True,
            hide_index=True,
            height=min(35 * n_cohorts + 50, 500),
        )

    # Tab 2: Aggregate Recovery vector
    with tabs[1]:
        if show_pct:
            st.markdown(f"**Aggregate Recovery Vector (% of total EAD)** — {n_periods} periods")
            rec_vals = detail.recoveries / total_ead if total_ead else detail.recoveries
            rec_fmt = '{:.5f}'
        else:
            st.markdown(f"**Aggregate Recovery Vector (Rand)** — {n_periods} periods")
            rec_vals = detail.recoveries
            rec_fmt = '{:,.4f}'
        rec_df = pd.DataFrame({
            'TID': range(n_periods),
            'Recovery': rec_vals,
        })
        st.dataframe(
            rec_df.style.format({'Recovery': rec_fmt}),
            use_container_width=True,
            hide_index=True,
        )

    # Tab 3: Cumulative Balance matrix
    with tabs[2]:
        if show_pct:
            st.markdown(f"**Cumulative Balance Matrix (% of total EAD)** — {n_periods} x {n_periods}")
            cb_display = detail.cum_bal / total_ead if total_ead else detail.cum_bal
            cb_fmt = {c: '{:.5f}' for c in [f"TID {c}" for c in range(n_periods)]}
        else:
            st.markdown(f"**Cumulative Balance Matrix (Rand)** — {n_periods} x {n_periods}")
            cb_display = detail.cum_bal
            cb_fmt = {c: '{:,.2f}' for c in [f"TID {c}" for c in range(n_periods)]}
        cb_df = _format_matrix_df(cb_display, row_labels=[str(r) for r in range(n_periods)])
        st.dataframe(
            cb_df.style.format(cb_fmt, na_rep=''),
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
                {c: '{:.5f}' for c in dm_df.columns if c.startswith('TID')},
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
            lgd_df.style.format({'LGD': '{:.5f}', 'Recovery Rate': '{:.5f}'}),
            use_container_width=True,
            hide_index=True,
        )
