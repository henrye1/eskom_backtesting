import { useEffect, useRef, useState } from 'react';
import { useAnalysisStore } from '../store/analysisStore';
import { getJobStatus, getSummary, getBacktest, getTidBacktest, getCharts } from '../api/client';
import type { AnalysisSummaryResponse, BacktestData, TidBacktestResponse, ChartsResponse } from '../api/types';
import KpiCards from '../components/cards/KpiCards';
import ScenarioTable from '../components/tables/ScenarioTable';
import BacktestTriangles from '../components/tables/BacktestTriangles';
import TidBacktest from '../components/charts/TidBacktest';
import ChartGrid from '../components/charts/ChartGrid';
import DownloadButtons from '../components/common/DownloadButtons';

export default function Dashboard() {
  const status = useAnalysisStore(s => s.status);
  const jobId = useAnalysisStore(s => s.jobId);
  const selectedWindow = useAnalysisStore(s => s.selectedWindow);
  const error = useAnalysisStore(s => s.error);

  const [summary, setSummary] = useState<AnalysisSummaryResponse | null>(null);
  const [backtest, setBacktest] = useState<BacktestData | null>(null);
  const [tidData, setTidData] = useState<TidBacktestResponse | null>(null);
  const [charts, setCharts] = useState<ChartsResponse | null>(null);
  const [uiState, setUiState] = useState<'idle' | 'polling' | 'loading' | 'ready'>('idle');

  const loadedWindow = useRef<number | null>(null);
  // Use a counter to trigger the main flow without depending on store.status
  const [runTrigger, setRunTrigger] = useState(0);
  const prevJobId = useRef<string | null>(null);

  // Detect new job and trigger the flow
  useEffect(() => {
    if (jobId && jobId !== prevJobId.current && status === 'running') {
      prevJobId.current = jobId;
      setRunTrigger(t => t + 1);
    }
  }, [jobId, status]);

  // Main async flow — only triggered by runTrigger, NOT by status changes
  useEffect(() => {
    if (runTrigger === 0) return;
    const currentJobId = useAnalysisStore.getState().jobId;
    if (!currentJobId) return;

    let cancelled = false;

    (async () => {
      setUiState('polling');
      setSummary(null);
      setBacktest(null);
      setTidData(null);
      setCharts(null);
      loadedWindow.current = null;

      try {
        // Poll until done
        while (true) {
          const res = await getJobStatus(currentJobId);
          if (res.status === 'completed') break;
          if (res.status === 'failed') throw new Error(res.error ?? 'Analysis failed');
          await new Promise(r => setTimeout(r, 1000));
          if (cancelled) return;
        }
        if (cancelled) return;

        setUiState('loading');
        useAnalysisStore.getState().setStatus('completed');

        // Fetch summary
        const s = await getSummary(currentJobId);
        if (cancelled) return;
        setSummary(s);

        const bestWindow = s.recommended_window || s.scenarios[0]?.window_size || 60;
        useAnalysisStore.getState().setSelectedWindow(bestWindow);

        // Fetch window data
        const [bt, td, ch] = await Promise.all([
          getBacktest(currentJobId, bestWindow),
          getTidBacktest(currentJobId, bestWindow),
          getCharts(currentJobId, bestWindow),
        ]);
        if (cancelled) return;

        console.log('[Dashboard] Data loaded, setting state', { bt: !!bt, td: !!td, ch: !!ch, cancelled });
        setBacktest(bt);
        setTidData(td);
        setCharts(ch);
        loadedWindow.current = bestWindow;
        setUiState('ready');
        console.log('[Dashboard] uiState set to ready');
      } catch (err: any) {
        console.error('[Dashboard] Flow error:', err, 'cancelled:', cancelled);
        if (cancelled) return;
        useAnalysisStore.getState().setError(err.message);
        setUiState('idle');
      }
    })();

    return () => { cancelled = true; };
  }, [runTrigger]);

  // Window switch — only when user changes window after results are loaded
  useEffect(() => {
    if (uiState !== 'ready') return;
    if (selectedWindow === loadedWindow.current) return;
    const currentJobId = useAnalysisStore.getState().jobId;
    if (!currentJobId || !summary) return;
    if (!summary.scenarios.some(s => s.window_size === selectedWindow)) return;

    let cancelled = false;

    (async () => {
      try {
        const [bt, td, ch] = await Promise.all([
          getBacktest(currentJobId, selectedWindow),
          getTidBacktest(currentJobId, selectedWindow),
          getCharts(currentJobId, selectedWindow),
        ]);
        if (cancelled) return;
        setBacktest(bt);
        setTidData(td);
        setCharts(ch);
        loadedWindow.current = selectedWindow;
      } catch (err) {
        console.error('Window switch failed:', err);
      }
    })();

    return () => { cancelled = true; };
  }, [selectedWindow, uiState, summary]);

  // --- Render ---
  if (status === 'failed') {
    return <div className="p-6 text-red-600">Error: {error}</div>;
  }

  if (uiState === 'idle') {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-lg">
        {status === 'uploading' ? 'Uploading...' : 'Upload an Excel workbook and click Run Analysis'}
      </div>
    );
  }

  if (uiState === 'polling') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
        <p className="text-gray-500">Running analysis...</p>
      </div>
    );
  }

  if (uiState === 'loading' && !backtest) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600" />
        <p className="text-gray-500">Loading results...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800">Development Factor LGD Backtesting</h1>
        {summary && (
          <select value={selectedWindow}
            onChange={e => useAnalysisStore.getState().setSelectedWindow(Number(e.target.value))}
            className="border border-gray-300 rounded px-3 py-1 text-sm">
            {summary.scenarios.map(s => (
              <option key={s.window_size} value={s.window_size}>
                {s.window_size}m Window {s.rank === 1 ? '(Best)' : ''}
              </option>
            ))}
          </select>
        )}
      </div>

      {summary && <KpiCards kpi={summary.kpi} />}
      {summary && jobId && <DownloadButtons jobId={jobId} windowSize={selectedWindow} />}
      {summary && (
        <ScenarioTable
          scenarios={summary.scenarios}
          selectedWindow={selectedWindow}
          onSelectWindow={w => useAnalysisStore.getState().setSelectedWindow(w)}
        />
      )}

      {backtest && <BacktestTriangles data={backtest} />}
      {tidData && backtest && (
        <TidBacktest items={tidData.items} allLabels={backtest.vintage_labels} />
      )}
      {charts && <ChartGrid charts={charts} />}
    </div>
  );
}
