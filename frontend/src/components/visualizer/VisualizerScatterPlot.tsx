/* ─── Imports ────────────────────────────────────────────────────────────────────────────── */

import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Zap } from 'lucide-react';
import type { VizData } from '@/types/api';

/* ─── Types ──────────────────────────────────────────────────────────────────────────────── */

export interface VisualizerScatterPlotProps {
  data: VizData;
  varX: string;
  varY: string;
  setVarX: (val: string) => void;
  setVarY: (val: string) => void;
}

interface ScatterData {
  points: { x: number; y: number }[];
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  slope: number;
  intercept: number;
  rValue: number;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────────────────── */

/**
 * Returns UI styling details based on correlation magnitude.
 *
 * @param {number} r - Pearson correlation coefficient.
 * @returns {object} Text and class colors.
 */
const getCorrelationBadge = (r: number): { text: string; color: string } => {
  const abs = Math.abs(r);
  const dir = r < 0 ? 'Negative' : 'Positive';
  if (abs >= 0.7) {
    return {
      text: `Strong ${dir}`,
      color:
        r < 0
          ? 'text-red-400 bg-red-500/10 border-red-500/30'
          : 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
    };
  }
  if (abs >= 0.3) {
    return {
      text: `Moderate ${dir}`,
      color: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
    };
  }
  if (abs > 0.1) {
    return { text: `Weak ${dir}`, color: 'text-neutral-400 bg-neutral-800 border-neutral-700' };
  }
  return { text: 'Neutral / No Correlation', color: 'text-neutral-500 bg-black border-neutral-800' };
};

/* ─── Scatter Line Component ─────────────────────────────────────────────────────────────── */

/**
 * LineOfBestFit renders the regression line using SVG elements.
 *
 * @param {object} props - ScatterData parameters.
 * @returns {JSX.Element} SVG Line.
 */
function LineOfBestFit({ scatterData }: { scatterData: ScatterData }): JSX.Element {
  const { xMin, xMax, slope, intercept, rValue, yMin, yMax } = scatterData;
  const x1 = 40;
  const y1 = 360 - (((slope * xMin + intercept) - yMin) / (yMax - yMin || 1)) * 320;
  const x2 = 760;
  const y2 = 360 - (((slope * xMax + intercept) - yMin) / (yMax - yMin || 1)) * 320;

  return (
    <motion.line
      initial={{ pathLength: 0, opacity: 0 }}
      animate={{ pathLength: 1, opacity: 1 }}
      transition={{ duration: 1, delay: 0.5 }}
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke={rValue < 0 ? '#F87171' : '#34D399'}
      strokeWidth="3"
      strokeDasharray="8 4"
    />
  );
}

/* ─── Main Component ─────────────────────────────────────────────────────────────────────── */

/**
 * VisualizerScatterPlot renders the pairwise distribution matrix.
 *
 * @param {VisualizerScatterPlotProps} props - Variables configuration.
 * @returns {JSX.Element} The rendered plot.
 */
export default function VisualizerScatterPlot({
  data,
  varX,
  varY,
  setVarX,
  setVarY,
}: VisualizerScatterPlotProps): JSX.Element {
  const scatterData = useMemo<ScatterData | null>(() => {
    if (!data || !data.clean_sample || !varX || !varY || data.columns.length < 2) return null;

    const points = data.clean_sample
      .map((row: Record<string, unknown>) => ({ x: Number(row[varX]), y: Number(row[varY]) }))
      .filter((p: { x: number; y: number }) => Number.isFinite(p.x) && Number.isFinite(p.y));

    if (points.length === 0) return null;

    const xValues = points.map((p: { x: number }) => p.x);
    const yValues = points.map((p: { y: number }) => p.y);
    const xMin = Math.min(...xValues);
    const xMax = Math.max(...xValues);
    const yMin = Math.min(...yValues);
    const yMax = Math.max(...yValues);

    const n = points.length;
    const meanX = n > 0 ? xValues.reduce((a: number, b: number) => a + b, 0) / n : 0;
    const meanY = n > 0 ? yValues.reduce((a: number, b: number) => a + b, 0) / n : 0;

    let ssXY = 0,
      ssXX = 0;
    for (let i = 0; i < n; i++) {
      ssXY += (points[i].x - meanX) * (points[i].y - meanY);
      ssXX += (points[i].x - meanX) ** 2;
    }

    const slope = ssXX === 0 ? 0 : ssXY / ssXX;
    const intercept = meanY - slope * meanX;

    let rValue = 0;
    if (data.correlation && data.correlation.features) {
      const xIdx = data.correlation.features.indexOf(varX);
      const yIdx = data.correlation.features.indexOf(varY);
      if (xIdx !== -1 && yIdx !== -1) rValue = data.correlation.matrix[yIdx][xIdx];
    }

    return { points, xMin, xMax, yMin, yMax, slope, intercept, rValue };
  }, [data, varX, varY]);

  const badgeInfo = scatterData ? getCorrelationBadge(scatterData.rValue) : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8"
    >
      <div className="flex flex-col md:flex-row md:items-start justify-between mb-8 gap-6">
        <div>
          <h3 className="text-xl font-bold text-white mb-1">Pairwise Scatter Explorer</h3>
          <p className="text-sm text-neutral-400">
            Select two variables to plot their actual data points and reveal hidden trends.
          </p>
        </div>

        {scatterData && badgeInfo && (
          <div className="flex items-center space-x-4 bg-black/40 border border-neutral-800 p-4 rounded-xl shrink-0">
            <div>
              <div className="text-[10px] text-neutral-500 uppercase font-bold tracking-wider mb-1">
                Pearson Correlation (r)
              </div>
              <div className="text-2xl font-mono text-white leading-none">
                {scatterData.rValue.toFixed(4)}
              </div>
            </div>
            <div
              className={`px-4 py-2 rounded-lg border text-sm font-bold ${badgeInfo.color}`}
            >
              {badgeInfo.text}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div>
          <label className="block text-xs font-bold text-neutral-500 uppercase mb-2">
            Variable X (Horizontal Axis)
          </label>
          <select
            value={varX}
            onChange={(e) => setVarX(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
          >
            {data.columns.map((col: string) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-bold text-neutral-500 uppercase mb-2">
            Variable Y (Vertical Axis)
          </label>
          <select
            value={varY}
            onChange={(e) => setVarY(e.target.value)}
            className="w-full bg-neutral-950 border border-neutral-800 text-white rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors"
          >
            {data.columns.map((col: string) => (
              <option key={col} value={col}>
                {col}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!scatterData ? (
        <div className="py-20 text-center text-neutral-500 flex flex-col items-center bg-black/20 rounded-xl border border-neutral-800/50">
          <Zap className="w-12 h-12 mb-4 opacity-20" />
          <p>Cannot generate plot. Ensure variables have valid numeric data.</p>
        </div>
      ) : (
        <div className="relative w-full aspect-[2/1] bg-[#0A0A0A] border border-neutral-800 rounded-xl overflow-hidden">
          <svg viewBox="0 0 800 400" className="w-full h-full">
            <line x1={40} y1={40} x2={40} y2={360} stroke="#262626" strokeWidth="1" />
            <line x1={40} y1={360} x2={760} y2={360} stroke="#262626" strokeWidth="1" />

            {scatterData.points.map((p: { x: number; y: number }, i: number) => {
              const cx =
                40 + ((p.x - scatterData.xMin) / (scatterData.xMax - scatterData.xMin || 1)) * 720;
              const cy =
                360 - ((p.y - scatterData.yMin) / (scatterData.yMax - scatterData.yMin || 1)) * 320;

              return (
                <motion.circle
                  key={i}
                  initial={{ cx, cy: 200, opacity: 0 }}
                  animate={{ cx, cy, opacity: 0.6 }}
                  transition={{ duration: 0.5, delay: (i % 10) * 0.05 }}
                  r="3"
                  fill="#60A5FA"
                  className="hover:opacity-100 hover:fill-white transition-all cursor-crosshair"
                >
                  <title>
                    X: {p.x.toFixed(2)} | Y: {p.y.toFixed(2)}
                  </title>
                </motion.circle>
              );
            })}

            <LineOfBestFit scatterData={scatterData} />
          </svg>

          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[10px] font-bold text-neutral-500 uppercase tracking-widest">
            {varX}
          </div>
          <div className="absolute top-1/2 left-2 -translate-y-1/2 -rotate-90 origin-left text-[10px] font-bold text-neutral-500 uppercase tracking-widest whitespace-nowrap">
            {varY}
          </div>
        </div>
      )}
    </motion.div>
  );
}

/* ─── Exports ────────────────────────────────────────────────────────────────────────────── */
