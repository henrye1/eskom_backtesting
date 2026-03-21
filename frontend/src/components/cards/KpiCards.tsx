interface KpiProps {
  kpi: Record<string, number>;
}

const CARDS = [
  { key: 'recommended_window', label: 'Recommended Window', fmt: (v: number) => `${v}m` },
  { key: 'rmse', label: 'RMSE', fmt: (v: number) => (v * 100).toFixed(2) + '%' },
  { key: 'mae', label: 'MAE', fmt: (v: number) => (v * 100).toFixed(2) + '%' },
  { key: 'bias', label: 'Bias', fmt: (v: number) => (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%' },
  { key: 'lgd_tid0', label: 'LGD at TID=0', fmt: (v: number) => (v * 100).toFixed(2) + '%' },
];

export default function KpiCards({ kpi }: KpiProps) {
  return (
    <div className="grid grid-cols-5 gap-3 mb-6">
      {CARDS.map(c => (
        <div key={c.key} className="bg-white rounded-lg border border-gray-200 p-4 text-center shadow-sm">
          <div className="text-xs text-gray-500 mb-1">{c.label}</div>
          <div className="text-xl font-bold text-gray-800">{c.fmt(kpi[c.key] ?? 0)}</div>
        </div>
      ))}
    </div>
  );
}
