import { lazy, Suspense } from 'react';

const LazyPlot = lazy(async () => {
  const factoryModule = await import('react-plotly.js/factory');
  const plotlyModule = await import('plotly.js-dist-min');

  // Dig through nested default exports to find the function
  let factory: any = factoryModule;
  while (factory && typeof factory !== 'function' && factory.default) {
    factory = factory.default;
  }

  const Plotly = (plotlyModule as any).default || plotlyModule;

  if (typeof factory !== 'function') {
    console.error('Factory after unwrap:', factory);
    throw new Error('Failed to resolve createPlotlyComponent');
  }

  const Plot = factory(Plotly);
  return { default: Plot };
});

export default function PlotlyWrapper(props: any) {
  return (
    <Suspense fallback={
      <div style={{
        height: props.style?.height || 400,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#999', fontSize: 12, border: '1px dashed #ddd', borderRadius: 4,
      }}>
        Loading chart...
      </div>
    }>
      <LazyPlot {...props} />
    </Suspense>
  );
}
