import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  GripVertical,
  ArrowUp,
  ArrowDown,
  Power,
  RefreshCw,
  CheckCircle2,
  ChevronRight,
  HelpCircle,
} from 'lucide-react';
import { systemService } from '../../services/SystemService';
import type { RoutingUpdateRequest } from '../../types';
import { useControlCenterStore } from '../../features/control-center/store/useControlCenterStore';

interface ProviderCardState {
  id: string;
  name: string;
  status?: string;
  isOffline?: boolean;
  isConfigured?: boolean;
  tier?: string;
  model?: string;
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
  universal: 'Universal / Custom API',
};

// Canonical provider ID normalizer to prevent duplication (e.g. custom vs universal)
const canonicalId = (pid: string): string => {
  const norm = (pid || '').toLowerCase().trim();
  if (norm === 'custom') return 'universal';
  return norm;
};

const DEFAULT_DISABLED = ['mistral'];

export const LLMRoutingOrchestrator: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [activeChain, setActiveChain] = useState<string[]>([]);
  const [disabledList, setDisabledList] = useState<string[]>(DEFAULT_DISABLED);
  const [primaryProvider, setPrimaryProvider] = useState<string>('gemini');
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
  const [showDisabled, setShowDisabled] = useState<boolean>(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup debounce timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // Auto-dismiss confirmation banner after 4 seconds
  useEffect(() => {
    if (!feedbackBanner) return;
    const timer = setTimeout(() => setFeedbackBanner(null), 4000);
    return () => clearTimeout(timer);
  }, [feedbackBanner]);

  // Load live routing from backend GET /api/system/routing & dynamically filter to detected/connected LLMs
  const fetchLiveRouting = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await systemService.getRouting();
      const raw = res.data as any;
      if (raw) {
        const rawOrder: string[] = (raw.fallback_order || raw.fallback_chain || []).map(canonicalId);
        const disabled: string[] = (raw.disabled_providers || []).map(canonicalId);
        const primary: string = canonicalId(
          raw.pinned_primary_provider ||
          raw.primary_provider ||
          'gemini'
        );

        const storeApiKeys = useControlCenterStore.getState().config.apiKeys || [];
        const hasStoreKey = (pid: string) => {
          const norm = canonicalId(pid);
          return storeApiKeys.some((k) => {
            const kProv = canonicalId(k?.provider);
            const isVerified = k?.verified === true && (typeof k?.latencyMs === 'number' && k.latencyMs > 0);
            const hasValidKey = Boolean(k?.key && k.key.trim().length >= 8);
            return (isVerified || hasValidKey) && kProv === norm;
          });
        };

        const merged: Record<string, ProviderCardState> = {};
        Object.entries(CLEAN_PROVIDER_NAMES).forEach(([id, name]) => {
          merged[id] = { id, name };
        });

        // Parse providers whether returned as an Array or Record/Object
        const providersSource: any[] = Array.isArray(raw.providers_list)
          ? raw.providers_list
          : Array.isArray(raw.providers)
            ? raw.providers
            : typeof raw.providers === 'object' && raw.providers !== null
              ? Object.entries(raw.providers).map(([k, v]: [string, any]) => ({ id: k, ...v }))
              : [];

        providersSource.forEach((item: any) => {
          if (!item || !item.id) return;
          const pid = canonicalId(item.id);
          const fallbackName = CLEAN_PROVIDER_NAMES[pid] || item.displayName || pid.toUpperCase();
          const status = (item.status || '').toUpperCase().trim();
          const isOffline = status === 'OFFLINE' || status === 'LOCAL_OFFLINE';
          const isConfigured = Boolean(
            item.configured ||
            item.isActive ||
            status === 'READY' ||
            status === 'CONFIGURED' ||
            status === 'ACTIVE' ||
            hasStoreKey(pid)
          );

          merged[pid] = {
            id: pid,
            name: item.displayName || fallbackName,
            status: item.status,
            isOffline,
            isConfigured,
            tier: item.tier,
            model: item.model,
          };
        });

        // Also merge any configured or verified keys present in the control center store
        storeApiKeys.forEach((k) => {
          if (!k?.provider || k.provider === 'unknown') return;
          const pid = canonicalId(k.provider);
          const hasValidKey = Boolean(k?.key && k.key.trim().length >= 8);
          const isVerified = k.verified === true && (typeof k.latencyMs === 'number' && k.latencyMs > 0);
          if (!hasValidKey && !isVerified) return;
          if (!merged[pid]) {
            merged[pid] = {
              id: pid,
              name: k.providerName || CLEAN_PROVIDER_NAMES[pid] || pid.toUpperCase(),
              status: 'READY',
              isOffline: false,
              isConfigured: true,
              tier: isVerified ? `Connected (${k.latencyMs}ms)` : 'Configured (Active)',
              model: (k as any).model || (pid === 'gemini' ? 'gemini-2.5-flash' : 'Universal Custom LLM'),
            };
          } else {
            merged[pid].isConfigured = true;
            merged[pid].status = 'READY';
            merged[pid].isOffline = false;
          }
        });

        // Determine strictly if a provider is live, detected, and connected
        const isConnectedAndLive = (pid: string): boolean => {
          const norm = canonicalId(pid);
          const info = merged[norm];

          // 1. Providers already present in rawOrder (the server's active fallback chain)
          // Do not discard unless explicitly marked isOffline: true (prevents flash during reordering)
          if (rawOrder.includes(norm)) {
            if (info && info.isOffline) {
              return false;
            }
            return true;
          }

          // 2. Local engines: MUST be actively running and responding (status READY/ONLINE/ACTIVE)
          // OFFLINE, LOCAL_OFFLINE, STANDBY mean not running or not loaded in process
          if (norm === 'vllm' || norm === 'ollama' || norm === 'local') {
            if (!info) return false;
            if (info.isOffline) return false;
            const st = (info.status || '').toUpperCase().trim();
            return st === 'READY' || st === 'ONLINE' || st === 'ACTIVE';
          }

          // 3. Cloud engines (Gemini, Groq, Universal, etc.):
          // Live if valid key is in store or reported configured/ready by backend
          if (hasStoreKey(norm)) return true;

          if (info) {
            if (info.isOffline) return false;
            const st = (info.status || '').toUpperCase().trim();
            if (st === 'NOT_CONFIGURED' || st === 'OFFLINE' || st === 'STANDBY' || st === 'LOCAL_OFFLINE') {
              return false;
            }
            if (st === 'CONFIGURED' || st === 'READY' || st === 'ONLINE' || st === 'ACTIVE') {
              return true;
            }
            if (info.isConfigured) return true;
          }

          return false;
        };

        // Construct activeChain strictly from connected & detected providers (deduplicated)
        const liveChain: string[] = [];
        const pushToChain = (pid: string) => {
          const cId = canonicalId(pid);
          if (cId && !liveChain.includes(cId) && isConnectedAndLive(cId) && !disabled.includes(cId)) {
            liveChain.push(cId);
          }
        };

        if (primary) pushToChain(primary);
        rawOrder.forEach(pushToChain);
        Object.keys(merged).forEach(pushToChain);

        setActiveChain(liveChain);
        setDisabledList(disabled);
        setPrimaryProvider(liveChain[0] || primary);
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
    const handleSyncEvent = () => {
      fetchLiveRouting();
    };
    window.addEventListener('raise:sync-routing', handleSyncEvent);
    const interval = setInterval(() => {
      fetchLiveRouting();
    }, 10000);
    return () => {
      window.removeEventListener('raise:sync-routing', handleSyncEvent);
      clearInterval(interval);
    };
  }, [fetchLiveRouting]);

  // Save changes to backend POST /api/system/routing with optimistic UI & 300ms debounce
  const persistRouting = (
    newChain: string[],
    newDisabled: string[],
    newPrimary: string,
    actionDesc: string
  ) => {
    // 1. Immediate optimistic local state update for 60 FPS responsiveness
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

    // 2. Debounce server persistence by 300ms
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(async () => {
      try {
        await systemService.updateRouting(payload);
      } catch {
        setFeedbackBanner({
          message: 'Backend unreachable: Failed to persist routing priority. Check port 8000.',
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    }, 300);
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
    const newPrimary = updatedChain[0] || primaryProvider;
    const pName = providersData[providerId]?.name || providerId.toUpperCase();
    persistRouting(updatedChain, updatedDisabled, newPrimary, `Disabled ${pName}`);
  };

  const enableProvider = (providerId: string) => {
    const updatedDisabled = disabledList.filter((p) => p !== providerId);
    const updatedChain = [...activeChain, providerId];
    const pName = providersData[providerId]?.name || providerId.toUpperCase();
    persistRouting(updatedChain, updatedDisabled, primaryProvider, `Enabled ${pName}`);
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-white/10">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Interactive LLM Routing Orchestrator & Fallback Priority
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Only verified, connected LLMs are shown in the active execution chain. Sub-second queries failover sequentially down the chain.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchLiveRouting}
          disabled={isLoading}
          className="self-start sm:self-auto inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-white/20 text-white bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
          title="Refresh runtime routing state"
        >
          <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Sync State</span>
        </button>
      </div>

      {/* Confirmation Banner */}
      {feedbackBanner && (
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-white/10 border border-white/20 text-white text-xs shadow-xs animate-in fade-in duration-200">
          <div className="flex items-center gap-1.5 truncate">
            <CheckCircle2 className="w-3.5 h-3.5 text-white shrink-0" />
            <span className="font-medium truncate">{feedbackBanner.message}</span>
            <span className="text-[10px] opacity-75 shrink-0 font-mono">({feedbackBanner.timestamp})</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedbackBanner(null)}
            className="text-zinc-400 hover:text-white shrink-0 cursor-pointer text-xs"
          >
            ✕
          </button>
        </div>
      )}

      {/* Active Inference Chain Cards (Drag & Drop) */}
      <div className="flex flex-col gap-1.5">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
          <span>ACTIVE INFERENCE CHAIN (RANKED #1 TO #{Math.max(1, activeChain.length)})</span>
          <span className="text-[10px] font-normal normal-case text-slate-400">Top provider executes first; falls through on error</span>
        </div>

        <div className="flex flex-col gap-1">
          {activeChain.length === 0 ? (
            <div className="p-4 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] text-left space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <HelpCircle className="w-4 h-4 text-slate-300" />
                <span>No Active LLM Inference Engine</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Connect a verified cloud API key (Google Gemini, Groq, OpenAI) in <strong>Cloud LLM</strong> or launch a local container (vLLM / Ollama) in <strong>Local LLM</strong>. The orchestrator will automatically place the first available engine as Primary #1.
              </p>
            </div>
          ) : (
            activeChain.map((providerId, idx) => {
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
                  draggable={activeChain.length > 1}
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={(e) => handleDragOver(e, idx)}
                  onDrop={(e) => handleDrop(e, idx)}
                  onDragEnd={() => {
                    setDraggedIndex(null);
                    setDragOverIndex(null);
                  }}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl border transition-all select-none ${
                    isPrimary
                      ? 'bg-white/10 border-white/30 text-white shadow-xs'
                      : 'bg-[#131622] border-white/15 text-white hover:border-white/25'
                  } ${isDragged ? 'opacity-40 scale-98' : ''} ${
                    isDropTarget ? 'ring-2 ring-white border-transparent' : ''
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span
                      className={`text-slate-400 shrink-0 ${
                        activeChain.length > 1
                          ? 'cursor-grab active:cursor-grabbing hover:text-white'
                          : 'opacity-30 cursor-default'
                      }`}
                      title={activeChain.length > 1 ? 'Drag to reorder' : 'Single provider active'}
                    >
                      <GripVertical className="w-4 h-4" />
                    </span>

                    <span
                      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0 ${
                        isPrimary
                          ? 'bg-white text-black'
                          : 'bg-white/10 text-white border border-white/20'
                      }`}
                    >
                      {idx + 1}
                    </span>

                    <div className="flex items-center gap-2 truncate">
                      <span className="text-xs font-semibold text-white truncate">
                        {p.name}
                      </span>
                      {isPrimary ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-white text-black text-[9.5px] font-bold uppercase tracking-wider">
                          PRIMARY #1
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded-md bg-white/10 text-white border border-white/20 text-[9.5px] font-medium">
                          FALLBACK #{idx + 1}
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-white/10 text-white border border-white/15 text-[9.5px] font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse" />
                        Online
                      </span>
                    </div>
                  </div>

                  {/* Reordering Controls: Up, Down, Disable */}
                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <button
                      type="button"
                      onClick={() => moveItem(idx, idx - 1)}
                      disabled={idx === 0}
                      className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 disabled:opacity-20 cursor-pointer"
                      title="Move Up"
                    >
                      <ArrowUp className="w-3.5 h-3.5" />
                    </button>

                    <button
                      type="button"
                      onClick={() => moveItem(idx, idx + 1)}
                      disabled={idx === activeChain.length - 1}
                      className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 disabled:opacity-20 cursor-pointer"
                      title="Move Down"
                    >
                      <ArrowDown className="w-3.5 h-3.5" />
                    </button>

                    <button
                      type="button"
                      onClick={() => disableProvider(providerId)}
                      disabled={activeChain.length <= 1}
                      className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors disabled:opacity-20 cursor-pointer"
                      title="Disable provider"
                    >
                      <Power className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Disabled Providers Pool (Collapsible) */}
      {disabledList.length > 0 && (
        <div className="pt-2 border-t border-white/10">
          <button
            type="button"
            onClick={() => setShowDisabled((prev) => !prev)}
            className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            <ChevronRight
              className={`w-3 h-3 text-slate-400 transition-transform ${showDisabled ? 'rotate-90' : ''}`}
            />
            <span>Disabled Providers ({disabledList.length})</span>
          </button>

          {showDisabled && (
            <div className="flex flex-wrap items-center gap-1.5 mt-2 pl-4 animate-in fade-in duration-100">
              {disabledList.map((pId) => {
                const name = providersData[pId]?.name || CLEAN_PROVIDER_NAMES[pId] || pId.toUpperCase();
                return (
                  <div
                    key={`dis-${pId}`}
                    className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-300"
                  >
                    <span className="font-medium">{name}</span>
                    <button
                      type="button"
                      onClick={() => enableProvider(pId)}
                      className="text-[11px] text-white hover:underline font-semibold cursor-pointer pl-1"
                    >
                      Enable
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
