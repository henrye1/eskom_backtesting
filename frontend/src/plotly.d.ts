declare module 'react-plotly.js/factory' {
  import { ComponentType } from 'react';
  function createPlotlyComponent(plotly: any): ComponentType<any>;
  export default createPlotlyComponent;
}

declare module 'plotly.js-dist-min' {
  const Plotly: any;
  export default Plotly;
}
