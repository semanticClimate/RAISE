import {
  ChevronRight,
  ExternalLink,
  HelpCircle,
  HardDrive,
  RefreshCw,
  Terminal,
} from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
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

  const [showCatalog, setShowCatalog] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

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

  return (
    <div className="space-y-4">
      {/* 1. COMPACT ENGINE STATUS STRIP */}
      <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="relative">
            <HardDrive className="w-4 h-4 text-white shrink-0" />
            <span
              className={`absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full ${
                isLocalEngineOnline ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse' : 'bg-zinc-600'
              }`}
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-white">Local Runtimes:</span>
            {isVllmOnline && (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/10 border border-white/20 text-[11px] font-mono text-white">
                <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse" />
                vLLM Engine (Online)
              </span>
            )}
            {isOllamaOnline && (
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-white/10 border border-white/20 text-[11px] font-mono text-white">
                <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse" />
                Ollama (Running)
              </span>
            )}
            {!isVllmOnline && !isOllamaOnline && (
              <span className="text-[11px] font-mono text-slate-400">
                None active
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <button
            type="button"
            onClick={fetchModels}
            disabled={isLoadingModels}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-white/15 bg-white/5 hover:bg-white/10 text-white text-xs font-medium transition-colors cursor-pointer"
            title="Rescan installed local models"
          >
            <RefreshCw className={`w-3 h-3 ${isLoadingModels ? 'animate-spin' : ''}`} />
            <span>Rescan</span>
          </button>
        </div>
      </div>

      {/* 2. PRIMARY VIEW: INSTALLED LOCAL MODELS */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-bold text-white tracking-tight">
            Installed Models
          </span>
          <span className="text-[11px] font-mono text-slate-400">
            {installedModels.length} detected
          </span>
        </div>

        {isLoadingModels ? (
          <div className="p-8 text-center text-xs text-slate-400 rounded-2xl bg-[#111111] border border-[#292929]">
            <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-2 text-white" />
            Scanning local Docker containers and Ollama runtime...
          </div>
        ) : installedModels.length === 0 ? (
          /* Empty State: Actionable guidance */
          <div className="p-4 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] text-left space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <HelpCircle className="w-4 h-4 text-slate-300" />
              <span>No Local Models Detected</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              No active model was found in your local vLLM container (:8002) or Ollama service (:11434).
            </p>
            <div className="p-3 rounded-xl bg-black/60 border border-white/10 space-y-1.5 text-xs">
              <div className="text-slate-300 font-semibold flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5 text-white" />
                <span>Quick Setup (Terminal):</span>
              </div>
              <div className="font-mono text-[11px] text-white bg-black/40 p-2 rounded border border-white/10 select-all">
                ollama run &lt;model-name&gt;
              </div>
              <p className="text-[10.5px] text-slate-400">
                After pulling or starting your container, click &ldquo;Rescan&rdquo; above. Or switch to Cloud LLM to start immediately without downloading.
              </p>
            </div>
          </div>
        ) : (
          /* Installed models cards */
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
                    • <strong>Source:</strong> {m.source === 'vllm_local' ? 'vLLM Engine' : 'Ollama Service'}
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
                  className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center justify-between gap-3 ${
                    isSelected
                      ? 'bg-white text-black border-white font-bold shadow-sm'
                      : 'bg-[#111111] border-[#292929] text-white hover:border-white/25 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                        isSelected
                          ? 'bg-black ring-2 ring-black/20'
                          : 'bg-white/20 border border-white/40'
                      }`}
                    />
                    <div className="min-w-0">
                      <div className="text-xs font-bold truncate">{m.displayName}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.2 rounded ${
                            isSelected ? 'bg-black/10 text-black' : 'bg-white/10 text-slate-300 border border-white/15'
                          }`}
                        >
                          {m.source === 'vllm_local' ? 'vLLM GPU Engine' : 'Ollama'}
                        </span>
                        <span
                          className={`text-[10px] font-mono truncate ${
                            isSelected ? 'text-slate-800' : 'text-slate-400'
                          }`}
                        >
                          {m.model}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    {m.sizeGb && (
                      <span
                        className={`text-[11px] font-mono ${
                          isSelected ? 'text-slate-800 font-bold' : 'text-slate-400'
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
      </div>

      {/* 3. PROGRESSIVE DISCLOSURE: COLLAPSIBLE CATALOG PRESETS */}
      {catalogModels.length > 0 && (
        <div className="pt-2 border-t border-white/10">
          <button
            type="button"
            onClick={() => setShowCatalog((prev) => !prev)}
            className="w-full flex items-center justify-between text-xs font-medium text-slate-300 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2">
              <ChevronRight
                className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showCatalog ? 'rotate-90' : ''}`}
              />
              <span>Downloadable Catalog Presets ({catalogModels.length})</span>
            </div>
            <span className="text-[10.5px] font-mono text-slate-500">
              {showCatalog ? 'Collapse' : 'Expand'}
            </span>
          </button>

          {showCatalog && (
            <div className="mt-2 space-y-1.5 pl-2 animate-in fade-in duration-100">
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
                    className={`p-2.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                      isSelected
                        ? 'bg-white text-black border-white font-bold'
                        : 'bg-[#111111]/80 border-[#292929] text-slate-300 hover:border-white/20 hover:bg-white/5'
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
          )}
        </div>
      )}

      {/* 4. PROGRESSIVE DISCLOSURE: COLLAPSIBLE DAEMON DIAGNOSTICS & PORTS */}
      <div className="pt-2 border-t border-white/10">
        <button
          type="button"
          onClick={() => setShowDiagnostics((prev) => !prev)}
          className="w-full flex items-center justify-between text-xs font-medium text-slate-400 hover:text-white p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <ChevronRight
              className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showDiagnostics ? 'rotate-90' : ''}`}
            />
            <span>Daemon Diagnostics & Endpoints</span>
          </div>
          <span className="text-[10.5px] font-mono text-slate-500">
            {showDiagnostics ? 'Hide' : 'Show'}
          </span>
        </button>

        {showDiagnostics && (
          <div className="mt-2 p-3 rounded-xl bg-black/60 border border-white/10 space-y-2.5 animate-in fade-in duration-100 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 space-y-1">
                <div className="text-[11px] font-bold text-white flex items-center justify-between">
                  <span>vLLM Engine Port:</span>
                  <span className="font-mono text-slate-300">8002</span>
                </div>
                <div className="text-[10.5px] font-mono text-slate-400">http://localhost:8002</div>
                <div className="text-[10px] text-slate-500">
                  Container status: {isVllmOnline ? 'Running / Responding' : 'Offline'}
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 space-y-1">
                <div className="text-[11px] font-bold text-white flex items-center justify-between">
                  <span>Ollama Service Port:</span>
                  <span className="font-mono text-slate-300">11434</span>
                </div>
                <div className="text-[10.5px] font-mono text-slate-400">http://localhost:11434</div>
                <div className="text-[10px] text-slate-500 flex items-center justify-between">
                  <span>Daemon status: {isOllamaOnline ? 'Running' : 'Standby'}</span>
                  {!isOllamaOnline && (
                    <a
                      href="https://ollama.ai/download"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-white hover:underline flex items-center gap-0.5"
                    >
                      <span>Install</span>
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
