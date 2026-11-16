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

  const isOllamaOnline =
    dynamicModels.some((m) => m.isInstalled || m.source === 'ollama_local') ||
    localDiscoveredLLMs.some((m) => m.provider === 'ollama' && m.status === 'READY');

  const isVllmOnline =
    dynamicModels.some((m) => m.source === 'vllm_local') ||
    localDiscoveredLLMs.some((m) => (m.provider === 'vllm' || m.provider === 'vllm_local') && m.status === 'READY');

  const isLocalEngineOnline =
    isVllmOnline ||
    isOllamaOnline ||
    dynamicModels.some((m) => m.isInstalled || m.source === 'ollama_local' || m.source === 'vllm_local');

  const installedModels = dynamicModels.filter(
    (m) => m.isInstalled || m.source === 'ollama_local' || m.source === 'vllm_local' || m.tier?.includes('Installed')
  );
  const catalogModels = dynamicModels.filter(
    (m) => !m.isInstalled && m.source !== 'ollama_local' && m.source !== 'vllm_local' && !m.tier?.includes('Installed')
  );

  const activeLocalEngines = localDiscoveredLLMs.filter(
    (m) =>
      (m.status === 'READY' || m.isActive) &&
      m.status !== 'LOCAL_OFFLINE' &&
      m.status !== 'OFFLINE'
  );

  return (
    <div className="space-y-4">
      {/* Local Daemons Status Check (vLLM Docker :8002 & Ollama :11434) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <span>vLLM Engine</span>
              <span
                className={`w-2 h-2 rounded-full ${
                  isVllmOnline ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse' : 'bg-zinc-600'
                }`}
              />
              <span
                className={`text-[10px] font-mono ${
                  isVllmOnline ? 'text-white font-semibold' : 'text-slate-400'
                }`}
              >
                {isVllmOnline ? 'Online (:8002)' : 'Standby (:8002)'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-mono">
              http://localhost:8002
            </p>
          </div>
        </div>

        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <span>Ollama Service</span>
              <span
                className={`w-2 h-2 rounded-full ${
                  isOllamaOnline ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse' : 'bg-zinc-600'
                }`}
              />
              <span
                className={`text-[10px] font-mono ${
                  isOllamaOnline ? 'text-white font-semibold' : 'text-slate-400'
                }`}
              >
                {isOllamaOnline ? 'Running (:11434)' : 'Standby (:11434)'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5 font-mono">
              http://localhost:11434
            </p>
          </div>
          {!isOllamaOnline && (
            <a
              href="https://ollama.ai/download"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] font-semibold text-white px-2.5 py-1 rounded-lg border border-white/15 bg-white/10 hover:bg-white/15 transition-colors flex items-center gap-1 shrink-0"
            >
              Get Ollama
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          )}
        </div>
      </div>

      {/* Model Selection from Dynamic Backend API */}
      <div className="space-y-3">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-300">Installed Local Models:</span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isLocalEngineOnline ? 'bg-white animate-pulse' : 'bg-zinc-600'
              }`}
              title={isLocalEngineOnline ? 'Local inference engine online' : 'Local inference engine offline'}
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-mono">
              {installedModels.length} installed
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
        ) : installedModels.length === 0 ? (
          <div className="p-4 rounded-xl border border-white/10 bg-black/40 text-center space-y-2">
            <p className="text-xs text-slate-300">
              No local models currently discovered in vLLM container or Ollama daemon.
            </p>
            <p className="text-[11px] text-slate-500 font-mono">
              Start vLLM container on port 8002, run <code className="text-slate-300">ollama run qwen2.5:7b</code> in your terminal, or select a catalog preset below to pull.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {installedModels.map((m) => {
              const isSelected = config.selectedLocalModel === m.model;
              const modelTooltip = (
                <div className="space-y-1 font-mono text-[11px]">
                  <div className="font-bold text-white border-b border-white/10 pb-1">
                    {m.displayName}
                  </div>
                  {m.sizeGb && (
                    <div>
                      • <strong>Disk Footprint:</strong> {m.sizeGb} GB
                    </div>
                  )}
                  {m.ramGb && (
                    <div>
                      • <strong>Memory Required:</strong> ~{m.ramGb} GB RAM
                    </div>
                  )}
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
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-white border border-white/15">
                      {m.source === 'vllm_local'
                        ? 'vLLM Local GPU Engine (:8002)'
                        : m.tier?.includes('Installed')
                          ? m.tier
                          : 'Ollama Inference Service (:11434)'}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    {m.sizeGb && (
                      <span
                        className={`text-[11px] font-mono ${
                          isSelected ? 'text-slate-800' : 'text-slate-400'
                        }`}
                      >
                        {m.sizeGb} GB
                      </span>
                    )}
                    <Tooltip content={modelTooltip} />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Downloadable Open-Weight Models Catalog */}
        {catalogModels.length > 0 && (
          <div className="pt-3 border-t border-white/10 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400">
                Downloadable Catalog Presets:
              </span>
              <span className="text-[10px] font-mono text-slate-500">
                Requires <code className="text-slate-400">ollama pull</code>
              </span>
            </div>

            <div className="space-y-1.5">
              {catalogModels.slice(0, 5).map((m) => {
                const isSelected = config.selectedLocalModel === m.model;
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
                    className={`p-2.5 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-white text-black border-white font-bold'
                        : 'bg-[#131622]/80 border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-medium truncate">{m.displayName}</span>
                      <code className="text-[10px] font-mono text-slate-500 truncate">
                        {m.model}
                      </code>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {m.sizeGb && (
                        <span className="text-[10.5px] font-mono text-slate-400">
                          ~{m.sizeGb} GB
                        </span>
                      )}
                      <span className="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                        Requires Pull
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Detected Local Runtimes (vLLM / Local GPU / Ollama) */}
        <div className="pt-3 border-t border-white/10 space-y-1.5">
          <span className="text-[11px] font-mono text-slate-400">
            Active Local Inference Engines:
          </span>
          {activeLocalEngines.length > 0 ? (
            activeLocalEngines.map((m) => (
              <div
                key={`${m.provider}-${m.model}`}
                className="p-2.5 rounded-lg border border-white/10 bg-[#131622] text-xs flex items-center justify-between"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse shrink-0" />
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
            ))
          ) : (
            <div className="p-2.5 rounded-lg border border-white/5 bg-black/20 text-[11px] font-mono text-slate-500">
              No local container or daemon active on port 8002 / 11434.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
