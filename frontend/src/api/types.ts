export interface UploadResponse {
  file_id: string;
  filename: string;
  size_bytes: number;
}

export interface AnalysisRequest {
  file_id: string;
  window_sizes: number[];
  discount_rate: number;
  lgd_cap: number | null;
  ci_percentile: number;
  max_tid: number;
  store_detail: boolean;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'running' | 'completed' | 'failed';
  error?: string;
}

export interface ScenarioSummaryRow {
  rank: number;
  window_size: number;
  n_vintages: number;
  n_residuals: number;
  rmse: number;
  mae: number;
  bias: number;
  composite_score: number;
  latest_lgd_tid0: number;
  latest_weighted_lgd: number;
}

export interface AnalysisSummaryResponse {
  recommended_window: number;
  kpi: Record<string, number>;
  scenarios: ScenarioSummaryRow[];
}

export interface BacktestData {
  forecast: (number | null)[][];
  actual: (number | null)[][];
  residual: (number | null)[][];
  mean_lgd: (number | null)[];
  std_lgd: (number | null)[];
  mean_matrix: (number | null)[][];
  upper_ci: (number | null)[][];
  lower_ci: (number | null)[][];
  upper_ci_vector: (number | null)[];
  lower_ci_vector: (number | null)[];
  avg_error_by_tid: (number | null)[];
  vintage_labels: string[];
  periods: string[];
  hindsights: number[];
  ci_percentile: number;
  z_score: number;
  coverage_by_tid: (number | null)[];
  overall_coverage: number;
  normality_stats: Record<string, number | boolean | string>;
}

export interface TidBacktestItem {
  tid: number;
  actual: (number | null)[];
  mean_val: number | null;
  forecast_center: number | null;  // oldest vintage forecast — CI center
  upper_vals: (number | null)[];   // per-vintage upper CI at this TID
  lower_vals: (number | null)[];   // per-vintage lower CI at this TID
  vintage_labels: string[];
  vintage_indices: number[];
  coverage: number;
  within: number;
  total: number;
}

export interface TidBacktestResponse {
  items: TidBacktestItem[];
}

export interface ConfigDefaults {
  discount_rate: number;
  window_sizes: number[];
  ci_percentile: number;
  max_tid: number;
}

// Plotly figure data from backend
export interface PlotlyFigure {
  data: any[];
  layout: Record<string, any>;
}

export type ChartsResponse = Record<string, PlotlyFigure>;
