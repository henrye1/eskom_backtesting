import PlotlyChart from './PlotlyChart';
import type { ChartsResponse } from '../../api/types';

interface Props {
  charts: ChartsResponse;
}

const CHART_ORDER = [
  { key: 'lgd_term_structure', label: 'LGD Term Structure by Vintage' },
  { key: 'forecast_vs_actual', label: 'Forecast vs Actual' },
  { key: 'avg_error_by_tid', label: 'Average Error by TID' },
  { key: 'ci_bands', label: 'Confidence Interval Bands' },
  { key: 'residual_histogram', label: 'Residual Distribution' },
  { key: 'residual_heatmap', label: 'Residual Heatmap' },
  { key: 'window_comparison', label: 'Window Size Comparison' },
  { key: 'lgd_comparison', label: 'LGD Term Structure Comparison' },
  { key: 'weighted_lgd', label: 'Vintage Weighted LGD' },
  { key: 'qq_plot', label: 'Q-Q Plot' },
];

export default function ChartGrid({ charts }: Props) {
  return (
    <div>
      <h3 className="text-sm font-bold text-gray-700 mb-3">Charts</h3>
      <div className="grid grid-cols-2 gap-4">
        {CHART_ORDER.map(({ key }) => {
          const fig = charts[key];
          if (!fig) return null;
          return (
            <div key={key} className="bg-white rounded border border-gray-200 p-2">
              <PlotlyChart data={fig.data} layout={{ ...fig.layout, height: 350 }} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
