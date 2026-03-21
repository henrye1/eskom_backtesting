"""Chart rendering components for the Streamlit dashboard.

All 10 charts from the static dashboard, rendered with st.plotly_chart.
"""

import numpy as np
import plotly.express as px
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


def render_all_charts(
    scenarios: list[ScenarioResult],
    selected_window: int | None = None,
) -> None:
    """Render all 10 charts in Streamlit tabs.

    Parameters
    ----------
    scenarios : list[ScenarioResult]
        Sorted scenario results.
    selected_window : int or None
        Window to show detailed charts for. Defaults to best.
    """
    if selected_window is None:
        sel = scenarios[0]
    else:
        sel = next(
            (s for s in scenarios if s.window_size == selected_window),
            scenarios[0],
        )

    bt = sel.backtest
    vr = sel.vintage_results
    best = scenarios[0]
    n_tid = bt.forecast_matrix.shape[1]
    tids_all = np.arange(n_tid)

    tabs = st.tabs([
        "Term Structure",
        "Forecast vs Actual",
        "Error by TID",
        "Confidence Intervals",
        "Residual Distribution",
        "Window Comparison",
        "LGD Comparison",
        "Residual Heatmap",
        "Weighted LGD",
        "QQ-Plot",
    ])

    # Tab 1: LGD Term Structure by Vintage
    with tabs[0]:
        fig1 = go.Figure()
        n_show = min(len(vr), 8)
        step = max(1, len(vr) // n_show)
        indices = list(range(0, len(vr), step))
        if len(vr) - 1 not in indices:
            indices.append(len(vr) - 1)
        colors = px.colors.qualitative.Set2
        for idx, vi in enumerate(indices):
            v = vr[vi]
            max_t = min(sel.window_size + 1, len(v.lgd_term_structure))
            fig1.add_trace(go.Scatter(
                x=list(range(max_t)),
                y=v.lgd_term_structure[:max_t].tolist(),
                mode='lines', name=v.vintage_label,
                line=dict(color=colors[idx % len(colors)]),
            ))
        fig1.update_layout(
            title=f'LGD Term Structure by Vintage ({sel.window_size}m window)',
            xaxis_title='Time in Default (months)',
            yaxis_title='LGD', yaxis_tickformat='.0%',
            template='plotly_white',
        )
        st.plotly_chart(fig1, use_container_width=True)

    # Tab 2: Forecast vs Actual
    with tabs[1]:
        fig2 = go.Figure()
        fc_oldest = bt.forecast_matrix[0, :]
        ac_oldest = bt.actual_matrix[0, :]
        valid_mask = ~np.isnan(ac_oldest)
        fig2.add_trace(go.Scatter(
            x=tids_all.tolist(), y=fc_oldest.tolist(),
            mode='lines', name='Forecast', line=dict(color=BLUE, width=2),
        ))
        fig2.add_trace(go.Scatter(
            x=tids_all[valid_mask].tolist(), y=ac_oldest[valid_mask].tolist(),
            mode='lines+markers', name='Actual',
            line=dict(color=ORANGE, width=2), marker=dict(size=4),
        ))
        fig2.update_layout(
            title=f'Forecast vs Actual — Oldest Vintage ({bt.vintage_labels[0]})',
            xaxis_title='Time in Default (months)',
            yaxis_title='LGD', yaxis_tickformat='.0%',
            template='plotly_white',
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Tab 3: Average Forecast Error by TID
    with tabs[2]:
        fig3 = go.Figure()
        avg_err = bt.avg_error_by_tid
        valid_tids = ~np.isnan(avg_err)
        colors_bar = [RED if v > 0 else GREEN for v in avg_err[valid_tids]]
        fig3.add_trace(go.Bar(
            x=tids_all[valid_tids].tolist(), y=avg_err[valid_tids].tolist(),
            marker_color=colors_bar, name='Avg Error',
        ))
        fig3.add_hline(y=0, line_dash='dash', line_color='black')
        fig3.update_layout(
            title=f'Average Forecast Error by TID ({sel.window_size}m window)',
            xaxis_title='Time in Default (months)',
            yaxis_title='Average Forecast Error', yaxis_tickformat='.2%',
            template='plotly_white',
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Tab 4: Confidence Interval Bands
    with tabs[3]:
        fig4 = go.Figure()
        forecast_oldest = bt.forecast_matrix[0, :]  # CI center
        upper_ci_0 = bt.upper_ci[0, :]
        lower_ci_0 = bt.lower_ci[0, :]
        valid_ci = ~np.isnan(upper_ci_0)
        t_valid = tids_all[valid_ci]
        fig4.add_trace(go.Scatter(
            x=t_valid.tolist(), y=upper_ci_0[valid_ci].tolist(),
            mode='lines', name='Upper CI',
            line=dict(color=BLUE, width=1, dash='dash'),
        ))
        fig4.add_trace(go.Scatter(
            x=t_valid.tolist(), y=lower_ci_0[valid_ci].tolist(),
            mode='lines', name='Lower CI',
            line=dict(color=BLUE, width=1, dash='dash'),
            fill='tonexty', fillcolor='rgba(31,119,180,0.1)',
        ))
        fig4.add_trace(go.Scatter(
            x=t_valid.tolist(), y=forecast_oldest[valid_ci].tolist(),
            mode='lines', name='Forecast (oldest vintage)',
            line=dict(color=BLUE, width=2),
        ))
        ac_v = bt.actual_matrix[0, :]
        ac_valid = ~np.isnan(ac_v)
        fig4.add_trace(go.Scatter(
            x=tids_all[ac_valid].tolist(), y=ac_v[ac_valid].tolist(),
            mode='markers', name='Actual (oldest vintage)',
            marker=dict(color=ORANGE, size=5),
        ))
        fig4.update_layout(
            title=f'Confidence Interval — SEM Scaled ({sel.window_size}m)',
            xaxis_title='Time in Default (months)',
            yaxis_title='LGD', yaxis_tickformat='.0%',
            template='plotly_white',
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Tab 5: Residual Distribution
    with tabs[4]:
        flat_r = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        fig5 = go.Figure()
        fig5.add_trace(go.Histogram(
            x=flat_r.tolist(), nbinsx=30,
            marker_color=BLUE, opacity=0.7, name='Residuals',
        ))
        ns = bt.normality_stats
        if 'mean' in ns and 'std' in ns:
            x_norm = np.linspace(flat_r.min(), flat_r.max(), 100)
            y_norm = stats.norm.pdf(x_norm, ns['mean'], ns['std'])
            bin_width = (flat_r.max() - flat_r.min()) / 30
            y_norm_scaled = y_norm * len(flat_r) * bin_width
            fig5.add_trace(go.Scatter(
                x=x_norm.tolist(), y=y_norm_scaled.tolist(),
                mode='lines', name='Normal fit',
                line=dict(color=RED, width=2, dash='dash'),
            ))
        jb_text = (
            f"JB={ns.get('jarque_bera_stat', 0):.1f}, "
            f"Reject={'Yes' if ns.get('jb_reject') else 'No'}"
        )
        fig5.update_layout(
            title=f'Residual Distribution ({sel.window_size}m) — {jb_text}',
            xaxis_title='Residual (Actual - Forecast)',
            yaxis_title='Frequency',
            template='plotly_white',
        )
        st.plotly_chart(fig5, use_container_width=True)

    # Tab 6: Window Size Comparison
    with tabs[5]:
        fig6 = make_subplots(
            rows=1, cols=3,
            subplot_titles=('RMSE', 'MAE', 'Mean Bias'),
        )
        ws_labels = [str(s.window_size) for s in scenarios]
        best_ws = str(scenarios[0].window_size)
        rmse_c = [GREEN if w == best_ws else BLUE for w in ws_labels]
        mae_c = [GREEN if w == best_ws else ORANGE for w in ws_labels]
        bias_c = [GREEN if w == best_ws else PURPLE for w in ws_labels]
        fig6.add_trace(go.Bar(
            x=ws_labels, y=[s.rmse for s in scenarios],
            marker_color=rmse_c, showlegend=False), row=1, col=1)
        fig6.add_trace(go.Bar(
            x=ws_labels, y=[s.mae for s in scenarios],
            marker_color=mae_c, showlegend=False), row=1, col=2)
        fig6.add_trace(go.Bar(
            x=ws_labels, y=[s.mean_error for s in scenarios],
            marker_color=bias_c, showlegend=False), row=1, col=3)
        fig6.update_xaxes(title_text='Window (months)')
        fig6.update_layout(height=400, template='plotly_white')
        st.plotly_chart(fig6, use_container_width=True)

    # Tab 7: LGD Term Structure Comparison
    with tabs[6]:
        fig7 = go.Figure()
        for s in scenarios:
            latest_v = s.vintage_results[-1]
            max_t = min(s.window_size + 1, len(latest_v.lgd_term_structure))
            fig7.add_trace(go.Scatter(
                x=list(range(max_t)),
                y=latest_v.lgd_term_structure[:max_t].tolist(),
                mode='lines', name=f'{s.window_size}m',
                line=dict(width=2 if s.window_size == best.window_size else 1),
            ))
        fig7.update_layout(
            title='Latest Vintage LGD — Comparison Across Window Sizes',
            xaxis_title='Time in Default (months)',
            yaxis_title='LGD', yaxis_tickformat='.0%',
            template='plotly_white',
        )
        st.plotly_chart(fig7, use_container_width=True)

    # Tab 8: Residual Heatmap
    with tabs[7]:
        fig8 = go.Figure()
        resid = bt.residual_matrix.copy()
        max_show = min(n_tid, sel.window_size + 1)
        fig8.add_trace(go.Heatmap(
            z=resid[:, :max_show].tolist(),
            x=[str(t) for t in range(max_show)],
            y=bt.vintage_labels,
            colorscale='RdBu_r', zmid=0,
            colorbar=dict(title='Residual'),
        ))
        fig8.update_layout(
            title=f'Residual Heatmap ({sel.window_size}m window)',
            xaxis_title='TID',
            yaxis_title='Vintage', yaxis_autorange='reversed',
            template='plotly_white',
        )
        st.plotly_chart(fig8, use_container_width=True)

    # Tab 9: Vintage Weighted LGD
    with tabs[8]:
        fig9 = go.Figure()
        periods = [
            v.period.strftime('%Y-%m') if hasattr(v.period, 'strftime') else str(v.period)
            for v in vr
        ]
        fig9.add_trace(go.Scatter(
            x=periods, y=[v.weighted_lgd for v in vr],
            mode='lines+markers', name='Weighted LGD',
            line=dict(color=BLUE, width=2), marker=dict(size=5),
        ))
        fig9.update_layout(
            title=f'EAD-Weighted LGD Over Time ({sel.window_size}m window)',
            xaxis_title='Vintage Period',
            yaxis_title='EAD-Weighted LGD', yaxis_tickformat='.0%',
            template='plotly_white',
        )
        st.plotly_chart(fig9, use_container_width=True)

    # Tab 10: QQ-Plot
    with tabs[9]:
        flat_r = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
        fig10 = go.Figure()
        sorted_r = np.sort(flat_r)
        n_r = len(sorted_r)
        ns = bt.normality_stats
        theoretical_q = stats.norm.ppf(
            (np.arange(1, n_r + 1) - 0.5) / n_r,
            loc=ns.get('mean', 0), scale=ns.get('std', 1),
        )
        fig10.add_trace(go.Scatter(
            x=theoretical_q.tolist(), y=sorted_r.tolist(),
            mode='markers', name='Residuals',
            marker=dict(color=BLUE, size=4, opacity=0.6),
        ))
        min_v = min(theoretical_q.min(), sorted_r.min())
        max_v = max(theoretical_q.max(), sorted_r.max())
        fig10.add_trace(go.Scatter(
            x=[min_v, max_v], y=[min_v, max_v],
            mode='lines', name='45deg line',
            line=dict(color=RED, dash='dash'),
        ))
        fig10.update_layout(
            title='QQ-Plot of Residuals — Normality Check',
            xaxis_title='Theoretical Quantiles (Normal)',
            yaxis_title='Sample Quantiles',
            template='plotly_white',
        )
        st.plotly_chart(fig10, use_container_width=True)
