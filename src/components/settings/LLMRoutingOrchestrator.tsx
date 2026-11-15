import React, { useState, useEffect, useCallback } from 'react';
import {
  GripVertical,
  ArrowUp,
  ArrowDown,
  Star,
  Power,
  Zap,
  Cloud,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Cpu,
  Server,
} from 'lucide-react';
import { systemService } from '../../services/SystemService';
import type { ProviderRoutingInfo, RoutingUpdateRequest } from '../../types';

interface ProviderCardState extends ProviderRoutingInfo {
  id: string;
  name: string;
}

const DEFAULT_PROVIDERS: Record<string, ProviderCardState> = {
  vllm: {
    id: 'vllm',
    name: 'vLLM Local Engine',
    configured: true,
    model: 'Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4',
    status: 'READY',
    tier: 'Local Engine (Docker/GPU :8002)',
    is_primary: true,
    is_disabled: false,
    is_in_fallback_chain: true,
    order_rank: 1,
  },
  gemini: {
    id: 'gemini',
    name: 'Google Gemini',
    configured: true,
    model: 'gemini-flash-lite-latest',
    status: 'CONFIGURED',
    tier: 'Cloud Fast',
    is_primary: false,
    is_disabled: false,
    is_in_fallback_chain: true,
    order_rank: 2,
  },
  groq: {
    id: 'groq',
    name: 'Groq LPU',
    configured: true,
    model: 'openai/gpt-oss-120b',
    status: 'READY',
    tier: 'Cloud Fast Inference',
    is_primary: false,
    is_disabled: false,
    is_in_fallback_chain: true,
    order_rank: 3,
  },
  ollama: {
    id: 'ollama',
    name: 'Ollama Daemon',
    configured: true,
    model: 'llama3.2:latest',
    status: 'READY',
    tier: 'Local Daemon (:11434)',
    is_primary: false,
    is_disabled: false,
    is_in_fallback_chain: true,
    order_rank: 4,
  },
  local: {
    id: 'local',
    name: 'Embedded Local Fallback',
    configured: true,
    model: 'embedded-tiny-llm',
    status: 'READY',
    tier: 'On-Device Zero-Key Fallback',
    is_primary: false,
    is_disabled: false,
    is_in_fallback_chain: true,
    order_rank: 5,
  },
  mistral: {
    id: 'mistral',
    name: 'Mistral AI',
    configured: false,
    model: 'mistral-large-latest',
    status: 'DISABLED',
    tier: 'Cloud Standard',
    is_primary: false,
    is_disabled: true,
    is_in_fallback_chain: false,
    order_rank: 999,
  },
};

export const LLMRoutingOrchestrator: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [activeChain, setActiveChain] = useState<string[]>(['vllm', 'gemini', 'groq', 'ollama', 'local']);
  const [disabledList, setDisabledList] = useState<string[]>(['mistral']);
  const [primaryProvider, setPrimaryProvider] = useState<string>('vllm');
  const [providersData, setProvidersData] = useState<Record<string, ProviderCardState>>(DEFAULT_PROVIDERS);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [feedbackBanner, setFeedbackBanner] = useState<{ message: string; timestamp: string } | null>(null);

  // Auto-dismiss confirmation banner after 5 seconds
  useEffect(() => {
    if (!feedbackBanner) return;
    const timer = setTimeout(() => setFeedbackBanner(null), 5000);
    return () => clearTimeout(timer);
  }, [feedbackBanner]);

  // Load live routing from backend GET /api/system/routing
  const fetchLiveRouting = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await systemService.getRouting();
      if (res.data && res.data.fallback_order) {
        const order = res.data.fallback_order;
        const disabled = res.data.disabled_providers || [];
        const primary = res.data.primary_provider || order[0] || 'vllm';
        setActiveChain(order);
        setDisabledList(disabled);
        setPrimaryProvider(primary);

        if (res.data.providers) {
          const merged: Record<string, ProviderCardState> = { ...DEFAULT_PROVIDERS };
          Object.entries(res.data.providers).forEach(([key, info]) => {
            merged[key] = {
              ...info,
              id: key,
              name: DEFAULT_PROVIDERS[key]?.name || key.toUpperCase(),
            };
          });
          setProvidersData(merged);
        }
      }
    } catch {
      // Backend not yet wired; graceful local state retention
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

    const timeStr = new Date().toLocaleTimeString();
    const bannerMsg = `✅ ${actionDesc}: ${newPrimary.toUpperCase()} is Primary (#1) | Active Chain: ${newChain.join(' → ')}`;
    setFeedbackBanner({ message: bannerMsg, timestamp: timeStr });

    const payload: RoutingUpdateRequest = {
      fallback_order: newChain,
      disabled_providers: newDisabled,
      primary_provider: newPrimary,
      routing_policy: newPrimary === 'vllm' ? 'LOCAL_FIRST' : 'CLOUD_FIRST',
    };

    try {
      await systemService.updateRouting(payload);
    } catch {
      // Standalone mode: state preserved in UI
    }
  };

  // Reordering handlers
  const moveItem = (fromIdx: number, toIdx: number) => {
    if (toIdx < 0 || toIdx >= activeChain.length) return;
    const updated = [...activeChain];
    const [moved] = updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, moved);
    const newPrimary = updated[0];
    persistRouting(updated, disabledList, newPrimary, `Moved ${moved} to position #${toIdx + 1}`);
  };

  const makePrimary = (providerId: string) => {
    const remaining = activeChain.filter((p) => p !== providerId);
    const updated = [providerId, ...remaining];
    persistRouting(updated, disabledList, providerId, `Promoted ${providerId} to primary (#1)`);
  };

  const disableProvider = (providerId: string) => {
    const updatedChain = activeChain.filter((p) => p !== providerId);
    const updatedDisabled = Array.from(new Set([...disabledList, providerId]));
    const newPrimary = updatedChain[0] || 'local';
    persistRouting(updatedChain, updatedDisabled, newPrimary, `Disabled ${providerId}`);
  };

  const enableProvider = (providerId: string) => {
    const updatedDisabled = disabledList.filter((p) => p !== providerId);
    const updatedChain = [...activeChain, providerId];
    persistRouting(updatedChain, updatedDisabled, primaryProvider, `Enabled ${providerId}`);
  };

  // 1-Click Routing Presets
  const applyPreset = (preset: 'local' | 'cloud' | 'offline') => {
    if (preset === 'local') {
      const newChain = ['vllm', 'gemini', 'groq', 'ollama', 'local'];
      const newDisabled = disabledList.filter((p) => !newChain.includes(p));
      persistRouting(newChain, newDisabled, 'vllm', '⚡ Local GPU Preset Applied');
    } else if (preset === 'cloud') {
      const newChain = ['gemini', 'groq', 'vllm', 'ollama', 'local'];
      const newDisabled = disabledList.filter((p) => !newChain.includes(p));
      persistRouting(newChain, newDisabled, 'gemini', '☁️ Cloud First Preset Applied');
    } else if (preset === 'offline') {
      const newChain = ['vllm', 'ollama', 'local'];
      const newDisabled = ['gemini', 'groq', 'openai', 'anthropic', 'mistral', 'deepseek'];
      persistRouting(newChain, newDisabled, 'vllm', '🔒 Pure Offline (GPU Only) Preset Applied');
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
    <div className={`llm-routing-orchestrator flex flex-col gap-4 ${className}`} data-testid="llm-routing-orchestrator">
      {/* Header and Live Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2 border-b border-slate-200/80 dark:border-white/10">
        <div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <Cpu className="w-4 h-4 text-indigo-500 shrink-0" />
            <span>Interactive LLM Routing Orchestrator & Fallback Priority</span>
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
          Quick Presets:
        </span>
        <button
          type="button"
          onClick={() => applyPreset('local')}
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            primaryProvider === 'vllm'
              ? 'bg-emerald-600 text-white shadow-xs'
              : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/30 hover:bg-emerald-100'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>⚡ Local GPU (vLLM #1)</span>
        </button>
        <button
          type="button"
          onClick={() => applyPreset('cloud')}
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
            primaryProvider === 'gemini'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 border border-indigo-300 dark:border-indigo-500/30 hover:bg-indigo-100'
          }`}
        >
          <Cloud className="w-3.5 h-3.5" />
          <span>☁️ Cloud First</span>
        </button>
        <button
          type="button"
          onClick={() => applyPreset('offline')}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-slate-100 dark:bg-white/10 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-white/15 hover:bg-slate-200 transition-all cursor-pointer"
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>🔒 Pure Offline (GPU Only)</span>
        </button>
      </div>

      {/* Responsive Confirmation Banner */}
      {feedbackBanner && (
        <div className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/15 border border-emerald-300 dark:border-emerald-500/40 text-emerald-800 dark:text-emerald-200 text-xs shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center gap-2 truncate">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
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
      <div className="flex flex-col gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center justify-between">
          <span>Active Inference Chain (Ranked #1 to #{activeChain.length})</span>
          <span className="text-[10px] font-normal normal-case">Top provider executes first; falls through on error</span>
        </div>

        <div className="flex flex-col gap-1.5">
          {activeChain.map((providerId, idx) => {
            const p = providersData[providerId] || {
              id: providerId,
              name: providerId.toUpperCase(),
              configured: true,
              model: 'default',
              status: 'READY',
              tier: 'Inference Provider',
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
                className={`flex items-center justify-between p-2.5 rounded-xl border transition-all select-none ${
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
                    className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-bold shrink-0 ${
                      isPrimary
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-200 dark:bg-white/15 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {idx + 1}
                  </span>

                  <div className="flex flex-col min-w-0">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                        {p.name}
                      </span>
                      {isPrimary && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded-md bg-indigo-600 text-white text-[9.5px] font-bold uppercase tracking-wider">
                          Primary #1
                        </span>
                      )}
                      {p.tier?.includes('Docker') && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded-md bg-emerald-100 dark:bg-emerald-500/20 text-emerald-800 dark:text-emerald-300 text-[9.5px] font-medium">
                          RTX 3090 GPU
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                      Model: <code className="font-mono text-[10px]">{p.model}</code> • {p.tier}
                    </span>
                  </div>
                </div>

                {/* Control Actions: Up / Down, Make Primary, Disable */}
                <div className="flex items-center gap-1 shrink-0 ml-2">
                  {!isPrimary && (
                    <button
                      type="button"
                      onClick={() => makePrimary(providerId)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-500/20 border border-amber-300 dark:border-amber-500/30 transition-colors cursor-pointer"
                      title="Promote to Primary (#1)"
                    >
                      <Star className="w-3 h-3 fill-amber-400 text-amber-500" />
                      <span className="hidden sm:inline">Make #1</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => moveItem(idx, idx - 1)}
                    disabled={idx === 0}
                    className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 cursor-pointer"
                    title="Move Up"
                  >
                    <ArrowUp className="w-3.5 h-3.5" />
                  </button>

                  <button
                    type="button"
                    onClick={() => moveItem(idx, idx + 1)}
                    disabled={idx === activeChain.length - 1}
                    className="p-1 rounded-md text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10 disabled:opacity-30 cursor-pointer"
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
            Disabled Providers (Bypassed entirely during execution)
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {disabledList.map((pId) => {
              const p = providersData[pId] || { name: pId.toUpperCase(), model: 'disabled' };
              return (
                <div
                  key={`dis-${pId}`}
                  className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-white/5 border border-slate-300 dark:border-white/10 text-xs text-slate-600 dark:text-slate-400"
                >
                  <Server className="w-3 h-3 opacity-60" />
                  <span className="font-medium">{p.name}</span>
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
