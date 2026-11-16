import type { DetectedProvider } from './services/keyDetector';

export type TargetPlatform = 'macos' | 'windows' | 'linux' | 'ios' | 'android' | 'web';
export type LLMDeployment = 'cloud' | 'local';
export type SubstrateMode = 'cloud' | 'local' | 'in_memory_fallback';

export interface CloudApiKeyEntry {
  id: string;
  key: string;
  provider: DetectedProvider;
  providerName: string;
  verified: boolean | null; // null = untested, true = connected, false = failed
  latencyMs?: number;
  isTesting?: boolean;
  error?: string;
  fromEnv?: boolean;
  envVarName?: string;
}

export interface SubstrateConfig {
  mode: SubstrateMode;
  uri?: string;
  user?: string;
  password?: string;
  database?: string;
  tested?: boolean;
  online?: boolean;
  latencyMs?: number;
}

export interface DynamicLLMModel {
  provider: string;
  displayName: string;
  model: string;
  status: string;
  isActive: boolean;
  tier?: string;
  sizeGb?: number;
  ramGb?: number;
  isInstalled?: boolean;
  source?: string;
}

export interface SystemHardwareInfo {
  platform: TargetPlatform;
  osName: string;
  totalRamGb: number;
  cpuCores: number;
  freeRamGb?: number;
  cpuUsagePct?: number;
  gpuName?: string;
  hasMetalOrCuda: boolean;
  ollamaRunning?: boolean;
}

// Backward-compatible alias types for existing references
export type LLMMode =
  | 'cloud_groq'
  | 'cloud_gemini'
  | 'cloud_openai'
  | 'cloud_anthropic'
  | 'cloud_mistral'
  | 'cloud_deepseek'
  | 'cloud_nvidia'
  | 'cloud_cohere'
  | 'cloud_openrouter'
  | 'cloud_universal'
  | 'local_ollama'
  | 'local_vllm'
  | (string & {});
export type DatabaseMode = SubstrateMode;

export interface ControlCenterConfig {
  firstRunCompleted: boolean;
  targetPlatform: TargetPlatform;
  llmDeployment: LLMDeployment;
  apiKeys: CloudApiKeyEntry[];
  selectedLocalModel: string;
  tunnelUrl?: string;

  // Neural Pipeline Substrates
  embeddingModel?: string;
  rerankerModel?: string;
  nliVerifierModel?: string;
  neuralDevice?: 'auto' | 'mps' | 'cuda' | 'cpu';
  huggingfaceToken?: string;
  huggingfaceConfigured?: boolean;
  huggingfaceMasked?: string;

  // Architectural Substrates
  knowledgeGraph: SubstrateConfig; // Neo4j Property Graph
  sessionMemory: SubstrateConfig; // PostgreSQL Chat History
  cacheAndSignals: SubstrateConfig; // Redis Cache & Bus

  // Backward compatibility fields
  llmMode?: LLMMode;
  groqApiKey?: string;
  geminiApiKey?: string;
  neo4jMode?: DatabaseMode;
  neo4jUri?: string;
  neo4jPassword?: string;
  postgresMode?: DatabaseMode;
  redisMode?: DatabaseMode;
}
