import type { ScenarioSummaryRow } from '../../api/types';

interface Props {
  scenarios: ScenarioSummaryRow[];
  selectedWindow: number;
  onSelectWindow: (w: number) => void;
}

export default function ScenarioTable({ scenarios, selectedWindow, onSelectWindow }: Props) {
  return (
    <div className="mb-6">
      <h3 className="text-sm font-bold text-gray-700 mb-2">Scenario Comparison</h3>
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Rank</th><th>Window</th><th>Vintages</th><th>Residuals</th>
              <th>RMSE</th><th>MAE</th><th>Bias</th><th>Score</th>
              <th>LGD TID=0</th><th>Weighted LGD</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map(s => (
              <tr key={s.window_size}
                onClick={() => onSelectWindow(s.window_size)}
                className={`cursor-pointer hover:bg-blue-50 ${
                  s.window_size === selectedWindow ? 'bg-blue-100 font-semibold' : ''
                } ${s.rank === 1 ? 'bg-green-50' : ''}`}>
                <td>{s.rank}</td>
                <td>{s.window_size}m</td>
                <td>{s.n_vintages}</td>
                <td>{s.n_residuals}</td>
                <td>{(s.rmse * 100).toFixed(2)}%</td>
                <td>{(s.mae * 100).toFixed(2)}%</td>
                <td>{(s.bias >= 0 ? '+' : '')}{(s.bias * 100).toFixed(2)}%</td>
                <td>{s.composite_score.toFixed(4)}</td>
                <td>{(s.latest_lgd_tid0 * 100).toFixed(2)}%</td>
                <td>{(s.latest_weighted_lgd * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
