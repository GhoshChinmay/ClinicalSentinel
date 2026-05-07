"use client";

import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Network, Users, AlertTriangle, RefreshCw, Info } from "lucide-react";
import api from "@/services/api.service";

interface Props {
  sessionId: string;
  columns: string[];
}

interface GraphNode {
  id: string;
  crcs: number;
}

interface GraphEdge {
  source: string;
  target: string;
}

interface CollusionReport {
  CRCS_score: number;
  network_connections: number;
  warning: string;
}

interface GNNResult {
  flagged_investigators: number;
  collusion_reports: Record<string, CollusionReport>;
  graph_nodes?: GraphNode[];
  graph_edges?: GraphEdge[];
}

// ── SVG Force-Layout Network Graph ───────────────────────────────────────────
function NetworkGraph({ nodes, edges, reports }: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  reports: Record<string, CollusionReport>;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const [tooltip, setTooltip] = useState<{ id: string; x: number; y: number } | null>(null);

  useEffect(() => {
    if (!nodes.length) return;
    // Simple circular layout with force-like jitter
    const W = 560, H = 380, cx = W / 2, cy = H / 2;
    const r = Math.min(cx, cy) * 0.72;
    const pos: Record<string, { x: number; y: number }> = {};
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      pos[n.id] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
    setPositions(pos);
  }, [nodes]);

  const getNodeColor = (crcs: number, inReport: boolean) => {
    if (inReport && crcs > 80) return "#ef4444";
    if (inReport && crcs > 60) return "#f59e0b";
    return "#6366f1";
  };

  return (
    <div className="relative">
      <svg ref={svgRef} viewBox="0 0 560 380" className="w-full rounded-xl bg-black/20 border border-white/5" style={{ minHeight: 300 }}>
        {/* Edges */}
        {edges.map((e, i) => {
          const src = positions[e.source];
          const tgt = positions[e.target];
          if (!src || !tgt) return null;
          return (
            <line
              key={i}
              x1={src.x} y1={src.y}
              x2={tgt.x} y2={tgt.y}
              stroke="#ffffff12"
              strokeWidth={1.5}
            />
          );
        })}
        {/* Nodes */}
        {nodes.map((n) => {
          const pos = positions[n.id];
          if (!pos) return null;
          const report = reports[n.id];
          const inReport = !!report;
          const color = getNodeColor(n.crcs, inReport);
          const radius = inReport ? 22 : 14;
          return (
            <g
              key={n.id}
              transform={`translate(${pos.x},${pos.y})`}
              className="cursor-pointer"
              onMouseEnter={(ev) => {
                const rect = svgRef.current?.getBoundingClientRect();
                if (rect) setTooltip({ id: n.id, x: pos.x, y: pos.y });
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              {inReport && (
                <circle r={radius + 8} fill={color} opacity={0.12} />
              )}
              <circle
                r={radius}
                fill={color}
                opacity={0.9}
                stroke={inReport ? color : "#ffffff15"}
                strokeWidth={inReport ? 2 : 1}
              />
              {inReport && (
                <text textAnchor="middle" dy="0.35em" fontSize={9} fill="white" fontWeight="bold">
                  {Math.round(n.crcs)}
                </text>
              )}
              <text
                textAnchor="middle"
                dy={radius + 14}
                fontSize={9}
                fill={inReport ? color : "#94a3b8"}
                fontWeight={inReport ? "bold" : "normal"}
              >
                {n.id.length > 10 ? n.id.slice(0, 9) + "…" : n.id}
              </text>
            </g>
          );
        })}
      </svg>
      {/* Tooltip */}
      {tooltip && reports[tooltip.id] && (
        <div
          className="absolute z-10 bg-neutral-900 border border-white/10 rounded-xl p-3 text-xs pointer-events-none shadow-xl"
          style={{ left: "50%", bottom: 12, transform: "translateX(-50%)", maxWidth: 280 }}
        >
          <p className="font-bold text-red-300 mb-1">{tooltip.id}</p>
          <p className="text-neutral-400">CRCS Score: <span className="text-red-400 font-mono font-bold">{reports[tooltip.id].CRCS_score.toFixed(1)}</span></p>
          <p className="text-neutral-400">Connections: {reports[tooltip.id].network_connections}</p>
          <p className="text-neutral-300 mt-1">{reports[tooltip.id].warning}</p>
        </div>
      )}
      {/* Legend */}
      <div className="flex gap-4 mt-3 text-xs text-neutral-500">
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-red-500 inline-block" /> High Collusion Risk (&gt;80)</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-amber-500 inline-block" /> Elevated Risk (60–80)</span>
        <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-indigo-500 inline-block" /> Clean / Low Risk</span>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function CollusionNetwork({ sessionId, columns }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GNNResult | null>(null);

  const [invCol, setInvCol] = useState(columns.find(c => ["investigator","inv_id"].some(k => c.toLowerCase().includes(k))) ?? "");
  const [sharedCols, setSharedCols] = useState(
    columns.filter(c => ["site","cro","sponsor","hospital"].some(k => c.toLowerCase().includes(k))).join(",")
  );

  const runGNN = async () => {
    if (!invCol || !sharedCols) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/api/clinical/gnn-collusion/${sessionId}`, {
        params: { investigator_col: invCol, shared_attr_cols: sharedCols }
      });
      setResult(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.error ?? "GNN Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  // Build graph from collusion_reports if graph_nodes/edges not returned by backend
  const graphNodes: GraphNode[] = result?.graph_nodes
    ?? (result
      ? Object.keys(result.collusion_reports ?? {}).map(id => ({
          id,
          crcs: (result.collusion_reports[id] as CollusionReport)?.CRCS_score ?? 0
        }))
      : []);
  const graphEdges: GraphEdge[] = result?.graph_edges ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-black text-white mb-1">
          GNN Collusion Detector <span className="text-purple-400">F2</span>
        </h2>
        <p className="text-neutral-500 text-sm">
          Detects coordinated fraud rings using Graph Neural Networks to propagate risk across shared sites and CROs.
        </p>
      </div>

      <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-neutral-500 mb-1.5 block">Investigator Column</label>
          <select value={invCol} onChange={e => setInvCol(e.target.value)} className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none">
            <option value="">— Select —</option>{columns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[160px]">
          <label className="text-xs text-neutral-500 mb-1.5 block">Shared Attributes (site, cro, etc)</label>
          <input
            type="text"
            value={sharedCols}
            onChange={e => setSharedCols(e.target.value)}
            placeholder="site_id,cro_name"
            className="w-full bg-neutral-900 border border-white/10 rounded-xl px-3 py-2 text-sm text-white focus:outline-none"
          />
        </div>
        
        <button onClick={runGNN} disabled={loading || !invCol || !sharedCols} className="px-6 py-2.5 bg-gradient-to-r from-rose-600 to-red-600 text-white font-bold rounded-xl disabled:opacity-40 hover:opacity-90 transition-opacity flex items-center gap-2">
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Network size={14} />} Run GNN Analysis
        </button>
      </div>

      {error && <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">{error}</div>}

      {result && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-center">
              <Users className="w-4 h-4 mx-auto mb-2 text-red-400" />
              <p className="text-xs text-neutral-400">Flagged Investigators</p>
              <p className="text-xl font-bold font-mono text-red-400">{result.flagged_investigators}</p>
            </div>
            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-center">
              <Network className="w-4 h-4 mx-auto mb-2 text-purple-400" />
              <p className="text-xs text-neutral-400">Network Nodes</p>
              <p className="text-xl font-bold font-mono text-white">{graphNodes.length}</p>
            </div>
            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-center">
              <AlertTriangle className="w-4 h-4 mx-auto mb-2 text-amber-400" />
              <p className="text-xs text-neutral-400">Graph Edges</p>
              <p className="text-xl font-bold font-mono text-amber-400">{graphEdges.length}</p>
            </div>
            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 text-center">
              <Info className="w-4 h-4 mx-auto mb-2 text-blue-400" />
              <p className="text-xs text-neutral-400">Avg CRCS</p>
              <p className="text-xl font-bold font-mono text-blue-400">
                {(() => {
                  const reports = Object.values(result.collusion_reports ?? {}) as CollusionReport[];
                  const valid = reports.filter(r => r && typeof r.CRCS_score === "number" && !isNaN(r.CRCS_score));
                  return valid.length > 0
                    ? (valid.reduce((s, r) => s + r.CRCS_score, 0) / valid.length).toFixed(1)
                    : "—";
                })()}
              </p>
            </div>
          </div>

          {/* Network Graph */}
          {graphNodes.length > 0 && (
            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <h3 className="font-bold text-white mb-4 flex items-center gap-2">
                <Network className="text-purple-400" size={16} /> Investigator Risk Graph
                <span className="text-xs text-neutral-500 font-normal ml-1">— hover nodes to see CRCS details</span>
              </h3>
              <NetworkGraph
                nodes={graphNodes}
                edges={graphEdges}
                reports={result.collusion_reports ?? {}}
              />
            </div>
          )}

          {/* Flagged Investigators Detail */}
          {Object.keys(result.collusion_reports ?? {}).length > 0 && (
            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-5">
              <h3 className="font-bold text-white mb-4">High-Risk Collusion Clusters</h3>
              <div className="space-y-3">
                {Object.entries(result.collusion_reports as Record<string, CollusionReport>)
                  .sort(([, a], [, b]) => b.CRCS_score - a.CRCS_score)
                  .map(([inv, report]) => (
                    <div key={inv} className="flex items-start gap-4 p-4 bg-red-500/5 border border-red-500/20 rounded-xl">
                      <div className="w-16 h-16 rounded-xl bg-red-500/10 flex flex-col items-center justify-center shrink-0">
                        <span className="text-2xl font-black text-red-400 font-mono">{Math.round(report.CRCS_score)}</span>
                        <span className="text-[9px] text-red-600 uppercase tracking-wider">CRCS</span>
                      </div>
                      <div>
                        <p className="font-bold text-white text-sm">{inv}</p>
                        <p className="text-xs text-neutral-400 mt-0.5">{report.network_connections} network connections</p>
                        <p className="text-xs text-red-300 mt-1">{report.warning}</p>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {result.flagged_investigators === 0 && (
            <div className="p-6 bg-emerald-500/5 border border-emerald-500/20 rounded-2xl text-center">
              <p className="text-emerald-400 font-bold">No High-Risk Collusion Clusters Detected</p>
              <p className="text-neutral-500 text-sm mt-1">Investigators appear to operate independently without suspicious structural linkage.</p>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
