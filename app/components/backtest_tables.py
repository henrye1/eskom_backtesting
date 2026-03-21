"""Backtest summary tables and per-TID CI blocks on a single page.

Layout:
1-7. Summary triangles (Forecast, Actual, Mean, Upper, Lower, Difference)
8. Normality tests
9. Per-TID backtest blocks: for each TID column, transpose the Actual, Mean,
   Upper, Lower across vintages to show a stationary time series view.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lgd_model.backtest import BacktestResult
from lgd_model.scenario import ScenarioResult


BLUE = '#1f77b4'
ORANGE = '#ff7f0e'
GREEN = '#2ca02c'
RED = '#d62728'


def _matrix_to_df(
    matrix: np.ndarray,
    vintage_labels: list[str],
    periods: list,
    hindsights: list[int],
    max_tid_show: int,
) -> pd.DataFrame:
    n_tid = min(matrix.shape[1], max_tid_show + 1)
    tid_cols = [f"TID {t}" for t in range(n_tid)]
    df = pd.DataFrame(matrix[:, :n_tid], columns=tid_cols)
    df.insert(0, 'Hindsight', hindsights)
    df.insert(0, 'Period', [
        p.strftime('%Y-%m') if hasattr(p, 'strftime') else str(p)
        for p in periods
    ])
    df.insert(0, 'Vintage', vintage_labels)
    return df


def render_backtest_summary(scenario: ScenarioResult) -> None:
    """Render the complete LGD Backtest Summary on a single page."""
    bt = scenario.backtest
    vr = scenario.vintage_results
    n_v = len(vr)

    hindsights = [v.hindsight for v in vr]
    max_tid_show = n_v

    st.subheader(f"LGD Backtest Summary — {scenario.window_size}m Window")
    st.info(
        f"CI Method: **SEM Scaled** | Percentile: **{bt.ci_percentile:.0%}** | "
        f"z = **{bt.z_score}** | "
        f"Overall Coverage: **{bt.overall_coverage:.1%}**"
    )

    tbl_height = min(35 * n_v + 50, 600)
    fmt6 = lambda df: {c: '{:.6f}' for c in df.columns if c.startswith('TID')}

    # ── 1. FORECAST ──
    st.markdown("#### FORECAST LGD BY VINTAGE")
    fc_df = _matrix_to_df(bt.forecast_matrix, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    st.dataframe(fc_df.style.format(fmt6(fc_df), na_rep=''),
                 use_container_width=True, hide_index=True, height=tbl_height)

    # ── 2. ACTUAL ──
    st.markdown("#### ACTUAL LGD BY VINTAGE (DIAGONAL)")
    ac_df = _matrix_to_df(bt.actual_matrix, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    st.dataframe(ac_df.style.format(fmt6(ac_df), na_rep=''),
                 use_container_width=True, hide_index=True, height=tbl_height)

    # ── 3. Mean / Std ──
    st.markdown("#### Mean / Std Deviation")
    mean_row = bt.mean_lgd[:max_tid_show + 1]
    std_row = bt.std_lgd[:max_tid_show + 1]
    stats_df = pd.DataFrame([mean_row, std_row],
                            columns=[f"TID {t}" for t in range(len(mean_row))],
                            index=['Mean', 'Std Deviation'])
    st.dataframe(stats_df.style.format('{:.6f}', na_rep=''), use_container_width=True)

    # ── 4. MEAN LGD BY VINTAGE ──
    st.markdown("#### MEAN LGD BY VINTAGE")
    mean_df = _matrix_to_df(bt.mean_matrix, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    st.dataframe(mean_df.style.format(fmt6(mean_df), na_rep=''),
                 use_container_width=True, hide_index=True, height=tbl_height)

    # ── 5. UPPER BOUND ──
    st.markdown(f"#### UPPER BOUND — SEM Scaled (z={bt.z_score}, pctl={bt.ci_percentile:.0%}, n={n_v})")
    upper_df = _matrix_to_df(bt.upper_ci, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    st.dataframe(upper_df.style.format(fmt6(upper_df), na_rep=''),
                 use_container_width=True, hide_index=True, height=tbl_height)

    # ── 6. LOWER BOUND ──
    st.markdown(f"#### LOWER BOUND — SEM Scaled (z={bt.z_score}, pctl={bt.ci_percentile:.0%}, n={n_v})")
    lower_df = _matrix_to_df(bt.lower_ci, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    st.dataframe(lower_df.style.format(fmt6(lower_df), na_rep=''),
                 use_container_width=True, hide_index=True, height=tbl_height)

    # ── 7. DIFFERENCE ──
    st.markdown("#### DIFFERENCE (ACTUAL - FORECAST)")
    diff_df = _matrix_to_df(bt.residual_matrix, bt.vintage_labels, bt.periods, hindsights, max_tid_show)
    tid_cols = [c for c in diff_df.columns if c.startswith('TID')]

    def color_residuals(val):
        if pd.isna(val) or not isinstance(val, (int, float)):
            return ''
        return 'background-color: #ffcccc' if val > 0.05 else (
            'background-color: #ccffcc' if val < -0.05 else '')

    st.dataframe(
        diff_df.style.format({c: '{:+.6f}' for c in tid_cols}, na_rep='')
        .map(color_residuals, subset=tid_cols),
        use_container_width=True, hide_index=True, height=tbl_height)

    # ── 8. Normality Tests ──
    st.markdown("#### Normality Tests")
    ns = bt.normality_stats
    if 'error' not in ns:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"N={ns['n']}, Mean={ns['mean']:.6f}, Std={ns['std']:.6f}")
            st.write(f"Skew={ns['skewness']:.4f}, Kurt={ns['excess_kurtosis']:.4f}")
        with c2:
            st.write(f"JB={ns['jarque_bera_stat']:.4f}, Crit={ns['jb_critical_005']:.4f}")
            st.write(f"Reject: **{'YES' if ns['jb_reject'] else 'NO'}**")
        with c3:
            if not np.isnan(ns.get('chi_sq_stat', np.nan)):
                st.write(f"Chi²={ns['chi_sq_stat']:.4f}, Crit={ns['chi_sq_critical_005']:.4f}")
                st.write(f"Reject: **{'YES' if ns['chi_sq_reject'] else 'NO'}**")

    # ── 9. Per-TID Backtest Blocks ──
    st.markdown("---")
    st.markdown("### Per-TID Backtest")
    st.caption(
        "Backtesting by TID column: for each TID, the Actual, Mean, Upper and "
        "Lower are transposed from the corresponding column across all vintages. "
        "Green = within CI, Red = outside CI."
    )

    # Determine which TIDs have actual data (at least 2 non-NaN values)
    tid_range = []
    for t in range(max_tid_show + 1):
        n_actual = np.sum(~np.isnan(bt.actual_matrix[:, t]))
        if n_actual >= 1:
            tid_range.append(t)

    # Render in pairs (2 charts side by side), highest TID first
    for row_start in range(0, len(tid_range), 2):
        pair = tid_range[row_start:row_start + 2]
        cols = st.columns(len(pair))
        for col_idx, t in enumerate(pair):
            with cols[col_idx]:
                _render_tid_backtest_block(bt, t)


def _render_tid_backtest_block(
    bt: BacktestResult,
    tid: int,
) -> None:
    """Render one per-TID backtest block: table + chart.

    Transposes column `tid` from each matrix across vintages:
    - Actual    = actual_matrix[:, tid]    (varies per vintage)
    - Forecast  = forecast_matrix[0, tid]  (CI center — oldest vintage forecast)
    - Upper     = upper_ci[:, tid]         (varies per vintage — hindsight scaling)
    - Lower     = lower_ci[:, tid]         (varies per vintage — hindsight scaling)

    X-axis = vintage labels/periods.
    """
    actual_col = bt.actual_matrix[:, tid]
    forecast_center = bt.forecast_matrix[0, tid]  # CI center = oldest vintage forecast
    upper_col = bt.upper_ci[:, tid]   # per-vintage upper CI at this TID
    lower_col = bt.lower_ci[:, tid]   # per-vintage lower CI at this TID

    valid_mask = ~np.isnan(actual_col)
    if not valid_mask.any():
        return

    n_valid = int(valid_mask.sum())
    valid_indices = np.where(valid_mask)[0]
    valid_labels = [bt.vintage_labels[i] for i in valid_indices]
    valid_actuals = actual_col[valid_mask]
    valid_uppers = upper_col[valid_mask]
    valid_lowers = lower_col[valid_mask]

    # Coverage for this TID (per-vintage CI)
    has_ci_mask = ~np.isnan(valid_uppers) & ~np.isnan(valid_lowers)
    has_any_ci = has_ci_mask.any()
    if has_any_ci:
        within = int(np.sum(
            (valid_actuals[has_ci_mask] >= valid_lowers[has_ci_mask]) &
            (valid_actuals[has_ci_mask] <= valid_uppers[has_ci_mask])
        ))
        n_with_ci = int(has_ci_mask.sum())
        coverage = within / n_with_ci
    else:
        within = 0
        n_with_ci = 0
        coverage = 0.0

    # ── Table: vintages as columns, 4 rows ──
    table_data = {'': ['Actual', 'Forecast (CI center)', 'Upper', 'Lower']}
    for j, idx in enumerate(valid_indices):
        lbl = bt.vintage_labels[idx]
        short = lbl.replace('Latest ', '').strip()
        table_data[short] = [
            valid_actuals[j],
            forecast_center,
            valid_uppers[j] if not np.isnan(valid_uppers[j]) else np.nan,
            valid_lowers[j] if not np.isnan(valid_lowers[j]) else np.nan,
        ]
    table_df = pd.DataFrame(table_data)
    num_cols = [c for c in table_df.columns if c != '']
    st.dataframe(
        table_df.style.format({c: '{:.1%}' for c in num_cols}, na_rep=''),
        use_container_width=True, hide_index=True, height=180,
    )

    # ── Chart ──
    fig = go.Figure()

    # Use vintage period dates for x-axis where available
    x_dates = []
    for i in valid_indices:
        p = bt.periods[i]
        x_dates.append(p.strftime('%b %y') if hasattr(p, 'strftime') else str(p))

    # CI shaded band (per-vintage upper/lower → shaped envelope)
    if has_any_ci:
        fig.add_trace(go.Scatter(
            x=x_dates + x_dates[::-1],
            y=valid_uppers.tolist() + valid_lowers[::-1].tolist(),
            fill='toself', fillcolor='rgba(31,119,180,0.12)',
            line=dict(color='rgba(0,0,0,0)'),
            showlegend=False, hoverinfo='skip',
        ))
        # Upper line (varies per vintage)
        fig.add_trace(go.Scatter(
            x=x_dates, y=valid_uppers.tolist(),
            mode='lines', showlegend=False,
            line=dict(color='rgba(31,119,180,0.5)', width=1),
            hovertemplate='Upper: %{y:.2%}<extra></extra>',
        ))
        # Lower line (varies per vintage)
        fig.add_trace(go.Scatter(
            x=x_dates, y=valid_lowers.tolist(),
            mode='lines', showlegend=False,
            line=dict(color='rgba(31,119,180,0.5)', width=1),
            hovertemplate='Lower: %{y:.2%}<extra></extra>',
        ))

    # Forecast center line (CI is symmetric around this)
    if not np.isnan(forecast_center):
        fig.add_trace(go.Scatter(
            x=x_dates, y=[forecast_center] * n_valid,
            mode='lines', name='Forecast (CI center)',
            line=dict(color=BLUE, width=2),
            hovertemplate='Forecast: %{y:.2%}<extra></extra>',
        ))

    # Actual markers — green if within per-vintage CI, red if outside
    colors = []
    for j, a in enumerate(valid_actuals):
        u_j = valid_uppers[j]
        l_j = valid_lowers[j]
        if not np.isnan(u_j) and not np.isnan(l_j) and l_j <= a <= u_j:
            colors.append(GREEN)
        else:
            colors.append(RED)

    fig.add_trace(go.Scatter(
        x=x_dates, y=valid_actuals.tolist(),
        mode='markers', name='Actual',
        marker=dict(
            color=colors, size=6,
            symbol='circle',
            line=dict(width=0.8, color='#333'),
        ),
        hovertemplate='%{x}<br>Actual: %{y:.2%}<extra></extra>',
    ))

    # y-axis range: pad around data
    all_vals = list(valid_actuals)
    if has_any_ci:
        all_vals += [v for v in valid_uppers if not np.isnan(v)]
        all_vals += [v for v in valid_lowers if not np.isnan(v)]
    y_min = min(all_vals) - 0.03
    y_max = max(all_vals) + 0.03

    fig.update_layout(
        title=dict(
            text=f'<b>TID {tid}</b>  Coverage: {coverage:.0%} ({within}/{n_with_ci})',
            font=dict(size=12),
            x=0.01, xanchor='left',
        ),
        xaxis=dict(
            showgrid=False,
            tickangle=-45,
            tickfont=dict(size=7),
            nticks=min(n_valid, 12),
        ),
        yaxis=dict(
            tickformat='.0%',
            range=[y_min, y_max],
            gridcolor='rgba(0,0,0,0.06)',
        ),
        template='plotly_white',
        height=280,
        margin=dict(l=45, r=10, t=40, b=45),
        showlegend=False,
        plot_bgcolor='white',
    )
    st.plotly_chart(fig, use_container_width=True)
