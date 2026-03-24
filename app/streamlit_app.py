"""Main Streamlit dashboard for the Municipal LGD Development Factor Model.

Layout matches the Excel LGD Backtest Summary sheet:
1. Backtest summary tables (Forecast, Actual, Difference, Normality tests)
2. Triangle inspection per vintage (Balance, Recovery, CumBal, Discount, LGD)
3. Scenario comparison across window sizes
4. Charts
"""
from __future__ import annotations

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
    page_title="Municipal LGD Backtesting",
    page_icon="📊",
    layout="wide",
)

st.title("Municipal LGD Backtesting")
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


def _run_scenarios_uncached(
    file_bytes: bytes,
    file_hash: str,
    window_sizes: tuple[int, ...],
    discount_rate: float,
    lgd_cap: float | None,
    ci_percentile: float = 0.75,
    store_detail: bool = False,
    max_tid: int = 60,
    window_size: int = 60,
) -> list[ScenarioResult]:
    """Run multi-scenario analysis."""
    master_df = _load_data(file_bytes, file_hash)

    n_cohorts = len(master_df)
    st.sidebar.info(
        f"Data: {n_cohorts} cohorts, "
        f"{master_df['Period'].min().strftime('%Y-%m')} to "
        f"{master_df['Period'].max().strftime('%Y-%m')}"
    )

    base_config = ModelConfig(
        discount_rate=discount_rate,
        window_size=window_size,
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


# Render sidebar
params = render_sidebar()

if params['uploaded_file'] is not None and params['run_clicked']:
    file_bytes = params['uploaded_file'].getvalue()
    file_hash = hashlib.md5(file_bytes).hexdigest()

    if not params['window_sizes']:
        st.error("Please select at least one window size.")
        st.stop()

    # Add toggle for triangle detail storage
    store_detail = st.sidebar.checkbox(
        "Store triangle details (for inspection)",
        value=True,
        help="Enable to inspect balance matrices, recovery vectors, etc. per vintage.",
    )

    with st.spinner("Running multi-scenario analysis..."):
        scenarios = _run_scenarios_uncached(
            file_bytes=file_bytes,
            file_hash=file_hash,
            window_sizes=tuple(sorted(params['window_sizes'])),
            discount_rate=params['discount_rate'],
            lgd_cap=params['lgd_cap'],
            ci_percentile=params['ci_percentile'],
            store_detail=store_detail,
            max_tid=params['max_tid'],
            window_size=params['window_size'],
        )

    if not scenarios:
        st.error("No scenarios produced valid results. Check your data.")
        st.stop()

    # KPI cards
    render_summary_cards(scenarios[0])

    # -- Window selector (applies to all sections) --
    st.markdown("---")
    sel_window = st.selectbox(
        "Select min-observation window",
        options=[s.window_size for s in scenarios],
        index=next(
            (i for i, s in enumerate(scenarios) if s.window_size == params['window_size']),
            0,
        ),
        format_func=lambda w: f"{w} months"
            + (" (full)" if w == params['window_size'] else "")
            + (" (recommended)" if w == scenarios[0].window_size else ""),
    )
    sel_scenario = next(
        (s for s in scenarios if s.window_size == sel_window),
        scenarios[0],
    )

    # -- 1. Full Backtest Summary (all tables + per-vintage CI blocks) --
    render_backtest_summary(sel_scenario)

    # -- 2. Scenario Comparison --
    st.markdown("---")
    st.subheader("Scenario Comparison -- All Min-Observation Windows")
    st.caption(
        f"All scenarios use {params['window_size']}-cohort vintages. "
        "Min-obs window controls cohort restriction per TID. "
        "Ranked by composite score (lower = better)."
    )
    render_scenario_table(scenarios)

    # -- 3. Scenario Comparison (pick any two) --
    if len(scenarios) >= 2:
        st.markdown("---")
        render_scenario_comparison(scenarios)

    # -- 4. Charts --
    st.markdown("---")
    render_all_charts(scenarios, selected_window=sel_window)

    # -- 5. Triangle Inspection --
    st.markdown("---")
    render_triangle_viewer(sel_scenario)

    # -- 6. Downloads --
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
        )
        dl_scenario = next(
            (s for s in scenarios if s.window_size == dl_window),
            scenarios[0],
        )
        tmp_path = tempfile.mktemp(suffix='.xlsx')
        config = ModelConfig(
            discount_rate=params['discount_rate'],
            window_size=dl_window,
            max_tid=params['max_tid'],
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

elif params['uploaded_file'] is None:
    st.info("Upload an Excel workbook and click **Run Analysis** to begin.")
else:
    st.info("Click **Run Analysis** to start the computation.")
