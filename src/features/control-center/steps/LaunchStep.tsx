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
  const { config, hardware, setHardware, setActiveTab } = useControlCenterStore();
  const { appMode, apiBaseUrl, latencyMs, runCapabilityProbe } = useModeStore();
  const isConnected = appMode === 'connected';

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
          : 'macOS (Desktop)');

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

  const getSubstrateDisplayMode = (rawMode?: string): string => {
    if (!rawMode || rawMode === 'in_memory_fallback') {
      return 'Local Embedded (Zero-Dependency)';
    }
    if (rawMode === 'local') return 'Local Daemon';
    if (rawMode === 'cloud') return 'Cloud Endpoint';
    return rawMode;
  };

  const substrates = [
    {
      name: 'ChromaDB Vector Store',
      role: 'Dense Embeddings',
      mode: 'Local Embedded',
      status: isConnected ? 'Online' : 'Standby',
      online: isConnected,
      latency: isConnected ? `${latencyMs || 8}ms` : undefined,
    },
    {
      name: 'Neo4j Graph Database',
      role: 'Knowledge Graph',
      mode: getSubstrateDisplayMode(config.knowledgeGraph?.mode || config.neo4jMode),
      status: testResults?.neo4j?.online
        ? 'Online'
        : testResults
          ? 'Offline'
          : (!config.knowledgeGraph?.mode || config.knowledgeGraph?.mode === 'in_memory_fallback'
            ? 'Local Embedded (Zero-Dependency)'
            : 'Configured'),
      online: testResults?.neo4j?.online ?? (!config.knowledgeGraph?.mode || config.knowledgeGraph?.mode === 'in_memory_fallback'),
      latency: testResults?.neo4j?.latency_ms ? `${testResults.neo4j.latency_ms}ms` : undefined,
    },
    {
      name: 'Redis Fast Bus',
      role: 'Response Cache & Signals',
      mode: getSubstrateDisplayMode(config.cacheAndSignals?.mode || config.redisMode),
      status: testResults?.redis?.online
        ? 'Online'
        : testResults
          ? 'Offline'
          : (!config.cacheAndSignals?.mode || config.cacheAndSignals?.mode === 'in_memory_fallback'
            ? 'Local Embedded (Zero-Dependency)'
            : 'Configured'),
      online: testResults?.redis?.online ?? (!config.cacheAndSignals?.mode || config.cacheAndSignals?.mode === 'in_memory_fallback'),
      latency: testResults?.redis?.latency_ms ? `${testResults.redis.latency_ms}ms` : undefined,
    },
    {
      name: 'PostgreSQL Store',
      role: 'Session Memory & Chat History',
      mode: getSubstrateDisplayMode(config.sessionMemory?.mode || config.postgresMode),
      status: testResults?.postgres?.online
        ? 'Online'
        : testResults
          ? 'Offline'
          : (!config.sessionMemory?.mode || config.sessionMemory?.mode === 'in_memory_fallback'
            ? 'Local Embedded (Zero-Dependency)'
            : 'Configured'),
      online: testResults?.postgres?.online ?? (!config.sessionMemory?.mode || config.sessionMemory?.mode === 'in_memory_fallback'),
    },
  ];

  const offlineSubstrates = substrates.filter((s) => !s.online);
  const isAllSubstratesOnline = offlineSubstrates.length === 0;

  return (
    <div
      className="space-y-4 animate-in fade-in duration-200"
      data-testid="control-center-launch-step"
    >
      {/* Ready / Incomplete Status Banner */}
      {!hasConfiguredKey ? (
        <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
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
            className="text-xs font-bold text-amber-300 hover:text-white underline underline-offset-2 cursor-pointer shrink-0"
          >
            Configure &rarr;
          </button>
        </div>
      ) : isAllSubstratesOnline ? (
        <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
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
            className="px-3 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingSubstrates ? 'animate-spin' : ''}`} />
            <span>Test Substrates</span>
          </button>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl border border-sky-500/30 bg-sky-500/10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-sky-400 shrink-0" />
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
            className="px-3 py-1.5 rounded-lg border border-sky-500/30 bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingSubstrates ? 'animate-spin' : ''}`} />
            <span>Test Substrates</span>
          </button>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {/* Device & Platform */}
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Laptop className="w-3.5 h-3.5 text-indigo-400" />
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
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            <span>Backend Gateway</span>
          </div>
          <div className="text-xs font-bold text-white flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-emerald-400 ring-2 ring-emerald-400/20'
                  : 'bg-amber-400 animate-pulse'
              }`}
            />
            <span>{isConnected ? 'Active & Synced' : 'Offline / Standby'}</span>
            <span className="text-[11px] font-mono text-slate-400 font-normal">
              ({apiBaseUrl || '127.0.0.1:8000'})
            </span>
          </div>
          <div className="text-[10px] font-mono text-emerald-400">
            {isConnected ? `Latency: ${latencyMs || 12}ms` : 'Start backend on port 8000'}
          </div>
        </div>

        {/* Intelligence Engine */}
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              <span>Inference Engine</span>
            </span>
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className="text-[10px] text-indigo-400 hover:text-indigo-300 cursor-pointer"
            >
              Change
            </button>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {isCloud ? providers : config.selectedLocalModel || 'Local Ollama'}
          </div>
          <div className="text-[10px] font-mono text-slate-400">
            Mode: {isCloud ? 'Cloud API' : 'Local Neural Acceleration'}
          </div>
        </div>

        {/* Neural Pipeline Substrates */}
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              <span>Neural Stack</span>
            </span>
            <button
              type="button"
              onClick={() => setActiveTab('neural')}
              className="text-[10px] text-indigo-400 hover:text-indigo-300 cursor-pointer"
            >
              Change
            </button>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {config.embeddingModel?.split('/').pop() || 'Embedding Gemma 2'} &bull; {config.rerankerModel?.split('/').pop() || 'Jina Reranker v3.5'}
          </div>
          <div className="text-[10px] font-mono text-slate-400 truncate">
            Quality Gate: {config.nliVerifierModel?.split('/').pop() || 'FineCat NLI Ultra-L'}
          </div>
        </div>
      </div>

      {/* Substrates Status Table */}
      <div className="rounded-xl bg-[#131622] border border-white/10 overflow-hidden">
        <div className="p-3 border-b border-white/10 flex items-center justify-between bg-black/30">
          <div className="flex items-center gap-2">
            <Database className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-xs font-bold text-white">Live Storage Substrates</span>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab('databases')}
            className="text-[11px] text-indigo-300 hover:text-white flex items-center gap-1 cursor-pointer"
          >
            <span>Manage</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
        <div className="divide-y divide-white/5">
          {substrates.map((s) => (
            <div key={s.name} className="px-3.5 py-2.5 flex items-center justify-between text-xs hover:bg-white/[0.02]">
              <div>
                <div className="font-semibold text-white flex items-center gap-2">
                  <span>{s.name}</span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-white/5 text-slate-400">
                    {s.mode}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400">{s.role}</div>
              </div>
              <div className="flex items-center gap-2 text-[11px] font-mono">
                {s.latency && <span className="text-slate-400">{s.latency}</span>}
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                    s.online
                      ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                      : 'bg-slate-500/15 text-slate-400 border border-white/10'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${s.online ? 'bg-emerald-400' : 'bg-slate-400'}`} />
                  <span>{s.status}</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
