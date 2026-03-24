"""Main Streamlit dashboard for the LGD Development Factor Model.

Layout matches the Excel LGD Backtest Summary sheet:
1. Backtest summary tables (Forecast, Actual, Difference, Normality tests)
2. Triangle inspection per vintage (Balance, Recovery, CumBal, Discount, LGD)
3. Scenario comparison across window sizes
4. Charts
"""

import sys
import os
import hashlib
import tempfile

import numpy as np
import streamlit as st

# Add src to path so lgd_model is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle
from lgd_model.scenario import run_scenario, ScenarioResult
from lgd_model.export import export_results_to_excel, export_multi_scenario_excel
from lgd_model.dashboard import generate_dashboard

from components.sidebar import render_sidebar
from components.summary_cards import render_summary_cards
from components.tables import render_scenario_table
from components.charts import render_all_charts
from components.backtest_tables import render_backtest_summary
from components.triangle_viewer import render_triangle_viewer
from components.comparison import render_scenario_comparison

st.set_page_config(
    page_title="Development Factor LGD Backtesting",
    page_icon="📊",
    layout="wide",
)

st.title("Development Factor LGD Backtesting")
st.caption("IFRS 9 Loss Given Default estimation using development factors (chain-ladder)")


@st.cache_data
def _load_data(file_bytes: bytes, _file_hash: str):
    """Load recovery triangle from uploaded file bytes, cached by hash."""
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return load_recovery_triangle(tmp_path)
    finally:
        os.unlink(tmp_path)


@st.cache_data(show_spinner="Running multi-scenario analysis...")
def _run_scenarios_cached(
    file_bytes: bytes,
    file_hash: str,
    window_sizes: tuple[int, ...],
    discount_rate: float,
    lgd_cap: float | None,
    ci_percentile: float,
    store_detail: bool,
    max_tid: int = 60,
) -> list[ScenarioResult]:
    """Run multi-scenario analysis, cached on all parameters."""
    master_df = _load_data(file_bytes, file_hash)
    base_config = ModelConfig(
        discount_rate=discount_rate,
        window_size=60,
        max_tid=max_tid,
        lgd_cap=lgd_cap,
        ci_percentile=ci_percentile,
    )

    scenarios: list[ScenarioResult] = []
    for ws in window_sizes:
        result = run_scenario(master_df, ws, base_config, store_detail=store_detail)
        if result is not None:
            scenarios.append(result)

    scenarios.sort(key=lambda s: s.composite_score)
    return scenarios


# Render sidebar (no more "Run Analysis" button — auto-runs on parameter change)
params = render_sidebar()

if params['uploaded_file'] is not None:
    file_bytes = params['uploaded_file'].getvalue()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    if not params['window_sizes']:
        st.error("Please select at least one window size.")
        st.stop()

    scenarios = _run_scenarios_cached(
        file_bytes=file_bytes,
        file_hash=file_hash,
        window_sizes=tuple(sorted(params['window_sizes'])),
        discount_rate=params['discount_rate'],
        lgd_cap=params['lgd_cap'],
        ci_percentile=params['ci_percentile'],
        store_detail=params['store_detail'],
    )

    if not scenarios:
        st.error("No scenarios produced valid results. Check your data.")
        st.stop()

    # KPI cards
    render_summary_cards(scenarios[0])

    # ── Window selector with descriptive label ──
    st.markdown("---")

    best_window = scenarios[0].window_size

    def _format_window(w: int) -> str:
        parts = [f"{w}-month window"]
        s = next((s for s in scenarios if s.window_size == w), None)
        if s is not None:
            parts.append(f"RMSE {s.rmse:.4f}")
            parts.append(f"LGD₀ {s.latest_lgd_tid0:.4f}")
        if w == 60:
            parts.append("full")
        if w == best_window:
            parts.append("★ recommended")
        return " | ".join(parts)

    sel_window = st.selectbox(
        "Review window — select to inspect backtest details below",
        options=[s.window_size for s in scenarios],
        index=next(
            (i for i, s in enumerate(scenarios) if s.window_size == 60),
            0,
        ),
        format_func=_format_window,
    )
    sel_scenario = next(
        (s for s in scenarios if s.window_size == sel_window),
        scenarios[0],
    )

    # ── Active selection banner ──
    st.info(
        f"**Reviewing: {sel_window}-month window** — "
        f"{sel_scenario.n_vintages} vintages, "
        f"{sel_scenario.n_residuals} residuals, "
        f"RMSE {sel_scenario.rmse:.4f}, "
        f"MAE {sel_scenario.mae:.4f}, "
        f"Bias {sel_scenario.mean_error:+.4f}"
    )

    # ── 1. Full Backtest Summary (all tables + per-vintage CI blocks) ──
    render_backtest_summary(sel_scenario)

    # ── 2. Scenario Comparison ──
    st.markdown("---")
    st.subheader("Scenario Comparison — All Min-Observation Windows")
    st.caption(
        "All scenarios use 60-cohort vintages (23 vintages). "
        "Min-obs window controls cohort restriction per TID. "
        "Ranked by composite score (lower = better)."
    )
    render_scenario_table(scenarios)

    # ── 3. Scenario Comparison (pick any two) ──
    if len(scenarios) >= 2:
        st.markdown("---")
        render_scenario_comparison(scenarios)

    # ── 4. Charts ──
    st.markdown("---")
    render_all_charts(scenarios, selected_window=sel_window)

    # ── 5. Triangle Inspection ──
    st.markdown("---")
    render_triangle_viewer(sel_scenario)

    # ── 6. Downloads ──
    st.markdown("---")
    st.subheader("Downloads")
    col1, col2, col3 = st.columns(3)

    with col1:
        tmp_path = tempfile.mktemp(suffix='.xlsx')
        export_multi_scenario_excel(scenarios, tmp_path)
        with open(tmp_path, 'rb') as f:
            data = f.read()
        os.unlink(tmp_path)
        st.download_button(
            "Download Multi-Scenario Excel",
            data=data,
            file_name="LGD_Multi_Scenario_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col2:
        dl_window = st.selectbox(
            "Window for single export",
            options=[s.window_size for s in scenarios],
            index=0,
            key="dl_window",
            format_func=lambda w: f"{w}-month window",
        )
        dl_scenario = next(
            (s for s in scenarios if s.window_size == dl_window),
            scenarios[0],
        )
        tmp_path = tempfile.mktemp(suffix='.xlsx')
        config = ModelConfig(
            discount_rate=params['discount_rate'],
            window_size=dl_window,
            max_tid=60,
            lgd_cap=params['lgd_cap'],
            ci_percentile=params['ci_percentile'],
        )
        export_results_to_excel(
            dl_scenario.vintage_results, dl_scenario.backtest, config, tmp_path
        )
        with open(tmp_path, 'rb') as f:
            data = f.read()
        os.unlink(tmp_path)
        st.download_button(
            f"Download {dl_window}m Window Excel",
            data=data,
            file_name=f"LGD_Model_Output_{dl_window}m.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col3:
        tmp_path = tempfile.mktemp(suffix='.html')
        generate_dashboard(scenarios, output_path=tmp_path)
        with open(tmp_path, 'rb') as f:
            data = f.read()
        os.unlink(tmp_path)
        st.download_button(
            "Download HTML Dashboard",
            data=data,
            file_name="LGD_Dashboard.html",
            mime="text/html",
        )

else:
    st.info("Upload an Excel workbook to begin. Analysis runs automatically.")
