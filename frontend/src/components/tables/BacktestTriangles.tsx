import type { BacktestData } from '../../api/types';

interface Props {
  data: BacktestData;
}

function fmt(v: number | null): string {
  if (v === null || v === undefined) return '';
  return (v * 100).toFixed(2) + '%';
}

function fmtSigned(v: number | null): string {
  if (v === null || v === undefined) return '';
  const s = (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%';
  return s;
}

function MatrixTable({
  title,
  matrix,
  labels,
  periods,
  hindsights,
  maxTid,
  formatter = fmt,
  colorize = false,
}: {
  title: string;
  matrix: (number | null)[][];
  labels: string[];
  periods: string[];
  hindsights: number[];
  maxTid: number;
  formatter?: (v: number | null) => string;
  colorize?: boolean;
}) {
  const nTid = Math.min(matrix[0]?.length ?? 0, maxTid + 1);
  return (
    <div className="mb-4">
      <h4 className="text-xs font-bold text-gray-700 mb-1">{title}</h4>
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Vintage</th><th>Period</th><th>H</th>
              {Array.from({ length: nTid }, (_, i) => <th key={i}>{i}</th>)}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, i) => (
              <tr key={i}>
                <td className="label-cell">{labels[i]}</td>
                <td className="label-cell">{periods[i]}</td>
                <td>{hindsights[i]}</td>
                {row.slice(0, nTid).map((v, t) => {
                  let cls = '';
                  if (colorize && v !== null) {
                    cls = v > 0.05 ? 'cell-positive' : v < -0.05 ? 'cell-negative' : '';
                  }
                  return <td key={t} className={cls}>{formatter(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function VectorRow({ title, values, maxTid }: { title: string; values: (number | null)[]; maxTid: number }) {
  const nTid = Math.min(values.length, maxTid + 1);
  return (
    <tr>
      <td className="label-cell" colSpan={3}>{title}</td>
      {values.slice(0, nTid).map((v, i) => <td key={i}>{fmt(v)}</td>)}
    </tr>
  );
}

export default function BacktestTriangles({ data }: Props) {
  const maxTid = data.vintage_labels.length;
  const common = {
    labels: data.vintage_labels,
    periods: data.periods,
    hindsights: data.hindsights,
    maxTid,
  };

  return (
    <div>
      <h3 className="text-sm font-bold text-gray-700 mb-2">
        LGD Backtest Summary — SEM Scaled | Percentile: {((data.ci_percentile ?? 0.75) * 100).toFixed(0)}% | z={data.z_score} | Coverage: {(data.overall_coverage * 100).toFixed(0)}%
      </h3>

      <MatrixTable title="FORECAST LGD BY VINTAGE" matrix={data.forecast} {...common} />
      <MatrixTable title="ACTUAL LGD BY VINTAGE (DIAGONAL)" matrix={data.actual} {...common} />

      {/* Mean / Std row */}
      <div className="mb-4">
        <h4 className="text-xs font-bold text-gray-700 mb-1">Mean / Std Deviation</h4>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th colSpan={3}>Statistic</th>
                {Array.from({ length: Math.min(data.mean_lgd.length, maxTid + 1) }, (_, i) => <th key={i}>{i}</th>)}
              </tr>
            </thead>
            <tbody>
              <VectorRow title="Mean" values={data.mean_lgd} maxTid={maxTid} />
              <VectorRow title="Std Deviation" values={data.std_lgd} maxTid={maxTid} />
            </tbody>
          </table>
        </div>
      </div>

      <MatrixTable title="MEAN LGD BY VINTAGE" matrix={data.mean_matrix} {...common} />
      <MatrixTable title="UPPER BOUND (SEM Scaled)" matrix={data.upper_ci} {...common} />
      <MatrixTable title="LOWER BOUND (SEM Scaled)" matrix={data.lower_ci} {...common} />
      <MatrixTable title="DIFFERENCE (ACTUAL - FORECAST)" matrix={data.residual} {...common}
        formatter={fmtSigned} colorize />

      {/* Normality Tests */}
      <div className="mb-4 p-3 bg-gray-50 rounded border border-gray-200">
        <h4 className="text-xs font-bold text-gray-700 mb-2">Normality Tests</h4>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div>
            <div>N={String(data.normality_stats.n)}, Mean={Number(data.normality_stats.mean).toFixed(6)}</div>
            <div>Std={Number(data.normality_stats.std).toFixed(6)}, Skew={Number(data.normality_stats.skewness).toFixed(4)}</div>
          </div>
          <div>
            <div>JB={Number(data.normality_stats.jarque_bera_stat).toFixed(4)}</div>
            <div>Reject: <b>{data.normality_stats.jb_reject ? 'YES' : 'NO'}</b></div>
          </div>
          <div>
            <div>Chi²={Number(data.normality_stats.chi_sq_stat).toFixed(4)}</div>
            <div>Reject: <b>{data.normality_stats.chi_sq_reject ? 'YES' : 'NO'}</b></div>
          </div>
        </div>
      </div>
    </div>
  );
}
