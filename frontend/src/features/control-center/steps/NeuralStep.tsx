import {
  Check,
  Cpu,
  Download,
  Eye,
  EyeOff,
  Key,
  Layers,
  Sparkles,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
import { useControlCenterStore } from '../store/useControlCenterStore';

interface ModelOption {
  id: string;
  name: string;
  dimOrType: string;
  tokens: string;
  chunkSize: string;
  desc: string;
  recommended?: boolean;
}

const EMBEDDING_PRESETS: ModelOption[] = [
  {
    id: 'google/embeddinggemma-2',
    name: 'Embedding Gemma 2',
    dimOrType: '768-dim',
    tokens: '8,192 tokens context',
    chunkSize: '512 tokens (64 overlap)',
    desc: 'Dense semantic embeddings with Google Gemma 2 architecture',
    recommended: true,
  },
  {
    id: 'BAAI/bge-large-en-v1.5',
    name: 'BGE Large EN v1.5',
    dimOrType: '1024-dim',
    tokens: '512 tokens max',
    chunkSize: '256 tokens (32 overlap)',
    desc: 'MTEB top-tier benchmark dense vector substrate',
  },
  {
    id: 'nomic-ai/nomic-embed-text-v1.5',
    name: 'Nomic Embed Text v1.5',
    dimOrType: '768-dim',
    tokens: '8,192 tokens context',
    chunkSize: '512 tokens',
    desc: 'Extended long-context document embedding',
  },
  {
    id: 'sentence-transformers/all-MiniLM-L6-v2',
    name: 'All MiniLM L6 v2',
    dimOrType: '384-dim',
    tokens: '256 tokens max',
    chunkSize: '128 tokens',
    desc: 'SentenceTransformers lightweight low-latency embeddings',
  },
];

const RERANKER_PRESETS: ModelOption[] = [
  {
    id: 'BAAI/bge-reranker-v2-m3',
    name: 'BGE Reranker v2 M3',
    dimOrType: 'Multilingual Cross-Attention',
    tokens: '8,192 tokens max',
    chunkSize: 'Reranks candidate top-20 chunks down to top-4',
    desc: 'Production 8,192-token context cross-encoder matching Gemma 2',
    recommended: true,
  },
  {
    id: 'jinaai/jina-reranker-v3.5',
    name: 'Jina Reranker v3.5',
    dimOrType: 'Listwise Cross-Attention',
    tokens: '8,192 tokens max',
    chunkSize: 'Reranks candidate top-20 chunks down to top-4',
    desc: 'State-of-the-art listwise neural reranker with Flash Attention',
  },
  {
    id: 'BAAI/bge-reranker-large',
    name: 'BGE Reranker Large',
    dimOrType: 'Cross-Attention',
    tokens: '512 tokens max',
    chunkSize: 'Reranks candidate top-20 chunks down to top-4',
    desc: 'Deep cross-attention scoring on passage chunks',
  },
  {
    id: 'cross-encoder/ms-marco-MiniLM-L-6-v2',
    name: 'MS MARCO MiniLM L6',
    dimOrType: 'Lightweight Cross-Encoder',
    tokens: '512 tokens max',
    chunkSize: 'Reranks candidate top-20 chunks down to top-4',
    desc: 'Fast passage scoring optimized for high throughput',
  },
  {
    id: 'mixedbread-ai/mxbai-rerank-large-v1',
    name: 'MxBAI Rerank Large v1',
    dimOrType: 'High Precision',
    tokens: '512 tokens max',
    chunkSize: 'Scoring on 512-token chunks',
    desc: 'Fine-tuned cross-encoder for scientific domain retrieval',
  },
];

const NLI_PRESETS: ModelOption[] = [
  {
    id: 'dleemiller/finecat-nli-ultra-l',
    name: 'FineCat NLI Ultra-L',
    dimOrType: 'Ultra-L / RoBERTa',
    tokens: '512 tokens max',
    chunkSize: 'Pairwise Citation Chunk vs. Claim verification',
    desc: 'Fine-grained claim entailment verification & strict hallucination guard',
    recommended: true,
  },
  {
    id: 'FineCat-NLI-DeBERTa',
    name: 'FineCat NLI DeBERTa',
    dimOrType: 'DeBERTa-v3',
    tokens: '512 tokens max',
    chunkSize: 'Pairwise Citation Chunk vs. Claim verification',
    desc: 'Standard DeBERTa-v3 claim entailment verification',
  },
  {
    id: 'facebook/bart-large-mnli',
    name: 'BART Large MNLI',
    dimOrType: 'Zero-Shot',
    tokens: '1,024 tokens max',
    chunkSize: 'Multi-genre claim premise-hypothesis verification',
    desc: 'Zero-shot multi-genre NLI classification',
  },
  {
    id: 'In-Memory Verifier',
    name: 'In-Memory Verifier',
    dimOrType: 'Zero-Dep',
    tokens: '512 tokens',
    chunkSize: 'Heuristic lexical premise checking',
    desc: 'Zero-dependency local verification fallback',
  },
];

export const NeuralStep: React.FC = () => {
  const { config, updateConfig } = useControlCenterStore();

  const currentEmbedding = config.embeddingModel || 'google/embeddinggemma-2';
  const currentReranker = config.rerankerModel || 'jinaai/jina-reranker-v3.5';
  const currentNli = config.nliVerifierModel || 'dleemiller/finecat-nli-ultra-l';
  const currentDevice = config.neuralDevice || 'auto';

  const isCustomEmbedding = !EMBEDDING_PRESETS.some((p) => p.id === currentEmbedding);
  const isCustomReranker = !RERANKER_PRESETS.some((p) => p.id === currentReranker);
  const isCustomNli = !NLI_PRESETS.some((p) => p.id === currentNli);

  const [customEmbeddingInput, setCustomEmbeddingInput] = useState(
    isCustomEmbedding ? currentEmbedding : ''
  );
  const [customRerankerInput, setCustomRerankerInput] = useState(
    isCustomReranker ? currentReranker : ''
  );
  const [customNliInput, setCustomNliInput] = useState(
    isCustomNli ? currentNli : ''
  );

  const [showCustomEmbedding, setShowCustomEmbedding] = useState(isCustomEmbedding);
  const [showCustomReranker, setShowCustomReranker] = useState(isCustomReranker);
  const [showCustomNli, setShowCustomNli] = useState(isCustomNli);

  const [showHfToken, setShowHfToken] = useState(false);
  const [snippetNotice, setSnippetNotice] = useState<string | null>(null);

  // Helper to extract Hugging Face / SentenceTransformers identifiers
  const handleExtractSnippet = (
    rawText: string,
    target: 'embedding' | 'reranker' | 'nli'
  ) => {
    let cleaned = rawText.trim();
    if (!cleaned) return;

    // Detect Python sentence_transformers snippet: SentenceTransformer("...") or CrossEncoder("...")
    const match = cleaned.match(
      /(?:SentenceTransformer|CrossEncoder|from_pretrained)\s*\(\s*["']([^"']+)["']\s*\)/i
    );
    if (match && match[1]) {
      cleaned = match[1].trim();
      setSnippetNotice(`SentenceTransformers model extracted: "${cleaned}"`);
      setTimeout(() => setSnippetNotice(null), 4000);
    } else {
      // Detect huggingface.co URLs
      const urlMatch = cleaned.match(/huggingface\.co\/([a-zA-Z0-9_\-./]+)/i);
      if (urlMatch && urlMatch[1]) {
        cleaned = urlMatch[1].replace(/\/+$/, '').trim();
        setSnippetNotice(`Hugging Face repo extracted: "${cleaned}"`);
        setTimeout(() => setSnippetNotice(null), 4000);
      }
    }

    cleaned = cleaned.replace(/^["']|["']$/g, '');

    if (target === 'embedding') {
      setCustomEmbeddingInput(cleaned);
      updateConfig({ embeddingModel: cleaned });
    } else if (target === 'reranker') {
      setCustomRerankerInput(cleaned);
      updateConfig({ rerankerModel: cleaned });
    } else {
      setCustomNliInput(cleaned);
      updateConfig({ nliVerifierModel: cleaned });
    }
  };

  const selectedEmbeddingObj = EMBEDDING_PRESETS.find((p) => p.id === currentEmbedding);
  const selectedRerankerObj = RERANKER_PRESETS.find((p) => p.id === currentReranker);
  const selectedNliObj = NLI_PRESETS.find((p) => p.id === currentNli);

  return (
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">AI Retrieval & Embedding Models</h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Select your models for semantic document search, relevance reranking, and factual claim verification.
        </p>
      </div>

      {snippetNotice && (
        <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-mono text-indigo-300 animate-in fade-in flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{snippetNotice}</span>
        </div>
      )}

      {/* SINGLE UNIFIED FORM CONTAINER */}
      <div className="p-4 sm:p-5 rounded-2xl bg-[#131622] border border-white/10 space-y-5 shadow-lg">
        {/* 1. DENSE VECTOR EMBEDDING FIELD */}
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <label className="text-xs font-bold text-white flex items-center gap-2">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              <span>Dense Vector Embedding</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 font-semibold">
                {selectedEmbeddingObj ? selectedEmbeddingObj.dimOrType : 'Custom Embedder'}
              </span>
            </label>
            <div className="text-[11px] font-mono text-slate-400 flex items-center gap-2">
              <span className="text-indigo-300 font-medium">
                {selectedEmbeddingObj ? selectedEmbeddingObj.tokens : 'SentenceTransformers supported'}
              </span>
              <span>•</span>
              <span className="text-slate-400">
                Chunk: {selectedEmbeddingObj ? selectedEmbeddingObj.chunkSize : '512 tokens'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {EMBEDDING_PRESETS.map((m) => {
              const isSelected = !showCustomEmbedding && currentEmbedding === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setShowCustomEmbedding(false);
                    updateConfig({ embeddingModel: m.id });
                  }}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-white text-black border-white shadow-xs font-semibold'
                      : 'bg-white/[0.03] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/[0.06]'
                  }`}
                >
                  <div className="min-w-0 pr-1">
                    <div className="text-xs font-bold truncate">{m.name}</div>
                    <div
                      className={`text-[10px] font-mono mt-0.5 ${
                        isSelected ? 'text-slate-800' : 'text-slate-400'
                      }`}
                    >
                      {m.dimOrType} • {m.tokens} • Chunk: {m.chunkSize}
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-black stroke-[3] shrink-0" />}
                </button>
              );
            })}
          </div>

          {/* Other / Custom SentenceTransformers & Hugging Face Option */}
          <div className="pt-1">
            <button
              type="button"
              onClick={() => {
                setShowCustomEmbedding(!showCustomEmbedding);
                if (!showCustomEmbedding && customEmbeddingInput) {
                  updateConfig({ embeddingModel: customEmbeddingInput });
                }
              }}
              className={`w-full py-1.5 px-3 rounded-xl border text-xs font-medium flex items-center justify-between cursor-pointer transition-colors ${
                showCustomEmbedding
                  ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300'
                  : 'border-white/10 bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}
            >
              <span>Other (SentenceTransformers / Hugging Face repo ID)</span>
              <span className="text-[11px] font-mono">
                {showCustomEmbedding ? '▲ Active' : '▼ Select custom'}
              </span>
            </button>

            {showCustomEmbedding && (
              <div className="mt-2 space-y-1 animate-in fade-in duration-150">
                <input
                  type="text"
                  value={customEmbeddingInput}
                  onChange={(e) => {
                    setCustomEmbeddingInput(e.target.value);
                    handleExtractSnippet(e.target.value, 'embedding');
                  }}
                  placeholder="e.g. sentence-transformers/all-MiniLM-L6-v2 or BAAI/bge-m3"
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-indigo-500/40 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-400"
                />
                <p className="text-[10.5px] text-slate-400 font-sans">
                  SentenceTransformers and Hugging Face repositories work out-of-the-box. Python code like <code className="text-indigo-300 font-mono">SentenceTransformer("...")</code> is auto-parsed.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* 2. CROSS-ENCODER RERANKER FIELD */}
        <div className="space-y-2 pt-3 border-t border-white/10">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <label className="text-xs font-bold text-white flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-amber-400" />
              <span>Cross-Encoder Reranker</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-300 font-semibold">
                {selectedRerankerObj ? selectedRerankerObj.dimOrType : 'Cross-Encoder'}
              </span>
            </label>
            <div className="text-[11px] font-mono text-slate-400 flex items-center gap-2">
              <span className="text-amber-300 font-medium">
                {selectedRerankerObj ? selectedRerankerObj.tokens : '512 tokens max'}
              </span>
              <span>•</span>
              <span className="text-slate-400">
                {selectedRerankerObj ? selectedRerankerObj.chunkSize : 'Reranks candidate chunks -> top 4'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {RERANKER_PRESETS.map((m) => {
              const isSelected = !showCustomReranker && currentReranker === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setShowCustomReranker(false);
                    updateConfig({ rerankerModel: m.id });
                  }}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-white text-black border-white shadow-xs font-semibold'
                      : 'bg-white/[0.03] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/[0.06]'
                  }`}
                >
                  <div className="min-w-0 pr-1">
                    <div className="text-xs font-bold truncate">{m.name}</div>
                    <div
                      className={`text-[10px] font-mono mt-0.5 ${
                        isSelected ? 'text-slate-800' : 'text-slate-400'
                      }`}
                    >
                      {m.dimOrType} • {m.tokens}
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-black stroke-[3] shrink-0" />}
                </button>
              );
            })}
          </div>

          {/* Other / Custom Reranker Option */}
          <div className="pt-1">
            <button
              type="button"
              onClick={() => {
                setShowCustomReranker(!showCustomReranker);
                if (!showCustomReranker && customRerankerInput) {
                  updateConfig({ rerankerModel: customRerankerInput });
                }
              }}
              className={`w-full py-1.5 px-3 rounded-xl border text-xs font-medium flex items-center justify-between cursor-pointer transition-colors ${
                showCustomReranker
                  ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
                  : 'border-white/10 bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}
            >
              <span>Other (CrossEncoder or Hugging Face repo ID)</span>
              <span className="text-[11px] font-mono">
                {showCustomReranker ? '▲ Active' : '▼ Select custom'}
              </span>
            </button>

            {showCustomReranker && (
              <div className="mt-2 space-y-1 animate-in fade-in duration-150">
                <input
                  type="text"
                  value={customRerankerInput}
                  onChange={(e) => {
                    setCustomRerankerInput(e.target.value);
                    handleExtractSnippet(e.target.value, 'reranker');
                  }}
                  placeholder="e.g. cross-encoder/ms-marco-MiniLM-L-6-v2"
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-amber-500/40 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-amber-400"
                />
                <p className="text-[10.5px] text-slate-400 font-sans">
                  SentenceTransformers CrossEncoder models and Hugging Face repos supported.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* 3. NLI CLAIM VERIFIER FIELD */}
        <div className="space-y-2 pt-3 border-t border-white/10">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <label className="text-xs font-bold text-white flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
              <span>NLI Claim Verifier</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-semibold">
                {selectedNliObj ? selectedNliObj.dimOrType : 'Claim Verifier'}
              </span>
            </label>
            <div className="text-[11px] font-mono text-slate-400 flex items-center gap-2">
              <span className="text-emerald-300 font-medium">
                {selectedNliObj ? selectedNliObj.tokens : '512 tokens max'}
              </span>
              <span>•</span>
              <span className="text-slate-400">
                {selectedNliObj ? selectedNliObj.chunkSize : 'Pairwise Chunk vs. Claim'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {NLI_PRESETS.map((m) => {
              const isSelected = !showCustomNli && currentNli === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => {
                    setShowCustomNli(false);
                    updateConfig({ nliVerifierModel: m.id });
                  }}
                  className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-white text-black border-white shadow-xs font-semibold'
                      : 'bg-white/[0.03] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/[0.06]'
                  }`}
                >
                  <div className="min-w-0 pr-1">
                    <div className="text-xs font-bold truncate">{m.name}</div>
                    <div
                      className={`text-[10px] font-mono mt-0.5 ${
                        isSelected ? 'text-slate-800' : 'text-slate-400'
                      }`}
                    >
                      {m.dimOrType} • {m.tokens}
                    </div>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-black stroke-[3] shrink-0" />}
                </button>
              );
            })}
          </div>

          {/* Other / Custom NLI Verifier */}
          <div className="pt-1">
            <button
              type="button"
              onClick={() => {
                setShowCustomNli(!showCustomNli);
                if (!showCustomNli && customNliInput) {
                  updateConfig({ nliVerifierModel: customNliInput });
                }
              }}
              className={`w-full py-1.5 px-3 rounded-xl border text-xs font-medium flex items-center justify-between cursor-pointer transition-colors ${
                showCustomNli
                  ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300'
                  : 'border-white/10 bg-white/[0.02] text-slate-400 hover:text-white hover:bg-white/[0.05]'
              }`}
            >
              <span>Other (Custom NLI model or Hugging Face repo ID)</span>
              <span className="text-[11px] font-mono">
                {showCustomNli ? '▲ Active' : '▼ Select custom'}
              </span>
            </button>

            {showCustomNli && (
              <div className="mt-2 space-y-1 animate-in fade-in duration-150">
                <input
                  type="text"
                  value={customNliInput}
                  onChange={(e) => {
                    setCustomNliInput(e.target.value);
                    handleExtractSnippet(e.target.value, 'nli');
                  }}
                  placeholder="e.g. MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
                  className="w-full px-3 py-2 rounded-xl bg-black/60 border border-emerald-500/40 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-emerald-400"
                />
              </div>
            )}
          </div>
        </div>

        {/* 4. HUGGING FACE ACCESS TOKEN (INSIDE SAME FORM) */}
        <div className="space-y-2 pt-3 border-t border-white/10">
          <div className="flex items-center justify-between gap-2">
            <label className="text-xs font-bold text-white flex items-center gap-2">
              <Key className="w-3.5 h-3.5 text-indigo-400" />
              <span>Hugging Face Access Token</span>
              <span className="text-[10px] font-normal text-slate-400 font-mono">(Optional)</span>
            </label>
            <span className="text-[10.5px] font-mono text-slate-400">For gated or private repos</span>
          </div>

          <div className="relative">
            <input
              type={showHfToken ? 'text' : 'password'}
              value={config.huggingfaceToken || ''}
              onChange={(e) => updateConfig({ huggingfaceToken: e.target.value })}
              placeholder="hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              className="w-full px-3 py-2 pr-9 rounded-xl bg-black/60 border border-white/15 text-xs font-mono text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-400 transition-colors"
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
          <p className="text-[10.5px] text-slate-400 font-sans leading-tight">
            Required only if using gated models (e.g. Meta-Llama, Mistral gated repos, or private corporate libraries).
          </p>
        </div>

        {/* 5. HARDWARE DEVICE SELECTION (INSIDE SAME FORM) */}
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
                { id: 'auto', label: 'Auto (MPS / CUDA)' },
                { id: 'mps', label: 'MPS' },
                { id: 'cuda', label: 'CUDA' },
                { id: 'cpu', label: 'CPU' },
              ] as const
            ).map((dev) => {
              const isSelected = currentDevice === dev.id;
              return (
                <button
                  key={dev.id}
                  type="button"
                  onClick={() => updateConfig({ neuralDevice: dev.id })}
                  className={`px-2.5 py-1 rounded-lg border text-[11px] font-mono transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-white text-black border-white font-bold'
                      : 'bg-white/[0.04] border-white/10 text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {dev.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 6. DOWNLOAD PIPELINE & EXECUTION INFO FOOTER */}
        <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/10 flex items-start gap-3 text-xs">
          <Download className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="font-semibold text-white flex items-center gap-2">
              <span>Automatic Download on "Next"</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                Streaming Pipeline Ready
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
              Clicking <strong>Next</strong> saves your substrate configuration to RAISE. If model weights are not cached locally on your device, RAISE triggers automatic background streaming download with live progress telemetry before query execution starts.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
