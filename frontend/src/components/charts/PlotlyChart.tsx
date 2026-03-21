import Plot from './PlotlyWrapper';

interface Props {
  data: any[];
  layout: Record<string, any>;
  className?: string;
}

export default function PlotlyChart({ data, layout, className }: Props) {
  return (
    <div className={className}>
      <Plot
        data={data}
        layout={{
          ...layout,
          autosize: true,
          margin: { l: 50, r: 20, t: 40, b: 50 },
        }}
        config={{ responsive: true, displayModeBar: false }}
        useResizeHandler
        style={{ width: '100%', height: layout.height || 400 }}
      />
    </div>
  );
}
