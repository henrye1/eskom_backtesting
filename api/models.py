"""Pydantic request/response models for the LGD API."""

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    file_id: str
    window_sizes: list[int] = Field(default=[12, 18, 24, 30, 36, 42, 48, 54, 60])
    discount_rate: float = 0.15
    lgd_cap: float | None = None
    ci_percentile: float = 0.75
    max_tid: int = 60
    store_detail: bool = False


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "running" | "completed" | "failed"
    error: str | None = None


class ScenarioSummaryRow(BaseModel):
    rank: int
    window_size: int
    n_vintages: int
    n_residuals: int
    rmse: float
    mae: float
    bias: float
    composite_score: float
    latest_lgd_tid0: float
    latest_weighted_lgd: float


class AnalysisSummaryResponse(BaseModel):
    recommended_window: int
    kpi: dict
    scenarios: list[ScenarioSummaryRow]


class BacktestDataResponse(BaseModel):
    forecast: list[list[float | None]]
    actual: list[list[float | None]]
    residual: list[list[float | None]]
    mean_lgd: list[float | None]
    std_lgd: list[float | None]
    mean_matrix: list[list[float | None]]
    upper_ci: list[list[float | None]]
    lower_ci: list[list[float | None]]
    upper_ci_vector: list[float | None]
    lower_ci_vector: list[float | None]
    avg_error_by_tid: list[float | None]
    vintage_labels: list[str]
    periods: list[str]
    hindsights: list[int]
    ci_percentile: float
    z_score: float
    coverage_by_tid: list[float | None]
    overall_coverage: float
    normality_stats: dict


class TidBacktestItem(BaseModel):
    tid: int
    actual: list[float | None]
    mean_val: float | None
    forecast_center: float | None     # oldest vintage forecast — CI center
    upper_vals: list[float | None]    # per-vintage upper CI at this TID
    lower_vals: list[float | None]    # per-vintage lower CI at this TID
    vintage_labels: list[str]
    vintage_indices: list[int]
    coverage: float
    within: int
    total: int


class TidBacktestResponse(BaseModel):
    items: list[TidBacktestItem]


class ConfigDefaultsResponse(BaseModel):
    discount_rate: float
    window_sizes: list[int]
    ci_percentile: float
    max_tid: int
