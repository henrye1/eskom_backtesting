import axios from 'axios';
import type {
  UploadResponse,
  AnalysisRequest,
  JobStatusResponse,
  AnalysisSummaryResponse,
  BacktestData,
  TidBacktestResponse,
  ChartsResponse,
  ConfigDefaults,
} from './types';

const api = axios.create({ baseURL: '/api' });

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<UploadResponse>('/upload', form);
  return data;
}

export async function startAnalysis(req: AnalysisRequest): Promise<{ job_id: string }> {
  const { data } = await api.post('/analysis', req);
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await api.get<JobStatusResponse>(`/analysis/${jobId}/status`);
  return data;
}

export async function getSummary(jobId: string): Promise<AnalysisSummaryResponse> {
  const { data } = await api.get<AnalysisSummaryResponse>(`/analysis/${jobId}/summary`);
  return data;
}

export async function getBacktest(jobId: string, windowSize: number): Promise<BacktestData> {
  const { data } = await api.get<BacktestData>(`/analysis/${jobId}/scenario/${windowSize}/backtest`);
  return data;
}

export async function getTidBacktest(jobId: string, windowSize: number): Promise<TidBacktestResponse> {
  const { data } = await api.get<TidBacktestResponse>(`/analysis/${jobId}/scenario/${windowSize}/tid-backtest`);
  return data;
}

export async function getCharts(jobId: string, windowSize: number): Promise<ChartsResponse> {
  const { data } = await api.get<ChartsResponse>(`/analysis/${jobId}/scenario/${windowSize}/charts`);
  return data;
}

export async function getConfigDefaults(): Promise<ConfigDefaults> {
  const { data } = await api.get<ConfigDefaults>('/config/defaults');
  return data;
}

export function getDownloadUrl(jobId: string, type: 'multi-scenario-excel' | 'html-dashboard', windowSize?: number): string {
  if (type === 'multi-scenario-excel') return `/api/analysis/${jobId}/download/multi-scenario-excel`;
  if (type === 'html-dashboard') return `/api/analysis/${jobId}/download/html-dashboard`;
  return `/api/analysis/${jobId}/download/single-excel/${windowSize}`;
}
