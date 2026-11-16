import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { detectProviderFromKey, type DetectedProvider } from '../services/keyDetector';
import { detectEnvCredentials } from '../services/envDetector';
import { detectHostOS, platformAdapter } from '../services/platformAdapter';
import type {
  CloudApiKeyEntry,
  ControlCenterConfig,
  SubstrateConfig,
  SubstrateMode,
  SystemHardwareInfo,
} from '../types';

interface ControlCenterState {
  isOpen: boolean;
  activeTab: 'platform' | 'models' | 'neural' | 'databases' | 'launch';
  hardware: SystemHardwareInfo | null;
  config: ControlCenterConfig;
  downloadProgress: number; // 0 - 100
  downloadSpeed: string;
  isDownloading: boolean;
  statusMessage: string | null;
  preflightAssets: import('../services/platformAdapter').PreflightAsset[];
  preflightFootprint: string;

  setOpen: (open: boolean) => void;
  setActiveTab: (tab: 'platform' | 'models' | 'neural' | 'databases' | 'launch') => void;
  updateConfig: (patch: Partial<ControlCenterConfig>) => void;
  setHardware: (info: SystemHardwareInfo) => void;
  setDownloadProgress: (percent: number, speed: string) => void;
  setIsDownloading: (downloading: boolean) => void;
  setPreflightAssets: (
    assets: import('../services/platformAdapter').PreflightAsset[],
    footprint?: string
  ) => void;
  setStatusMessage: (msg: string | null) => void;
  completeFirstRun: () => void;

  // Granular actions for API keys and substrates
  addApiKey: (initialKey?: string) => void;
  updateApiKey: (id: string, key: string) => void;
  removeApiKey: (id: string) => void;
  setKeyVerification: (id: string, verified: boolean, latencyMs?: number, error?: string) => void;
  updateSubstrate: (
    type: 'knowledgeGraph' | 'sessionMemory' | 'cacheAndSignals',
    patch: Partial<SubstrateConfig>
  ) => void;
  syncEnvCredentials: () => void;
  syncBackendConfig: () => Promise<void>;
  setAllSubstratesMode: (mode: 'in_memory_fallback' | 'cloud' | 'local') => void;
}

const defaultPlatform = detectHostOS();

export const useControlCenterStore = create<ControlCenterState>()(
  persist(
    (set) => ({
      isOpen: false,
      activeTab: 'platform',
      hardware: {
        platform: defaultPlatform,
        osName: defaultPlatform === 'macos' ? 'macOS (Apple Silicon)' : defaultPlatform === 'windows' ? 'Windows' : 'Linux',
        totalRamGb: 8.0,
        cpuCores: 8,
        hasMetalOrCuda: true,
      },
      downloadProgress: 0,
      downloadSpeed: '',
      isDownloading: false,
      statusMessage: null,
      preflightAssets: [],
      preflightFootprint: '~4.6 GB Total Footprint',
      config: {
        firstRunCompleted: typeof process !== 'undefined' && process.env.NODE_ENV === 'test',
        targetPlatform: defaultPlatform,
        llmDeployment: 'cloud',
        embeddingModel: 'google/embeddinggemma-2',
        rerankerModel: 'BAAI/bge-reranker-v2-m3',
        nliVerifierModel: 'dleemiller/finecat-nli-ultra-l',
        neuralDevice: 'auto',
        huggingfaceToken: '',
        huggingfaceConfigured: false,
        huggingfaceMasked: '',
        apiKeys: [
          {
            id: 'key-1',
            key: '',
            provider: 'unknown',
            providerName: 'Unconfigured Key',
            verified: null,
          },
        ],
        selectedLocalModel: 'llama3.2:3b',
        tunnelUrl: '',

        knowledgeGraph: {
          mode: 'in_memory_fallback',
          uri: 'bolt://localhost:7687',
          password: '',
        },
        sessionMemory: {
          mode: 'in_memory_fallback',
        },
        cacheAndSignals: {
          mode: 'in_memory_fallback',
        },

        // Backward compatibility getters
        llmMode: 'cloud_groq',
        groqApiKey: '',
        geminiApiKey: '',
        neo4jMode: 'in_memory_fallback',
        neo4jUri: 'bolt://localhost:7687',
        neo4jPassword: '',
        postgresMode: 'in_memory_fallback',
        redisMode: 'in_memory_fallback',
      },

      setOpen: (open) => set({ isOpen: open }),
      setActiveTab: (tab) => set({ activeTab: tab }),

      updateConfig: (patch) =>
        set((s) => {
          const updated = { ...s.config, ...patch };
          // Sync backward compatible fields
          if (patch.llmDeployment) {
            updated.llmMode = patch.llmDeployment === 'local' ? 'local_ollama' : 'cloud_groq';
          }
          if (patch.knowledgeGraph?.mode) {
            updated.neo4jMode = patch.knowledgeGraph.mode;
          }
          if (patch.sessionMemory?.mode) {
            updated.postgresMode = patch.sessionMemory.mode;
          }
          if (patch.cacheAndSignals?.mode) {
            updated.redisMode = patch.cacheAndSignals.mode;
          }
          return { config: updated };
        }),

      setHardware: (hardware) => set({ hardware }),
      setDownloadProgress: (percent, speed) =>
        set({ downloadProgress: percent, downloadSpeed: speed }),
      setIsDownloading: (isDownloading) => set({ isDownloading }),
      setPreflightAssets: (preflightAssets, footprint) =>
        set((s) => ({
          preflightAssets,
          preflightFootprint: footprint || s.preflightFootprint,
        })),
      setStatusMessage: (statusMessage) => set({ statusMessage }),
      completeFirstRun: () =>
        set((s) => ({
          config: { ...s.config, firstRunCompleted: true },
          isOpen: false,
        })),

      addApiKey: (initialKey = '') => {
        const id = `key-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
        const detection = detectProviderFromKey(initialKey);
        const newEntry: CloudApiKeyEntry = {
          id,
          key: initialKey,
          provider: detection.provider,
          providerName: detection.displayName,
          verified: null,
        };
        set((s) => {
          const currentKeys = Array.isArray(s.config?.apiKeys) ? s.config.apiKeys : [];
          return {
            config: {
              ...s.config,
              apiKeys: [...currentKeys, newEntry],
            },
          };
        });
      },

      updateApiKey: (id, key) => {
        const detection = detectProviderFromKey(key);
        set((s) => {
          const currentKeys: CloudApiKeyEntry[] = Array.isArray(s.config?.apiKeys)
            ? s.config.apiKeys
            : [];
          const apiKeys = currentKeys.map((k: CloudApiKeyEntry) =>
            k.id === id
              ? {
                  ...k,
                  key,
                  provider: detection.provider,
                  providerName: detection.displayName,
                  verified: null,
                  latencyMs: undefined,
                  error: undefined,
                }
              : k
          );
          // Sync backward-compatible keys
          const groq = apiKeys.find((k: CloudApiKeyEntry) => k.provider === 'groq')?.key || '';
          const gemini = apiKeys.find((k: CloudApiKeyEntry) => k.provider === 'gemini')?.key || '';
          return {
            config: {
              ...s.config,
              apiKeys,
              groqApiKey: groq || s.config.groqApiKey,
              geminiApiKey: gemini || s.config.geminiApiKey,
            },
          };
        });
      },

      removeApiKey: (id) => {
        set((s) => {
          const currentKeys: CloudApiKeyEntry[] = Array.isArray(s.config?.apiKeys)
            ? s.config.apiKeys
            : [];
          const filtered = currentKeys.filter((k: CloudApiKeyEntry) => k.id !== id);
          return {
            config: {
              ...s.config,
              apiKeys:
                filtered.length > 0
                  ? filtered
                  : [
                      {
                        id: `key-${Date.now()}`,
                        key: '',
                        provider: 'unknown',
                        providerName: 'Unconfigured Key',
                        verified: null,
                      },
                    ],
            },
          };
        });
      },

      setKeyVerification: (id, verified, latencyMs, error) => {
        set((s) => {
          const currentKeys: CloudApiKeyEntry[] = Array.isArray(s.config?.apiKeys)
            ? s.config.apiKeys
            : [];
          return {
            config: {
              ...s.config,
              apiKeys: currentKeys.map((k: CloudApiKeyEntry) =>
                k.id === id ? { ...k, verified, latencyMs, error, isTesting: false } : k
              ),
            },
          };
        });
      },

      updateSubstrate: (type, patch) => {
        set((s) => {
          const current = s.config[type] || { mode: 'in_memory_fallback' };
          const updatedSub = { ...current, ...patch };
          const updatedConfig: ControlCenterConfig = {
            ...s.config,
            [type]: updatedSub,
          };
          if (type === 'knowledgeGraph' && patch.mode) {
            updatedConfig.neo4jMode = patch.mode;
          }
          if (type === 'sessionMemory' && patch.mode) {
            updatedConfig.postgresMode = patch.mode;
          }
          if (type === 'cacheAndSignals' && patch.mode) {
            updatedConfig.redisMode = patch.mode;
          }
          return { config: updatedConfig };
        });
      },

      syncEnvCredentials: () => {
        const envData = detectEnvCredentials();
        set((s) => {
          let updatedApiKeys = [...(s.config?.apiKeys || [])];

          // Purge any bogus or obsolete env keys (e.g. LLM_MODE or short strings like 'cloud')
          updatedApiKeys = updatedApiKeys.filter((k) => {
            if (k.fromEnv) {
              return envData.llmKeys.some((ek) => ek.key === k.key);
            }
            if (k.key && k.key.length > 0 && k.key.length < 10) {
              return false;
            }
            return true;
          });

          if (envData.llmKeys.length > 0) {
            for (const envKey of envData.llmKeys) {
              const existingIdx = updatedApiKeys.findIndex(
                (k) => k.key === envKey.key || k.provider === envKey.provider
              );
              if (existingIdx >= 0) {
                updatedApiKeys[existingIdx] = {
                  ...updatedApiKeys[existingIdx],
                  key: envKey.key,
                  provider: envKey.provider,
                  providerName: envKey.providerName,
                  fromEnv: true,
                  envVarName: envKey.sourceEnvVar,
                };
              } else {
                if (updatedApiKeys.length === 1 && !updatedApiKeys[0].key.trim()) {
                  updatedApiKeys = [
                    {
                      id: envKey.id,
                      key: envKey.key,
                      provider: envKey.provider,
                      providerName: envKey.providerName,
                      verified: null,
                      fromEnv: true,
                      envVarName: envKey.sourceEnvVar,
                    },
                  ];
                } else {
                  updatedApiKeys.push({
                    id: envKey.id,
                    key: envKey.key,
                    provider: envKey.provider,
                    providerName: envKey.providerName,
                    verified: null,
                    fromEnv: true,
                    envVarName: envKey.sourceEnvVar,
                  });
                }
              }
            }
          }

          // If no keys detected and current keys are empty, ensure clean empty single row
          if (updatedApiKeys.length === 0) {
            updatedApiKeys = [
              {
                id: `key-${Date.now()}`,
                key: '',
                provider: 'unknown',
                providerName: 'Unconfigured Key',
                verified: null,
              },
            ];
          }

          return {
            config: {
              ...s.config,
              apiKeys: updatedApiKeys,
            },
          };
        });
      },

      syncBackendConfig: async () => {
        try {
          const cfg = await platformAdapter.getConfig();
          if (!cfg) return;

          const llmMode = String(cfg.llm_mode || '');
          const llmBackend = String(cfg.llm_backend || '');
          const isLocal =
            llmMode.startsWith('local_') ||
            llmBackend === 'ollama' ||
            llmBackend === 'vllm' ||
            llmBackend === 'local';

          // Discover configured API keys from live backend system status
          const providerDefs: { keyPrefix: string; provider: DetectedProvider; name: string }[] = [
            { keyPrefix: 'custom', provider: 'custom', name: 'Universal / Custom API' },
            { keyPrefix: 'groq', provider: 'groq', name: 'Groq' },
            { keyPrefix: 'gemini', provider: 'gemini', name: 'Google Gemini' },
            { keyPrefix: 'openai', provider: 'openai', name: 'OpenAI' },
            { keyPrefix: 'anthropic', provider: 'anthropic', name: 'Anthropic' },
            { keyPrefix: 'nvidia', provider: 'nvidia', name: 'NVIDIA' },
            { keyPrefix: 'cohere', provider: 'cohere', name: 'Cohere' },
            { keyPrefix: 'mistral', provider: 'mistral', name: 'Mistral' },
            { keyPrefix: 'deepseek', provider: 'deepseek', name: 'DeepSeek' },
            { keyPrefix: 'openrouter', provider: 'openrouter', name: 'OpenRouter' },
          ];

          const backendApiKeys: CloudApiKeyEntry[] = [];
          for (const p of providerDefs) {
            if (cfg[`${p.keyPrefix}_configured`]) {
              const rawMasked = String(cfg[`${p.keyPrefix}_masked`] || '');
              backendApiKeys.push({
                id: `key-backend-${p.provider}`,
                key: rawMasked || '••••••••••••••••',
                provider: p.provider,
                providerName: p.name,
                verified: true,
                fromEnv: true,
                envVarName: `${p.keyPrefix.toUpperCase()}_API_KEY`,
              });
            }
          }

          const rawStorageMode = String(cfg.storage_mode || cfg.raise_storage_mode || '').toLowerCase();
          let defaultSubstrateMode: SubstrateMode = 'in_memory_fallback';
          if (rawStorageMode === 'docker') {
            defaultSubstrateMode = 'local';
          } else if (rawStorageMode === 'cloud') {
            defaultSubstrateMode = 'cloud';
          }

          const kgMode = (cfg.neo4j_mode as SubstrateMode) || defaultSubstrateMode;
          const memMode = (cfg.postgres_mode as SubstrateMode) || defaultSubstrateMode;
          const cacheMode = (cfg.redis_mode as SubstrateMode) || defaultSubstrateMode;

          set((s) => {
            // Merge: preserve any user-entered manual keys that are not from backend
            const mergedKeys = [...backendApiKeys];
            for (const existingKey of s.config.apiKeys || []) {
              if (
                existingKey.key &&
                !existingKey.fromEnv &&
                !mergedKeys.some((k) => k.provider === existingKey.provider)
              ) {
                mergedKeys.push(existingKey);
              }
            }

            if (mergedKeys.length === 0) {
              mergedKeys.push({
                id: `key-${Date.now()}`,
                key: '',
                provider: 'unknown',
                providerName: 'Unconfigured Key',
                verified: null,
              });
            }

            return {
              config: {
                ...s.config,
                firstRunCompleted: Boolean(cfg.first_run_completed ?? s.config.firstRunCompleted),
                llmDeployment: isLocal ? 'local' : 'cloud',
                llmMode: (llmMode || s.config.llmMode) as any,
                embeddingModel:
                  (cfg.embedding_model as string) || s.config.embeddingModel || 'google/embeddinggemma-2',
                rerankerModel:
                  (cfg.reranker_model as string) || s.config.rerankerModel || 'BAAI/bge-reranker-v2-m3',
                nliVerifierModel:
                  (cfg.nli_verifier_model as string) ||
                  (cfg.nli_model as string) ||
                  s.config.nliVerifierModel ||
                  'dleemiller/finecat-nli-ultra-l',
                neuralDevice:
                  (cfg.neural_device as any) ||
                  (cfg.embedding_device as any) ||
                  s.config.neuralDevice ||
                  'auto',
                huggingfaceConfigured: Boolean(cfg.huggingface_configured),
                huggingfaceMasked: String(cfg.huggingface_masked || ''),
                huggingfaceToken:
                  s.config.huggingfaceToken ||
                  (cfg.huggingface_configured ? String(cfg.huggingface_masked || '') : ''),
                apiKeys: mergedKeys,
                knowledgeGraph: {
                  ...s.config.knowledgeGraph,
                  mode: kgMode,
                  uri: (cfg.neo4j_uri as string) || s.config.knowledgeGraph?.uri || '',
                  database: (cfg.neo4j_database as string) || 'neo4j',
                  online: true,
                },
                sessionMemory: {
                  ...s.config.sessionMemory,
                  mode: memMode,
                  online: true,
                },
                cacheAndSignals: {
                  ...s.config.cacheAndSignals,
                  mode: cacheMode,
                  online: true,
                },
                neo4jMode: kgMode,
                postgresMode: memMode,
                redisMode: cacheMode,
              },
            };
          });
        } catch (err) {
          console.warn('Failed to sync backend configuration into Control Center:', err);
        }
      },

      setAllSubstratesMode: (mode) => {
        const envData = detectEnvCredentials();
        set((s) => {
          const kg: SubstrateConfig = {
            ...s.config.knowledgeGraph,
            mode,
            uri:
              mode === 'cloud' && envData.neo4j.present
                ? envData.neo4j.uri
                : mode === 'local'
                ? 'bolt://localhost:7687'
                : s.config.knowledgeGraph?.uri || '',
            user:
              mode === 'cloud' && envData.neo4j.present
                ? envData.neo4j.user
                : mode === 'local'
                ? 'neo4j'
                : s.config.knowledgeGraph?.user || 'neo4j',
            password:
              mode === 'cloud' && envData.neo4j.present
                ? envData.neo4j.password
                : mode === 'local'
                ? 'raise_password'
                : s.config.knowledgeGraph?.password || '',
          };
          const mem: SubstrateConfig = {
            ...s.config.sessionMemory,
            mode,
            uri:
              mode === 'cloud' && envData.postgres.present
                ? envData.postgres.uri
                : mode === 'local'
                ? 'postgresql://raise_user:raise_password@localhost:5432/raise_db'
                : s.config.sessionMemory?.uri || '',
            user:
              mode === 'cloud' && envData.postgres.present
                ? envData.postgres.user
                : mode === 'local'
                ? 'raise_user'
                : s.config.sessionMemory?.user || '',
            password:
              mode === 'cloud' && envData.postgres.present
                ? envData.postgres.password
                : mode === 'local'
                ? 'raise_password'
                : s.config.sessionMemory?.password || '',
          };
          const cache: SubstrateConfig = {
            ...s.config.cacheAndSignals,
            mode,
            uri:
              mode === 'cloud' && envData.redis.present
                ? envData.redis.uri
                : mode === 'local'
                ? 'redis://localhost:6379/0'
                : s.config.cacheAndSignals?.uri || '',
          };
          return {
            config: {
              ...s.config,
              knowledgeGraph: kg,
              sessionMemory: mem,
              cacheAndSignals: cache,
              neo4jMode: mode,
              postgresMode: mode,
              redisMode: mode,
            },
          };
        });
      },
    }),
    {
      name: 'raise-control-center-storage',
      partialize: (state) => ({ config: state.config }),
      merge: (persistedState: any, currentState: ControlCenterState) => {
        const mergedConfig = {
          ...currentState.config,
          ...(persistedState?.config || {}),
        };
        // Clean out stale hardcoded temporary tunnel urls
        if (
          mergedConfig.tunnelUrl &&
          mergedConfig.tunnelUrl.includes('estimates-racial-aud-strap')
        ) {
          mergedConfig.tunnelUrl = '';
        }
        // Normalize platform away from 'web' or mobile, or old hardcoded 'windows' on Mac
        if (
          !mergedConfig.targetPlatform ||
          mergedConfig.targetPlatform === 'web' ||
          mergedConfig.targetPlatform === 'ios' ||
          mergedConfig.targetPlatform === 'android' ||
          (defaultPlatform === 'macos' && mergedConfig.targetPlatform === 'windows')
        ) {
          mergedConfig.targetPlatform = defaultPlatform;
        }
        if (!mergedConfig.embeddingModel || mergedConfig.embeddingModel === 'BAAI/bge-large-en-v1.5') {
          mergedConfig.embeddingModel = 'google/embeddinggemma-2';
        }
        if (!mergedConfig.rerankerModel || mergedConfig.rerankerModel === 'BAAI/bge-reranker-large' || mergedConfig.rerankerModel === 'jinaai/jina-reranker-v3.5') {
          mergedConfig.rerankerModel = 'BAAI/bge-reranker-v2-m3';
        }
        if (
          !mergedConfig.nliVerifierModel ||
          mergedConfig.nliVerifierModel === 'FineCat-NLI-DeBERTa' ||
          mergedConfig.nliVerifierModel === 'dleemiller/finecat-nli-l'
        ) {
          mergedConfig.nliVerifierModel = 'dleemiller/finecat-nli-ultra-l';
        }
        if (!mergedConfig.neuralDevice) mergedConfig.neuralDevice = 'auto';
        if (!Array.isArray(mergedConfig.apiKeys) || mergedConfig.apiKeys.length === 0) {
          mergedConfig.apiKeys = [
            {
              id: 'key-1',
              key: mergedConfig.groqApiKey || '',
              provider: mergedConfig.groqApiKey ? 'groq' : 'unknown',
              providerName: mergedConfig.groqApiKey ? 'Groq' : 'Unconfigured Key',
              verified: null,
            },
          ];
        }
        return {
          ...currentState,
          config: mergedConfig,
        };
      },
    }
  )
);
