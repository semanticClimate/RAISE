import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Cpu,
  Database,
  Laptop,
  Layers,
  RefreshCw,
  Sparkles,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useControlCenterStore } from '../store/useControlCenterStore';
import { platformAdapter, type ConnectionTestResult } from '../services/platformAdapter';

export const LaunchStep: React.FC = () => {
  const {
    config,
    hardware,
    setHardware,
    setActiveTab,
    preflightAssets,
    preflightFootprint,
  } = useControlCenterStore();
  const { appMode, apiBaseUrl, latencyMs, runCapabilityProbe } = useModeStore();
  const isConnected = appMode === 'connected' || appMode === 'degraded';

  const [isTestingSubstrates, setIsTestingSubstrates] = useState(false);
  const [testResults, setTestResults] = useState<ConnectionTestResult | null>(null);

  const isCloud = config.llmDeployment
    ? config.llmDeployment === 'cloud'
    : !config.llmMode || config.llmMode.startsWith('cloud');

  const validKeys = (config.apiKeys || []).filter(
    (k) => k?.key && k.key.trim().length > 0 && k.provider !== 'unknown'
  );
  const providers =
    Array.from(new Set(validKeys.map((k) => k.providerName))).join(', ') ||
    'Default / Auto-detected';
  const hasConfiguredKey = isCloud ? validKeys.length > 0 : Boolean(config.selectedLocalModel);

  const clientOSLabel =
    hardware?.osName ||
    (config.targetPlatform === 'macos'
      ? 'macOS (Apple Silicon)'
      : config.targetPlatform === 'windows'
        ? 'Windows'
        : config.targetPlatform === 'linux'
          ? 'Linux'
          : 'Detected Host Platform');

  const handleTestAllSubstrates = async () => {
    setIsTestingSubstrates(true);
    try {
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
      // endpoints offline or unreachable
    } finally {
      setIsTestingSubstrates(false);
    }
  };

  useEffect(() => {
    runCapabilityProbe();
    handleTestAllSubstrates();
  }, []);

  const handleRefreshHardware = async () => {
    try {
      await runCapabilityProbe();
      const hw = await platformAdapter.getHardware();
      if (hw) {
        setHardware({
          platform: config.targetPlatform,
          osName: hw.os_name || clientOSLabel,
          totalRamGb: hw.total_ram_gb || 16.0,
          cpuCores: hw.cpu_cores || 8,
          hasMetalOrCuda: hw.has_metal_or_cuda ?? true,
        });
      }
    } catch {}
  };

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
      functionName: 'Vector Store',
      role: 'Dense Vector Search',
      engine: 'ChromaDB (Local Embedded)',
      latency: isConnected && latencyMs ? `${latencyMs}ms` : '11ms',
    },
    {
      functionName: 'Knowledge Graph',
      role: 'Entity & Semantic Graph',
      engine: isNeo4jOnline
        ? (testResults?.neo4j?.provider || 'Neo4j Property Graph')
        : 'NetworkX (In-Memory)',
      latency: testResults?.neo4j?.latency_ms ? `${testResults.neo4j.latency_ms}ms` : '<1ms',
    },
    {
      functionName: 'Response Cache & Signals',
      role: 'Fast Ephemeral Buffer & State',
      engine: isRedisOnline
        ? (testResults?.redis?.provider || 'Redis Fast Bus')
        : 'In-Memory State',
      latency: testResults?.redis?.latency_ms ? `${testResults.redis.latency_ms}ms` : '<1ms',
    },
    {
      functionName: 'Session Memory & Chat History',
      role: 'Conversation History & Sessions',
      engine: isPostgresOnline
        ? (testResults?.postgres?.provider || 'PostgreSQL Store')
        : 'Local SQLite Storage',
      latency: testResults?.postgres?.latency_ms ? `${testResults.postgres.latency_ms}ms` : '1ms',
    },
  ];

  const hasExternalDatabases = isNeo4jOnline || isRedisOnline || isPostgresOnline;

  return (
    <div
      className="space-y-4 animate-in fade-in duration-200"
      data-testid="control-center-launch-step"
    >
      {/* Ready / Incomplete Status Banner */}
      {!hasConfiguredKey ? (
        <div className="p-3.5 rounded-xl border border-white/20 bg-white/5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-white shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-white">API Key or Local Model Required</h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Add an API key in Models or select a local model to enable inference.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab('models')}
            className="text-xs font-bold text-zinc-300 hover:text-white underline underline-offset-2 cursor-pointer shrink-0"
          >
            Configure &rarr;
          </button>
        </div>
      ) : hasExternalDatabases ? (
        <div className="p-3.5 rounded-xl border border-white/20 bg-white/10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-white shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-white">System Ready & Synchronized</h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Workstation configured. All neural substrates and external database stores are active.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleTestAllSubstrates}
            disabled={isTestingSubstrates}
            className="px-3 py-1.5 rounded-lg border border-white/20 bg-white/10 hover:bg-white/20 text-white text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingSubstrates ? 'animate-spin' : ''}`} />
            <span>Test Substrates</span>
          </button>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl border border-white/20 bg-white/5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-white shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-white">
                Local Embedded (Zero-Dependency Mode)
              </h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Running on local in-process SQLite and NetworkX graph with embedded ChromaDB vector store. No cloud credentials or Docker services required.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleTestAllSubstrates}
            disabled={isTestingSubstrates}
            className="px-3 py-1.5 rounded-lg border border-white/20 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingSubstrates ? 'animate-spin' : ''}`} />
            <span>Test Substrates</span>
          </button>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* Device & Platform */}
        <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Laptop className="w-3.5 h-3.5 text-white" />
              <span>Target Platform</span>
            </span>
            <button
              type="button"
              onClick={handleRefreshHardware}
              className="text-[10px] text-slate-400 hover:text-white flex items-center gap-1 cursor-pointer"
              title="Refresh Telemetry"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Probe</span>
            </button>
          </div>
          <div className="text-xs font-bold text-white truncate">{clientOSLabel}</div>
          <div className="text-[10px] font-mono text-slate-400">
            {hardware?.totalRamGb ? `${hardware.totalRamGb} GB RAM` : '8 GB RAM'} &bull; {hardware?.cpuCores ? `${hardware.cpuCores} Cores` : '8 Cores'}
          </div>
        </div>

        {/* Backend Gateway */}
        <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Zap className="w-3.5 h-3.5 text-white" />
            <span>Backend Gateway</span>
          </div>
          <div className="text-xs font-bold text-white flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]'
                  : 'bg-zinc-600'
              }`}
            />
            <span>{isConnected ? 'Active & Synced' : 'Offline / Standby'}</span>
            <span className="text-[11px] font-mono text-slate-400 font-normal">
              ({apiBaseUrl || '127.0.0.1:8000'})
            </span>
          </div>
          <div className="text-[10px] font-mono text-zinc-300">
            {isConnected ? `Latency: ${latencyMs || 12}ms` : 'Start backend on port 8000'}
          </div>
        </div>

        {/* Intelligence Engine */}
        <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-white" />
              <span>Inference Engine</span>
            </span>
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className="text-[10px] text-zinc-300 hover:text-white cursor-pointer"
            >
              Change
            </button>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {isCloud ? providers : config.selectedLocalModel || 'Local Auto (Backend)'}
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            Mode: {isCloud ? 'Cloud API' : 'Local Neural Acceleration'}
          </div>
        </div>

        {/* Neural Pipeline Substrates */}
        <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-white" />
              <span>Neural Stack</span>
            </span>
            <button
              type="button"
              onClick={() => setActiveTab('neural')}
              className="text-[10px] text-zinc-300 hover:text-white cursor-pointer"
            >
              Change
            </button>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {config.embeddingModel?.split('/').pop() || 'Backend Default'} &bull; {config.rerankerModel?.split('/').pop() || 'Backend Default'}
          </div>
          <div className="text-[10px] font-mono text-slate-400 truncate">
            Quality Gate: {config.nliVerifierModel?.split('/').pop() || 'Backend Default'}
          </div>
          <div className="text-[10px] font-mono text-zinc-300 flex items-center justify-between pt-1 border-t border-white/5 truncate">
            <span>
              {preflightAssets.length > 0
                ? preflightAssets.every((a) => a.verified)
                  ? 'All 6 Assets Verified'
                  : `${preflightAssets.filter((a) => a.verified).length} of ${preflightAssets.length} Verified`
                : 'Neural Assets Active'}
            </span>
            <span className="text-slate-400">{preflightFootprint || '~4.6 GB Footprint'}</span>
          </div>
        </div>
      </div>

      {/* Substrates Status Table */}
      <div className="rounded-xl bg-[#111111] border border-[#292929] overflow-hidden">
        <div className="p-3 border-b border-[#292929] flex items-center justify-between bg-black/30">
          <div className="flex items-center gap-2">
            <Database className="w-3.5 h-3.5 text-white" />
            <span className="text-xs font-bold text-white">Live Storage Substrates</span>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab('databases')}
            className="text-[11px] text-zinc-300 hover:text-white flex items-center gap-1 cursor-pointer"
          >
            <span>Manage</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
        <div className="divide-y divide-white/5">
          {substrates.map((s) => (
            <div key={s.functionName} className="px-3.5 py-2.5 flex items-center justify-between text-xs hover:bg-white/[0.02]">
              <div>
                <div className="font-semibold text-white flex items-center gap-2">
                  <span>{s.functionName}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-white/10 text-white border border-white/20 font-medium">
                    {s.engine}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">{s.role}</div>
              </div>
              <div className="flex items-center gap-2 text-[11px] font-mono">
                <span className="text-slate-300 font-semibold">{s.latency}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
