"use client";

/**
 * PlotWrapper — A lightweight Plotly wrapper using plotly.js-dist-min.
 * Avoids the 3MB full plotly.js bundle required by react-plotly.js.
 * Uses a simple imperative approach: creates a div, calls Plotly.newPlot().
 */

import { useEffect, useRef } from "react";

interface PlotWrapperProps {
  data: object[];
  layout?: object;
  config?: object;
  style?: React.CSSProperties;
  className?: string;
}

export default function PlotWrapper({ data, layout = {}, config = {}, style, className }: PlotWrapperProps) {
  const divRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!divRef.current) return;
    let cancelled = false;

    import("plotly.js-dist-min").then((Plotly: any) => {
      if (cancelled || !divRef.current) return;
      Plotly.newPlot(
        divRef.current,
        data,
        {
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#94a3b8", size: 11 },
          margin: { l: 40, r: 20, t: 20, b: 40 },
          ...layout,
        },
        {
          displayModeBar: false,
          responsive: true,
          ...config,
        }
      );
    });

    return () => {
      cancelled = true;
      if (divRef.current) {
        import("plotly.js-dist-min").then((Plotly: any) => {
          if (divRef.current) Plotly.purge(divRef.current);
        });
      }
    };
  }, [data, layout, config]);

  return (
    <div
      ref={divRef}
      style={{ width: "100%", minHeight: 300, ...style }}
      className={className}
    />
  );
}
