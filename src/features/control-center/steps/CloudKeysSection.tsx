import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clipboard,
  Eye,
  EyeOff,
  HelpCircle,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
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
  const [showTestErrorDetails, setShowTestErrorDetails] = useState(false);

  // Form expansion state (collapsible when keys are already configured)
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customBaseUrl, setCustomBaseUrl] = useState('');

  // Key item interaction states
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [testingKeyId, setTestingKeyId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [expandedKeyErrors, setExpandedKeyErrors] = useState<Record<string, boolean>>({});

  const maskKey = (rawKey: string): string => {
    if (!rawKey) return '';
    const trimmed = rawKey.trim();
    if (trimmed.length <= 8) return 'xxxxxxxxxxxxxxxx';
    const prefix = trimmed.slice(0, 4);
    const suffix = trimmed.slice(-4);
    return `${prefix}••••••••••••••••${suffix}`;
  };

  // Auto-detect provider if user pastes a recognizable key prefix
  const handleKeyInputChange = (val: string) => {
    setNewKeyInput(val);
    setTestResult(null);
    setShowTestErrorDetails(false);
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
    setShowTestErrorDetails(false);
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
    updateApiKey(keyId, key);

    // Persist directly to backend .env
    try {
      const savePayload: Record<string, any> = {
        [`${selectedProvider}_api_key`]: key,
        llm_mode: `cloud_${selectedProvider}`,
        llm_backend: selectedProvider,
      };
      if (customBaseUrl.trim()) {
        savePayload[`${selectedProvider}_base_url`] = customBaseUrl.trim();
      }
      await platformAdapter.saveConfig(savePayload);

      // Verify connection immediately with live latency
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
    setShowTestErrorDetails(false);
    setCustomBaseUrl('');
    setShowAdvanced(false);
    setIsAddOpen(false);
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
  const formShouldShow = isAddOpen || configuredKeys.length === 0;

  return (
    <div className="space-y-4">
      {/* 1. CONFIGURED PROVIDERS PRIMARY DASHBOARD LIST */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-white tracking-tight">
              Configured Cloud Providers
            </span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-white/10 text-white border border-white/15">
              {configuredKeys.length} {configuredKeys.length === 1 ? 'active' : 'active'}
            </span>
          </div>

          {/* Primary Action Button: Toggle Add Provider Form */}
          {configuredKeys.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setIsAddOpen((prev) => !prev);
                setTestResult(null);
                setShowTestErrorDetails(false);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/10 hover:bg-white/15 border border-white/20 text-white transition-colors cursor-pointer"
            >
              {isAddOpen ? (
                <>
                  <X className="w-3.5 h-3.5" />
                  <span>Close Form</span>
                </>
              ) : (
                <>
                  <Plus className="w-3.5 h-3.5" />
                  <span>Add Provider</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Empty State: Explains clearly what to do next */}
        {configuredKeys.length === 0 && (
          <div className="p-4 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] text-left space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-white">
              <HelpCircle className="w-4 h-4 text-slate-300" />
              <span>No Cloud Providers Connected</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Connect your cloud model provider (Google Gemini, Groq, OpenAI, etc.) below by pasting your API key. Once connected, your active engine will automatically power sub-second research queries.
            </p>
          </div>
        )}

        {/* Configured Keys Compact Cards */}
        {configuredKeys.length > 0 && (
          <div className="space-y-2">
            {configuredKeys.map((item) => {
              const show = showKeys[item.id];
              const isTesting = testingKeyId === item.id;
              const isDeleting = confirmDeleteId === item.id;
              const isFromEnv = Boolean(item.fromEnv);
              const isErrorExpanded = Boolean(expandedKeyErrors[item.id]);
              const provName =
                CLOUD_PROVIDERS.find((p) => p.id === item.provider)?.name ||
                item.providerName ||
                item.provider.toUpperCase();

              return (
                <div
                  key={item.id}
                  className="rounded-xl border border-[#292929] bg-[#111111] transition-all hover:border-[#FFFFFF]/25 overflow-hidden"
                >
                  <div className="p-3 flex items-center justify-between gap-3">
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
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-mono text-zinc-300 flex items-center gap-1 bg-white/5 px-2 py-0.5 rounded border border-white/10">
                                <XCircle className="w-3 h-3 text-zinc-400" />
                                Connection Failed
                              </span>
                              {item.error && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedKeyErrors((prev) => ({
                                      ...prev,
                                      [item.id]: !prev[item.id],
                                    }))
                                  }
                                  className="text-[10px] font-mono text-slate-400 hover:text-white underline cursor-pointer"
                                >
                                  {isErrorExpanded ? 'Hide error' : 'Show error'}
                                </button>
                              )}
                            </div>
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

                    {/* Right Actions: Reveal, Test, Delete (with inline confirmation) */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      {isDeleting ? (
                        <div className="flex items-center gap-1.5 animate-in fade-in duration-100">
                          <span className="text-[11px] text-zinc-300 font-medium">Remove?</span>
                          <button
                            type="button"
                            onClick={async () => {
                              removeApiKey(item.id);
                              setConfirmDeleteId(null);
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
                            className="px-2 py-1 rounded-md text-[11px] font-bold bg-white text-black hover:bg-slate-200 transition-colors cursor-pointer"
                          >
                            Yes
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-2 py-1 rounded-md text-[11px] font-medium bg-white/10 text-white hover:bg-white/15 transition-colors cursor-pointer"
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <>
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
                            onClick={() => setConfirmDeleteId(item.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                            title="Remove Provider Key"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Expandable detailed error message for failed keys */}
                  {isErrorExpanded && item.error && (
                    <div className="px-3 pb-3 pt-1 border-t border-white/10 bg-black/40 text-[10.5px] font-mono text-zinc-300">
                      <div className="text-slate-400 font-semibold mb-0.5">Failure Reason:</div>
                      <div className="p-2 rounded bg-black/60 border border-white/10 select-all break-all">
                        {item.error}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. ADD CLOUD PROVIDER FORM (COLLAPSIBLE / STREAMLINED) */}
      {formShouldShow && (
        <div className="p-4 rounded-2xl bg-[#111111] border border-[#292929] space-y-3.5 shadow-sm animate-in fade-in duration-150">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-white" />
              <span className="text-xs font-bold text-white tracking-tight">
                {configuredKeys.length === 0 ? 'Connect Your First Provider' : 'Add Another Provider'}
              </span>
            </div>
            {configuredKeys.length > 0 && (
              <button
                type="button"
                onClick={() => setIsAddOpen(false)}
                className="text-slate-400 hover:text-white p-1 cursor-pointer"
                title="Collapse"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Provider Select & Key Input */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {/* Provider Dropdown */}
            <div className="relative">
              <select
                value={selectedProvider}
                onChange={(e) => {
                  setSelectedProvider(e.target.value as DetectedProvider);
                  setTestResult(null);
                  setShowTestErrorDetails(false);
                }}
                className="w-full appearance-none px-3 py-2.5 rounded-xl bg-black/60 border border-[#292929] text-white font-medium text-xs focus:outline-none focus:border-white transition-all cursor-pointer pr-8"
              >
                {CLOUD_PROVIDERS.map((prov) => (
                  <option key={prov.id} value={prov.id} className="bg-[#111111] text-white">
                    {prov.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            {/* Key Input Field with Paste and Show/Hide */}
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
                <button
                  type="button"
                  onClick={handlePasteClipboard}
                  title="Paste from clipboard"
                  aria-label="Paste API key"
                  className="p-1 text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  <Clipboard className="w-3.5 h-3.5" />
                </button>

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

          {/* Progressive Disclosure: Collapsible Advanced Settings (Custom Base URL) */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              <ChevronRight
                className={`w-3 h-3 text-slate-400 transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
              />
              <span>Advanced: Custom Endpoint URL (Optional)</span>
            </button>

            {showAdvanced && (
              <div className="mt-2 pl-4 border-l border-white/10 space-y-2 animate-in fade-in duration-100">
                <input
                  type="text"
                  placeholder="https://api.openai.com/v1 (or custom gateway)"
                  value={customBaseUrl}
                  onChange={(e) => setCustomBaseUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-white/15 text-white font-mono text-xs placeholder:text-slate-500 focus:outline-none focus:border-white transition-all"
                />
                <p className="text-[10px] text-slate-500">
                  Override default cloud endpoint for private LLM proxies or enterprise gateways.
                </p>
              </div>
            )}
          </div>

          {/* Action Row: Inline Status, Test Connection, Add Provider */}
          <div className="flex items-center justify-between gap-2 flex-wrap pt-1 border-t border-white/10">
            {/* Inline Status & Expandable Error */}
            <div className="flex items-center gap-2">
              {testResult && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-[11px] font-mono flex items-center gap-1.5 px-2.5 py-1 rounded-lg border ${
                      testResult.available
                        ? 'bg-white/10 text-white border-white/20'
                        : 'bg-white/5 text-zinc-300 border-white/10'
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
                        <span>Connection Rejected</span>
                      </>
                    )}
                  </span>

                  {/* Expand Error Details */}
                  {!testResult.available && testResult.error && (
                    <button
                      type="button"
                      onClick={() => setShowTestErrorDetails((prev) => !prev)}
                      className="text-[10.5px] font-mono text-slate-400 hover:text-white underline cursor-pointer"
                    >
                      {showTestErrorDetails ? 'Hide details' : 'Show details'}
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Primary Action Buttons */}
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

              {/* Add Provider button is strictly rendered ONLY when connection test is successful */}
              {testResult?.available === true && (
                <button
                  type="button"
                  onClick={handleAddProvider}
                  className="px-4 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 bg-white text-black hover:bg-slate-200 cursor-pointer shadow-sm animate-in fade-in zoom-in-95 duration-150"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Provider
                </button>
              )}
            </div>
          </div>

          {/* Expanded Error Box */}
          {showTestErrorDetails && testResult && !testResult.available && testResult.error && (
            <div className="p-2.5 rounded-xl bg-black/60 border border-white/15 text-[10.5px] font-mono text-zinc-300 space-y-1 animate-in fade-in duration-100">
              <div className="text-slate-400 font-semibold">Upstream Probe Response:</div>
              <div className="select-all break-all whitespace-pre-wrap">{testResult.error}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
