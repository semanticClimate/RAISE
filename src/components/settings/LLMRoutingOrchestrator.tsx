import React, { useState, useEffect, useCallback } from 'react';
import {
  GripVertical,
  ArrowUp,
  ArrowDown,
  Power,
  RefreshCw,
  CheckCircle2,
} from 'lucide-react';
import { systemService } from '../../services/SystemService';
import type { RoutingUpdateRequest } from '../../types';

interface ProviderCardState {
  id: string;
  name: string;
  status?: string;
  isOffline?: boolean;
}

const CLEAN_PROVIDER_NAMES: Record<string, string> = {
  gemini: 'Google Gemini',
  groq: 'Groq LPU',
  vllm: 'vLLM Local Engine',
  ollama: 'Ollama Daemon',
  local: 'Embedded Local Fallback',
  mistral: 'Mistral AI',
  nvidia: 'NVIDIA NIM',
  cohere: 'Cohere',
  deepseek: 'DeepSeek',
  openrouter: 'OpenRouter',
};

const DEFAULT_CHAIN = ['groq', 'gemini', 'vllm', 'ollama', 'local'];
const DEFAULT_DISABLED = ['mistral'];

export const LLMRoutingOrchestrator: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [activeChain, setActiveChain] = useState<string[]>(DEFAULT_CHAIN);
  const [disabledList, setDisabledList] = useState<string[]>(DEFAULT_DISABLED);
  const [primaryProvider, setPrimaryProvider] = useState<string>('groq');
  const [providersData, setProvidersData] = useState<Record<string, ProviderCardState>>(() => {
    const initial: Record<string, ProviderCardState> = {};
    Object.entries(CLEAN_PROVIDER_NAMES).forEach(([id, name]) => {
      initial[id] = { id, name };
    });
    return initial;
  });
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [feedbackBanner, setFeedbackBanner] = useState<{ message: string; timestamp: string } | null>(null);

  // Auto-dismiss confirmation banner after 4 seconds
  useEffect(() => {
    if (!feedbackBanner) return;
    const timer = setTimeout(() => setFeedbackBanner(null), 4000);
    return () => clearTimeout(timer);
  }, [feedbackBanner]);

  // Load live routing from backend GET /api/system/routing & GET /api/system/dynamic-llms
  const fetchLiveRouting = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await systemService.getRouting();
      const raw = res.data as any;
      if (raw) {
        const order: string[] = raw.fallback_order || raw.fallback_chain || [];
        const disabled: string[] = raw.disabled_providers || [];
        const primary: string = raw.primary_provider || order[0] || 'groq';

        if (order.length > 0) {
          setActiveChain(order);
          setPrimaryProvider(primary);
        }
        setDisabledList(disabled);

        const merged: Record<string, ProviderCardState> = {};
        Object.entries(CLEAN_PROVIDER_NAMES).forEach(([id, name]) => {
          merged[id] = { id, name };
        });

        // Parse providers whether returned as an Array or Record/Object
        if (Array.isArray(raw.providers)) {
          raw.providers.forEach((item: any) => {
            if (item && item.id) {
              const fallbackName = CLEAN_PROVIDER_NAMES[item.id] || item.id.toUpperCase();
              merged[item.id] = {
                id: item.id,
                name: item.displayName || item.name || fallbackName,
                status: item.status,
                isOffline: item.status === 'OFFLINE' || item.status === 'LOCAL_OFFLINE',
              };
            }
          });
        } else if (raw.providers && typeof raw.providers === 'object') {
          Object.entries(raw.providers).forEach(([key, info]: [string, any]) => {
            const fallbackName = CLEAN_PROVIDER_NAMES[key] || key.toUpperCase();
            merged[key] = {
              id: key,
              name: info.displayName || info.name || fallbackName,
              status: info.status,
              isOffline: info.status === 'OFFLINE' || info.status === 'LOCAL_OFFLINE',
            };
          });
        }

        setProvidersData(merged);
      }
    } catch {
      // Backend not yet reachable; state smoothly retained
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLiveRouting();
  }, [fetchLiveRouting]);

  // Save changes to backend POST /api/system/routing
  const persistRouting = async (
    newChain: string[],
    newDisabled: string[],
    newPrimary: string,
    actionDesc: string
  ) => {
    setActiveChain(newChain);
    setDisabledList(newDisabled);
    setPrimaryProvider(newPrimary);

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const bannerMsg = `${actionDesc}: ${newPrimary.toUpperCase()} is Primary (#1)`;
    setFeedbackBanner({ message: bannerMsg, timestamp: timeStr });

    const payload: RoutingUpdateRequest = {
      fallback_order: newChain,
      disabled_providers: newDisabled,
      primary_provider: newPrimary,
      routing_policy: newPrimary === 'vllm' || newPrimary === 'ollama' ? 'LOCAL_FIRST' : 'CLOUD_FIRST',
    };

    try {
      await systemService.updateRouting(payload);
    } catch {
      // Standalone mode: UI state persists locally
    }
  };

  // Reordering handlers
  const moveItem = (fromIdx: number, toIdx: number) => {
    if (toIdx < 0 || toIdx >= activeChain.length) return;
    const updated = [...activeChain];
    const [moved] = updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, moved);
    const newPrimary = updated[0];
    const movedName = providersData[moved]?.name || moved.toUpperCase();
    persistRouting(updated, disabledList, newPrimary, `Moved ${movedName} to #${toIdx + 1}`);
  };

  const disableProvider = (providerId: string) => {
    const updatedChain = activeChain.filter((p) => p !== providerId);
    const updatedDisabled = Array.from(new Set([...disabledList, providerId]));
    const newPrimary = updatedChain[0] || 'local';
    const pName = providersData[providerId]?.name || providerId.toUpperCase();
    persistRouting(updatedChain, updatedDisabled, newPrimary, `Disabled ${pName}`);
  };

  const enableProvider = (providerId: string) => {
    const updatedDisabled = disabledList.filter((p) => p !== providerId);
    const updatedChain = [...activeChain, providerId];
    const pName = providersData[providerId]?.name || providerId.toUpperCase();
    persistRouting(updatedChain, updatedDisabled, primaryProvider, `Enabled ${pName}`);
  };

  // 1-Click Routing Presets
  const applyPreset = (preset: 'local' | 'cloud' | 'offline') => {
    if (preset === 'local') {
      const newChain = ['vllm', 'gemini', 'groq', 'ollama', 'local'];
      const newDisabled = disabledList.filter((p) => !newChain.includes(p));
      persistRouting(newChain, newDisabled, 'vllm', 'Local GPU (vLLM #1)');
    } else if (preset === 'cloud') {
      const newChain = ['groq', 'gemini', 'vllm', 'ollama', 'local'];
      const newDisabled = disabledList.filter((p) => !newChain.includes(p));
      persistRouting(newChain, newDisabled, 'groq', 'Cloud First');
    } else if (preset === 'offline') {
      const newChain = ['vllm', 'ollama', 'local'];
      const newDisabled = ['gemini', 'groq', 'mistral', 'nvidia', 'cohere', 'deepseek', 'openrouter'];
      persistRouting(newChain, newDisabled, 'vllm', 'Pure Offline (GPU Only)');
    }
  };

  // Drag and drop handlers
  const handleDragStart = (idx: number) => {
    setDraggedIndex(idx);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    if (dragOverIndex !== idx) setDragOverIndex(idx);
  };

  const handleDrop = (e: React.DragEvent, targetIdx: number) => {
    e.preventDefault();
    if (draggedIndex !== null && draggedIndex !== targetIdx) {
      moveItem(draggedIndex, targetIdx);
    }
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div className={`llm-routing-orchestrator flex flex-col gap-3.5 ${className}`} data-testid="llm-routing-orchestrator">
      {/* Header and Live Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-200/80 dark:border-white/10">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Interactive LLM Routing Orchestrator & Fallback Priority
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Drag cards or use controls to set fallback order. Sub-second queries failover instantly if a provider is rate-limited or offline.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchLiveRouting}
          disabled={isLoading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-300 dark:border-white/15 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors cursor-pointer"
          title="Refresh runtime routing state"
        >
          <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Sync State</span>
        </button>
      </div>

      {/* 1-Click Routing Presets */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mr-1">
          QUICK PRESETS:
        </span>
        <button
          type="button"
          onClick={() => applyPreset('local')}
          className={`inline-flex items-center px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            primaryProvider === 'vllm'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/30 hover:bg-emerald-100'
          }`}
        >
          ⚡ Local GPU (vLLM #1)
        </button>
        <button
          type="button"
          onClick={() => applyPreset('cloud')}
          className={`inline-flex items-center px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            primaryProvider === 'groq' || primaryProvider === 'gemini'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-500/30 hover:bg-indigo-100'
          }`}
        >
          ☁️ Cloud First
        </button>
        <button
          type="button"
          onClick={() => applyPreset('offline')}
          className="inline-flex items-center px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-white/15 hover:bg-slate-200 transition-all cursor-pointer"
        >
          🔒 Pure Offline (GPU Only)
        </button>
      </div>

      {/* Confirmation Banner */}
      {feedbackBanner && (
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-300 dark:border-emerald-500/40 text-emerald-800 dark:text-emerald-200 text-xs shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center gap-1.5 truncate">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span className="font-medium truncate">{feedbackBanner.message}</span>
            <span className="text-[10px] opacity-75 shrink-0">({feedbackBanner.timestamp})</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedbackBanner(null)}
            className="text-emerald-700 hover:text-emerald-900 dark:hover:text-white shrink-0 cursor-pointer text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Active Fallback Chain Cards (Drag & Drop) */}
      <div className="flex flex-col gap-1.5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center justify-between">
          <span>ACTIVE INFERENCE CHAIN (RANKED #1 TO #{activeChain.length})</span>
          <span className="text-[10px] font-normal normal-case">Top provider executes first; falls through on error</span>
        </div>

        <div className="flex flex-col gap-1">
          {activeChain.map((providerId, idx) => {
            const p = providersData[providerId] || {
              id: providerId,
              name: CLEAN_PROVIDER_NAMES[providerId] || providerId.toUpperCase(),
            };
            const isPrimary = idx === 0;
            const isDragged = draggedIndex === idx;
            const isDropTarget = dragOverIndex === idx;

            return (
              <div
                key={providerId}
                draggable
                onDragStart={() => handleDragStart(idx)}
                onDragOver={(e) => handleDragOver(e, idx)}
                onDrop={(e) => handleDrop(e, idx)}
                onDragEnd={() => {
                  setDraggedIndex(null);
                  setDragOverIndex(null);
                }}
                className={`flex items-center justify-between px-3 py-2 rounded-xl border transition-all select-none ${
                  isPrimary
                    ? 'bg-indigo-50/70 dark:bg-indigo-500/10 border-indigo-300 dark:border-indigo-500/40 shadow-xs'
                    : 'bg-white dark:bg-white/[0.03] border-slate-200 dark:border-white/10 hover:border-slate-300'
                } ${isDragged ? 'opacity-40 scale-98' : ''} ${
                  isDropTarget ? 'ring-2 ring-indigo-500 border-transparent' : ''
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className="cursor-grab active:cursor-grabbing text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 shrink-0"
                    title="Drag to reorder"
                  >
                    <GripVertical className="w-4 h-4" />
                  </span>

                  <span
                    className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0 ${
                      isPrimary
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 dark:bg-white/15 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {idx + 1}
                  </span>

                  <div className="flex items-center gap-2 truncate">
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                      {p.name}
                    </span>
                    {isPrimary && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-indigo-600 text-white text-[9.5px] font-bold uppercase tracking-wider">
                        PRIMARY #1
                      </span>
                    )}
                    {p.isOffline && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-slate-400 text-[9.5px] font-medium">
                        Offline
                      </span>
                    )}
                  </div>
                </div>

                {/* Reordering Controls: Up, Down, Disable - clean, minimal, no 'Make #1' clutter */}
                <div className="flex items-center gap-1 shrink-0 ml-2">
                  <button
                    type="button"
                    onClick={() => moveItem(idx, idx - 1)}
                    disabled={idx === 0}
                    className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-20 cursor-pointer"
                    title="Move Up"
                  >
                    <ArrowUp className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => moveItem(idx, idx + 1)}
                    disabled={idx === activeChain.length - 1}
                    className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-20 cursor-pointer"
                    title="Move Down"
                  >
                    <ArrowDown className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => disableProvider(providerId)}
                    disabled={activeChain.length <= 1}
                    className="p-1 rounded-md text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors disabled:opacity-20 cursor-pointer"
                    title="Disable provider"
                  >
                    <Power className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Disabled Providers Pool */}
      {disabledList.length > 0 && (
        <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-200/80 dark:border-white/10">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            DISABLED PROVIDERS (BYPASSED ENTIRELY DURING EXECUTION)
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {disabledList.map((pId) => {
              const name = providersData[pId]?.name || CLEAN_PROVIDER_NAMES[pId] || pId.toUpperCase();
              return (
                <div
                  key={`dis-${pId}`}
                  className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-xs text-slate-600 dark:text-slate-400"
                >
                  <span className="font-medium">{name}</span>
                  <button
                    type="button"
                    onClick={() => enableProvider(pId)}
                    className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline font-semibold cursor-pointer pl-1"
                  >
                    Enable
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
