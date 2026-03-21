import { useAnalysisStore } from '../../store/analysisStore';
import { uploadFile, startAnalysis } from '../../api/client';

const ALL_WINDOWS = [12, 18, 24, 30, 36, 42, 48, 54, 60];

export default function Sidebar() {
  const store = useAnalysisStore();

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const { setStatus, setFileId, setError } = useAnalysisStore.getState();
    setStatus('uploading');
    try {
      const res = await uploadFile(file);
      setFileId(res.file_id, res.filename);
      setStatus('idle');
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message);
    }
  };

  const handleRun = async () => {
    const s = useAnalysisStore.getState();
    if (!s.fileId) return;
    s.setStatus('running');
    try {
      const res = await startAnalysis({
        file_id: s.fileId,
        window_sizes: s.params.windowSizes,
        discount_rate: s.params.discountRate,
        lgd_cap: s.params.lgdCap,
        ci_percentile: s.params.ciPercentile,
        max_tid: s.params.maxTid,
        store_detail: s.params.storeDetail,
      });
      s.setJobId(res.job_id);
    } catch (err: any) {
      s.setError(err?.response?.data?.detail || err.message);
    }
  };

  const toggleWindow = (w: number) => {
    const current = store.params.windowSizes;
    const next = current.includes(w) ? current.filter(x => x !== w) : [...current, w].sort((a, b) => a - b);
    store.updateParams({ windowSizes: next });
  };

  return (
    <aside className="w-72 bg-white border-r border-gray-200 p-4 flex flex-col gap-4 overflow-y-auto h-screen sticky top-0">
      <h2 className="text-lg font-bold text-gray-800">Parameters</h2>

      {/* File Upload */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Excel Workbook</label>
        <input type="file" accept=".xlsx" onChange={handleFile}
          className="block w-full text-xs file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:bg-blue-50 file:text-blue-700 file:cursor-pointer" />
        {store.fileName && <p className="text-xs text-green-600 mt-1">{store.fileName}</p>}
      </div>

      {/* Window Sizes */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Window Sizes</label>
        <div className="flex flex-wrap gap-1">
          {ALL_WINDOWS.map(w => (
            <button key={w} onClick={() => toggleWindow(w)}
              className={`text-xs px-2 py-1 rounded border ${
                store.params.windowSizes.includes(w)
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-300'
              }`}>{w}m</button>
          ))}
        </div>
      </div>

      {/* CI Percentile */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">
          CI Percentile: {(store.params.ciPercentile * 100).toFixed(0)}%
        </label>
        <input type="range" min="0.50" max="0.99" step="0.01"
          value={store.params.ciPercentile}
          onChange={e => store.updateParams({ ciPercentile: parseFloat(e.target.value) })}
          className="w-full" />
        <p className="text-[10px] text-gray-400 mt-0.5">z derived via norm.ppf. Bands widen with term point.</p>
      </div>

      {/* Discount Rate */}
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Discount Rate</label>
        <input type="number" step="0.01" value={store.params.discountRate}
          onChange={e => store.updateParams({ discountRate: parseFloat(e.target.value) })}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1" />
      </div>

      {/* LGD Cap */}
      <div className="flex items-center gap-2">
        <input type="checkbox" checked={store.params.lgdCap !== null}
          onChange={e => store.updateParams({ lgdCap: e.target.checked ? 1.0 : null })} />
        <span className="text-xs text-gray-600">Cap LGD at 1.0</span>
      </div>

      {/* Run Button */}
      <button onClick={handleRun} disabled={!store.fileId || store.status === 'running'}
        className="mt-auto bg-blue-600 text-white py-2 rounded font-medium text-sm hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed">
        {store.status === 'running' ? 'Running...' : 'Run Analysis'}
      </button>

      {store.error && <p className="text-xs text-red-600">{store.error}</p>}
    </aside>
  );
}
