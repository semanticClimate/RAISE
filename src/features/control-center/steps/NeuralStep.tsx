import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Cpu,
  Eye,
  EyeOff,
  Key,
  Layers,
  Loader2,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react';
import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { platformAdapter, type PreflightAsset } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';

export type ModelCategory = 'embedding' | 'reranker' | 'verifier';

export interface BackendModelItem {
  id: string;
  name: string;
  cached?: boolean;
  status?: string;
  specifications?: string;
  [key: string]: unknown;
}

export const NeuralStep: React.FC = () => {
  const { config, updateConfig } = useControlCenterStore();

  const [isLoading, setIsLoading] = useState(true);
  const [backendConfig, setBackendConfig] = useState<Record<string, unknown> | null>(null);
  const [preflightAssets, setPreflightAssets] = useState<PreflightAsset[]>([]);
  const [activeCategoryModal, setActiveCategoryModal] = useState<ModelCategory | null>(null);

  // Status and notification banners
  const [statusMessage, setStatusMessage] = useState<{
    text: string;
    type: 'success' | 'error';
  } | null>(null);

  // Hugging Face token state
  const [showHfToken, setShowHfToken] = useState(false);
  const [isSavingHfToken, setIsSavingHfToken] = useState(false);
  const [hfSavedNotice, setHfSavedNotice] = useState<string | null>(null);

  // Advanced / Custom model expansion
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [customModelCategory, setCustomModelCategory] = useState<ModelCategory>('embedding');
  const [customModelInput, setCustomModelInput] = useState('');
  const [isApplyingCustom, setIsApplyingCustom] = useState(false);

  // Load backend configuration & preflight status
  const refreshBackendData = useCallback(async () => {
    try {
      const [cfg, assetsRes] = await Promise.all([
        platformAdapter.getConfig(),
        platformAdapter.getPreflightAssets(),
      ]);
      if (cfg) {
        setBackendConfig(cfg);
        updateConfig({
          embeddingModel: (cfg.embedding_model as string) || config.embeddingModel,
          rerankerModel: (cfg.reranker_model as string) || config.rerankerModel,
          nliVerifierModel:
            (cfg.nli_verifier_model as string) ||
            (cfg.nli_model as string) ||
            config.nliVerifierModel,
          neuralDevice: (cfg.neural_device as any) || config.neuralDevice,
          huggingfaceConfigured: Boolean(cfg.huggingface_configured),
          huggingfaceMasked: String(cfg.huggingface_masked || ''),
        });
      }
      if (assetsRes && Array.isArray(assetsRes.assets)) {
        setPreflightAssets(assetsRes.assets);
      }
    } catch (err) {
      console.warn('Failed to fetch backend neural configuration:', err);
    } finally {
      setIsLoading(false);
    }
  }, [config.embeddingModel, config.rerankerModel, config.nliVerifierModel, config.neuralDevice, updateConfig]);

  useEffect(() => {
    refreshBackendData();
  }, [refreshBackendData]);

  // Dynamic values currently configured in backend
  const configuredEmbedding =
    (backendConfig?.embedding_model as string) || config.embeddingModel || '';
  const configuredReranker =
    (backendConfig?.reranker_model as string) || config.rerankerModel || '';
  const configuredVerifier =
    (backendConfig?.nli_verifier_model as string) ||
    (backendConfig?.nli_model as string) ||
    config.nliVerifierModel ||
    '';
  const configuredDevice =
    (backendConfig?.neural_device as string) || config.neuralDevice || 'auto';

  // Dynamic models returned from backend registry
  const neuralRegistry = (backendConfig?.neural_registry as Record<string, any>) || {};
  const availableEmbeddingModels: BackendModelItem[] = Array.isArray(neuralRegistry.embedding)
    ? (neuralRegistry.embedding as BackendModelItem[])
    : [];
  const availableRerankerModels: BackendModelItem[] = Array.isArray(neuralRegistry.reranker)
    ? (neuralRegistry.reranker as BackendModelItem[])
    : [];
  const availableVerifierModels: BackendModelItem[] = Array.isArray(neuralRegistry.verifier)
    ? (neuralRegistry.verifier as BackendModelItem[])
    : [];
  const customModelSupport: boolean = Boolean(neuralRegistry.custom_model_supported);

  // Dynamic status evaluation
  const getModelStatus = (modelId: string, category: ModelCategory): { label: string; tone: 'ready' | 'pending' | 'muted' } => {
    if (isLoading) return { label: 'Loading...', tone: 'muted' };
    if (!modelId) return { label: 'Not configured', tone: 'muted' };

    // Check preflight asset matching
    const asset = preflightAssets.find(
      (a) =>
        a.name === modelId ||
        a.id === modelId ||
        (a.name && a.name.includes(modelId)) ||
        (a.desc && a.desc.includes(modelId))
    );
    if (asset) {
      if (asset.verified) return { label: 'Cached & Verified', tone: 'ready' };
      return { label: asset.status || 'Requires Download', tone: 'pending' };
    }

    // Check backend registry item status
    const modelsList =
      category === 'embedding'
        ? availableEmbeddingModels
        : category === 'reranker'
          ? availableRerankerModels
          : availableVerifierModels;
    const regItem = modelsList.find((m) => m.id === modelId);
    if (regItem) {
      if (regItem.cached || regItem.status?.includes('Built-in') || regItem.status?.includes('Cached')) {
        return { label: regItem.status || 'Cached & Ready', tone: 'ready' };
      }
      return { label: regItem.status || 'Requires Download', tone: 'pending' };
    }

    return { label: 'Configured in Backend', tone: 'ready' };
  };

  // Helper to extract Hugging Face / SentenceTransformers identifiers
  const handleExtractSnippet = (rawText: string) => {
    let cleaned = rawText.trim();
    if (!cleaned) return '';

    const match = cleaned.match(
      /(?:SentenceTransformer|CrossEncoder|from_pretrained)\s*\(\s*["']([^"']+)["']\s*\)/i
    );
    if (match && match[1]) {
      cleaned = match[1].trim();
    } else {
      const urlMatch = cleaned.match(/huggingface\.co\/([a-zA-Z0-9_\-./]+)/i);
      if (urlMatch && urlMatch[1]) {
        cleaned = urlMatch[1].replace(/\/+$/, '').trim();
      }
    }
    return cleaned.replace(/^["']|["']$/g, '');
  };

  // Apply selected model directly to backend
  const handleSelectModel = async (category: ModelCategory, modelId: string) => {
    const payloadKey =
      category === 'embedding'
        ? 'embedding_model'
        : category === 'reranker'
          ? 'reranker_model'
          : 'nli_verifier_model';

    try {
      const res = await platformAdapter.saveConfig({
        [payloadKey]: modelId,
      });

      if (res.success) {
        setStatusMessage({
          text: `Applied ${category === 'embedding' ? 'Embedding' : category === 'reranker' ? 'Reranker' : 'Verifier'} model: ${modelId}`,
          type: 'success',
        });
        setTimeout(() => setStatusMessage(null), 4000);
        await refreshBackendData();
        setActiveCategoryModal(null);
      } else {
        setStatusMessage({
          text: res.message || 'Failed to update backend model configuration',
          type: 'error',
        });
        setTimeout(() => setStatusMessage(null), 5000);
      }
    } catch (err: any) {
      setStatusMessage({
        text: err?.message || 'Error communicating with backend API',
        type: 'error',
      });
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  // Apply custom model ID
  const handleApplyCustomModel = async () => {
    const cleaned = handleExtractSnippet(customModelInput);
    if (!cleaned) return;

    setIsApplyingCustom(true);
    await handleSelectModel(customModelCategory, cleaned);
    setIsApplyingCustom(false);
    setCustomModelInput('');
  };

  // Save Hugging Face Access Token to Backend
  const handleSaveHfToken = async () => {
    const raw = config.huggingfaceToken?.trim();
    if (!raw) return;
    setIsSavingHfToken(true);
    try {
      const res = await platformAdapter.saveConfig({
        huggingface_token: raw,
        hf_token: raw,
      });
      if (res.success) {
        setHfSavedNotice('Token persisted in backend .env');
        updateConfig({
          huggingfaceConfigured: true,
          huggingfaceMasked: raw.length > 8 ? `${raw.slice(0, 4)}...${raw.slice(-4)}` : 'Active',
        });
        setTimeout(() => setHfSavedNotice(null), 3500);
        await refreshBackendData();
      } else {
        setHfSavedNotice(res.message || 'Failed to persist token');
        setTimeout(() => setHfSavedNotice(null), 3500);
      }
    } catch {
      setHfSavedNotice('Failed to communicate with backend');
      setTimeout(() => setHfSavedNotice(null), 3500);
    } finally {
      setIsSavingHfToken(false);
    }
  };

  // Change Execution Device
  const handleSelectDevice = async (device: 'auto' | 'mps' | 'cuda' | 'cpu') => {
    updateConfig({ neuralDevice: device });
    try {
      await platformAdapter.saveConfig({
        neural_device: device,
        embedding_device: device,
        reranker_device: device,
        nli_device: device,
      });
      await refreshBackendData();
    } catch (err) {
      console.warn('Device update failed:', err);
    }
  };

  // Dynamic context matching between reranker and embedder
  const isContextMatched =
    configuredEmbedding.includes('embeddinggemma-2') &&
    configuredReranker.includes('bge-reranker-v2-m3');

  const embeddingStatus = getModelStatus(configuredEmbedding, 'embedding');
  const rerankerStatus = getModelStatus(configuredReranker, 'reranker');
  const verifierStatus = getModelStatus(configuredVerifier, 'verifier');

  return (
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      {/* HEADER */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            <span>AI Retrieval & Embedding Models</span>
            {isLoading && <Loader2 className="w-3.5 h-3.5 text-purple-400 animate-spin" />}
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Dynamically configured via live backend model registry. Zero hardcoded model options.
          </p>
        </div>
      </div>

      {/* STATUS NOTIFICATION BANNER */}
      {statusMessage && (
        <div
          className={`p-3 rounded-xl border text-xs font-mono animate-in fade-in flex items-center gap-2.5 ${
            statusMessage.type === 'success'
              ? 'bg-purple-500/10 border-purple-500/30 text-purple-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <Check className="w-4 h-4 text-purple-400 shrink-0 stroke-[2.5]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* SINGLE UNIFIED FORM CONTAINER */}
      <div className="p-4 sm:p-5 rounded-2xl bg-[#131622] border border-white/10 space-y-4 shadow-lg">
        {/* 1. HUGGING FACE ACCESS TOKEN (TOP POSITION) */}
        <div className="space-y-2 pb-4 border-b border-white/10">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <label className="text-xs font-bold text-white flex items-center gap-2 flex-wrap">
              <Key className="w-3.5 h-3.5 text-purple-400" />
              <span>Hugging Face Access Token</span>
              <span className="text-[10px] font-normal text-slate-400 font-mono">(Optional)</span>
              {config.huggingfaceConfigured ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-semibold">
                  Configured in Backend ({config.huggingfaceMasked || 'Active'})
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-slate-400">
                  Optional • Unconfigured
                </span>
              )}
            </label>
            <div className="flex items-center gap-2">
              {hfSavedNotice && (
                <span className="text-[11px] font-mono text-purple-400 animate-in fade-in flex items-center gap-1">
                  <Check className="w-3 h-3" />
                  {hfSavedNotice}
                </span>
              )}
              <span className="text-[10.5px] font-mono text-slate-400">For gated or private repos</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <input
                type={showHfToken ? 'text' : 'password'}
                value={config.huggingfaceToken || ''}
                onChange={(e) => updateConfig({ huggingfaceToken: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSaveHfToken();
                  }
                }}
                placeholder={
                  config.huggingfaceConfigured && config.huggingfaceMasked
                    ? config.huggingfaceMasked
                    : 'hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
                }
                className="w-full px-3 py-2 pr-9 rounded-xl bg-black/60 border border-white/15 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-purple-400 transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowHfToken(!showHfToken)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white p-0.5 cursor-pointer"
                title={showHfToken ? 'Hide token' : 'Show token'}
              >
                {showHfToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
            {config.huggingfaceToken && config.huggingfaceToken !== config.huggingfaceMasked && (
              <button
                type="button"
                onClick={handleSaveHfToken}
                disabled={isSavingHfToken}
                className="px-3 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium shrink-0 transition-colors cursor-pointer disabled:opacity-50 shadow-xs"
              >
                {isSavingHfToken ? 'Saving...' : 'Save Token'}
              </button>
            )}
          </div>
          <p className="text-[10.5px] text-slate-400 font-sans leading-tight">
            Required only if using gated models (e.g. Meta-Llama, Mistral gated repos, or private corporate libraries).
          </p>
        </div>

        {/* 2. THREE COMPACT CONFIGURATION CARDS */}
        <div className="space-y-3 pt-1">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            Configured Neural Models
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* CARD 1: EMBEDDING MODEL */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-purple-500/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <Layers className="w-3.5 h-3.5 text-purple-400" />
                    <span>Embedding Model</span>
                  </div>
                  <span
                    className={`text-[9.5px] font-mono px-2 py-0.5 rounded-md font-semibold ${
                      embeddingStatus.tone === 'ready'
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
                        : embeddingStatus.tone === 'pending'
                          ? 'bg-amber-500/15 border border-amber-500/30 text-amber-400'
                          : 'bg-white/5 border border-white/10 text-slate-400'
                    }`}
                  >
                    {embeddingStatus.label}
                  </span>
                </div>

                <div className="font-mono text-xs text-purple-300 font-semibold truncate" title={configuredEmbedding}>
                  {configuredEmbedding || (isLoading ? 'Loading...' : 'Not configured')}
                </div>

                <div className="text-[10.5px] font-mono text-slate-400 truncate">
                  {availableEmbeddingModels.find((m) => m.id === configuredEmbedding)?.specifications ||
                    'Dense Vector Semantic Embeddings'}
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('embedding')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-purple-500/15 border border-white/10 hover:border-purple-500/40 text-xs font-medium text-slate-200 hover:text-purple-300 transition-all flex items-center justify-between cursor-pointer"
              >
                <span>Change Model</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>

            {/* CARD 2: RERANKER */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-purple-500/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Reranker</span>
                  </div>
                  <span
                    className={`text-[9.5px] font-mono px-2 py-0.5 rounded-md font-semibold ${
                      rerankerStatus.tone === 'ready'
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
                        : rerankerStatus.tone === 'pending'
                          ? 'bg-amber-500/15 border border-amber-500/30 text-amber-400'
                          : 'bg-white/5 border border-white/10 text-slate-400'
                    }`}
                  >
                    {rerankerStatus.label}
                  </span>
                </div>

                <div className="font-mono text-xs text-purple-300 font-semibold truncate" title={configuredReranker}>
                  {configuredReranker || (isLoading ? 'Loading...' : 'Not configured')}
                </div>

                {/* Dynamic Reranker Context Labels */}
                {isContextMatched ? (
                  <div className="text-[10px] font-mono text-emerald-400/90 leading-tight">
                    Context (8,192 tokens) matches google/embeddinggemma-2 for zero-truncation cross-attention
                  </div>
                ) : (
                  <div className="text-[10.5px] font-mono text-slate-400 truncate">
                    {availableRerankerModels.find((m) => m.id === configuredReranker)?.specifications ||
                      'Cross-Attention Passage Reranker'}
                  </div>
                )}
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('reranker')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-purple-500/15 border border-white/10 hover:border-purple-500/40 text-xs font-medium text-slate-200 hover:text-purple-300 transition-all flex items-center justify-between cursor-pointer"
              >
                <span>Change Model</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>

            {/* CARD 3: CLAIM VERIFIER */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-purple-500/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <ShieldCheck className="w-3.5 h-3.5 text-purple-400" />
                    <span>Claim Verifier</span>
                  </div>
                  <span
                    className={`text-[9.5px] font-mono px-2 py-0.5 rounded-md font-semibold ${
                      verifierStatus.tone === 'ready'
                        ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
                        : verifierStatus.tone === 'pending'
                          ? 'bg-amber-500/15 border border-amber-500/30 text-amber-400'
                          : 'bg-white/5 border border-white/10 text-slate-400'
                    }`}
                  >
                    {verifierStatus.label}
                  </span>
                </div>

                <div className="font-mono text-xs text-purple-300 font-semibold truncate" title={configuredVerifier}>
                  {configuredVerifier || (isLoading ? 'Loading...' : 'Not configured')}
                </div>

                <div className="text-[10.5px] font-mono text-slate-400 truncate">
                  {availableVerifierModels.find((m) => m.id === configuredVerifier)?.specifications ||
                    'Pairwise Citation & Factuality Verification'}
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('verifier')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-purple-500/15 border border-white/10 hover:border-purple-500/40 text-xs font-medium text-slate-200 hover:text-purple-300 transition-all flex items-center justify-between cursor-pointer"
              >
                <span>Change Model</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>
          </div>
        </div>

        {/* 3. ADVANCED / CUSTOM MODELS (PROGRESSIVE DISCLOSURE) */}
        {customModelSupport && (
          <div className="pt-2 border-t border-white/10">
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="py-1.5 text-xs font-medium text-slate-400 hover:text-purple-300 flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {showAdvanced ? (
                <ChevronDown className="w-3.5 h-3.5 text-purple-400" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-purple-400" />
              )}
              <span>Advanced Configuration (Custom Hugging Face Repositories)</span>
            </button>

            {showAdvanced && (
              <div className="mt-2.5 p-3 rounded-xl bg-black/40 border border-purple-500/20 space-y-3 animate-in fade-in duration-150">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono text-slate-400">Target Category:</span>
                  <div className="flex gap-1.5">
                    {(['embedding', 'reranker', 'verifier'] as ModelCategory[]).map((cat) => (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => setCustomModelCategory(cat)}
                        className={`px-2 py-0.5 rounded-md text-[11px] font-mono capitalize transition-all cursor-pointer ${
                          customModelCategory === cat
                            ? 'bg-purple-600 text-white font-semibold shadow-xs'
                            : 'bg-white/5 text-slate-400 hover:text-white'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={customModelInput}
                    onChange={(e) => setCustomModelInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleApplyCustomModel();
                      }
                    }}
                    placeholder={`e.g. ${
                      customModelCategory === 'embedding'
                        ? 'BAAI/bge-m3 or sentence-transformers/all-MiniLM-L6-v2'
                        : customModelCategory === 'reranker'
                          ? 'BAAI/bge-reranker-v2-m3'
                          : 'MoritzLaurer/DeBERTa-v3-base-mnli'
                    }`}
                    className="flex-1 px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-purple-400"
                  />
                  <button
                    type="button"
                    onClick={handleApplyCustomModel}
                    disabled={isApplyingCustom || !customModelInput.trim()}
                    className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-medium shrink-0 transition-colors cursor-pointer"
                  >
                    {isApplyingCustom ? 'Applying...' : 'Apply Custom Model'}
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 font-sans">
                  Accepts Hugging Face repo IDs or Python snippets like <code className="text-purple-300 font-mono">SentenceTransformer("...")</code>. Automatically verified against backend runtime rules.
                </p>
              </div>
            )}
          </div>
        )}

        {/* 4. HARDWARE DEVICE SELECTION */}
        <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs font-bold text-white">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span>Execution Device:</span>
            <span className="text-[11px] font-mono text-slate-400 font-normal">
              {config.targetPlatform === 'macos' ? 'Apple Silicon (Metal / MPS)' : 'Host Acceleration'}
            </span>
          </div>

          <div className="flex gap-1.5">
            {(
              [
                { id: 'auto', label: 'Auto' },
                { id: 'mps', label: 'Metal (MPS)' },
                { id: 'cuda', label: 'CUDA' },
                { id: 'cpu', label: 'CPU' },
              ] as const
            ).map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => handleSelectDevice(d.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-colors cursor-pointer ${
                  configuredDevice === d.id
                    ? 'bg-purple-600 text-white font-bold shadow-xs'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white border border-white/10'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* POPUP-BASED MODEL SELECTION MODAL */}
      {activeCategoryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-xs animate-in fade-in duration-150">
          <div
            className="w-full max-w-xl max-h-[85vh] rounded-2xl bg-[#11131c] border border-white/15 shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* MODAL HEADER */}
            <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between gap-2 shrink-0">
              <div className="flex items-center gap-2">
                {activeCategoryModal === 'embedding' ? (
                  <Layers className="w-4 h-4 text-purple-400" />
                ) : activeCategoryModal === 'reranker' ? (
                  <Sparkles className="w-4 h-4 text-purple-400" />
                ) : (
                  <ShieldCheck className="w-4 h-4 text-purple-400" />
                )}
                <div>
                  <h4 className="text-sm font-bold text-white capitalize">
                    Select {activeCategoryModal === 'embedding' ? 'Dense Vector Embedding' : activeCategoryModal === 'reranker' ? 'Cross-Encoder Reranker' : 'Claim Verifier'}
                  </h4>
                  <p className="text-[11px] font-mono text-slate-400">
                    Sourced dynamically from backend model catalog
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveCategoryModal(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* MODAL BODY (MODELS LIST) */}
            <div className="p-4 overflow-y-auto space-y-2 flex-1 overscroll-contain">
              {(() => {
                const list =
                  activeCategoryModal === 'embedding'
                    ? availableEmbeddingModels
                    : activeCategoryModal === 'reranker'
                      ? availableRerankerModels
                      : availableVerifierModels;

                const currentConfigured =
                  activeCategoryModal === 'embedding'
                    ? configuredEmbedding
                    : activeCategoryModal === 'reranker'
                      ? configuredReranker
                      : configuredVerifier;

                if (list.length === 0) {
                  return (
                    <div className="p-8 text-center text-xs font-mono text-slate-400">
                      No models returned by backend for this category.
                    </div>
                  );
                }

                return list.map((m) => {
                  const isSelected = currentConfigured === m.id;
                  const isCached = Boolean(m.cached || m.status?.includes('Built-in') || m.status?.includes('Cached'));

                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectModel(activeCategoryModal, m.id)}
                      className={`w-full p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-purple-600/15 border-purple-500/60 shadow-xs'
                          : 'bg-white/[0.02] border-white/10 hover:bg-white/[0.05] hover:border-white/20'
                      }`}
                    >
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-white">{m.name}</span>
                          <span
                            className={`text-[9.5px] font-mono px-1.5 py-0.2 rounded ${
                              isCached
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                            }`}
                          >
                            {m.status || (isCached ? 'Cached & Ready' : 'Requires Download')}
                          </span>
                        </div>

                        <div className="text-[11px] font-mono text-slate-400 truncate">
                          {m.id}
                        </div>

                        {m.specifications && (
                          <div className="text-[10px] font-mono text-purple-300/80">
                            {m.specifications}
                          </div>
                        )}
                      </div>

                      <div className="shrink-0 flex items-center">
                        {isSelected ? (
                          <div className="w-5 h-5 rounded-full bg-purple-600 text-white flex items-center justify-center shadow-xs">
                            <Check className="w-3 h-3 stroke-[3]" />
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-full border border-white/20" />
                        )}
                      </div>
                    </button>
                  );
                });
              })()}
            </div>

            {/* MODAL FOOTER */}
            <div className="px-5 py-3 border-t border-white/10 bg-black/20 flex items-center justify-between shrink-0">
              <span className="text-[11px] font-mono text-slate-400">
                Selecting applies immediately to backend runtime
              </span>
              <button
                type="button"
                onClick={() => setActiveCategoryModal(null)}
                className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-xs text-white transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
