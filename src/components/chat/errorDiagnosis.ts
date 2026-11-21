import { useControlCenterStore } from '../../features/control-center/store/useControlCenterStore';

export interface BackendErrorDetails {
  title: string;
  message: string;
  cause?: string;
  action?: string;
  status?: number;
  isOffline?: boolean;
  isTimeout?: boolean;
  isAborted?: boolean;
}

export type ControlCenterSection =
  | 'overview'
  | 'models'
  | 'neural'
  | 'databases'
  | 'platform'
  | 'launch';

export interface ParsedErrorDiagnosis {
  category:
    | 'neural_embedding'
    | 'neural_reranker'
    | 'neural_verifier'
    | 'llm_inference'
    | 'storage_substrate'
    | 'server_offline'
    | 'generic';
  headline: string;
  cleanMessage: string;
  recommendedAction: string;
  targetTab: ControlCenterSection;
  primaryButtonLabel: string;
  badgeLabel: string;
  modelName?: string;
  isDownloadableModel?: boolean;
}

function extractModel(rawMsg: string, regex: RegExp, fallback = ''): string {
  return rawMsg.match(regex)?.[1] || fallback;
}

export function diagnoseBackendError(
  error: BackendErrorDetails,
  targetUrl: string
): ParsedErrorDiagnosis {
  const rawMsg = (error.message || '').trim();
  const rawTitle = (error.title || '').trim();
  const rawCause = (error.cause || '').trim();
  const combined = `${rawTitle} ${rawMsg} ${rawCause}`.toLowerCase();
  const ccConfig = useControlCenterStore.getState().config;

  // 1. Neural Embedding
  if (
    combined.includes('embedding model') ||
    combined.includes('dense_embedding') ||
    combined.includes('sentence-transformers') ||
    (combined.includes('embedding') && (combined.includes('not available') || combined.includes('not found') || combined.includes('missing')))
  ) {
    const model = extractModel(rawMsg, /['"]([a-zA-Z0-9_\-./]+(?:embedding|gemma|bge|minilm|bert)[a-zA-Z0-9_\-./]*)['"]/i, ccConfig?.embeddingModel);
    return {
      category: 'neural_embedding',
      headline: 'Embedding Model Required',
      cleanMessage: model ? `The embedding model '${model}' is not installed.` : 'The semantic embedding model is not installed.',
      recommendedAction: 'Download the embedding model in Control Center to enable semantic search.',
      targetTab: 'neural',
      primaryButtonLabel: 'Download in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName: model || undefined,
      isDownloadableModel: Boolean(model),
    };
  }

  // 2. Neural Reranker
  if (combined.includes('reranker') || combined.includes('cross-encoder')) {
    const model = extractModel(rawMsg, /['"]([a-zA-Z0-9_\-./]+(?:reranker|cross-encoder)[a-zA-Z0-9_\-./]*)['"]/i, ccConfig?.rerankerModel);
    return {
      category: 'neural_reranker',
      headline: 'Neural Reranker Required',
      cleanMessage: model ? `The cross-encoder reranker '${model}' is not cached.` : 'The configured cross-encoder reranker is not cached.',
      recommendedAction: 'Open the Neural Assets tab in the Control Center to configure the reranker.',
      targetTab: 'neural',
      primaryButtonLabel: 'Configure in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName: model || undefined,
      isDownloadableModel: Boolean(model),
    };
  }

  // 3. Citation Verifier
  if (combined.includes('nli') || combined.includes('verifier') || combined.includes('finecat')) {
    const model = extractModel(rawMsg, /['"]([a-zA-Z0-9_\-./]+(?:finecat|nli)[a-zA-Z0-9_\-./]*)['"]/i, ccConfig?.nliVerifierModel);
    return {
      category: 'neural_verifier',
      headline: 'Citation Verifier Required',
      cleanMessage: model ? `The citation verification model '${model}' is not cached.` : 'The configured citation verification model is not cached.',
      recommendedAction: 'Open the Neural Assets tab in the Control Center to configure the verifier.',
      targetTab: 'neural',
      primaryButtonLabel: 'Configure in Control Center',
      badgeLabel: 'ASSET MISSING',
      modelName: model || undefined,
      isDownloadableModel: Boolean(model),
    };
  }

  // 4. LLM Provider
  if (
    combined.includes('api key') || combined.includes('groq') || combined.includes('gemini') ||
    combined.includes('openai') || combined.includes('anthropic') || combined.includes('deepseek') ||
    combined.includes('openrouter') || combined.includes('vllm') || combined.includes('ollama') ||
    error.status === 401 || error.status === 403
  ) {
    return {
      category: 'llm_inference',
      headline: 'LLM Provider Configuration Required',
      cleanMessage: 'The selected language model requires valid API credentials or an active local inference engine.',
      recommendedAction: 'Open the Inference tab in the Control Center to update your API keys or switch providers.',
      targetTab: 'models',
      primaryButtonLabel: 'Configure Inference in Control Center',
      badgeLabel: 'AUTH / CONFIG',
    };
  }

  // 5. Database Substrates
  if (['postgres', 'redis', 'neo4j', 'chroma', 'sqlite', 'database'].some((db) => combined.includes(db))) {
    return {
      category: 'storage_substrate',
      headline: 'Database Substrate Issue',
      cleanMessage: 'Could not establish a connection to the configured database, graph, or caching substrate.',
      recommendedAction: 'Open the Storage tab in the Control Center to check connections or toggle in-memory fallbacks.',
      targetTab: 'databases',
      primaryButtonLabel: 'Configure Storage in Control Center',
      badgeLabel: 'STORAGE ERROR',
    };
  }

  // 6. Server Offline
  if (error.isOffline || error.status === 0 || combined.includes('offline') || combined.includes('failed to fetch')) {
    return {
      category: 'server_offline',
      headline: 'Backend Server Offline',
      cleanMessage: `The RAISE gateway server is not responding at ${targetUrl || 'http://localhost:8000'}.`,
      recommendedAction: 'Check that the backend server is running and accessible.',
      targetTab: 'platform',
      primaryButtonLabel: 'Open Control Center',
      badgeLabel: 'OFFLINE',
    };
  }

  // 7. Generic Fallback
  let cleanMsg = rawMsg.includes('pip install') ? rawMsg.split('(run:')[0].trim() : rawMsg;
  if (!cleanMsg || cleanMsg === 'Server returned an error') {
    cleanMsg = 'An unexpected error occurred during research query execution.';
  }

  let badgeLabel = 'PIPELINE ERROR';
  if (error.isTimeout) badgeLabel = 'TIMEOUT';
  else if (error.status && error.status !== 200) badgeLabel = `HTTP ${error.status}`;
  else if (rawCause && rawCause !== 'PIPELINE_ERROR') badgeLabel = rawCause.replace(/_/g, ' ');

  return {
    category: 'generic',
    headline: error.title || 'Query Execution Issue',
    cleanMessage: cleanMsg,
    recommendedAction: 'Review the details below or open the Control Center to verify system configuration.',
    targetTab: 'overview',
    primaryButtonLabel: 'Open Control Center',
    badgeLabel,
  };
}
