"""Side-by-side scenario comparison component.

Lets the user pick any two min-observation windows and view their
LGD term structures, residual profiles, CI bands, and key metrics
together so they can make an informed calibration choice.
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats
import streamlit as st

from lgd_model.scenario import ScenarioResult

BLUE = '#1f77b4'
ORANGE = '#ff7f0e'
GREEN = '#2ca02c'
RED = '#d62728'
PURPLE = '#9467bd'


def _label(s: ScenarioResult) -> str:
    return f"{s.window_size}m"


def render_comparison_selectors(
    scenarios: list[ScenarioResult],
) -> tuple[ScenarioResult, ScenarioResult] | None:
    """Render two drop-downs for picking the comparison pair.

    Returns None if the user picked the same scenario twice.
    """
    ws_options = [s.window_size for s in scenarios]

    col1, col2 = st.columns(2)
    with col1:
        left_ws = st.selectbox(
            "Scenario A",
            options=ws_options,
            index=0,
            format_func=lambda w: f"{w} months"
                + (" (recommended)" if w == scenarios[0].window_size else ""),
            key="cmp_left",
        )
    with col2:
        right_ws = st.selectbox(
            "Scenario B",
            options=ws_options,
            index=min(len(ws_options) - 1, 1),
            format_func=lambda w: f"{w} months"
                + (" (recommended)" if w == scenarios[0].window_size else ""),
            key="cmp_right",
        )

    left = next(s for s in scenarios if s.window_size == left_ws)
    right = next(s for s in scenarios if s.window_size == right_ws)

    if left_ws == right_ws:
        st.warning("Select two different scenarios to compare.")
        return None

    return left, right


def render_metric_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Side-by-side KPI metric cards with deltas."""

    metrics = [
        ("RMSE",           a.rmse,            b.rmse,            "{:.4f}", True),
        ("MAE",            a.mae,             b.mae,             "{:.4f}", True),
        ("Bias",           a.mean_error,      b.mean_error,      "{:+.4f}", None),
        ("Max |Error|",    a.max_abs_error,   b.max_abs_error,   "{:.4f}", True),
        ("Composite",      a.composite_score, b.composite_score, "{:.4f}", True),
        ("LGD TID=0",     a.latest_lgd_tid0, b.latest_lgd_tid0, "{:.2%}", None),
    ]

    cols = st.columns(len(metrics))
    for col, (name, va, vb, fmt, lower_better) in zip(cols, metrics):
        with col:
            delta = vb - va
            delta_str = fmt.format(delta) if delta >= 0 else fmt.format(delta)
            if lower_better is not None:
                delta_color = "inverse" if lower_better else "normal"
            else:
                delta_color = "off"
            st.metric(
                label=name,
                value=f"A: {fmt.format(va)}",
                delta=f"B: {fmt.format(vb)}",
                delta_color=delta_color,
            )


def render_lgd_term_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Overlay the latest-vintage LGD term structures."""

    fig = go.Figure()
    for s, color, dash in [(a, BLUE, 'solid'), (b, ORANGE, 'solid')]:
        latest = s.vintage_results[-1]
        n = len(latest.lgd_term_structure)
        fig.add_trace(go.Scatter(
            x=list(range(n)), y=latest.lgd_term_structure.tolist(),
            mode='lines', name=f'{_label(s)} — Latest',
            line=dict(color=color, width=2, dash=dash),
        ))
        oldest = s.vintage_results[0]
        n_o = len(oldest.lgd_term_structure)
        fig.add_trace(go.Scatter(
            x=list(range(n_o)), y=oldest.lgd_term_structure.tolist(),
            mode='lines', name=f'{_label(s)} — Oldest',
            line=dict(color=color, width=1, dash='dot'),
        ))

    fig.update_layout(
        title='LGD Term Structure — Latest & Oldest Vintages',
        xaxis_title='Time in Default (months)',
        yaxis_title='LGD', yaxis_tickformat='.0%',
        template='plotly_white', height=500,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_forecast_actual_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Side-by-side forecast vs actual for the oldest vintage."""

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[f'Scenario A — {_label(a)}', f'Scenario B — {_label(b)}'],
        shared_yaxes=True,
    )
    n_tid = a.backtest.forecast_matrix.shape[1]
    tids = np.arange(n_tid)

    for col_idx, s in enumerate([a, b], 1):
        bt = s.backtest
        fc = bt.forecast_matrix[0, :]
        ac = bt.actual_matrix[0, :]
        ac_valid = ~np.isnan(ac)
        fig.add_trace(go.Scatter(
            x=tids.tolist(), y=fc.tolist(),
            mode='lines', name='Forecast',
            line=dict(color=BLUE, width=2),
            showlegend=(col_idx == 1),
        ), row=1, col=col_idx)
        fig.add_trace(go.Scatter(
            x=tids[ac_valid].tolist(), y=ac[ac_valid].tolist(),
            mode='lines+markers', name='Actual',
            line=dict(color=ORANGE, width=2), marker=dict(size=3),
            showlegend=(col_idx == 1),
        ), row=1, col=col_idx)

    fig.update_yaxes(tickformat='.0%')
    fig.update_xaxes(title_text='TID')
    fig.update_layout(
        title='Forecast vs Actual — Oldest Vintage',
        template='plotly_white', height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_residual_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Overlaid residual histograms + side-by-side heatmaps."""

    flat_a = a.backtest.residual_matrix[~np.isnan(a.backtest.residual_matrix)]
    flat_b = b.backtest.residual_matrix[~np.isnan(b.backtest.residual_matrix)]

    # Overlaid histograms
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=flat_a.tolist(), nbinsx=30, opacity=0.5,
        marker_color=BLUE, name=f'{_label(a)} ({len(flat_a)} residuals)',
    ))
    fig_hist.add_trace(go.Histogram(
        x=flat_b.tolist(), nbinsx=30, opacity=0.5,
        marker_color=ORANGE, name=f'{_label(b)} ({len(flat_b)} residuals)',
    ))
    fig_hist.update_layout(
        title='Residual Distribution Comparison',
        xaxis_title='Residual', yaxis_title='Frequency',
        barmode='overlay', template='plotly_white', height=400,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # Side-by-side heatmaps
    fig_hm = make_subplots(
        rows=1, cols=2,
        subplot_titles=[f'{_label(a)}', f'{_label(b)}'],
        shared_yaxes=True,
    )
    for col_idx, s in enumerate([a, b], 1):
        bt = s.backtest
        n_tid = bt.residual_matrix.shape[1]
        max_show = min(n_tid, 61)
        fig_hm.add_trace(go.Heatmap(
            z=bt.residual_matrix[:, :max_show].tolist(),
            x=[str(t) for t in range(max_show)],
            y=bt.vintage_labels,
            colorscale='RdBu_r', zmid=0,
            showscale=(col_idx == 2),
            colorbar=dict(title='Residual') if col_idx == 2 else None,
        ), row=1, col=col_idx)

    fig_hm.update_yaxes(autorange='reversed')
    fig_hm.update_xaxes(title_text='TID')
    fig_hm.update_layout(
        title='Residual Heatmap Comparison',
        template='plotly_white', height=500,
    )
    st.plotly_chart(fig_hm, use_container_width=True)


def render_ci_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """CI bands overlay for the oldest vintage."""

    fig = go.Figure()
    n_tid = a.backtest.forecast_matrix.shape[1]
    tids = np.arange(n_tid)

    for s, color, lbl in [(a, BLUE, 'A'), (b, ORANGE, 'B')]:
        bt = s.backtest
        fc0 = bt.forecast_matrix[0, :]
        u0 = bt.upper_ci[0, :]
        l0 = bt.lower_ci[0, :]
        valid = ~np.isnan(u0)
        tv = tids[valid]

        fill_rgba = 'rgba(31,119,180,0.08)' if color == BLUE else 'rgba(255,127,14,0.08)'

        fig.add_trace(go.Scatter(
            x=tv.tolist(), y=u0[valid].tolist(),
            mode='lines', name=f'{_label(s)} Upper CI',
            line=dict(color=color, width=1, dash='dash'),
            legendgroup=lbl,
        ))
        fig.add_trace(go.Scatter(
            x=tv.tolist(), y=l0[valid].tolist(),
            mode='lines', name=f'{_label(s)} Lower CI',
            line=dict(color=color, width=1, dash='dash'),
            fill='tonexty', fillcolor=fill_rgba,
            legendgroup=lbl,
        ))
        fig.add_trace(go.Scatter(
            x=tv.tolist(), y=fc0[valid].tolist(),
            mode='lines', name=f'{_label(s)} Forecast',
            line=dict(color=color, width=2),
            legendgroup=lbl,
        ))

    fig.update_layout(
        title='Confidence Interval Bands — Oldest Vintage',
        xaxis_title='TID', yaxis_title='LGD', yaxis_tickformat='.0%',
        template='plotly_white', height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_error_by_tid_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Overlay average forecast error by TID."""

    fig = go.Figure()
    n_tid = a.backtest.avg_error_by_tid.shape[0]
    tids = np.arange(n_tid)

    for s, color in [(a, BLUE), (b, ORANGE)]:
        err = s.backtest.avg_error_by_tid
        valid = ~np.isnan(err)
        fig.add_trace(go.Bar(
            x=tids[valid].tolist(), y=err[valid].tolist(),
            name=_label(s), marker_color=color, opacity=0.6,
        ))

    fig.add_hline(y=0, line_dash='dash', line_color='black')
    fig.update_layout(
        title='Average Forecast Error by TID',
        xaxis_title='TID', yaxis_title='Error', yaxis_tickformat='.2%',
        barmode='group', template='plotly_white', height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_weighted_lgd_comparison(a: ScenarioResult, b: ScenarioResult) -> None:
    """Weighted LGD over time for both scenarios."""

    fig = go.Figure()
    for s, color in [(a, BLUE), (b, ORANGE)]:
        periods = [
            v.period.strftime('%Y-%m') if hasattr(v.period, 'strftime') else str(v.period)
            for v in s.vintage_results
        ]
        fig.add_trace(go.Scatter(
            x=periods, y=[v.weighted_lgd for v in s.vintage_results],
            mode='lines+markers', name=_label(s),
            line=dict(color=color, width=2), marker=dict(size=4),
        ))

    fig.update_layout(
        title='EAD-Weighted LGD Over Time',
        xaxis_title='Vintage Period', yaxis_title='Weighted LGD',
        yaxis_tickformat='.0%', template='plotly_white', height=450,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_scenario_comparison(
    scenarios: list[ScenarioResult],
) -> None:
    """Full comparison section: selectors + all comparison charts."""

    st.subheader("Scenario Comparison")
    st.caption(
        "Pick any two min-observation windows to compare side by side. "
        "Scenario A is shown in blue, Scenario B in orange."
    )

    pair = render_comparison_selectors(scenarios)
    if pair is None:
        return

    a, b = pair

    # Summary metrics
    render_metric_comparison(a, b)

    # Tabbed comparison charts
    tabs = st.tabs([
        "LGD Term Structure",
        "Forecast vs Actual",
        "Error by TID",
        "CI Bands",
        "Residuals",
        "Weighted LGD",
    ])

    with tabs[0]:
        render_lgd_term_comparison(a, b)
    with tabs[1]:
        render_forecast_actual_comparison(a, b)
    with tabs[2]:
        render_error_by_tid_comparison(a, b)
    with tabs[3]:
        render_ci_comparison(a, b)
    with tabs[4]:
        render_residual_comparison(a, b)
    with tabs[5]:
        render_weighted_lgd_comparison(a, b)
