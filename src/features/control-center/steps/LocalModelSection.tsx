import { ExternalLink, RefreshCw } from 'lucide-react';
import type React from 'react';
import { Tooltip } from '../components/Tooltip';
import type { DynamicModelItem } from '../../../hooks/useDynamicModels';
import type { DynamicLLMModel } from '../types';
import { useControlCenterStore } from '../store/useControlCenterStore';

export interface LocalModelSectionProps {
  dynamicModels: DynamicLLMModel[];
  localDiscoveredLLMs: DynamicModelItem[];
  isLoadingModels: boolean;
  fetchModels: () => void;
}

export const LocalModelSection: React.FC<LocalModelSectionProps> = ({
  dynamicModels,
  localDiscoveredLLMs,
  isLoadingModels,
  fetchModels,
}) => {
  const { config, updateConfig } = useControlCenterStore();

  return (
    <div className="space-y-4">
      {/* Local Daemon Status Check */}
      <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 flex items-center justify-between">
        <div>
          <div className="text-xs font-bold text-white flex items-center gap-2">
            <span>Ollama Inference Service</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Target endpoint:{' '}
            <code className="font-mono text-slate-300">http://localhost:11434</code>
          </p>
        </div>
        <a
          href="https://ollama.ai/download"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-semibold text-white px-3 py-1.5 rounded-lg border border-white/15 bg-white/10 hover:bg-white/15 transition-colors flex items-center gap-1.5"
        >
          Download Ollama
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>

      {/* Model Selection from Dynamic Backend API */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-300">Available Local Models:</span>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-mono">
              {dynamicModels.length} models detected
            </span>
            <button
              type="button"
              onClick={fetchModels}
              disabled={isLoadingModels}
              className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              title="Rescan model catalog"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingModels ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {isLoadingModels ? (
          <div className="p-6 text-center text-xs text-slate-400">
            <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-white" />
            Scanning local runtime...
          </div>
        ) : dynamicModels.length === 0 ? (
          <div className="p-6 rounded-xl border border-white/10 bg-black/40 text-center space-y-3">
            <p className="text-xs text-slate-300">
              No local models detected. Ensure Ollama is running.
            </p>
            <button
              type="button"
              onClick={fetchModels}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-white/10 hover:bg-white/15 text-white border border-white/10 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Scan Catalog
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {dynamicModels.map((m) => {
              const isSelected = config.selectedLocalModel === m.model;
              const modelTooltip = (
                <div className="space-y-1 font-mono text-[11px]">
                  <div className="font-bold text-white border-b border-white/10 pb-1">
                    {m.displayName}
                  </div>
                  <div>
                    • <strong>Disk Footprint:</strong> {m.sizeGb || 2.0} GB
                  </div>
                  <div>
                    • <strong>Memory Required:</strong> ~{m.ramGb || 4.0} GB RAM
                  </div>
                  <div>
                    • <strong>Runtime Status:</strong> {m.status}
                  </div>
                </div>
              );

              return (
                <div
                  key={m.model}
                  role="button"
                  tabIndex={0}
                  onClick={() => updateConfig({ selectedLocalModel: m.model })}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      updateConfig({ selectedLocalModel: m.model });
                    }
                  }}
                  className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                    isSelected
                      ? 'bg-white text-black border-white font-bold'
                      : 'bg-[#131622] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="text-xs font-bold">{m.displayName}</div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        isSelected ? 'bg-black/10 text-black' : 'bg-white/5 text-slate-400'
                      }`}
                    >
                      {m.model}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`text-[11px] font-mono ${
                        isSelected ? 'text-slate-800' : 'text-slate-400'
                      }`}
                    >
                      {m.sizeGb || 2.0} GB
                    </span>
                    <Tooltip content={modelTooltip} />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Detected Local Runtimes (vLLM / Local GPU / Ollama) */}
        {localDiscoveredLLMs.length > 0 && (
          <div className="pt-3 border-t border-white/10 space-y-1.5">
            <span className="text-[11px] font-mono text-slate-400">
              Detected Local Inference Engines:
            </span>
            {localDiscoveredLLMs.map((m) => (
              <div
                key={`${m.provider}-${m.model}`}
                className="p-2.5 rounded-lg border border-white/10 bg-[#131622] text-xs flex items-center justify-between"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-2 h-2 rounded-full bg-indigo-400 shrink-0" />
                  <span className="font-semibold text-white truncate">{m.displayName}</span>
                  <code className="text-[10px] font-mono bg-black/40 px-1.5 py-0.5 rounded text-slate-300 shrink-0">
                    {m.model}
                  </code>
                </div>
                {m.tier && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10 shrink-0">
                    {m.tier}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
