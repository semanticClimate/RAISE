import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Database,
  Laptop,
  RefreshCw,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { platformAdapter, type ConnectionTestResult } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';

export const OverviewStep: React.FC = () => {
  const {
    config,
    hardware,
    setActiveTab,
    setAllSubstratesMode,
    preflightAssets,
    preflightFootprint,
    syncBackendConfig,
  } = useControlCenterStore();

  const { appMode, latencyMs, runCapabilityProbe } = useModeStore();
  const isConnected = appMode === 'connected' || appMode === 'degraded';

  const [testResults, setTestResults] = useState<ConnectionTestResult | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [showDiagnostics, setShowDiagnostics] = useState(false);

  // Synchronize telemetry and probe substrates on mount
  useEffect(() => {
    let mounted = true;
    const probe = async () => {
      try {
        await runCapabilityProbe();
        await syncBackendConfig();
        const results = await platformAdapter.testConnections({
          neo4j_mode: config.knowledgeGraph?.mode || config.neo4jMode,
          neo4j_uri: config.knowledgeGraph?.uri || config.neo4jUri,
          neo4j_user: config.knowledgeGraph?.user,
          neo4j_password: config.knowledgeGraph?.password || config.neo4jPassword,
          postgres_mode: config.sessionMemory?.mode || config.postgresMode,
          postgres_uri: config.sessionMemory?.uri,
          redis_mode: config.cacheAndSignals?.mode || config.redisMode,
          redis_uri: config.cacheAndSignals?.uri,
        });
        if (mounted) {
          setTestResults(results);
        }
      } catch {
        // Fallback to local embedded states
      }
    };
    probe();
    return () => {
      mounted = false;
    };
  }, []);

  const handleRetest = async () => {
    setIsTesting(true);
    try {
      await runCapabilityProbe();
      const results = await platformAdapter.testConnections({
        neo4j_mode: config.knowledgeGraph?.mode || config.neo4jMode,
        neo4j_uri: config.knowledgeGraph?.uri || config.neo4jUri,
        neo4j_user: config.knowledgeGraph?.user,
        neo4j_password: config.knowledgeGraph?.password || config.neo4jPassword,
        postgres_mode: config.sessionMemory?.mode || config.postgresMode,
        postgres_uri: config.sessionMemory?.uri,
        redis_mode: config.cacheAndSignals?.mode || config.redisMode,
        redis_uri: config.cacheAndSignals?.uri,
      });
      setTestResults(results);
    } catch {
      // offline
    } finally {
      setIsTesting(false);
    }
  };

  // Inference Provider dynamic discovery
  const validKeys = (config.apiKeys || []).filter(
    (k) => k?.key && k.key.trim().length > 0 && k.provider !== 'unknown'
  );
  const isCloud = config.llmDeployment !== 'local';
  const primaryProviderName =
    (validKeys[0]?.providerName) ||
    (config.selectedLocalModel ? `Ollama (${config.selectedLocalModel})` : 'Google Gemini');
  const activeModelName =
    (config.selectedLocalModel) ||
    'gemini-2.5-flash';

  // Storage Profile determination
  const currentStorageMode =
    config.storageMode ||
    (config.knowledgeGraph?.mode === 'cloud'
      ? 'cloud'
      : config.knowledgeGraph?.mode === 'local'
      ? 'docker'
      : 'fast');

  const clientOSLabel =
    hardware?.osName ||
    (config.targetPlatform === 'macos'
      ? 'macOS (Apple Silicon)'
      : config.targetPlatform === 'windows'
      ? 'Windows'
      : 'Linux');

  const acceleratorLabel =
    config.targetPlatform === 'macos'
      ? 'Apple Metal (MPS)'
      : hardware?.hasMetalOrCuda
      ? 'CUDA / ROCm'
      : 'CPU Optimized';

  // Substrates list
  const isNeo4jOnline = Boolean(
    testResults?.neo4j?.online &&
      testResults?.neo4j?.provider &&
      !testResults?.neo4j?.provider?.toLowerCase().includes('in-memory')
  );
  const isRedisOnline = Boolean(
    testResults?.redis?.online &&
      testResults?.redis?.provider &&
      !testResults?.redis?.provider?.toLowerCase().includes('in-memory')
  );
  const isPostgresOnline = Boolean(
    testResults?.postgres?.online &&
      testResults?.postgres?.provider &&
      !testResults?.postgres?.provider?.toLowerCase().includes('in-memory')
  );

  const substrates = [
    {
      id: 'vector',
      name: 'Vector Store',
      role: 'ChromaDB (Local Embedded)',
      spec: 'Dense vector embeddings & HNSW semantic search',
      latency: isConnected && latencyMs ? `${latencyMs}ms` : '12ms',
      status: 'Ready',
      isHealthy: true,
      mode: 'Embedded',
    },
    {
      id: 'graph',
      name: 'Knowledge Graph',
      role: isNeo4jOnline
        ? (testResults?.neo4j?.provider || 'Neo4j Property Graph')
        : 'NetworkX In-Memory',
      spec: 'Entity relation graphs & multi-hop citations',
      latency: testResults?.neo4j?.latency_ms ? `${testResults.neo4j.latency_ms}ms` : '<1ms',
      status: isNeo4jOnline ? 'Online' : 'In-Memory',
      isHealthy: true,
      mode: isNeo4jOnline ? 'Docker/Cloud' : 'In-Memory',
    },
    {
      id: 'memory',
      name: 'Session Memory',
      role: isPostgresOnline
        ? (testResults?.postgres?.provider || 'PostgreSQL Store')
        : 'Local SQLite Storage',
      spec: 'Cross-session conversation turns & persistent chat',
      latency: testResults?.postgres?.latency_ms ? `${testResults.postgres.latency_ms}ms` : '1ms',
      status: isPostgresOnline ? 'Online' : 'Local SQLite',
      isHealthy: true,
      mode: isPostgresOnline ? 'Docker/Cloud' : 'Local File',
    },
    {
      id: 'cache',
      name: 'Response Cache',
      role: isRedisOnline
        ? (testResults?.redis?.provider || 'Redis Fast Bus')
        : 'In-Memory State & Signals',
      spec: 'Sub-millisecond query cache & stream signals',
      latency: testResults?.redis?.latency_ms ? `${testResults.redis.latency_ms}ms` : '<1ms',
      status: isRedisOnline ? 'Online' : 'In-Memory',
      isHealthy: true,
      mode: isRedisOnline ? 'Docker/Cloud' : 'In-Memory',
    },
  ];

  return (
    <div className="space-y-5 animate-in fade-in duration-150 text-[#FFFFFF]">
      {/* 2-Column Overview Grid (Answers 5 questions under 5 seconds) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {/* Card 1: Infrastructure & Backend Gateway */}
        <div className="p-4 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between hover:border-[#FFFFFF]/20 transition-colors">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-sm font-medium text-[#A3A3A3] block">Infrastructure</span>
              <span className="text-base sm:text-lg font-semibold text-[#FFFFFF] mt-0.5 block">
                Backend Gateway
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#171717] border border-[#292929] text-xs font-mono">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isConnected ? 'bg-[#FFFFFF]' : 'border border-[#FFFFFF]/40'
                }`}
              />
              <span className="text-[#FFFFFF]">
                {isConnected ? 'Port 8000' : 'Offline'}
              </span>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[#292929]/60 flex items-center justify-between text-xs text-[#A3A3A3]">
            <div className="flex items-center gap-2">
              <Laptop className="w-3.5 h-3.5 text-[#FFFFFF]" />
              <span className="text-[#FFFFFF]">{clientOSLabel}</span>
              <span>•</span>
              <span>{acceleratorLabel}</span>
            </div>
            {isConnected && latencyMs ? (
              <span className="font-mono text-[#FFFFFF]">{latencyMs}ms</span>
            ) : null}
          </div>
        </div>

        {/* Card 2: Inference Engine */}
        <div className="p-4 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between hover:border-[#FFFFFF]/20 transition-colors">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-sm font-medium text-[#A3A3A3] block">Inference Engine</span>
              <span className="text-base sm:text-lg font-semibold text-[#FFFFFF] mt-0.5 block truncate max-w-[200px] sm:max-w-[240px]">
                {primaryProviderName}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className="text-xs font-medium text-[#FFFFFF] hover:text-[#FFFFFF] px-2.5 py-1 rounded-md bg-[#171717] border border-[#292929] hover:bg-[#292929] transition-all flex items-center gap-1 cursor-pointer shrink-0"
              title="Configure inference providers and keys"
            >
              <span>Configure</span>
              <ArrowRight className="w-3 h-3 text-[#FFFFFF]" />
            </button>
          </div>

          <div className="mt-4 pt-3 border-t border-[#292929]/60 flex items-center justify-between text-xs text-[#A3A3A3]">
            <div className="flex items-center gap-1.5 font-mono text-[#FFFFFF]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF]" />
              <span>{activeModelName}</span>
            </div>
            <span>{isCloud ? `${validKeys.length} key active` : 'Local weights'}</span>
          </div>
        </div>

        {/* Card 3: Neural Pipeline */}
        <div className="p-4 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between hover:border-[#FFFFFF]/20 transition-colors">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-sm font-medium text-[#A3A3A3] block">Neural Pipeline</span>
              <span className="text-base sm:text-lg font-semibold text-[#FFFFFF] mt-0.5 block truncate max-w-[220px]">
                {config.embeddingModel || 'google/embeddinggemma-2'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowDiagnostics((prev) => !prev)}
              className="text-xs font-medium text-[#FFFFFF] px-2.5 py-1 rounded-md bg-[#171717] border border-[#292929] hover:bg-[#292929] transition-all flex items-center gap-1 cursor-pointer shrink-0"
              title="Toggle neural diagnostics"
            >
              <span>{showDiagnostics ? 'Hide' : 'Diagnostics'}</span>
              {showDiagnostics ? (
                <ChevronUp className="w-3 h-3 text-[#FFFFFF]" />
              ) : (
                <ChevronDown className="w-3 h-3 text-[#FFFFFF]" />
              )}
            </button>
          </div>

          <div className="mt-4 pt-3 border-t border-[#292929]/60 flex items-center justify-between text-xs text-[#A3A3A3]">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF]" />
              <span className="text-[#FFFFFF]">Reranker & NLI Ready</span>
            </div>
            <span className="font-mono text-[#A3A3A3]">{preflightFootprint || '119.2 MB'}</span>
          </div>
        </div>

        {/* Card 4: Runtime Storage Profile */}
        <div className="p-4 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between hover:border-[#FFFFFF]/20 transition-colors">
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-sm font-medium text-[#A3A3A3] block">Storage Profile</span>
              <span className="text-base sm:text-lg font-semibold text-[#FFFFFF] mt-0.5 block capitalize">
                {currentStorageMode === 'docker'
                  ? 'Docker Local (Stack)'
                  : currentStorageMode === 'cloud'
                  ? 'Cloud Managed'
                  : 'Fast Local (Embedded)'}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('databases')}
              className="text-xs font-medium text-[#FFFFFF] hover:text-[#FFFFFF] px-2.5 py-1 rounded-md bg-[#171717] border border-[#292929] hover:bg-[#292929] transition-all flex items-center gap-1 cursor-pointer shrink-0"
              title="Configure storage substrates"
            >
              <span>Details</span>
              <ArrowRight className="w-3 h-3 text-[#FFFFFF]" />
            </button>
          </div>

          {/* Quick Segmented Mode Buttons */}
          <div className="mt-3 pt-3 border-t border-[#292929]/60 grid grid-cols-3 gap-1.5">
            <button
              type="button"
              onClick={() => setAllSubstratesMode('in_memory_fallback')}
              className={`py-1 px-2 rounded-md text-xs font-medium transition-all text-center cursor-pointer ${
                currentStorageMode === 'fast'
                  ? 'bg-[#FFFFFF] text-[#000000] font-semibold'
                  : 'bg-[#171717] text-[#A3A3A3] hover:text-[#FFFFFF] border border-transparent'
              }`}
              title="Fast Local: Zero-dependency in-memory execution"
            >
              Fast
            </button>
            <button
              type="button"
              onClick={() => setAllSubstratesMode('local')}
              className={`py-1 px-2 rounded-md text-xs font-medium transition-all text-center cursor-pointer ${
                currentStorageMode === 'docker'
                  ? 'bg-[#FFFFFF] text-[#000000] font-semibold'
                  : 'bg-[#171717] text-[#A3A3A3] hover:text-[#FFFFFF] border border-transparent'
              }`}
              title="Docker Local: Local containerized daemons"
            >
              Docker
            </button>
            <button
              type="button"
              onClick={() => setAllSubstratesMode('cloud')}
              className={`py-1 px-2 rounded-md text-xs font-medium transition-all text-center cursor-pointer ${
                currentStorageMode === 'cloud'
                  ? 'bg-[#FFFFFF] text-[#000000] font-semibold'
                  : 'bg-[#171717] text-[#A3A3A3] hover:text-[#FFFFFF] border border-transparent'
              }`}
              title="Cloud Managed: Remote endpoints"
            >
              Cloud
            </button>
          </div>
        </div>
      </div>

      {/* Diagnostics Drawer (Progressive Disclosure) */}
      {showDiagnostics && (
        <div className="p-4 rounded-xl bg-[#111111] border border-[#292929] space-y-3 animate-in fade-in-50 duration-150">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-[#FFFFFF]">Neural Preflight Assets</span>
            <span className="text-xs text-[#A3A3A3] font-mono">{preflightFootprint}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {preflightAssets.length > 0 ? (
              preflightAssets.map((asset) => (
                <div
                  key={asset.id || asset.name}
                  className="p-2.5 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-between text-xs"
                >
                  <div className="min-w-0 pr-2">
                    <div className="font-medium text-[#FFFFFF] truncate">{asset.name}</div>
                    <div className="text-[11px] text-[#A3A3A3] truncate">{asset.desc || asset.size}</div>
                  </div>
                  <span className="text-[10px] font-mono text-[#FFFFFF] shrink-0 px-2 py-0.5 rounded bg-[#292929]">
                    {asset.verified ? 'Verified' : 'Built-in'}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-[#A3A3A3] col-span-2 py-2">
                All preflight assets loaded and operational.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Full-Width Substrate List */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-medium text-[#FFFFFF]">Storage Systems</h3>
          <button
            type="button"
            onClick={handleRetest}
            disabled={isTesting}
            className="text-xs text-[#A3A3A3] hover:text-[#FFFFFF] flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
            title="Probe substrate latency"
          >
            <RefreshCw className={`w-3 h-3 text-[#FFFFFF] ${isTesting ? 'animate-spin' : ''}`} />
            <span>Retest</span>
          </button>
        </div>

        <div className="rounded-xl bg-[#111111] border border-[#292929] divide-y divide-[#292929]/60 overflow-hidden">
          {substrates.map((sub) => (
            <div
              key={sub.id}
              className="p-3.5 flex items-center justify-between gap-3 hover:bg-[#171717]/50 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center shrink-0">
                  <Database className="w-4 h-4 text-[#FFFFFF]" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[#FFFFFF] truncate">
                      {sub.name}
                    </span>
                    <span className="text-xs text-[#A3A3A3] font-mono hidden sm:inline">
                      • {sub.role}
                    </span>
                  </div>
                  <p className="text-xs text-[#A3A3A3] truncate mt-0.5">
                    {sub.spec}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <div className="text-right">
                  <div className="flex items-center gap-1.5 justify-end">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF]" />
                    <span className="text-xs font-medium text-[#FFFFFF]">
                      {sub.status}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-[#A3A3A3] block mt-0.5">
                    {sub.latency}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
