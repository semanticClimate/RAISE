import {
  Check,
  Copy,
  Network,
  Search,
  X,
} from 'lucide-react';
import React, { useMemo, useState } from 'react';
import { useScrollLock } from '../../hooks';
import type { SubgraphData } from '../../types';

export interface SubgraphViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  subgraph: SubgraphData | null;
  query?: string;
}

// Sid says: Interactive Subgraph modal displaying extracted knowledge graph entities, multi-hop relationships, and document provenance
export const SubgraphViewerModal: React.FC<SubgraphViewerModalProps> = ({
  isOpen,
  onClose,
  subgraph,
  query,
}) => {
  useScrollLock(isOpen);

  const [activeTab, setActiveTab] = useState<'visual' | 'list'>('visual');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [copied, setCopied] = useState(false);

  const nodes = subgraph?.nodes || [];
  const edges = subgraph?.edges || [];

  // Filtered nodes based on search
  const filteredNodes = useMemo(() => {
    if (!searchFilter.trim()) return nodes;
    const lower = searchFilter.toLowerCase();
    return nodes.filter(
      (n) =>
        n.name?.toLowerCase().includes(lower) ||
        n.label?.toLowerCase().includes(lower) ||
        n.type?.toLowerCase().includes(lower) ||
        n.id?.toLowerCase().includes(lower)
    );
  }, [nodes, searchFilter]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return nodes[0] || null;
    return nodes.find((n) => n.id === selectedNodeId) || nodes[0] || null;
  }, [nodes, selectedNodeId]);

  // Connected edges for the selected node
  const connectedEdges = useMemo(() => {
    if (!selectedNode) return [];
    return edges.filter(
      (e) => e.source === selectedNode.id || e.target === selectedNode.id
    );
  }, [edges, selectedNode]);

  // Compute 2D coordinates for visual SVG node layout (circular distribution around center)
  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    const total = nodes.length;
    if (total === 0) return positions;

    const width = 640;
    const height = 400;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.36;

    nodes.forEach((node, idx) => {
      if (total === 1) {
        positions[node.id] = { x: centerX, y: centerY };
        return;
      }
      const angle = (2 * Math.PI * idx) / total - Math.PI / 2;
      positions[node.id] = {
        x: Math.round(centerX + radius * Math.cos(angle)),
        y: Math.round(centerY + radius * Math.sin(angle)),
      };
    });

    return positions;
  }, [nodes]);

  const handleCopyJson = () => {
    if (navigator?.clipboard && subgraph) {
      navigator.clipboard.writeText(JSON.stringify(subgraph, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!isOpen || !subgraph || (nodes.length === 0 && edges.length === 0)) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-[120] flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
      data-testid="subgraph-viewer-modal-backdrop"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Knowledge Graph Subgraph Viewer"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-4xl max-h-[90vh] bg-white dark:bg-[#161822] text-slate-900 dark:text-slate-100 border border-slate-200 dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-150"
      >
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b border-slate-200 dark:border-white/10 flex items-center justify-between gap-3 bg-slate-50 dark:bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
              <Network className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 truncate">
                <span>Knowledge Graph Subgraph</span>
                <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-medium bg-purple-100 text-purple-700 dark:bg-purple-950/80 dark:text-purple-300">
                  {nodes.length} {nodes.length === 1 ? 'node' : 'nodes'}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10.5px] font-mono font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300">
                  {edges.length} {edges.length === 1 ? 'edge' : 'edges'}
                </span>
              </h3>
              {query && (
                <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate mt-0.5">
                  Extracted for query: "{query}"
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* View Mode Toggle */}
            <div className="flex items-center rounded-xl bg-slate-200/80 dark:bg-black/40 p-0.5 border border-slate-300 dark:border-white/10 text-xs">
              <button
                type="button"
                onClick={() => setActiveTab('visual')}
                className={`px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer ${
                  activeTab === 'visual'
                    ? 'bg-purple-600 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                Visual Graph
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('list')}
                className={`px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer ${
                  activeTab === 'list'
                    ? 'bg-purple-600 text-white shadow-2xs font-semibold'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                Entities & Relations
              </button>
            </div>

            <button
              type="button"
              onClick={handleCopyJson}
              className="px-2.5 py-1.5 rounded-xl border border-slate-200 dark:border-white/10 text-xs text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors flex items-center gap-1.5 cursor-pointer"
              title="Copy Subgraph JSON payload"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{copied ? 'Copied' : 'JSON'}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/10 transition-colors cursor-pointer"
              title="Close (Esc)"
              aria-label="Close Subgraph Modal"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
          {activeTab === 'visual' ? (
            <>
              {/* Visual SVG Graph Canvas */}
              <div className="flex-1 bg-slate-950 relative overflow-hidden flex items-center justify-center p-4 min-h-[320px] select-none">
                <svg
                  viewBox="0 0 640 400"
                  className="w-full h-full max-h-[460px] drop-shadow"
                >
                  <defs>
                    <marker
                      id="arrow"
                      viewBox="0 0 10 10"
                      refX="18"
                      refY="5"
                      markerWidth="6"
                      markerHeight="6"
                      orient="auto-start-reverse"
                    >
                      <path d="M 0 0 L 10 5 L 0 10 z" fill="#818cf8" opacity="0.8" />
                    </marker>
                  </defs>

                  {/* Graph Edges */}
                  {edges.map((edge, idx) => {
                    const src = nodePositions[edge.source];
                    const tgt = nodePositions[edge.target];
                    if (!src || !tgt) return null;

                    const isHighlighted =
                      selectedNode &&
                      (edge.source === selectedNode.id || edge.target === selectedNode.id);

                    const midX = (src.x + tgt.x) / 2;
                    const midY = (src.y + tgt.y) / 2;

                    return (
                      <g key={`edge-${idx}`}>
                        <line
                          x1={src.x}
                          y1={src.y}
                          x2={tgt.x}
                          y2={tgt.y}
                          stroke={isHighlighted ? '#c084fc' : '#475569'}
                          strokeWidth={isHighlighted ? 2.5 : 1.5}
                          strokeDasharray={isHighlighted ? 'none' : '3 3'}
                          opacity={isHighlighted ? 1 : 0.6}
                          markerEnd="url(#arrow)"
                        />
                        {edge.relationship && (
                          <g transform={`translate(${midX}, ${midY})`}>
                            <rect
                              x="-34"
                              y="-9"
                              width="68"
                              height="18"
                              rx="9"
                              fill="#0f172a"
                              stroke="#64748b"
                              strokeWidth="0.8"
                              opacity="0.9"
                            />
                            <text
                              x="0"
                              y="3"
                              textAnchor="middle"
                              fill="#cbd5e1"
                              fontSize="8"
                              fontFamily="monospace"
                              fontWeight="bold"
                            >
                              {edge.relationship.length > 10
                                ? `${edge.relationship.slice(0, 9)}…`
                                : edge.relationship}
                            </text>
                          </g>
                        )}
                      </g>
                    );
                  })}

                  {/* Graph Nodes */}
                  {nodes.map((node) => {
                    const pos = nodePositions[node.id];
                    if (!pos) return null;

                    const isSelected = selectedNode?.id === node.id;
                    const initials = (node.name || node.label || 'N')
                      .split(' ')
                      .slice(0, 2)
                      .map((w) => w[0]?.toUpperCase())
                      .join('');

                    return (
                      <g
                        key={`node-${node.id}`}
                        transform={`translate(${pos.x}, ${pos.y})`}
                        onClick={() => setSelectedNodeId(node.id)}
                        className="cursor-pointer transition-transform duration-150 hover:scale-110"
                      >
                        <circle
                          r={isSelected ? 22 : 18}
                          fill={isSelected ? '#7e22ce' : '#1e1b4b'}
                          stroke={isSelected ? '#e879f9' : '#818cf8'}
                          strokeWidth={isSelected ? 3 : 1.5}
                          className="transition-all"
                        />
                        <text
                          textAnchor="middle"
                          y="4"
                          fill="#ffffff"
                          fontSize="10"
                          fontWeight="bold"
                          fontFamily="sans-serif"
                        >
                          {initials}
                        </text>
                        <text
                          textAnchor="middle"
                          y="32"
                          fill={isSelected ? '#e879f9' : '#e2e8f0'}
                          fontSize="9.5"
                          fontWeight={isSelected ? 'bold' : 'normal'}
                          fontFamily="sans-serif"
                          className="select-none"
                        >
                          {(node.name || node.label || node.id).slice(0, 16)}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                <div className="absolute bottom-2.5 left-3 text-[10.5px] font-mono text-slate-500 bg-slate-900/80 px-2.5 py-1 rounded-lg border border-slate-800">
                  Tip: Click any entity circle to view connected relationships and citations
                </div>
              </div>

              {/* Node Inspector Side Panel */}
              <div className="w-full md:w-80 border-t md:border-t-0 md:border-l border-slate-200 dark:border-white/10 p-4 bg-slate-50 dark:bg-white/[0.02] flex flex-col justify-between shrink-0 overflow-y-auto max-h-[320px] md:max-h-[460px]">
                {selectedNode ? (
                  <div className="space-y-3.5">
                    <div>
                      <span className="text-[10px] font-mono uppercase tracking-wider text-purple-600 dark:text-purple-400 font-semibold">
                        Selected Entity
                      </span>
                      <h4 className="text-sm font-bold text-slate-900 dark:text-white mt-0.5 leading-snug">
                        {selectedNode.name || selectedNode.label || selectedNode.id}
                      </h4>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300">
                          {selectedNode.type || selectedNode.label || 'Entity'}
                        </span>
                        <span className="text-[10px] font-mono text-slate-400 truncate">
                          ID: {selectedNode.id}
                        </span>
                      </div>
                    </div>

                    {/* Connected Relationships */}
                    <div>
                      <h5 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                        Connected Relations ({connectedEdges.length})
                      </h5>
                      {connectedEdges.length === 0 ? (
                        <p className="text-xs text-slate-400 italic">No direct connections found</p>
                      ) : (
                        <div className="space-y-1.5">
                          {connectedEdges.map((e, idx) => {
                            const isOutgoing = e.source === selectedNode.id;
                            const peerId = isOutgoing ? e.target : e.source;
                            const peerNode = nodes.find((n) => n.id === peerId);
                            const peerName = peerNode?.name || peerNode?.label || peerId;

                            return (
                              <div
                                key={idx}
                                onClick={() => setSelectedNodeId(peerId)}
                                className="p-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-white/5 hover:border-purple-400 transition-colors text-xs cursor-pointer flex items-center justify-between gap-2 shadow-2xs"
                              >
                                <div className="min-w-0">
                                  <span className="font-mono text-[10px] text-purple-600 dark:text-purple-400 font-bold uppercase block">
                                    {isOutgoing ? '→' : '←'} {e.relationship}
                                  </span>
                                  <span className="font-medium text-slate-800 dark:text-slate-200 truncate block">
                                    {peerName}
                                  </span>
                                </div>
                                <span className="text-[10px] font-mono text-slate-400 shrink-0">
                                  View
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Provenance Metadata if present */}
                    {selectedNode.provenance && Object.keys(selectedNode.provenance).length > 0 && (
                      <div className="pt-2 border-t border-slate-200 dark:border-white/10">
                        <h5 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                          Document Provenance
                        </h5>
                        <div className="text-[11px] font-mono text-slate-600 dark:text-slate-300 space-y-0.5 bg-white dark:bg-slate-900 p-2 rounded-xl border border-slate-200 dark:border-white/5">
                          {Object.entries(selectedNode.provenance).map(([k, v]) => (
                            <div key={k} className="truncate">
                              <span className="text-slate-400">{k}:</span> {String(v)}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-xs text-slate-400">
                    Select a node in the graph to inspect entity properties.
                  </div>
                )}
              </div>
            </>
          ) : (
            /* List / Table Tab */
            <div className="flex-1 p-4 space-y-4 overflow-y-auto max-h-[500px]">
              {/* Search input */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search entities, labels, or node IDs..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-xs rounded-xl bg-slate-100 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 focus:outline-none focus:ring-2 focus:ring-purple-500 text-slate-900 dark:text-white"
                />
              </div>

              {/* Entities Grid */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                  Knowledge Entities ({filteredNodes.length})
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {filteredNodes.map((n) => (
                    <div
                      key={n.id}
                      onClick={() => {
                        setSelectedNodeId(n.id);
                        setActiveTab('visual');
                      }}
                      className="p-2.5 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/5 hover:border-purple-400 transition-colors cursor-pointer"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">
                          {n.name || n.label || n.id}
                        </span>
                        <span className="px-1.5 py-0.5 rounded text-[9.5px] font-mono bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300 shrink-0">
                          {n.type || 'Entity'}
                        </span>
                      </div>
                      <div className="text-[10px] font-mono text-slate-400 truncate mt-0.5">
                        ID: {n.id}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Relationships List */}
              <div className="pt-2 border-t border-slate-200 dark:border-white/10">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                  Multi-Hop Graph Relationships ({edges.length})
                </h4>
                <div className="space-y-1.5 text-xs">
                  {edges.map((e, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-xl bg-slate-50 dark:bg-white/[0.02] border border-slate-200 dark:border-white/5 flex items-center justify-between gap-2 font-mono text-[11px]"
                    >
                      <span className="text-slate-700 dark:text-slate-300 truncate">
                        {e.source}
                      </span>
                      <span className="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-bold shrink-0">
                        → {e.relationship} →
                      </span>
                      <span className="text-slate-700 dark:text-slate-300 truncate text-right">
                        {e.target}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
