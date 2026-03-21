"""Background job manager for analysis tasks."""

import sys
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, "src")

from lgd_model.config import ModelConfig
from lgd_model.data_loader import load_recovery_triangle
from lgd_model.scenario import ScenarioResult, run_multi_scenario


class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobState:
    job_id: str
    status: JobStatus = JobStatus.RUNNING
    error: str | None = None
    scenarios: list[ScenarioResult] = field(default_factory=list)
    config_params: dict = field(default_factory=dict)


_JOBS: dict[str, JobState] = {}
_EXECUTOR = ThreadPoolExecutor(max_workers=2)


def _run_analysis(job_id: str, file_path: str, params: dict) -> None:
    job = _JOBS[job_id]
    try:
        base_config = ModelConfig(
            discount_rate=params.get("discount_rate", 0.15),
            window_size=60,
            max_tid=params.get("max_tid", 60),
            lgd_cap=params.get("lgd_cap"),
            ci_percentile=params.get("ci_percentile", 0.75),
        )
        window_sizes = params.get("window_sizes", [12, 18, 24, 30, 36, 42, 48, 54, 60])
        store_detail = params.get("store_detail", False)

        results = run_multi_scenario(
            filepath=file_path,
            window_sizes=window_sizes,
            base_config=base_config,
            verbose=False,
            store_detail=store_detail,
        )
        job.scenarios = results
        job.status = JobStatus.COMPLETED
    except Exception as e:
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        job.status = JobStatus.FAILED


def submit_job(file_path: str, params: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = JobState(job_id=job_id, config_params=params)
    _JOBS[job_id] = job
    _EXECUTOR.submit(_run_analysis, job_id, file_path, params)
    return job_id


def get_job(job_id: str) -> JobState | None:
    return _JOBS.get(job_id)


def delete_job(job_id: str) -> bool:
    return _JOBS.pop(job_id, None) is not None
