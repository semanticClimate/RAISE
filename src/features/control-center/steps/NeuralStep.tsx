import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  Cpu,
  Download,
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

  // Model download states
  const [downloadingModelId, setDownloadingModelId] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, { percent: number; status: string }>>({});

  // Hugging Face token state
  const [showHfToken, setShowHfToken] = useState(false);
  const [isCheckingHfToken, setIsCheckingHfToken] = useState(false);
  const [hfCheckNotice, setHfCheckNotice] = useState<{ text: string; success: boolean } | null>(null);

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

  // Clean model name resolver for compact cards
  const getCleanModelName = (modelId: string, category: ModelCategory): string => {
    if (!modelId) return isLoading ? 'Loading...' : 'Not configured';
    const list =
      category === 'embedding'
        ? availableEmbeddingModels
        : category === 'reranker'
          ? availableRerankerModels
          : availableVerifierModels;
    const found = list.find((m) => m.id === modelId);
    if (found && found.name) return found.name;
    const last = modelId.split('/').pop() || modelId;
    return last.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

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
      const isAlreadyCached = Boolean(
        regItem.cached ||
        regItem.isInstalled ||
        regItem.status?.toLowerCase().includes('cached') ||
        regItem.status?.toLowerCase().includes('ready') ||
        regItem.status?.toLowerCase().includes('installed') ||
        regItem.status?.includes('Built-in')
      );
      if (isAlreadyCached) {
        return { label: regItem.status || 'Cached & Ready', tone: 'ready' };
      }
      return { label: regItem.status || 'Requires Download', tone: 'pending' };
    }

    return { label: 'Configured in Backend', tone: 'ready' };
  };

  // Handle model weight download from backend
  const handleDownloadModel = async (modelId: string) => {
    if (!modelId || downloadingModelId === modelId) return;
    setDownloadingModelId(modelId);
    setStatusMessage({
      text: `Connecting to backend to download ${modelId}...`,
      type: 'success',
    });

    try {
      await platformAdapter.pullModel(
        modelId,
        (percent, status) => {
          setDownloadProgress((prev) => ({
            ...prev,
            [modelId]: { percent, status },
          }));
          if (percent > 0 && percent < 100) {
            setStatusMessage({
              text: `${status} (${percent}%)`,
              type: 'success',
            });
          }
        },
        config.huggingfaceToken || undefined
      );

      // Verify with backend preflight assets and config that it is actually cached on disk
      await refreshBackendData();
      const freshAssets = await platformAdapter.getPreflightAssets();

      const isVerifiedByBackend =
        (freshAssets?.assets || []).some(
          (a: any) =>
            (a.id === modelId ||
              a.name?.toLowerCase().includes(modelId.toLowerCase()) ||
              modelId.toLowerCase().includes(a.name?.toLowerCase())) &&
            a.verified
        ) ||
        Object.values((backendConfig?.neural_registry as Record<string, any>) || {})
          .flat()
          .some((m: any) => m && m.id === modelId && (m.cached || m.isInstalled));

      if (isVerifiedByBackend) {
        setStatusMessage({
          text: `Backend Approved: Model ${modelId} verified in disk cache!`,
          type: 'success',
        });
      } else {
        setStatusMessage({
          text: `Download stream completed for ${modelId}. Backend verifying cache integrity...`,
          type: 'success',
        });
      }
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      setStatusMessage({
        text: `Backend download rejected for ${modelId}: ${err?.message || 'Network error'}`,
        type: 'error',
      });
      setTimeout(() => setStatusMessage(null), 6000);
    } finally {
      setDownloadingModelId(null);
    }
  };

  // Compact status sign (icon only, with interactive download button for pending models)
  const renderStatusSign = (
    status: { label: string; tone: 'ready' | 'pending' | 'muted' },
    modelId: string
  ) => {
    if (isLoading) {
      return (
        <span title="Loading...">
          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
        </span>
      );
    }
    if (downloadingModelId === modelId) {
      const p = downloadProgress[modelId]?.percent ?? 0;
      return (
        <div className="flex items-center gap-1" title={`Downloading ${p}%`}>
          <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />
          <span className="text-[10px] font-mono text-zinc-300 font-semibold">{p}%</span>
        </div>
      );
    }
    if (status.tone === 'ready') {
      return (
        <span className="flex items-center justify-center w-5 h-5 rounded-md bg-white/10 border border-white/20 text-white" title="Cached & Ready">
          <Check className="w-3.5 h-3.5 stroke-[2.5]" />
        </span>
      );
    }
    if (status.tone === 'pending') {
      return (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleDownloadModel(modelId);
          }}
          className="flex items-center justify-center w-5 h-5 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 hover:border-white/40 text-white cursor-pointer transition-all shadow-xs"
          title="Click to Download Model Weights from Backend"
        >
          <Download className="w-3.5 h-3.5" />
        </button>
      );
    }
    return (
      <span className="w-2.5 h-2.5 rounded-full bg-zinc-600" title="Not configured" />
    );
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

  // Paste from clipboard into Hugging Face input
  const handlePasteHfToken = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        updateConfig({ huggingfaceToken: text.trim() });
      }
    } catch {
      // ignore clipboard error
    }
  };

  // Check and verify Hugging Face Access Token with backend
  const handleCheckHfToken = async () => {
    const raw = config.huggingfaceToken?.trim();
    if (!raw) return;
    setIsCheckingHfToken(true);
    try {
      // 1. Verify token with backend provider verification
      const verifyRes = await platformAdapter.pingApiKey('huggingface', raw);
      if (verifyRes.available) {
        // 2. Persist to backend .env and runtime
        await platformAdapter.saveConfig({
          huggingface_token: raw,
          hf_token: raw,
        });
        updateConfig({
          huggingfaceConfigured: true,
          huggingfaceMasked: raw.length > 8 ? `${raw.slice(0, 4)}...${raw.slice(-4)}` : 'Active',
        });
        setHfCheckNotice({ text: 'Token verified & saved to backend', success: true });
        setTimeout(() => setHfCheckNotice(null), 4000);
        await refreshBackendData();
      } else {
        setHfCheckNotice({
          text: verifyRes.error || 'Hugging Face authentication rejected',
          success: false,
        });
        setTimeout(() => setHfCheckNotice(null), 4500);
      }
    } catch (err: any) {
      setHfCheckNotice({
        text: err?.message || 'Connection error checking token',
        success: false,
      });
      setTimeout(() => setHfCheckNotice(null), 4500);
    } finally {
      setIsCheckingHfToken(false);
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
            {isLoading && <Loader2 className="w-3.5 h-3.5 text-white animate-spin" />}
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
              ? 'bg-white/10 border-white/25 text-white'
              : 'bg-white/5 border-white/15 text-zinc-300'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <Check className="w-4 h-4 text-white shrink-0 stroke-[2.5]" />
          ) : (
            <AlertCircle className="w-4 h-4 text-zinc-400 shrink-0" />
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
              <Key className="w-3.5 h-3.5 text-white" />
              <span>Hugging Face Access Token</span>
              {config.huggingfaceConfigured ? (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/10 border border-white/20 text-white font-semibold">
                  Configured in Backend ({config.huggingfaceMasked || 'Active'})
                </span>
              ) : (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-slate-400">
                  Unconfigured
                </span>
              )}
            </label>
            <div className="flex items-center gap-2">
              {hfCheckNotice && (
                <span
                  className={`text-[11px] font-mono animate-in fade-in flex items-center gap-1 ${
                    hfCheckNotice.success ? 'text-white' : 'text-zinc-400'
                  }`}
                >
                  {hfCheckNotice.success ? <Check className="w-3 h-3 text-white" /> : <AlertCircle className="w-3 h-3 text-zinc-400" />}
                  {hfCheckNotice.text}
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
                    handleCheckHfToken();
                  }
                }}
                placeholder={
                  config.huggingfaceConfigured && config.huggingfaceMasked
                    ? config.huggingfaceMasked
                    : 'hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
                }
                className="w-full px-3 py-2 pr-16 rounded-xl bg-black/60 border border-white/15 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-white transition-colors"
              />

              {/* Paste from clipboard button with exact requested SVG */}
              <button
                type="button"
                onClick={handlePasteHfToken}
                className="absolute right-8 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white p-1 cursor-pointer transition-colors"
                title="Paste token from clipboard"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </button>

              {/* Toggle visibility */}
              <button
                type="button"
                onClick={() => setShowHfToken(!showHfToken)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white p-1 cursor-pointer transition-colors"
                title={showHfToken ? 'Hide token' : 'Show token'}
              >
                {showHfToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>

            {/* Exact Check button as requested */}
            <button
              type="button"
              onClick={handleCheckHfToken}
              disabled={isCheckingHfToken || !config.huggingfaceToken?.trim()}
              className="px-3 py-2 rounded-lg text-xs font-semibold shrink-0 transition-all flex items-center gap-1.5 bg-white/10 hover:bg-white/15 border border-white/20 text-white cursor-pointer disabled:opacity-50"
            >
              {isCheckingHfToken ? <Loader2 className="w-3.5 h-3.5 animate-spin text-white" /> : null}
              <span>{isCheckingHfToken ? 'Checking...' : 'Check'}</span>
            </button>
          </div>
          <p className="text-[10.5px] text-slate-400 font-sans leading-tight">
            Required only if using gated models (e.g. Meta-Llama, Mistral gated repos, or private corporate libraries).
          </p>
        </div>

        {/* 2. THREE COMPACT CARDS (MINIMAL COGNITIVE LOAD: JUST MODEL NAME + STATUS SIGN + CHANGE BUTTON) */}
        <div className="space-y-2.5 pt-1">
          <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
            Configured Neural Models
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* CARD 1: EMBEDDING MODEL */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <Layers className="w-3.5 h-3.5 text-white" />
                    <span>Embedding Model</span>
                  </div>
                  {renderStatusSign(embeddingStatus, configuredEmbedding)}
                </div>

                <div className="font-semibold text-sm text-white truncate" title={configuredEmbedding}>
                  {getCleanModelName(configuredEmbedding, 'embedding')}
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('embedding')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 hover:border-white/30 text-xs font-medium text-slate-200 hover:text-white transition-all flex items-center justify-between cursor-pointer"
              >
                <span>Change Model</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>

            {/* CARD 2: RERANKER */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                    <span>Reranker</span>
                  </div>
                  {renderStatusSign(rerankerStatus, configuredReranker)}
                </div>

                <div className="font-semibold text-sm text-white truncate" title={configuredReranker}>
                  {getCleanModelName(configuredReranker, 'reranker')}
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('reranker')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 hover:border-white/30 text-xs font-medium text-slate-200 hover:text-white transition-all flex items-center justify-between cursor-pointer"
              >
                <span>Change Model</span>
                <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>

            {/* CARD 3: CLAIM VERIFIER */}
            <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 hover:border-white/30 transition-all flex flex-col justify-between space-y-3">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between gap-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                    <ShieldCheck className="w-3.5 h-3.5 text-white" />
                    <span>Claim Verifier</span>
                  </div>
                  {renderStatusSign(verifierStatus, configuredVerifier)}
                </div>

                <div className="font-semibold text-sm text-white truncate" title={configuredVerifier}>
                  {getCleanModelName(configuredVerifier, 'verifier')}
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveCategoryModal('verifier')}
                className="w-full py-1.5 px-3 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 hover:border-white/30 text-xs font-medium text-slate-200 hover:text-white transition-all flex items-center justify-between cursor-pointer"
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
              className="py-1 text-xs font-medium text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {showAdvanced ? (
                <ChevronDown className="w-3.5 h-3.5 text-white" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 text-white" />
              )}
              <span>Advanced Configuration (Custom Hugging Face Repositories)</span>
            </button>

            {showAdvanced && (
              <div className="mt-2.5 p-3 rounded-xl bg-black/40 border border-white/15 space-y-3 animate-in fade-in duration-150">
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
                            ? 'bg-white text-black font-bold shadow-xs'
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
                    className="flex-1 px-3 py-1.5 rounded-lg bg-black/60 border border-white/15 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-white"
                  />
                  <button
                    type="button"
                    onClick={handleApplyCustomModel}
                    disabled={isApplyingCustom || !customModelInput.trim()}
                    className="px-3 py-1.5 rounded-lg bg-white hover:bg-zinc-200 disabled:opacity-50 text-black text-xs font-bold shrink-0 transition-colors cursor-pointer"
                  >
                    {isApplyingCustom ? 'Applying...' : 'Apply Custom Model'}
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 font-sans">
                  Accepts Hugging Face repo IDs or Python snippets like <code className="text-white font-mono">SentenceTransformer("...")</code>. Automatically verified against backend runtime rules.
                </p>
              </div>
            )}
          </div>
        )}

        {/* 4. HARDWARE DEVICE SELECTION */}
        <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs font-bold text-white">
            <Cpu className="w-3.5 h-3.5 text-white" />
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
                    ? 'bg-white text-black font-bold shadow-xs'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white border border-white/10'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* POPUP-BASED MODEL SELECTION MODAL (DETAILS, CONTEXT MATCH & SPECS SHOWN HERE) */}
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
                  <Layers className="w-4 h-4 text-white" />
                ) : activeCategoryModal === 'reranker' ? (
                  <Sparkles className="w-4 h-4 text-white" />
                ) : (
                  <ShieldCheck className="w-4 h-4 text-white" />
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

            {/* MODAL BODY (MODELS LIST WITH FULL SPECIFICATIONS & CONTEXT LABELS) */}
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
                  const isCached = Boolean(
                    m.cached ||
                    m.isInstalled ||
                    m.status?.toLowerCase().includes('cached') ||
                    m.status?.toLowerCase().includes('ready') ||
                    m.status?.toLowerCase().includes('installed') ||
                    m.status?.includes('Built-in')
                  );
                  const isRerankerMatch =
                    activeCategoryModal === 'reranker' &&
                    m.id.includes('v2-m3') &&
                    configuredEmbedding.includes('embeddinggemma-2');

                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectModel(activeCategoryModal, m.id)}
                      className={`w-full p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-white/10 border-white/40 shadow-xs'
                          : 'bg-white/[0.02] border-white/10 hover:bg-white/[0.05] hover:border-white/20'
                      }`}
                    >
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-white">{m.name}</span>
                          <span
                            className={`text-[9.5px] font-mono px-1.5 py-0.2 rounded ${
                              isCached
                                ? 'bg-white/10 text-white border border-white/20'
                                : 'bg-white/5 text-zinc-400 border border-white/10'
                            }`}
                          >
                            {m.status || (isCached ? 'Cached & Ready' : 'Requires Download')}
                          </span>
                        </div>

                        <div className="text-[11px] font-mono text-slate-400 truncate">
                          {m.id}
                        </div>

                        {/* Full specifications and context matching in modal popup */}
                        {m.specifications && (
                          <div className="text-[10px] font-mono text-zinc-300">
                            {m.specifications}
                          </div>
                        )}

                        {isRerankerMatch && (
                          <div className="text-[9.5px] font-mono text-zinc-300 leading-tight">
                            Context (8,192 tokens) matches google/embeddinggemma-2 for zero-truncation cross-attention
                          </div>
                        )}
                      </div>

                      <div className="shrink-0 flex items-center gap-2">
                        {isCached ? (
                          <span
                            className="p-1.5 rounded-md bg-white/10 border border-white/20 text-white flex items-center justify-center shadow-xs"
                            title="Verified & Cached in Backend"
                          >
                            <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDownloadModel(m.id);
                            }}
                            disabled={downloadingModelId === m.id}
                            className="p-1.5 rounded-md bg-white/10 hover:bg-white/20 border border-white/20 text-white cursor-pointer transition-all"
                            title="Download Model Weights from Backend"
                          >
                            {downloadingModelId === m.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                            ) : (
                              <Download className="w-3.5 h-3.5 text-white" />
                            )}
                          </button>
                        )}
                        {isSelected ? (
                          <div className="w-5 h-5 rounded-full bg-white text-black flex items-center justify-center shadow-xs">
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
