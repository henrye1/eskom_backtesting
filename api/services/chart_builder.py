"""Build Plotly figures from scenario results — reuses chart logic server-side."""

import warnings

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lgd_model.scenario import ScenarioResult


def _fmt_pct(v: float) -> str:
    return f"{v:.1%}"


def build_lgd_term_structure(scenario: ScenarioResult) -> go.Figure:
    fig = go.Figure()
    vr_list = scenario.vintage_results
    n = len(vr_list)
    step = max(1, n // 8)
    indices = list(range(0, n, step))
    if n - 1 not in indices:
        indices.append(n - 1)
    for idx in indices:
        v = vr_list[idx]
        lgd = v.lgd_term_structure
        fig.add_trace(go.Scatter(
            x=list(range(len(lgd))), y=lgd.tolist(),
            mode="lines", name=v.vintage_label,
        ))
    fig.update_layout(
        title="LGD Term Structure by Vintage",
        xaxis_title="TID", yaxis_title="LGD",
        yaxis_tickformat=".0%", template="plotly_white", height=420,
    )
    return fig


def build_forecast_vs_actual(scenario: ScenarioResult) -> go.Figure:
    bt = scenario.backtest
    fig = go.Figure()
    n_tid = bt.forecast_matrix.shape[1]
    tids = list(range(n_tid))
    fig.add_trace(go.Scatter(
        x=tids, y=bt.forecast_matrix[0, :].tolist(),
        mode="lines", name="Forecast (oldest)",
    ))
    actual_row = bt.actual_matrix[0, :]
    valid = ~np.isnan(actual_row)
    fig.add_trace(go.Scatter(
        x=[t for t in tids if valid[t]],
        y=[float(actual_row[t]) for t in tids if valid[t]],
        mode="lines+markers", name="Actual",
    ))
    fig.update_layout(
        title="Forecast vs Actual — Oldest Vintage",
        xaxis_title="TID", yaxis_title="LGD",
        yaxis_tickformat=".0%", template="plotly_white", height=420,
    )
    return fig


def build_avg_error_by_tid(scenario: ScenarioResult) -> go.Figure:
    bt = scenario.backtest
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        avg_err = np.nanmean(bt.residual_matrix, axis=0)
    n = len(avg_err)
    colors = ["#d62728" if v > 0 else "#2ca02c" for v in avg_err]
    fig = go.Figure(go.Bar(
        x=list(range(n)), y=avg_err.tolist(),
        marker_color=colors,
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1)
    fig.update_layout(
        title="Average Forecast Error by TID",
        xaxis_title="TID", yaxis_title="Error",
        yaxis_tickformat=".1%", template="plotly_white", height=420,
    )
    return fig


def build_ci_bands(scenario: ScenarioResult) -> go.Figure:
    """CI bands chart for the oldest vintage (i=0).

    Uses per-cell CI values (upper_ci[0, :] / lower_ci[0, :]) which vary
    by TID because the oldest vintage has the most hindsight.
    """
    bt = scenario.backtest
    n_tid = len(bt.mean_lgd)
    tids = list(range(n_tid))
    # Use per-vintage CI for oldest vintage (row 0)
    upper = bt.upper_ci[0, :]
    lower = bt.lower_ci[0, :]
    valid = ~np.isnan(upper)
    vt = [t for t in tids if valid[t]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=vt + vt[::-1],
        y=[float(upper[t]) for t in vt] + [float(lower[t]) for t in reversed(vt)],
        fill="toself", fillcolor="rgba(31,119,180,0.15)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False,
    ))
    forecast_oldest = bt.forecast_matrix[0, :]  # CI center
    fig.add_trace(go.Scatter(
        x=vt, y=[float(forecast_oldest[t]) for t in vt],
        mode="lines", name="Forecast (CI center)", line=dict(color="#1f77b4", width=2),
    ))
    actual_row = bt.actual_matrix[0, :]
    va = ~np.isnan(actual_row)
    fig.add_trace(go.Scatter(
        x=[t for t in tids if va[t]],
        y=[float(actual_row[t]) for t in tids if va[t]],
        mode="markers", name="Actual (oldest)", marker=dict(size=5, color="#ff7f0e"),
    ))
    fig.update_layout(
        title="Confidence Interval Bands (Oldest Vintage)",
        xaxis_title="TID", yaxis_title="LGD",
        yaxis_tickformat=".0%", template="plotly_white", height=420,
    )
    return fig


def build_residual_histogram(scenario: ScenarioResult) -> go.Figure:
    bt = scenario.backtest
    flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
    ns = bt.normality_stats
    jb_txt = f"JB={ns.get('jarque_bera_stat', 0):.2f} ({'Reject' if ns.get('jb_reject') else 'Accept'})"
    fig = go.Figure(go.Histogram(
        x=flat.tolist(), nbinsx=30, histnorm="probability density",
        marker_color="rgba(31,119,180,0.7)",
    ))
    from scipy.stats import norm
    mu, sigma = float(np.mean(flat)), float(np.std(flat, ddof=1))
    x_range = np.linspace(mu - 4 * sigma, mu + 4 * sigma, 200)
    fig.add_trace(go.Scatter(
        x=x_range.tolist(), y=norm.pdf(x_range, mu, sigma).tolist(),
        mode="lines", name="Normal PDF", line=dict(color="#d62728", width=2),
    ))
    fig.update_layout(
        title=f"Residual Distribution — {jb_txt}",
        xaxis_title="Residual", yaxis_title="Density",
        template="plotly_white", height=420,
    )
    return fig


def build_window_comparison(scenarios: list[ScenarioResult]) -> go.Figure:
    if len(scenarios) < 2:
        return go.Figure()
    best_ws = scenarios[0].window_size
    windows = [s.window_size for s in scenarios]
    rmses = [s.rmse for s in scenarios]
    maes = [s.mae for s in scenarios]
    biases = [s.mean_error for s in scenarios]
    colors = ["#2ca02c" if w == best_ws else "#1f77b4" for w in windows]
    labels = [f"{w}m" for w in windows]

    fig = make_subplots(rows=1, cols=3, subplot_titles=["RMSE", "MAE", "Bias"])
    fig.add_trace(go.Bar(x=labels, y=rmses, marker_color=colors, showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=maes, marker_color=colors, showlegend=False), row=1, col=2)
    fig.add_trace(go.Bar(x=labels, y=biases, marker_color=colors, showlegend=False), row=1, col=3)
    fig.update_layout(title="Window Size Comparison", template="plotly_white", height=400)
    return fig


def build_lgd_comparison(scenarios: list[ScenarioResult]) -> go.Figure:
    fig = go.Figure()
    best_ws = scenarios[0].window_size if scenarios else None
    for s in scenarios:
        lgd = s.vintage_results[-1].lgd_term_structure
        width = 3 if s.window_size == best_ws else 1.5
        fig.add_trace(go.Scatter(
            x=list(range(len(lgd))), y=lgd.tolist(),
            mode="lines", name=f"{s.window_size}m",
            line=dict(width=width),
        ))
    fig.update_layout(
        title="LGD Term Structure Comparison (Latest Vintage)",
        xaxis_title="TID", yaxis_title="LGD",
        yaxis_tickformat=".0%", template="plotly_white", height=420,
    )
    return fig


def build_residual_heatmap(scenario: ScenarioResult) -> go.Figure:
    bt = scenario.backtest
    n_v = len(bt.vintage_labels)
    max_tid = min(n_v + 1, bt.residual_matrix.shape[1])
    matrix = bt.residual_matrix[:, :max_tid].copy()
    matrix = np.where(np.isnan(matrix), None, matrix)
    fig = go.Figure(go.Heatmap(
        z=matrix.tolist(),
        x=[str(t) for t in range(max_tid)],
        y=bt.vintage_labels,
        colorscale="RdBu_r", zmid=0,
        colorbar=dict(title="Residual", tickformat=".1%"),
    ))
    fig.update_layout(
        title="Residual Heatmap",
        xaxis_title="TID", yaxis_title="Vintage",
        template="plotly_white", height=500,
    )
    return fig


def build_weighted_lgd_over_time(scenario: ScenarioResult) -> go.Figure:
    vr = scenario.vintage_results
    labels = [v.vintage_label for v in vr]
    wlgd = [v.weighted_lgd for v in vr]
    fig = go.Figure(go.Scatter(
        x=labels, y=wlgd, mode="lines+markers",
        marker=dict(size=6), line=dict(width=2),
    ))
    fig.update_layout(
        title="Vintage Weighted LGD Over Time",
        xaxis_title="Vintage", yaxis_title="Weighted LGD",
        yaxis_tickformat=".0%", template="plotly_white", height=420,
        xaxis_tickangle=-45,
    )
    return fig


def build_qq_plot(scenario: ScenarioResult) -> go.Figure:
    from scipy.stats import probplot
    bt = scenario.backtest
    flat = bt.residual_matrix[~np.isnan(bt.residual_matrix)]
    (osm, osr), (slope, intercept, _) = probplot(flat, dist="norm")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=osm.tolist(), y=osr.tolist(),
        mode="markers", name="Sample", marker=dict(size=4),
    ))
    line_x = [float(osm.min()), float(osm.max())]
    line_y = [slope * line_x[0] + intercept, slope * line_x[1] + intercept]
    fig.add_trace(go.Scatter(
        x=line_x, y=line_y, mode="lines", name="Reference",
        line=dict(color="red", dash="dash"),
    ))
    fig.update_layout(
        title="Q-Q Plot (Residuals vs Normal)",
        xaxis_title="Theoretical Quantiles", yaxis_title="Sample Quantiles",
        template="plotly_white", height=420,
    )
    return fig


def build_all_charts(
    scenario: ScenarioResult,
    all_scenarios: list[ScenarioResult],
) -> dict[str, str]:
    """Build all 10 charts, return dict of name → Plotly JSON string."""
    charts = {
        "lgd_term_structure": build_lgd_term_structure(scenario),
        "forecast_vs_actual": build_forecast_vs_actual(scenario),
        "avg_error_by_tid": build_avg_error_by_tid(scenario),
        "ci_bands": build_ci_bands(scenario),
        "residual_histogram": build_residual_histogram(scenario),
        "window_comparison": build_window_comparison(all_scenarios),
        "lgd_comparison": build_lgd_comparison(all_scenarios),
        "residual_heatmap": build_residual_heatmap(scenario),
        "weighted_lgd": build_weighted_lgd_over_time(scenario),
        "qq_plot": build_qq_plot(scenario),
    }
    return {name: fig.to_json() for name, fig in charts.items()}
