"""Download endpoints for Excel and HTML exports."""

import io
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.services import job_manager

router = APIRouter(prefix="/api", tags=["download"])


def _get_completed_job(job_id: str) -> job_manager.JobState:
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != job_manager.JobStatus.COMPLETED:
        raise HTTPException(400, f"Job not completed (status={job.status.value})")
    return job


@router.get("/analysis/{job_id}/download/multi-scenario-excel")
async def download_multi_scenario_excel(job_id: str):
    job = _get_completed_job(job_id)
    from lgd_model.export import export_multi_scenario_excel

    buf = io.BytesIO()
    export_multi_scenario_excel(job.scenarios, buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=LGD_Multi_Scenario_Output.xlsx"},
    )


@router.get("/analysis/{job_id}/download/single-excel/{window_size}")
async def download_single_excel(job_id: str, window_size: int):
    job = _get_completed_job(job_id)
    scenario = None
    for s in job.scenarios:
        if s.window_size == window_size:
            scenario = s
            break
    if scenario is None:
        raise HTTPException(404, f"Window {window_size} not in results")

    from lgd_model.export import export_single_scenario_excel

    buf = io.BytesIO()
    export_single_scenario_excel(scenario, buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=LGD_{window_size}m_Output.xlsx"},
    )


@router.get("/analysis/{job_id}/download/html-dashboard")
async def download_html_dashboard(job_id: str):
    job = _get_completed_job(job_id)
    from lgd_model.dashboard import generate_html_dashboard

    html = generate_html_dashboard(job.scenarios)
    buf = io.BytesIO(html.encode("utf-8"))
    return StreamingResponse(
        buf,
        media_type="text/html",
        headers={"Content-Disposition": "attachment; filename=LGD_Dashboard.html"},
    )
