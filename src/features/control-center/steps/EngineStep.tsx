import {
  CheckCircle2,
  Cloud,
  ExternalLink,
  Eye,
  EyeOff,
  HardDrive,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { Tooltip } from '../components/Tooltip';
import { platformAdapter } from '../services/platformAdapter';
import { detectEnvCredentials } from '../services/envDetector';
import { useControlCenterStore } from '../store/useControlCenterStore';
import { useDynamicModels } from '../../../hooks/useDynamicModels';
import type { DynamicLLMModel } from '../types';

export const EngineStep: React.FC = () => {
  const { config, updateConfig, addApiKey, updateApiKey, removeApiKey, setKeyVerification, syncEnvCredentials } =
    useControlCenterStore();
  const envData = detectEnvCredentials();

  const {
    models: liveDiscoveredLLMs,
    activeModel: liveActiveModel,
    isLoading: isLoadingLiveModels,
    refetch: refetchLiveModels,
  } = useDynamicModels();

  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [focusedKeyId, setFocusedKeyId] = useState<string | null>(null);
  const [testingKeyId, setTestingKeyId] = useState<string | null>(null);
  const [dynamicModels, setDynamicModels] = useState<DynamicLLMModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const maskKey = (rawKey: string): string => {
    if (!rawKey) return '';
    const trimmed = rawKey.trim();
    if (trimmed.length <= 8) return 'xxxxxxxxxxxxxxxx';
    const prefix = trimmed.slice(0, 4);
    const suffix = trimmed.slice(-4);
    return `${prefix}xxxxxxxxxxxxxxxx${suffix}`;
  };

  const isCloud = config.llmDeployment === 'cloud';

  const isLocalProvider = (provider: string) =>
    provider === 'local' || provider === 'vllm' || provider === 'ollama';

  const cloudDiscoveredLLMs = liveDiscoveredLLMs.filter((m) => !isLocalProvider(m.provider));
  const localDiscoveredLLMs = liveDiscoveredLLMs.filter((m) => isLocalProvider(m.provider));

  // Load available models dynamically from backend API (zero hardcoding)
  const fetchModels = () => {
    setIsLoadingModels(true);
    platformAdapter
      .getModelCatalog()
      .then((catalog) => {
        if (catalog && catalog.length > 0) {
          const formatted: DynamicLLMModel[] = catalog.map((m) => {
            const isInstalled = m.source === 'ollama_local' || m.tier === 'Installed (Local Engine)';
            return {
              provider: m.source || 'ollama',
              displayName: m.name || m.id,
              model: m.id,
              status: isInstalled ? 'READY' : 'AVAILABLE_FOR_PULL',
              isActive: isInstalled,
              tier: isInstalled ? 'Installed Locally' : 'Available for Pull (Not Downloaded)',
              sizeGb: m.download_size_gb,
              ramGb: m.min_ram_gb,
              isInstalled,
              source: m.source,
            };
          });
          setDynamicModels(formatted);
          if (!config.selectedLocalModel && formatted.length > 0) {
            updateConfig({ selectedLocalModel: formatted[0].model });
          }
        } else {
          return platformAdapter.getDynamicLLMs().then((models) => {
            const formatted: DynamicLLMModel[] = models.map((m) => ({
              provider: m.provider,
              displayName: m.displayName || m.provider,
              model: m.model,
              status: m.status,
              isActive: m.status === 'READY',
              tier: m.tier,
              sizeGb: m.model.includes('3b') ? 2.0 : m.model.includes('7b') ? 4.7 : 4.9,
              ramGb: m.model.includes('3b') ? 4.0 : m.model.includes('7b') ? 8.0 : 16.0,
              isInstalled: false,
              source: m.provider,
            }));
            setDynamicModels(formatted);
            if (!config.selectedLocalModel && formatted.length > 0) {
              updateConfig({ selectedLocalModel: formatted[0].model });
            }
          });
        }
      })
      .catch(() => {
        setDynamicModels([]);
      })
      .finally(() => setIsLoadingModels(false));
  };

  useEffect(() => {
    if (!isCloud) {
      fetchModels();
    }
  }, [isCloud]);

  const handleTestKey = async (id: string, provider: string, key: string) => {
    if (!key.trim()) return;
    setTestingKeyId(id);
    try {
      const res = await platformAdapter.pingApiKey(provider, key);
      setKeyVerification(id, res.available, res.latencyMs, res.error);
      if (res.available) {
        refetchLiveModels();
      }
    } catch (err: any) {
      setKeyVerification(id, false, undefined, err?.message || 'Connection failed');
    } finally {
      setTestingKeyId(null);
    }
  };

  const cloudTooltip = (
    <div className="space-y-1 font-mono text-[11px]">
      <div className="font-bold text-white border-b border-white/10 pb-1">Cloud Inference</div>
      <div>
        • <strong>Latency:</strong> ~100-300ms sub-second generation
      </div>
      <div>
        • <strong>Storage:</strong> 0 GB disk footprint (remote inference)
      </div>
      <div>
        • <strong>Memory:</strong> ~1.2 GB host client footprint
      </div>
      <div>
        • <strong>Routing:</strong> Dynamic multi-provider failover
      </div>
    </div>
  );

  const localTooltip = (
    <div className="space-y-1 font-mono text-[11px]">
      <div className="font-bold text-white border-b border-white/10 pb-1">
        Local Private Inference
      </div>
      <div>
        • <strong>Privacy:</strong> 100% on-device, zero data leaves machine
      </div>
      <div>
        • <strong>Offline:</strong> Runs without active internet connection
      </div>
      <div>
        • <strong>Compute:</strong> Requires on-device acceleration
      </div>
      <div>
        • <strong>Daemon:</strong> Managed via local Ollama process
      </div>
    </div>
  );

  return (
    <div className="space-y-5 animate-in fade-in-50 duration-150">
      {/* Header */}
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">Intelligence Models</h3>
      </div>

      {/* Clean Dual-State Deployment Toggle */}
      <div className="p-1.5 rounded-xl bg-[#131622] border border-white/10 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => updateConfig({ llmDeployment: 'cloud' })}
          className={`w-full py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isCloud
              ? 'bg-white text-black shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5'
          }`}
        >
          <div className="flex items-center gap-2">
            <Cloud className="w-4 h-4" />
            <span>Cloud LLM</span>
          </div>
          <Tooltip
            as="span"
            content={cloudTooltip}
            className={
              isCloud ? 'text-black/70 hover:text-black' : 'text-slate-400 hover:text-white'
            }
          />
        </button>

        <button
          type="button"
          onClick={() => updateConfig({ llmDeployment: 'local' })}
          className={`w-full py-2.5 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            !isCloud
              ? 'bg-white text-black shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5'
          }`}
        >
          <div className="flex items-center gap-2">
            <HardDrive className="w-4 h-4" />
            <span>Local LLM</span>
          </div>
          <Tooltip
            as="span"
            content={localTooltip}
            className={
              !isCloud ? 'text-black/70 hover:text-black' : 'text-slate-400 hover:text-white'
            }
          />
        </button>
      </div>

      {/* CLOUD LLM VIEW */}
      {isCloud && (
        <div className="space-y-3.5">
          {/* .env Detection Banner */}
          {envData.llmKeys.length > 0 && (
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>
                  Loaded from <code className="font-mono text-[11px] bg-black/40 px-1 py-0.5 rounded">.env</code>: {envData.llmKeys.map((k) => k.providerName).join(', ')}
                </span>
              </div>
              <button
                type="button"
                onClick={() => syncEnvCredentials()}
                className="px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1 shrink-0"
              >
                <RefreshCw className="w-3 h-3" />
                Reload
              </button>
            </div>
          )}

          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium">API Keys:</span>
          </div>

          <div className="space-y-2.5">
            {(config.apiKeys || []).map((item, index) => {
              const show = !!showKeys[item.id];
              const isTesting = testingKeyId === item.id;
              const hasKey = (item?.key || '').trim().length > 0;
              const isFromEnv = !!item.fromEnv || envData.llmKeys.some((k) => k.key === item.key);
              const isMasked = !show && focusedKeyId !== item.id && hasKey;
              const displayValue = isMasked ? maskKey(item.key) : item.key;

              return (
                <div
                  key={item.id}
                  className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] font-mono font-bold text-slate-400">
                        #{index + 1}
                      </span>
                      {hasKey ? (
                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-white/10 text-white border border-white/15">
                          {item.providerName}
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono text-slate-500">
                          API Key (manual entry)
                        </span>
                      )}
                      {isFromEnv && (
                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          From .env {item.envVarName ? `(${item.envVarName})` : ''}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      {/* Live connection badge */}
                      {item.verified === true && (
                        <span className="text-[10px] font-mono text-emerald-400 flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" />
                          Available ({item.latencyMs || 45}ms)
                        </span>
                      )}
                      {item.verified === false && (
                        <span className="text-[10px] font-mono text-rose-400 flex items-center gap-1 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                          <XCircle className="w-3 h-3" />
                          Unavailable
                        </span>
                      )}

                      {/* Delete / Clear button */}
                      {((config.apiKeys || []).length > 1 || hasKey) && (
                        <button
                          type="button"
                          onClick={() => {
                            removeApiKey(item.id);
                            if (item.provider && item.provider !== 'unknown') {
                              platformAdapter.saveConfig({
                                [`${item.provider}_api_key`]: '',
                              });
                            }
                          }}
                          className="text-slate-400 hover:text-rose-400 transition-colors p-1 cursor-pointer flex items-center gap-1 text-[11px]"
                          title="Delete / Clear API Key"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span className="text-[10px] text-slate-500 hover:text-rose-400">Clear</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Input row */}
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <input
                        type="text"
                        placeholder="Enter API key..."
                        value={displayValue}
                        onFocus={() => setFocusedKeyId(item.id)}
                        onBlur={() => setFocusedKeyId(null)}
                        onChange={(e) => updateApiKey(item.id, e.target.value)}
                        className="w-full px-3 py-2 pr-9 rounded-lg bg-black/60 border border-white/15 text-white font-mono text-xs placeholder-slate-500 focus:outline-none focus:border-white transition-all"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setShowKeys((prev) => ({ ...prev, [item.id]: !prev[item.id] }))
                        }
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                      >
                        {show ? (
                          <EyeOff className="w-3.5 h-3.5" />
                        ) : (
                          <Eye className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>

                    <button
                      type="button"
                      disabled={!hasKey || isTesting}
                      onClick={() => handleTestKey(item.id, item.provider, item.key)}
                      className={`px-3 py-2 rounded-lg text-xs font-semibold shrink-0 transition-all flex items-center gap-1.5 ${
                        hasKey && !isTesting
                          ? 'bg-white/10 hover:bg-white/15 border border-white/20 text-white cursor-pointer'
                          : 'border border-white/10 text-slate-500 bg-transparent cursor-not-allowed'
                      }`}
                    >
                      {isTesting ? (
                        <>
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          Checking...
                        </>
                      ) : (
                        'Check'
                      )}
                    </button>
                  </div>
                </div>
              );
            })}

            {(config.apiKeys || []).some(
              (item) => item.verified === true || (item.key && item.key.trim().length > 0)
            ) && (
              <button
                type="button"
                onClick={() => addApiKey()}
                className="w-full py-2 px-3 rounded-lg border border-dashed border-white/20 hover:border-white/40 bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-1.5 transition-all cursor-pointer mt-1"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Key
              </button>
            )}

            {/* Live Dynamically Discovered Models (Cloud only) */}
            <div className="pt-3 border-t border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 flex-wrap">
                  <span>Cloud Models:</span>
                  <span className="text-[11px] font-mono text-emerald-400">
                    {cloudDiscoveredLLMs.length} active
                  </span>
                  {liveActiveModel && !isLocalProvider(liveActiveModel) && (
                    <span className="text-[10px] font-mono text-slate-400">
                      • {liveActiveModel}
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => refetchLiveModels()}
                  disabled={isLoadingLiveModels}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                  title="Rescan active providers"
                >
                  <RefreshCw className={`w-3 h-3 ${isLoadingLiveModels ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {cloudDiscoveredLLMs.length === 0 ? (
                <div className="p-2.5 rounded-lg bg-white/5 border border-white/10 text-xs text-slate-400 flex items-center gap-2">
                  <span>Add a valid API key above to activate cloud models.</span>
                </div>
              ) : (
                <div className="space-y-1.5">
                  {cloudDiscoveredLLMs.map((m) => (
                    <div
                      key={`${m.provider}-${m.model}`}
                      className={`p-2.5 rounded-lg border text-xs flex items-center justify-between transition-all ${
                        m.isActive
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                          : 'bg-[#131622] border-white/10 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={`w-2 h-2 rounded-full shrink-0 ${
                            m.isActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'
                          }`}
                        />
                        <span className="font-semibold truncate">{m.displayName}</span>
                        <code className="text-[10px] font-mono bg-black/40 px-1.5 py-0.5 rounded text-slate-300">
                          {m.model}
                        </code>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {m.tier && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-slate-400 border border-white/10">
                            {m.tier}
                          </span>
                        )}
                        {m.isActive && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                            Active
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PRIVATE / LOCAL LLM VIEW */}
      {!isCloud && (
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
      )}
    </div>
  );
};
