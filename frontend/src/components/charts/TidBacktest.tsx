import Plot from './PlotlyWrapper';
import type { TidBacktestItem } from '../../api/types';

interface Props {
  items: TidBacktestItem[];
  allLabels: string[];
}

function TidBlock({ item, allLabels }: { item: TidBacktestItem; allLabels: string[] }) {
  const labels = item.vintage_indices.map(i => allLabels[i] ?? `v${i}`);
  const actuals = item.vintage_indices.map(i => item.actual[i]);
  const uppers = item.upper_vals;  // per-vintage upper CI
  const lowers = item.lower_vals;  // per-vintage lower CI

  // Per-vintage CI check for coloring
  const colors = actuals.map((a, j) => {
    const u = uppers[j];
    const l = lowers[j];
    if (a !== null && u !== null && l !== null && a >= l && a <= u) return '#2ca02c';
    return '#d62728';
  });

  const hasAnyCI = uppers.some(v => v !== null) && lowers.some(v => v !== null);

  const traces: any[] = [];

  // CI band — per-vintage upper/lower creates a shaped envelope
  if (hasAnyCI) {
    const validUppers = uppers.map(v => v ?? 0);
    const validLowers = lowers.map(v => v ?? 0);
    traces.push({
      x: [...labels, ...labels.slice().reverse()],
      y: [...validUppers, ...validLowers.slice().reverse()],
      fill: 'toself', fillcolor: 'rgba(31,119,180,0.12)',
      line: { color: 'rgba(0,0,0,0)' },
      showlegend: false, hoverinfo: 'skip',
      type: 'scatter',
    });
    // Upper line (varies per vintage)
    traces.push({
      x: labels, y: validUppers,
      mode: 'lines', showlegend: false,
      line: { color: 'rgba(31,119,180,0.5)', width: 1 },
      hovertemplate: 'Upper: %{y:.2%}<extra></extra>',
      type: 'scatter',
    });
    // Lower line (varies per vintage)
    traces.push({
      x: labels, y: validLowers,
      mode: 'lines', showlegend: false,
      line: { color: 'rgba(31,119,180,0.5)', width: 1 },
      hovertemplate: 'Lower: %{y:.2%}<extra></extra>',
      type: 'scatter',
    });
  }

  // Forecast center line (CI is symmetric around oldest vintage's forecast)
  if (item.forecast_center !== null) {
    traces.push({
      x: labels, y: labels.map(() => item.forecast_center!),
      mode: 'lines', name: 'Forecast (CI center)',
      line: { color: '#1f77b4', width: 2 },
      type: 'scatter',
    });
  }

  // Actual markers
  traces.push({
    x: labels, y: actuals as number[],
    mode: 'markers', name: 'Actual',
    marker: { color: colors, size: 6, line: { width: 0.5, color: '#333' } },
    type: 'scatter',
  });

  return (
    <div className="bg-white rounded border border-gray-200 p-2">
      <Plot
        data={traces}
        layout={{
          title: { text: `TID ${item.tid} — Coverage: ${(item.coverage * 100).toFixed(0)}% (${item.within}/${item.total})`, font: { size: 11 } },
          xaxis: { showgrid: false, tickangle: -45, tickfont: { size: 7 }, nticks: Math.min(labels.length, 10) },
          yaxis: { tickformat: '.0%', gridcolor: 'rgba(0,0,0,0.06)' },
          template: 'plotly_white' as any,
          height: 260, margin: { l: 45, r: 10, t: 35, b: 45 },
          showlegend: false,
          autosize: true,
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%', height: 260 }}
      />
    </div>
  );
}

export default function TidBacktest({ items, allLabels }: Props) {
  return (
    <div>
      <h3 className="text-sm font-bold text-gray-700 mb-3">Per-TID Backtest</h3>
      <p className="text-xs text-gray-500 mb-3">
        Each TID column is tested across vintages. CI bands widen for newer vintages (less hindsight). Green = within CI, Red = outside.
      </p>
      <div className="grid grid-cols-2 gap-3">
        {items.map(item => (
          <TidBlock key={item.tid} item={item} allLabels={allLabels} />
        ))}
      </div>
    </div>
  );
}
