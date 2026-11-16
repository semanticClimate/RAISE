import { AlertCircle, CheckCircle2, Eye, EyeOff, Plus, RefreshCw, Trash2, XCircle } from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
import type { DynamicModelItem } from '../../../hooks/useDynamicModels';
import { platformAdapter } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';

export interface CloudKeysSectionProps {
  cloudDiscoveredLLMs?: DynamicModelItem[];
  liveActiveModel?: string | null;
  isLoadingLiveModels?: boolean;
  refetchLiveModels: () => void;
  isLocalProvider?: (provider: string) => boolean;
}

export const CloudKeysSection: React.FC<CloudKeysSectionProps> = ({
  refetchLiveModels,
}) => {
  const { config, addApiKey, updateApiKey, removeApiKey, setKeyVerification } =
    useControlCenterStore();

  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [focusedKeyId, setFocusedKeyId] = useState<string | null>(null);
  const [testingKeyId, setTestingKeyId] = useState<string | null>(null);

  const maskKey = (rawKey: string): string => {
    if (!rawKey) return '';
    const trimmed = rawKey.trim();
    if (trimmed.length <= 8) return 'xxxxxxxxxxxxxxxx';
    const prefix = trimmed.slice(0, 4);
    const suffix = trimmed.slice(-4);
    return `${prefix}xxxxxxxxxxxxxxxx${suffix}`;
  };

  const handleTestKey = async (id: string, provider: string, key: string) => {
    if (!key.trim()) return;
    setTestingKeyId(id);
    try {
      const res = await platformAdapter.pingApiKey(provider, key);
      const isVerified = Boolean(res.available);
      setKeyVerification(id, isVerified, res.latencyMs, res.error);
      if (isVerified) {
        if (provider && provider !== 'unknown') {
          await platformAdapter.saveConfig({
            [`${provider}_api_key`]: key.trim(),
            llm_mode: `cloud_${provider}`,
            llm_backend: provider,
          });
        }
        await refetchLiveModels();
      }
    } catch (err: any) {
      setKeyVerification(id, false, undefined, err?.message || 'Connection failed');
    } finally {
      setTestingKeyId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300">
            Configure Provider API Keys
          </span>
          <span className="text-[10px] font-mono text-slate-400">
            {(config.apiKeys || []).filter((k) => k?.key && k.key.trim().length > 0).length} configured
          </span>
        </div>

        <div className="space-y-2">
          {(config.apiKeys || []).map((item) => {
            const isFocused = focusedKeyId === item.id;
            const show = showKeys[item.id];
            const hasKey = Boolean(item.key && item.key.trim().length > 0);
            const isTesting = testingKeyId === item.id;
            const isFromEnv = Boolean(item.fromEnv);

            const displayValue = isFocused
              ? item.key
              : show
                ? item.key
                : maskKey(item.key);

            return (
              <div
                key={item.id}
                className="p-3 rounded-lg border border-white/10 bg-black/40 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
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
                      <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-white/10 text-white border border-white/20 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-white" />
                        From .env {item.envVarName ? `(${item.envVarName})` : ''}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {item.verified === true && (
                      <span className="text-[10px] font-mono text-white flex items-center gap-1 bg-white/10 px-2 py-0.5 rounded border border-white/20">
                        <CheckCircle2 className="w-3 h-3 text-white" />
                        Available ({item.latencyMs || 45}ms)
                      </span>
                    )}
                    {item.verified === false && (
                      <span className="text-[10px] font-mono text-zinc-400 flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                        <XCircle className="w-3 h-3 text-zinc-400" />
                        Unavailable / Invalid
                      </span>
                    )}
                    {hasKey && item.verified === undefined && (
                      <span className="text-[10px] font-mono text-zinc-400 flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                        <AlertCircle className="w-3 h-3 text-zinc-400" />
                        Unverified • Click Check
                      </span>
                    )}

                    {((config.apiKeys || []).length > 1 || hasKey) && (
                      <button
                        type="button"
                        onClick={async () => {
                          removeApiKey(item.id);
                          if (item.provider && item.provider !== 'unknown') {
                            await platformAdapter.saveConfig({
                              [`${item.provider}_api_key`]: '',
                            });
                            refetchLiveModels();
                          }
                        }}
                        className="text-slate-400 hover:text-white transition-colors p-1 cursor-pointer flex items-center gap-1 text-[11px]"
                        title="Delete / Clear API Key"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span className="text-[10px] text-slate-500 hover:text-white">Clear</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Input row with Paste Clipboard Button */}
                <div className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <input
                      type={show ? 'text' : 'password'}
                      placeholder="Enter API key..."
                      value={displayValue}
                      onFocus={() => setFocusedKeyId(item.id)}
                      onBlur={() => setFocusedKeyId(null)}
                      onChange={(e) => updateApiKey(item.id, e.target.value)}
                      className="w-full px-3 py-2 pr-16 rounded-lg bg-black/60 border border-white/15 text-white font-mono text-xs placeholder-slate-500 focus:outline-none focus:border-white transition-all"
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {/* Paste from clipboard button using exact requested SVG */}
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            if (navigator?.clipboard?.readText) {
                              const text = await navigator.clipboard.readText();
                              if (text) updateApiKey(item.id, text.trim());
                            }
                          } catch {}
                        }}
                        title="Paste API key from clipboard"
                        aria-label="Paste API key from clipboard"
                        className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                          />
                        </svg>
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          setShowKeys((prev) => ({ ...prev, [item.id]: !prev[item.id] }))
                        }
                        className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                        title={show ? 'Hide API key' : 'Show API key'}
                      >
                        {show ? (
                          <EyeOff className="w-3.5 h-3.5" />
                        ) : (
                          <Eye className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
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

          {(config.apiKeys || []).some((k) => k?.key && k.key.trim().length > 0) && (
            <button
              type="button"
              onClick={() => addApiKey()}
              className="w-full py-2 px-3 rounded-lg border border-dashed border-white/20 hover:border-white/40 bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-1.5 transition-all cursor-pointer mt-1"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Key
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
