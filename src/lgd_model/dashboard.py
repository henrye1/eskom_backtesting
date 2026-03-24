"""Interactive HTML dashboard generation using Plotly.

Generates a standalone HTML file with 10 charts covering LGD term
structures, backtest diagnostics, and multi-scenario comparisons.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from lgd_model.scenario import ScenarioResult


def generate_dashboard(
    scenarios: list[ScenarioResult],
    output_path: str = 'LGD_Dashboard.html',
    selected_window: int | None = None,
) -> None:
    """Generate a comprehensive interactive HTML dashboard.

    Charts included:
      1. LGD Term Structure by Vintage
      2. Forecast vs Actual — oldest vintage
      3. Average Forecast Error by TID
      4. Confidence Interval Bands
      5. Residual Distribution (histogram)
      6. Window Size Comparison: RMSE / MAE / Bias
      7. LGD Term Structure Comparison across windows
      8. Residual Heatmap
      9. Vintage Weighted LGD over Time
     10. QQ-Plot of Residuals

    Parameters
    ----------
    scenarios : list[ScenarioResult]
        Sorted scenario results.
    output_path : str
        Path for the output HTML file.
    selected_window : int or None
        Window size for detailed charts. If None, uses rank 1.
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.express as px

    if not scenarios:
        print("No scenarios to plot.")
        return

    if selected_window is None:
        sel = scenarios[0]
    else:
        sel = next(
            (s for s in scenarios if s.window_size == selected_window),
            scenarios[0],
        )

    bt = sel.backtest
    vr = sel.vintage_results

    # Colour palette
    BLUE = '#1f77b4'
    ORANGE = '#ff7f0e'
    GREEN = '#2ca02c'
    RED = '#d62728'
    PURPLE = '#9467bd'

    html_parts: list[str] = []
    html_parts.append(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>LGD Development Factor Model &mdash; Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
  h1 {{ color: #333; border-bottom: 3px solid {BLUE}; padding-bottom: 10px; }}
  h2 {{ color: #555; margin-top: 40px; }}
  .chart-container {{ background: white; padding: 20px; margin: 20px 0;
       border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .summary-box {{ background: white; padding: 20px; margin: 20px 0;
       border-radius: 8px; border-left: 4px solid {BLUE};
       box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .metric {{ display: inline-block; margin: 10px 20px; text-align: center; }}
  .metric-value {{ font-size: 24px; font-weight: bold; color: {BLUE}; }}
  .metric-label {{ font-size: 12px; color: #888; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
  th {{ background: {BLUE}; color: white; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  .best {{ background: #e8f5e9 !important; font-weight: bold; }}
</style></head><body>
<h1>LGD Development Factor Model &mdash; Dashboard</h1>
<p>Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')} |
   Entity: Eskom Municipal Debt (Non-Metro) |
   {bt.normality_stats.get('n', 0)} residuals analysed</p>
""")

    # Summary Box
    best = scenarios[0]
    html_parts.append(f"""
<div class="summary-box">
<h2 style="margin-top:0">Recommended Window: {best.window_size} months</h2>
<div class="metric"><div class="metric-value">{best.rmse:.4f}</div><div class="metric-label">RMSE</div></div>
<div class="metric"><div class="metric-value">{best.mae:.4f}</div><div class="metric-label">MAE</div></div>
<div class="metric"><div class="metric-value">{best.mean_error:+.4f}</div><div class="metric-label">Mean Bias</div></div>
<div class="metric"><div class="metric-value">{best.latest_lgd_tid0:.2%}</div><div class="metric-label">LGD at TID=0</div></div>
<div class="metric"><div class="metric-value">{best.latest_weighted_lgd:.2%}</div><div class="metric-label">Wtd LGD</div></div>
<div class="metric"><div class="metric-value">{best.n_vintages}</div><div class="metric-label">Vintages</div></div>
</div>
""")

    # Scenario Comparison Table
    html_parts.append(
        '<div class="chart-container"><h2>Window Size Comparison</h2><table>'
    )
    html_parts.append(
        '<tr><th>Rank</th><th>Window</th><th>Vintages</th><th>Residuals</th>'
        '<th>RMSE</th><th>MAE</th><th>Bias</th><th>Max |Err|</th>'
        '<th>Score</th><th>LGD TID=0</th></tr>'
    )
    for rank, s in enumerate(scenarios, 1):
        cls = ' class="best"' if rank == 1 else ''
        html_parts.append(
            f'<tr{cls}><td>{rank}</td><td>{s.window_size}m</td><td>{s.n_vintages}</td>'
            f'<td>{s.n_residuals}</td><td>{s.rmse:.4f}</td><td>{s.mae:.4f}</td>'
            f'<td>{s.mean_error:+.4f}</td><td>{s.max_abs_error:.4f}</td>'
            f'<td>{s.composite_score:.4f}</td><td>{s.latest_lgd_tid0:.4f}</td></tr>'
        )
    html_parts.append('</table></div>')

    chart_id = 0

    def add_chart_json(fig: go.Figure, title: str = "") -> None:
        nonlocal chart_id
        chart_id += 1
        div_id = f"chart_{chart_id}"
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=60, r=30, t=50, b=50),
            height=500,
            title=dict(text=title, font=dict(size=16)),
        )
        fig_json = fig.to_json()
        html_parts.append(
            f'<div class="chart-container"><div id="{div_id}"></div></div>'
        )
        html_parts.append(
            f'<script>(function(){{ var fig={fig_json}; '
            f'Plotly.newPlot("{div_id}", fig.data, fig.layout, '
            f'{{responsive: true}}); }})();</script>'
        )

    # Chart 1: LGD Term Structure by Vintage
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
        tids = list(range(max_t))
        fig1.add_trace(go.Scatter(
            x=tids, y=v.lgd_term_structure[:max_t].tolist(),
            mode='lines', name=v.vintage_label,
            line=dict(color=colors[idx % len(colors)]),
        ))
    fig1.update_xaxes(title_text='Time in Default (months)')
    fig1.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig1, f'LGD Term Structure by Vintage ({sel.window_size}m window)')

    # Chart 2: Forecast vs Actual — oldest vintage
    fig2 = go.Figure()
    n_tid = bt.forecast_matrix.shape[1]
    fc_oldest = bt.forecast_matrix[0, :]
    ac_oldest = bt.actual_matrix[0, :]
    valid_mask = ~np.isnan(ac_oldest)
    tids_all = np.arange(n_tid)
    fig2.add_trace(go.Scatter(
        x=tids_all.tolist(), y=fc_oldest.tolist(),
        mode='lines', name='Forecast', line=dict(color=BLUE, width=2),
    ))
    fig2.add_trace(go.Scatter(
        x=tids_all[valid_mask].tolist(), y=ac_oldest[valid_mask].tolist(),
        mode='lines+markers', name='Actual',
        line=dict(color=ORANGE, width=2), marker=dict(size=4),
    ))
    fig2.update_xaxes(title_text='Time in Default (months)')
    fig2.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig2, f'Forecast vs Actual — Oldest Vintage ({bt.vintage_labels[0]})')

    # Chart 3: Average Forecast Error by TID
    fig3 = go.Figure()
    avg_err = bt.avg_error_by_tid
    valid_tids = ~np.isnan(avg_err)
    colors_bar = [RED if v > 0 else GREEN for v in avg_err[valid_tids]]
    fig3.add_trace(go.Bar(
        x=tids_all[valid_tids].tolist(), y=avg_err[valid_tids].tolist(),
        marker_color=colors_bar, name='Avg Error',
    ))
    fig3.add_hline(y=0, line_dash='dash', line_color='black')
    fig3.update_xaxes(title_text='Time in Default (months)')
    fig3.update_yaxes(title_text='Average Forecast Error', tickformat='.2%')
    add_chart_json(fig3, f'Average Forecast Error by TID ({sel.window_size}m window)')

    # Chart 4: Confidence Interval Bands
    fig4 = go.Figure()
    mean_lgd = bt.mean_lgd
    upper_ci_0 = bt.upper_ci[0, :]
    lower_ci_0 = bt.lower_ci[0, :]
    valid_ci = ~np.isnan(upper_ci_0)
    t_valid = tids_all[valid_ci]
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=upper_ci_0[valid_ci].tolist(),
        mode='lines', name='Upper CI (SEM Scaled)',
        line=dict(color=BLUE, width=1, dash='dash'),
    ))
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=lower_ci_0[valid_ci].tolist(),
        mode='lines', name='Lower CI (SEM Scaled)',
        line=dict(color=BLUE, width=1, dash='dash'),
        fill='tonexty', fillcolor='rgba(31,119,180,0.1)',
    ))
    fig4.add_trace(go.Scatter(
        x=t_valid.tolist(), y=mean_lgd[valid_ci].tolist(),
        mode='lines', name='Mean LGD',
        line=dict(color=BLUE, width=2),
    ))
    ac_v = bt.actual_matrix[0, :]
    ac_valid = ~np.isnan(ac_v)
    fig4.add_trace(go.Scatter(
        x=tids_all[ac_valid].tolist(), y=ac_v[ac_valid].tolist(),
        mode='markers', name='Actual (oldest vintage)',
        marker=dict(color=ORANGE, size=5),
    ))
    fig4.update_xaxes(title_text='Time in Default (months)')
    fig4.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(
        fig4,
        f'Confidence Interval — SEM Scaled ({sel.window_size}m)',
    )

    # Chart 5: Residual Distribution
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
    fig5.update_xaxes(title_text='Residual (Actual - Forecast)')
    fig5.update_yaxes(title_text='Frequency')
    jb_text = (
        f"JB={ns.get('jarque_bera_stat', 0):.1f}, "
        f"Reject={'Yes' if ns.get('jb_reject') else 'No'}"
    )
    add_chart_json(fig5, f'Residual Distribution ({sel.window_size}m) — {jb_text}')

    # Chart 6: Window Size Comparison (multi-metric bar chart)
    fig6 = make_subplots(
        rows=1, cols=3,
        subplot_titles=('RMSE', 'MAE', 'Mean Bias'),
    )
    ws_labels = [str(s.window_size) for s in scenarios]
    rmses = [s.rmse for s in scenarios]
    maes = [s.mae for s in scenarios]
    biases = [s.mean_error for s in scenarios]
    best_ws = str(scenarios[0].window_size) if scenarios else ''
    rmse_colors = [GREEN if w == best_ws else BLUE for w in ws_labels]
    mae_colors = [GREEN if w == best_ws else ORANGE for w in ws_labels]
    bias_colors = [GREEN if w == best_ws else PURPLE for w in ws_labels]
    fig6.add_trace(
        go.Bar(x=ws_labels, y=rmses, marker_color=rmse_colors,
               name='RMSE', showlegend=False),
        row=1, col=1,
    )
    fig6.add_trace(
        go.Bar(x=ws_labels, y=maes, marker_color=mae_colors,
               name='MAE', showlegend=False),
        row=1, col=2,
    )
    fig6.add_trace(
        go.Bar(x=ws_labels, y=biases, marker_color=bias_colors,
               name='Bias', showlegend=False),
        row=1, col=3,
    )
    fig6.update_xaxes(title_text='Window (months)')
    fig6.update_layout(height=400)
    add_chart_json(fig6, 'Error Metrics by Window Size')

    # Chart 7: LGD Term Structure Comparison across windows
    fig7 = go.Figure()
    for s in scenarios:
        latest_v = s.vintage_results[-1]
        max_t = min(s.window_size + 1, len(latest_v.lgd_term_structure))
        tids_s = list(range(max_t))
        fig7.add_trace(go.Scatter(
            x=tids_s, y=latest_v.lgd_term_structure[:max_t].tolist(),
            mode='lines', name=f'{s.window_size}m',
            line=dict(width=2 if s.window_size == best.window_size else 1),
        ))
    fig7.update_xaxes(title_text='Time in Default (months)')
    fig7.update_yaxes(title_text='LGD', tickformat='.0%')
    add_chart_json(fig7, 'Latest Vintage LGD — Comparison Across Window Sizes')

    # Chart 8: Residual Heatmap
    fig8 = go.Figure()
    resid = bt.residual_matrix.copy()
    max_show = min(n_tid, sel.window_size + 1)
    resid_show = resid[:, :max_show]
    fig8.add_trace(go.Heatmap(
        z=resid_show.tolist(),
        x=[str(t) for t in range(max_show)],
        y=bt.vintage_labels,
        colorscale='RdBu_r', zmid=0,
        colorbar=dict(title='Residual'),
    ))
    fig8.update_xaxes(title_text='TID')
    fig8.update_yaxes(title_text='Vintage', autorange='reversed')
    add_chart_json(fig8, f'Residual Heatmap ({sel.window_size}m window)')

    # Chart 9: Vintage Weighted LGD over Time
    fig9 = go.Figure()
    periods = [v.period for v in vr]
    wlgds = [v.weighted_lgd for v in vr]
    fig9.add_trace(go.Scatter(
        x=[
            p.strftime('%Y-%m') if hasattr(p, 'strftime') else str(p)
            for p in periods
        ],
        y=wlgds, mode='lines+markers', name='Weighted LGD',
        line=dict(color=BLUE, width=2), marker=dict(size=5),
    ))
    fig9.update_xaxes(title_text='Vintage Period')
    fig9.update_yaxes(title_text='EAD-Weighted LGD', tickformat='.0%')
    add_chart_json(fig9, f'EAD-Weighted LGD Over Time ({sel.window_size}m window)')

    # Chart 10: QQ Plot
    fig10 = go.Figure()
    sorted_r = np.sort(flat_r)
    n_r = len(sorted_r)
    theoretical_q = stats.norm.ppf(
        (np.arange(1, n_r + 1) - 0.5) / n_r,
        loc=ns.get('mean', 0),
        scale=ns.get('std', 1),
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
    fig10.update_xaxes(title_text='Theoretical Quantiles (Normal)')
    fig10.update_yaxes(title_text='Sample Quantiles')
    add_chart_json(fig10, 'QQ-Plot of Residuals — Normality Check')

    # Close HTML
    html_parts.append("""
<div class="summary-box">
<h2 style="margin-top:0">Methodology Notes</h2>
<p><strong>Composite Score</strong> weights: 20% bias ratio, 35% RMSE, 25% MAE, 20% tail severity. Lower is better.</p>
<p><strong>Confidence Intervals</strong>: SEM-based with term-point scaling &mdash;
Upper = MIN(1, Mean + z &times; StdDev &times; &radic;(N_steps / N_vintages)),
Lower = MAX(0, Mean &minus; z &times; StdDev &times; &radic;(N_steps / N_vintages)).
Bands widen at longer horizons. z derived from user-configurable percentile via norm.ppf.</p>
<p><strong>Residual</strong> = Actual &minus; Forecast. Positive &rarr; model underestimated LGD (too optimistic).</p>
</div>
</body></html>""")

    html_content = '\n'.join(html_parts)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\n  Dashboard saved to: {output_path}")
