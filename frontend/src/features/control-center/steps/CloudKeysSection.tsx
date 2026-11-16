import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  Clipboard,
  Eye,
  EyeOff,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  XCircle,
} from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
import type { DynamicModelItem } from '../../../hooks/useDynamicModels';
import { platformAdapter } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { DetectedProvider } from '../services/keyDetector';

export interface CloudKeysSectionProps {
  cloudDiscoveredLLMs?: DynamicModelItem[];
  liveActiveModel?: string | null;
  isLoadingLiveModels?: boolean;
  refetchLiveModels: () => void;
  isLocalProvider?: (provider: string) => boolean;
}

interface ProviderMeta {
  id: DetectedProvider;
  name: string;
  placeholder: string;
  defaultModel: string;
}

const CLOUD_PROVIDERS: ProviderMeta[] = [
  { id: 'gemini', name: 'Google Gemini', placeholder: 'Enter Gemini API key (AIzaSy...)...', defaultModel: 'gemini-2.5-flash' },
  { id: 'groq', name: 'Groq LPU', placeholder: 'Enter Groq API key (gsk_...)...', defaultModel: 'openai/gpt-oss-120b' },
  { id: 'openai', name: 'OpenAI API', placeholder: 'Enter OpenAI API key (sk-...)...', defaultModel: 'gpt-4o-mini' },
  { id: 'anthropic', name: 'Anthropic Claude', placeholder: 'Enter Anthropic API key (sk-ant-...)...', defaultModel: 'claude-3-5-sonnet' },
  { id: 'mistral', name: 'Mistral AI', placeholder: 'Enter Mistral API key...', defaultModel: 'open-mistral-nemo' },
  { id: 'deepseek', name: 'DeepSeek API', placeholder: 'Enter DeepSeek API key...', defaultModel: 'deepseek-chat' },
  { id: 'openrouter', name: 'OpenRouter Gateway', placeholder: 'Enter OpenRouter key (sk-or-...)...', defaultModel: 'anthropic/claude-3-haiku' },
  { id: 'nvidia', name: 'NVIDIA NIM', placeholder: 'Enter NVIDIA NIM key (nvapi-...)...', defaultModel: 'meta/llama-3.2-11b-vision-instruct' },
  { id: 'cohere', name: 'Cohere Command', placeholder: 'Enter Cohere API key...', defaultModel: 'command-r-plus-08-2024' },
  { id: 'universal', name: 'Universal / Custom Cloud API', placeholder: 'Enter OpenAI-compatible key...', defaultModel: 'Universal Custom LLM' },
];

export const CloudKeysSection: React.FC<CloudKeysSectionProps> = ({
  refetchLiveModels,
}) => {
  const { config, addApiKey, updateApiKey, removeApiKey, setKeyVerification } =
    useControlCenterStore();

  const [selectedProvider, setSelectedProvider] = useState<DetectedProvider>('gemini');
  const [newKeyInput, setNewKeyInput] = useState('');
  const [showNewKey, setShowNewKey] = useState(false);
  const [isTestingNew, setIsTestingNew] = useState(false);
  const [testResult, setTestResult] = useState<{ available: boolean; latencyMs?: number; error?: string } | null>(null);

  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [testingKeyId, setTestingKeyId] = useState<string | null>(null);

  const maskKey = (rawKey: string): string => {
    if (!rawKey) return '';
    const trimmed = rawKey.trim();
    if (trimmed.length <= 8) return 'xxxxxxxxxxxxxxxx';
    const prefix = trimmed.slice(0, 4);
    const suffix = trimmed.slice(-4);
    return `${prefix}xxxxxxxxxxxxxxxx${suffix}`;
  };

  // Auto-detect provider if user pastes a recognizable key prefix
  const handleKeyInputChange = (val: string) => {
    setNewKeyInput(val);
    setTestResult(null);
    const trimmed = val.trim();
    if (trimmed.startsWith('AIzaSy') || trimmed.startsWith('AIza')) {
      setSelectedProvider('gemini');
    } else if (trimmed.startsWith('gsk_')) {
      setSelectedProvider('groq');
    } else if (trimmed.startsWith('nvapi-')) {
      setSelectedProvider('nvidia');
    } else if (trimmed.startsWith('sk-ant-')) {
      setSelectedProvider('anthropic');
    } else if (trimmed.startsWith('sk-or-')) {
      setSelectedProvider('openrouter');
    } else if (trimmed.startsWith('sk-')) {
      setSelectedProvider('openai');
    }
  };

  const handlePasteClipboard = async () => {
    try {
      if (navigator?.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          handleKeyInputChange(text.trim());
        }
      }
    } catch {}
  };

  // Test connection against live backend probe
  const handleTestNewKey = async () => {
    const key = newKeyInput.trim();
    if (!key) return;
    setIsTestingNew(true);
    setTestResult(null);
    try {
      const res = await platformAdapter.pingApiKey(selectedProvider, key);
      setTestResult(res);
    } catch (err: any) {
      setTestResult({ available: false, error: err?.message || 'Connection failed' });
    } finally {
      setIsTestingNew(false);
    }
  };

  // Add / Connect Provider & persist to backend environment
  const handleAddProvider = async () => {
    const key = newKeyInput.trim();
    if (!key) return;

    const keyId = `key-${Date.now()}`;

    // Add to store
    addApiKey(key);
    // Find the added entry (or update existing if same provider)
    updateApiKey(keyId, key);

    // Persist directly to backend .env
    try {
      await platformAdapter.saveConfig({
        [`${selectedProvider}_api_key`]: key,
        llm_mode: `cloud_${selectedProvider}`,
        llm_backend: selectedProvider,
      });

      // Verify connection immediately
      const ping = await platformAdapter.pingApiKey(selectedProvider, key);
      setKeyVerification(keyId, ping.available, ping.latencyMs, ping.error);

      // Auto-trigger sync across orchestrator
      refetchLiveModels();
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('raise:sync-routing'));
      }
    } catch (err: any) {
      console.warn('Failed to persist provider key:', err);
    }

    setNewKeyInput('');
    setTestResult(null);
  };

  // Test an existing configured key
  const handleTestExistingKey = async (id: string, provider: string, key: string) => {
    if (!key.trim()) return;
    setTestingKeyId(id);
    try {
      const res = await platformAdapter.pingApiKey(provider, key);
      setKeyVerification(id, res.available, res.latencyMs, res.error);
      if (res.available) {
        if (provider && provider !== 'unknown') {
          await platformAdapter.saveConfig({
            [`${provider}_api_key`]: key.trim(),
            llm_mode: `cloud_${provider}`,
            llm_backend: provider,
          });
        }
        refetchLiveModels();
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('raise:sync-routing'));
        }
      }
    } catch (err: any) {
      setKeyVerification(id, false, undefined, err?.message || 'Connection failed');
    } finally {
      setTestingKeyId(null);
    }
  };

  const configuredKeys = (config.apiKeys || []).filter(
    (k) => (k?.key && k.key.trim().length > 0 && k.provider !== 'unknown') || k?.verified === true
  );

  const activeProviderMeta = CLOUD_PROVIDERS.find((p) => p.id === selectedProvider) || CLOUD_PROVIDERS[0];

  return (
    <div className="space-y-4">
      {/* 1. ADD CLOUD PROVIDER CARD */}
      <div className="p-4 rounded-2xl bg-[#131622] border border-white/10 space-y-3.5 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-white" />
            <span className="text-xs font-bold text-white tracking-tight">
              Connect Cloud Provider
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            {configuredKeys.length} configured
          </span>
        </div>

        {/* Provider Dropdown & API Key Input */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {/* Provider Dropdown */}
          <div className="relative">
            <select
              value={selectedProvider}
              onChange={(e) => {
                setSelectedProvider(e.target.value as DetectedProvider);
                setTestResult(null);
              }}
              className="w-full appearance-none px-3 py-2.5 rounded-xl bg-black/60 border border-white/15 text-white font-medium text-xs focus:outline-none focus:border-white transition-all cursor-pointer pr-8"
            >
              {CLOUD_PROVIDERS.map((prov) => (
                <option key={prov.id} value={prov.id} className="bg-[#131622] text-white">
                  {prov.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Key Input Row */}
          <div className="sm:col-span-2 relative flex items-center">
            <input
              type={showNewKey ? 'text' : 'password'}
              placeholder={activeProviderMeta.placeholder}
              value={newKeyInput}
              onChange={(e) => handleKeyInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddProvider();
                }
              }}
              className="w-full px-3 py-2.5 pr-20 rounded-xl bg-black/60 border border-white/15 text-white font-mono text-xs placeholder:text-slate-500 focus:outline-none focus:border-white transition-all"
            />
            <div className="absolute right-2 flex items-center gap-1">
              {/* Paste Button */}
              <button
                type="button"
                onClick={handlePasteClipboard}
                title="Paste from clipboard"
                aria-label="Paste API key"
                className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                <Clipboard className="w-3.5 h-3.5" />
              </button>

              {/* Show / Hide Toggle */}
              <button
                type="button"
                onClick={() => setShowNewKey((prev) => !prev)}
                title={showNewKey ? 'Hide key' : 'Show key'}
                className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
              >
                {showNewKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Actions Row: Test Connection & Connect */}
        <div className="flex items-center justify-between gap-2 flex-wrap pt-1">
          <div className="flex items-center gap-2">
            {testResult && (
              <span
                className={`text-[11px] font-mono flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${
                  testResult.available
                    ? 'bg-white/10 text-white border-white/20'
                    : 'bg-white/5 text-zinc-400 border-white/10'
                }`}
              >
                {testResult.available ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                    <span>Connected ({testResult.latencyMs || 35}ms)</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-3.5 h-3.5 text-zinc-400" />
                    <span className="truncate max-w-[280px]">
                      {testResult.error || 'Connection rejected'}
                    </span>
                  </>
                )}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              type="button"
              disabled={!newKeyInput.trim() || isTestingNew}
              onClick={handleTestNewKey}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
                newKeyInput.trim() && !isTestingNew
                  ? 'bg-white/10 hover:bg-white/15 border border-white/20 text-white cursor-pointer'
                  : 'border border-white/10 text-slate-500 bg-transparent cursor-not-allowed'
              }`}
            >
              {isTestingNew ? (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  Testing...
                </>
              ) : (
                'Test Connection'
              )}
            </button>

            <button
              type="button"
              disabled={!newKeyInput.trim()}
              onClick={handleAddProvider}
              className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                newKeyInput.trim()
                  ? 'bg-white text-black hover:bg-slate-200 cursor-pointer shadow-sm'
                  : 'bg-white/10 text-slate-500 border border-white/10 cursor-not-allowed'
              }`}
            >
              <Plus className="w-3.5 h-3.5" />
              Add Provider
            </button>
          </div>
        </div>
      </div>

      {/* 2. CONFIGURED PROVIDERS COMPACT LIST */}
      {configuredKeys.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Configured Cloud Providers
            </span>
          </div>

          <div className="space-y-2">
            {configuredKeys.map((item) => {
              const show = showKeys[item.id];
              const isTesting = testingKeyId === item.id;
              const isFromEnv = Boolean(item.fromEnv);
              const provName =
                CLOUD_PROVIDERS.find((p) => p.id === item.provider)?.name ||
                item.providerName ||
                item.provider.toUpperCase();

              return (
                <div
                  key={item.id}
                  className="p-3 rounded-xl border border-white/10 bg-[#131622] flex items-center justify-between gap-3 transition-all hover:border-white/20"
                >
                  {/* Left Info */}
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className="w-2 h-2 rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] animate-pulse shrink-0" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-white truncate">
                          {provName}
                        </span>
                        {isFromEnv && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-white border border-white/20">
                            From .env
                          </span>
                        )}
                        {item.verified === true && (
                          <span className="text-[10px] font-mono text-white flex items-center gap-1 bg-white/10 px-2 py-0.5 rounded border border-white/20">
                            <CheckCircle2 className="w-3 h-3 text-white" />
                            Active ({item.latencyMs || 25}ms)
                          </span>
                        )}
                        {item.verified === false && (
                          <span className="text-[10px] font-mono text-zinc-400 flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                            <XCircle className="w-3 h-3 text-zinc-400" />
                            Failed
                          </span>
                        )}
                        {item.verified === null && (
                          <span className="text-[10px] font-mono text-zinc-400 flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                            <AlertCircle className="w-3 h-3 text-zinc-400" />
                            Unverified
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5 truncate">
                        {show ? item.key : maskKey(item.key)}
                      </div>
                    </div>
                  </div>

                  {/* Right Actions */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() =>
                        setShowKeys((prev) => ({ ...prev, [item.id]: !prev[item.id] }))
                      }
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                      title={show ? 'Hide key' : 'Show key'}
                    >
                      {show ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>

                    <button
                      type="button"
                      disabled={isTesting}
                      onClick={() => handleTestExistingKey(item.id, item.provider, item.key)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                      title="Test Connection"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin' : ''}`} />
                    </button>

                    <button
                      type="button"
                      onClick={async () => {
                        removeApiKey(item.id);
                        if (item.provider && item.provider !== 'unknown') {
                          await platformAdapter.saveConfig({
                            [`${item.provider}_api_key`]: '',
                          });
                          refetchLiveModels();
                          if (typeof window !== 'undefined') {
                            window.dispatchEvent(new CustomEvent('raise:sync-routing'));
                          }
                        }
                      }}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                      title="Delete / Remove Provider"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
