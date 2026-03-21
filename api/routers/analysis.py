"""Analysis endpoints — submit jobs, poll status, fetch results."""

import json

import numpy as np
from fastapi import APIRouter, HTTPException

from api.models import (
    AnalysisRequest,
    AnalysisSummaryResponse,
    BacktestDataResponse,
    JobStatusResponse,
    ScenarioSummaryRow,
    TidBacktestItem,
    TidBacktestResponse,
)
from api.services import file_store, job_manager
from api.services.chart_builder import build_all_charts
from api.services.serializers import clean_dict, ndarray_to_list, timestamp_to_str

router = APIRouter(prefix="/api", tags=["analysis"])


def _get_completed_job(job_id: str) -> job_manager.JobState:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status == job_manager.JobStatus.RUNNING:
        raise HTTPException(202, "Job still running")
    if job.status == job_manager.JobStatus.FAILED:
        raise HTTPException(500, f"Job failed: {job.error}")
    return job


def _find_scenario(job: job_manager.JobState, window_size: int):
    for s in job.scenarios:
        if s.window_size == window_size:
            return s
    raise HTTPException(404, f"Window size {window_size} not in results")


@router.post("/analysis")
async def start_analysis(req: AnalysisRequest):
    path = file_store.get_file_path(req.file_id)
    if path is None:
        raise HTTPException(404, "File not found — upload first")
    params = req.model_dump()
    job_id = job_manager.submit_job(path, params)
    return {"job_id": job_id, "status": "running"}


@router.get("/analysis/{job_id}/status", response_model=JobStatusResponse)
async def get_status(job_id: str):
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        error=job.error,
    )


@router.get("/analysis/{job_id}/summary", response_model=AnalysisSummaryResponse)
async def get_summary(job_id: str):
    job = _get_completed_job(job_id)
    scenarios = job.scenarios
    if not scenarios:
        raise HTTPException(500, "No scenario results")

    best = scenarios[0]
    rows = []
    for rank, s in enumerate(scenarios, 1):
        rows.append(ScenarioSummaryRow(
            rank=rank,
            window_size=s.window_size,
            n_vintages=s.n_vintages,
            n_residuals=s.n_residuals,
            rmse=round(s.rmse, 6),
            mae=round(s.mae, 6),
            bias=round(s.mean_error, 6),
            composite_score=round(s.composite_score, 6),
            latest_lgd_tid0=round(s.latest_lgd_tid0, 6),
            latest_weighted_lgd=round(s.latest_weighted_lgd, 6),
        ))

    return AnalysisSummaryResponse(
        recommended_window=best.window_size,
        kpi={
            "recommended_window": best.window_size,
            "rmse": round(best.rmse, 6),
            "mae": round(best.mae, 6),
            "bias": round(best.mean_error, 6),
            "lgd_tid0": round(best.latest_lgd_tid0, 6),
        },
        scenarios=rows,
    )


@router.get("/analysis/{job_id}/scenario/{window_size}/backtest")
async def get_backtest(job_id: str, window_size: int):
    job = _get_completed_job(job_id)
    s = _find_scenario(job, window_size)
    bt = s.backtest
    vr = s.vintage_results

    return BacktestDataResponse(
        forecast=ndarray_to_list(bt.forecast_matrix),
        actual=ndarray_to_list(bt.actual_matrix),
        residual=ndarray_to_list(bt.residual_matrix),
        mean_lgd=ndarray_to_list(bt.mean_lgd),
        std_lgd=ndarray_to_list(bt.std_lgd),
        mean_matrix=ndarray_to_list(bt.mean_matrix),
        upper_ci=ndarray_to_list(bt.upper_ci),
        lower_ci=ndarray_to_list(bt.lower_ci),
        upper_ci_vector=ndarray_to_list(bt.upper_ci_vector),
        lower_ci_vector=ndarray_to_list(bt.lower_ci_vector),
        avg_error_by_tid=ndarray_to_list(bt.avg_error_by_tid),
        vintage_labels=bt.vintage_labels,
        periods=[timestamp_to_str(p) for p in bt.periods],
        hindsights=[v.hindsight for v in vr],
        ci_percentile=bt.ci_percentile,
        z_score=bt.z_score,
        coverage_by_tid=ndarray_to_list(bt.coverage_by_tid),
        overall_coverage=bt.overall_coverage,
        normality_stats=clean_dict(bt.normality_stats),
    )


@router.get("/analysis/{job_id}/scenario/{window_size}/tid-backtest")
async def get_tid_backtest(job_id: str, window_size: int):
    job = _get_completed_job(job_id)
    s = _find_scenario(job, window_size)
    bt = s.backtest
    n_v = len(bt.vintage_labels)
    max_tid = min(n_v + 1, bt.actual_matrix.shape[1])

    items = []
    for t in range(max_tid):
        actual_col = bt.actual_matrix[:, t]
        upper_col = bt.upper_ci[:, t]
        lower_col = bt.lower_ci[:, t]
        valid_mask = ~np.isnan(actual_col)
        if not valid_mask.any():
            continue
        valid_indices = np.where(valid_mask)[0].tolist()
        valid_actuals = actual_col[valid_mask]
        valid_uppers = upper_col[valid_mask]
        valid_lowers = lower_col[valid_mask]
        mean_val = float(bt.mean_lgd[t]) if not np.isnan(bt.mean_lgd[t]) else None
        forecast_center = float(bt.forecast_matrix[0, t]) if not np.isnan(bt.forecast_matrix[0, t]) else None

        # Per-vintage upper/lower CI values
        upper_vals = [float(v) if not np.isnan(v) else None for v in valid_uppers]
        lower_vals = [float(v) if not np.isnan(v) else None for v in valid_lowers]

        # Coverage: compare each actual against its own vintage's CI
        n_valid = len(valid_actuals)
        ci_mask = ~np.isnan(valid_uppers) & ~np.isnan(valid_lowers)
        if ci_mask.any():
            within = int(np.sum(
                (valid_actuals[ci_mask] >= valid_lowers[ci_mask]) &
                (valid_actuals[ci_mask] <= valid_uppers[ci_mask])
            ))
        else:
            within = 0
        n_with_ci = int(ci_mask.sum())
        coverage = within / n_with_ci if n_with_ci > 0 else 0.0

        items.append(TidBacktestItem(
            tid=t,
            actual=[float(v) if not np.isnan(v) else None for v in actual_col],
            mean_val=mean_val,
            forecast_center=forecast_center,
            upper_vals=upper_vals,
            lower_vals=lower_vals,
            vintage_labels=[bt.vintage_labels[i] for i in valid_indices],
            vintage_indices=valid_indices,
            coverage=coverage,
            within=within,
            total=n_valid,
        ))
    return TidBacktestResponse(items=items)


@router.get("/analysis/{job_id}/scenario/{window_size}/charts")
async def get_charts(job_id: str, window_size: int):
    job = _get_completed_job(job_id)
    s = _find_scenario(job, window_size)
    charts_json = build_all_charts(s, job.scenarios)
    # Parse JSON strings back to dicts for proper response
    return {name: json.loads(j) for name, j in charts_json.items()}
