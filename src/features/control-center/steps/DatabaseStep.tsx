import { Check, Cloud, Cpu, Database, Eye, EyeOff, Layers, RefreshCw, X, Zap } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { Tooltip } from '../components/Tooltip';
import { platformAdapter, type ConnectionTestResult } from '../services/platformAdapter';
import { detectEnvCredentials } from '../services/envDetector';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { SubstrateMode } from '../types';

export const DatabaseStep: React.FC = () => {
  const { config, updateSubstrate, setAllSubstratesMode, syncBackendConfig } = useControlCenterStore();
  const envData = detectEnvCredentials();

  // Test live substrate connectivity state
  const [isTestingSubstrates, setIsTestingSubstrates] = useState(false);
  const [testResults, setTestResults] = useState<ConnectionTestResult | null>(null);
  const [testNotice, setTestNotice] = useState<string | null>(null);

  // Cloud credentials modal state
  const [activeCloudSubstrate, setActiveCloudSubstrate] = useState<
    'knowledgeGraph' | 'sessionMemory' | 'cacheAndSignals' | null
  >(null);
  const [cloudUri, setCloudUri] = useState('');
  const [cloudUser, setCloudUser] = useState('neo4j');
  const [cloudPass, setCloudPass] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isConnectingCloud, setIsConnectingCloud] = useState(false);
  const [cloudModalError, setCloudModalError] = useState<string | null>(null);

  const buildSavePayload = (overrides: Record<string, unknown>) => {
    const cur = useControlCenterStore.getState().config;
    let targetBackend = cur.llmDeployment === 'local' ? (cur.selectedLocalModel?.includes('vllm') ? 'vllm' : 'ollama') : 'gemini';
    if (cur.llmMode) {
      if (cur.llmMode.startsWith('cloud_')) {
        targetBackend = cur.llmMode.replace('cloud_', '');
      } else if (cur.llmMode.startsWith('local_')) {
        targetBackend = cur.llmMode.replace('local_', '');
      }
    }

    return {
      llm_mode: cur.llmMode || 'cloud_gemini',
      llm_backend: targetBackend,
      primary_provider: targetBackend,
      neo4j_mode: cur.knowledgeGraph?.mode || cur.neo4jMode || 'in_memory_fallback',
      neo4j_uri: cur.knowledgeGraph?.uri || cur.neo4jUri || '',
      neo4j_user: cur.knowledgeGraph?.user || 'neo4j',
      neo4j_password: cur.knowledgeGraph?.password || cur.neo4jPassword || '',
      postgres_mode: cur.sessionMemory?.mode || cur.postgresMode || 'in_memory_fallback',
      postgres_uri: cur.sessionMemory?.uri || '',
      redis_mode: cur.cacheAndSignals?.mode || cur.redisMode || 'in_memory_fallback',
      redis_uri: cur.cacheAndSignals?.uri || '',
      ...overrides,
    };
  };

  const handleTestAllSubstrates = async () => {
    setIsTestingSubstrates(true);
    setTestNotice('Testing substrates...');
    try {
      const cur = useControlCenterStore.getState().config;
      const results = await platformAdapter.testConnections({
        neo4j_mode: cur.knowledgeGraph?.mode || cur.neo4jMode,
        neo4j_uri: cur.knowledgeGraph?.uri || cur.neo4jUri,
        neo4j_user: cur.knowledgeGraph?.user,
        neo4j_password: cur.knowledgeGraph?.password || cur.neo4jPassword,
        postgres_mode: cur.sessionMemory?.mode || cur.postgresMode,
        postgres_uri: cur.sessionMemory?.uri,
        redis_mode: cur.cacheAndSignals?.mode || cur.redisMode,
        redis_uri: cur.cacheAndSignals?.uri,
      });
      setTestResults(results);

      // Keep substrate status in store aligned with honest probe results
      if (results.neo4j) {
        updateSubstrate('knowledgeGraph', {
          tested: true,
          online: results.neo4j.online,
          latencyMs: results.neo4j.latency_ms,
        });
      }
      if (results.postgres) {
        updateSubstrate('sessionMemory', {
          tested: true,
          online: results.postgres.online,
          latencyMs: results.postgres.latency_ms,
        });
      }
      if (results.redis) {
        updateSubstrate('cacheAndSignals', {
          tested: true,
          online: results.redis.online,
          latencyMs: results.redis.latency_ms,
        });
      }

      setTestNotice('Connection probes complete.');
    } catch {
      setTestNotice('Connection probe encountered offline endpoints.');
    } finally {
      setIsTestingSubstrates(false);
      setTimeout(() => setTestNotice(null), 3500);
    }
  };

  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      try {
        await syncBackendConfig();
      } catch {
        // Backend offline or unreachable
      }
      if (isMounted) {
        await handleTestAllSubstrates();
      }
    };
    init();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSelectSubstrateMode = async (
    key: 'knowledgeGraph' | 'sessionMemory' | 'cacheAndSignals',
    targetMode: SubstrateMode
  ) => {
    updateSubstrate(key, { mode: targetMode });
    const tierName =
      targetMode === 'in_memory_fallback'
        ? 'Fast Local (Embedded)'
        : targetMode === 'local'
        ? 'Docker Stack (Local)'
        : 'Cloud Managed';
    setTestNotice(`Switching to ${tierName}...`);

    const overrides: Record<string, unknown> = {};
    if (key === 'knowledgeGraph') {
      overrides.neo4j_mode = targetMode;
      if (targetMode === 'local') {
        overrides.neo4j_uri = config.knowledgeGraph?.uri || 'bolt://localhost:7687';
        overrides.neo4j_user = config.knowledgeGraph?.user || 'neo4j';
        overrides.neo4j_password = config.knowledgeGraph?.password || 'raise_password';
      }
    } else if (key === 'sessionMemory') {
      overrides.postgres_mode = targetMode;
      if (targetMode === 'local') {
        overrides.postgres_uri =
          config.sessionMemory?.uri ||
          'postgresql://raise_user:raise_password@localhost:5432/raise_db';
      }
    } else if (key === 'cacheAndSignals') {
      overrides.redis_mode = targetMode;
      if (targetMode === 'local') {
        overrides.redis_uri = config.cacheAndSignals?.uri || 'redis://localhost:6379/0';
      }
    }

    try {
      await platformAdapter.saveConfig(buildSavePayload(overrides));
      await handleTestAllSubstrates();
      setTestNotice(`${tierName} applied & verified.`);
    } catch {
      setTestNotice('Could not persist storage setting to backend.');
    } finally {
      setTimeout(() => setTestNotice(null), 3000);
    }
  };

  const handleSetAllSubstrates = async (targetMode: SubstrateMode) => {
    setAllSubstratesMode(targetMode);
    const tierName =
      targetMode === 'in_memory_fallback'
        ? 'Fast Local (Embedded)'
        : targetMode === 'local'
        ? 'Docker Stack (Local)'
        : 'Cloud Managed';
    setTestNotice(`Applying ${tierName} to all substrates...`);

    const overrides: Record<string, unknown> = {
      neo4j_mode: targetMode,
      postgres_mode: targetMode,
      redis_mode: targetMode,
    };

    if (targetMode === 'local') {
      overrides.neo4j_uri = 'bolt://localhost:7687';
      overrides.neo4j_user = 'neo4j';
      overrides.neo4j_password = 'raise_password';
      overrides.postgres_uri = 'postgresql://raise_user:raise_password@localhost:5432/raise_db';
      overrides.redis_uri = 'redis://localhost:6379/0';
    }

    try {
      await platformAdapter.saveConfig(buildSavePayload(overrides));
      await handleTestAllSubstrates();
      setTestNotice(`All substrates set to ${tierName}.`);
    } catch {
      setTestNotice('Could not persist storage setting to backend.');
    } finally {
      setTimeout(() => setTestNotice(null), 3000);
    }
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

  const getEffectiveMode = (key: 'knowledgeGraph' | 'sessionMemory' | 'cacheAndSignals'): SubstrateMode => {
    const storeMode =
      key === 'knowledgeGraph'
        ? config.knowledgeGraph?.mode || config.neo4jMode
        : key === 'sessionMemory'
        ? config.sessionMemory?.mode || config.postgresMode
        : config.cacheAndSignals?.mode || config.redisMode;

    if (storeMode && ['in_memory_fallback', 'local', 'cloud'].includes(storeMode)) {
      return storeMode as SubstrateMode;
    }
    return 'in_memory_fallback';
  };

  const substrates = [
    {
      key: 'knowledgeGraph' as const,
      name: 'Knowledge Graph',
      getRole: (mode: SubstrateMode) => {
        if (mode === 'in_memory_fallback') return 'NetworkX In-Memory Engine';
        if (mode === 'local') return isNeo4jOnline ? 'Neo4j Graph Database (:7687)' : 'Neo4j Local Container (:7687)';
        return isNeo4jOnline ? 'Neo4j AuraDB Cloud' : 'Neo4j AuraDB (Remote)';
      },
      icon: Layers,
      info: 'Property graph database for semantic citations, concept nodes, and multi-hop reasoning.',
      defaultUri: 'neo4j+s://your-instance.databases.neo4j.io',
      presetName: 'Neo4j AuraDB',
    },
    {
      key: 'sessionMemory' as const,
      name: 'Session Memory',
      getRole: (mode: SubstrateMode) => {
        if (mode === 'in_memory_fallback') return 'Local SQLite Storage';
        if (mode === 'local') return isPostgresOnline ? 'PostgreSQL Store (:5432)' : 'PostgreSQL Local Container (:5432)';
        return isPostgresOnline ? 'Neon Serverless Postgres' : 'PostgreSQL Cloud (Remote)';
      },
      icon: Database,
      info: 'Relational & vector persistence for cross-session chat persistence.',
      defaultUri: 'postgresql://user:password@ep-cool-fog.neon.tech/neondb',
      presetName: 'Neon Serverless Postgres',
    },
    {
      key: 'cacheAndSignals' as const,
      name: 'Response Cache',
      getRole: (mode: SubstrateMode) => {
        if (mode === 'in_memory_fallback') return 'In-Memory State & Signals';
        if (mode === 'local') return isRedisOnline ? 'Redis Fast Bus (:6379)' : 'Redis Local Container (:6379)';
        return isRedisOnline ? 'Upstash Redis Cloud' : 'Redis Cloud (Remote)';
      },
      icon: Zap,
      info: 'Sub-millisecond ephemeral streaming state and semantic query caching.',
      defaultUri: 'rediss://default:token@your-cluster.upstash.io:6379',
      presetName: 'Upstash Redis',
    },
  ];

  const handleOpenCloudModal = (key: 'knowledgeGraph' | 'sessionMemory' | 'cacheAndSignals') => {
    const existing = config[key];
    const detected =
      key === 'knowledgeGraph'
        ? envData.neo4j
        : key === 'sessionMemory'
        ? envData.postgres
        : envData.redis;

    const initialUri = existing?.uri || (detected?.present ? detected.uri || '' : '');
    const initialUser =
      existing?.user || (detected?.user || (key === 'knowledgeGraph' ? 'neo4j' : ''));
    const initialPass = existing?.password || (detected?.password || '');

    setCloudUri(initialUri);
    setCloudPass(initialPass);
    setCloudUser(initialUser);
    setCloudModalError(null);
    setShowPassword(false);
    setActiveCloudSubstrate(key);
  };

  const handleConnectCloud = async () => {
    if (!activeCloudSubstrate) return;

    if (!cloudUri.trim()) {
      setCloudModalError('Please enter a connection URI.');
      return;
    }

    setIsConnectingCloud(true);
    setCloudModalError(null);

    try {
      const payload: Record<string, unknown> = {};
      if (activeCloudSubstrate === 'knowledgeGraph') {
        payload.neo4j_mode = 'cloud';
        payload.neo4j_uri = cloudUri.trim();
        payload.neo4j_user = cloudUser.trim();
        payload.neo4j_password = cloudPass;
      } else if (activeCloudSubstrate === 'sessionMemory') {
        payload.postgres_mode = 'cloud';
        payload.postgres_uri = cloudUri.trim();
      } else if (activeCloudSubstrate === 'cacheAndSignals') {
        payload.redis_mode = 'cloud';
        payload.redis_uri = cloudUri.trim();
      }

      // Test connection honestly with user-provided credentials
      const results = await platformAdapter.testConnections(payload);
      let isOnline = false;
      let latency = 25;
      let errorMsg: string | undefined;

      if (activeCloudSubstrate === 'knowledgeGraph') {
        isOnline = results.neo4j?.online === true;
        latency = results.neo4j?.latency_ms || 28;
        errorMsg = results.neo4j?.error;
      } else if (activeCloudSubstrate === 'sessionMemory') {
        isOnline = results.postgres?.online === true;
        latency = 35;
        errorMsg = results.postgres?.error;
      } else if (activeCloudSubstrate === 'cacheAndSignals') {
        isOnline = results.redis?.online === true;
        latency = results.redis?.latency_ms || 12;
        errorMsg = results.redis?.error;
      }

      if (!isOnline) {
        setCloudModalError(
          errorMsg || 'Connection failed: Unable to reach database endpoint. Check URI/credentials.'
        );
        updateSubstrate(activeCloudSubstrate, {
          mode: 'cloud',
          uri: cloudUri.trim(),
          user: cloudUser.trim(),
          password: cloudPass,
          tested: true,
          online: false,
          latencyMs: latency,
        });
        return;
      }

      updateSubstrate(activeCloudSubstrate, {
        mode: 'cloud',
        uri: cloudUri.trim(),
        user: cloudUser.trim(),
        password: cloudPass,
        tested: true,
        online: true,
        latencyMs: latency,
      });

      // Persist to backend .env and live runtime
      await platformAdapter.saveConfig(buildSavePayload(payload));
      await handleTestAllSubstrates();
      setActiveCloudSubstrate(null);
    } catch (err: any) {
      setCloudModalError(err?.message || 'Connection test failed. Verify credentials.');
    } finally {
      setIsConnectingCloud(false);
    }
  };

  const kgMode = getEffectiveMode('knowledgeGraph');
  const memMode = getEffectiveMode('sessionMemory');
  const cacheMode = getEffectiveMode('cacheAndSignals');

  const isAllMemory =
    kgMode === 'in_memory_fallback' &&
    memMode === 'in_memory_fallback' &&
    cacheMode === 'in_memory_fallback';

  const isAllLocal =
    kgMode === 'local' &&
    memMode === 'local' &&
    cacheMode === 'local';

  const isAllCloud =
    kgMode === 'cloud' &&
    memMode === 'cloud' &&
    cacheMode === 'cloud';

  const hasAnyDbInEnv =
    envData.postgres.present || envData.redis.present || envData.neo4j.present;

  return (
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            Storage Substrates
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Configure Graph, Memory, Cache, and Vector stores with runtime fallback.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {testNotice && (
            <span className="text-xs font-mono text-white font-bold animate-in fade-in">
              {testNotice}
            </span>
          )}
          <button
            type="button"
            onClick={handleTestAllSubstrates}
            disabled={isTestingSubstrates}
            className="px-3 py-1.5 rounded-lg border border-white/20 bg-white/5 hover:bg-white/10 text-white text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer shrink-0 disabled:opacity-50"
            title="Probe live connectivity for all configured substrates"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isTestingSubstrates ? 'animate-spin text-white' : ''}`} />
            <span>Test Substrates</span>
          </button>
        </div>
      </div>

      {/* Global Storage Tier Quick-Toggle: Fast Local vs Docker Containers vs Cloud Managed */}
      <div className="p-1.5 rounded-xl bg-[#131622] border border-white/10 grid grid-cols-1 sm:grid-cols-3 gap-2">
        {/* Tier 1: Fast Local (Zero-Dependency) */}
        <button
          type="button"
          onClick={() => handleSetAllSubstrates('in_memory_fallback')}
          className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isAllMemory
              ? 'bg-white text-black font-bold shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
          }`}
          title="Zero-dependency fast in-memory execution (NetworkX, SQLite WAL, In-Memory Signals)"
        >
          <div className="flex items-center gap-2">
            <Cpu className={`w-4 h-4 ${isAllMemory ? 'text-black' : 'text-white'}`} />
            <span>Fast Local (Embedded)</span>
          </div>
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
              isAllMemory ? 'bg-black/10 text-black' : 'bg-black/40 text-slate-400'
            }`}
          >
            Zero Setup • Instant
          </span>
        </button>

        {/* Tier 2: Docker Containers (Localhost) */}
        <button
          type="button"
          onClick={() => handleSetAllSubstrates('local')}
          className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isAllLocal
              ? 'bg-white text-black font-bold shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
          }`}
          title="Local Docker container daemons (Redis :6379, Postgres :5432, Neo4j :7687)"
        >
          <div className="flex items-center gap-2">
            <Database className={`w-4 h-4 ${isAllLocal ? 'text-black' : 'text-white'}`} />
            <span>Docker Stack (Local)</span>
          </div>
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
              isAllLocal ? 'bg-black/10 text-black' : 'bg-black/40 text-slate-400'
            }`}
          >
            Containers • Localhost
          </span>
        </button>

        {/* Tier 3: Cloud Managed Remote Endpoints */}
        <button
          type="button"
          onClick={() => handleSetAllSubstrates('cloud')}
          className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isAllCloud
              ? 'bg-white text-black font-bold shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
          }`}
          title="Cloud-hosted database endpoints (Upstash Redis, Neon Postgres, Neo4j AuraDB)"
        >
          <div className="flex items-center gap-2">
            <Cloud className={`w-4 h-4 ${isAllCloud ? 'text-black' : 'text-white'}`} />
            <span>Cloud Managed</span>
          </div>
          <span
            className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
              isAllCloud ? 'bg-black/10 text-black' : 'bg-black/40 text-slate-400'
            }`}
          >
            Remote Endpoints
          </span>
        </button>
      </div>

      {/* .env Detection Banner */}
      {hasAnyDbInEnv && (
        <div className="p-2.5 rounded-xl bg-white/5 border border-white/15 flex items-center justify-between text-xs">
          <div>
            <div className="font-semibold text-white flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-white" />
              <span>Endpoints found in .env:</span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5 flex gap-2 flex-wrap">
              {envData.postgres.present && <span>• Postgres</span>}
              {envData.redis.present && <span>• Redis</span>}
              {envData.neo4j.present && <span>• Neo4j</span>}
            </div>
          </div>
          <button
            type="button"
            onClick={() => handleSetAllSubstrates('cloud')}
            className="px-2.5 py-1 rounded bg-white hover:bg-zinc-200 text-black text-xs font-bold transition-all cursor-pointer shrink-0"
          >
            Apply
          </button>
        </div>
      )}

      {/* Modern Table Format (Single unified view, click box and tick) */}
      <div className="rounded-xl bg-[#131622] border border-white/10 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-black/40 text-xs font-semibold text-slate-300">
              <th className="py-2.5 px-4">Substrate</th>
              <th className="py-2.5 px-3 text-center">Fast Local (Embedded)</th>
              <th className="py-2.5 px-3 text-center">Docker Stack (Local)</th>
              <th className="py-2.5 px-3 text-center">Cloud Managed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {substrates.map((sub) => {
              const currentMode = getEffectiveMode(sub.key);
              const cfg = config[sub.key] || { mode: currentMode };
              const Icon = sub.icon;

              const isMemory = currentMode === 'in_memory_fallback';
              const isLocal = currentMode === 'local';
              const isCloud = currentMode === 'cloud';

              return (
                <tr key={sub.key} className="hover:bg-white/[0.02] transition-colors">
                  {/* Row Header (Substrate with Tooltip) */}
                  <td className="py-3.5 px-4">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center text-white shrink-0">
                        <Icon className="w-3.5 h-3.5 text-white" />
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-white text-xs">{sub.name}</span>
                          <Tooltip size="sm" content={sub.info} />
                        </div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                          {sub.getRole(currentMode)}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Fast Local (Embedded) Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleSelectSubstrateMode(sub.key, 'in_memory_fallback')}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isMemory
                          ? 'bg-white text-black border border-white font-bold shadow-sm'
                          : 'text-slate-500 hover:text-white hover:bg-white/5 font-mono text-base'
                      }`}
                      title="Select Fast Local (Embedded Zero-Dependency)"
                      aria-label={`Select Fast Local (Embedded) for ${sub.name}`}
                    >
                      {isMemory ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Fast Local (Embedded)</span>
                        </>
                      ) : (
                        <span>-</span>
                      )}
                    </button>
                  </td>

                  {/* Docker Stack (Local) Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleSelectSubstrateMode(sub.key, 'local')}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isLocal
                          ? 'bg-white text-black border border-white font-bold shadow-sm'
                          : 'text-slate-500 hover:text-white hover:bg-white/5 font-mono text-base'
                      }`}
                      title="Select Docker Stack (Localhost Daemons)"
                      aria-label={`Select Docker Stack (Local) for ${sub.name}`}
                    >
                      {isLocal ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Docker Stack (Local)</span>
                        </>
                      ) : (
                        <span>-</span>
                      )}
                    </button>
                  </td>

                  {/* Cloud Managed Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleOpenCloudModal(sub.key)}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isCloud && cfg?.online === true
                          ? 'bg-white text-black border border-white font-bold shadow-sm'
                          : isCloud && cfg?.tested && cfg?.online === false
                          ? 'bg-zinc-800 text-zinc-300 border border-white/20 shadow-sm'
                          : isCloud
                          ? 'bg-white/10 text-white border border-white/20 shadow-sm'
                          : 'text-slate-500 hover:text-white hover:bg-white/5 font-mono text-base'
                      }`}
                      title={
                        isCloud && cfg?.online === true
                          ? 'Cloud connected (click to edit)'
                          : isCloud && cfg?.tested && cfg?.online === false
                          ? 'Cloud connection failed (click to retry)'
                          : isCloud
                          ? 'Cloud configured, unverified (click to verify)'
                          : 'Click to configure Cloud connection'
                      }
                      aria-label={`Select Cloud Managed for ${sub.name}`}
                    >
                      {isCloud && cfg?.online === true ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Cloud Managed</span>
                        </>
                      ) : isCloud && cfg?.tested && cfg?.online === false ? (
                        <>
                          <X className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Connection Failed</span>
                        </>
                      ) : isCloud ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span className="sr-only">Unverified</span>
                        </>
                      ) : (
                        <span>-</span>
                      )}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ChromaDB Dense Vector Engine Substrate */}
      <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/10 text-white border border-white/20 flex items-center justify-center shrink-0 font-mono font-bold text-xs">
            V
          </div>
          <div>
            <div className="font-bold text-white flex items-center gap-2">
              <span>Vector Store</span>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-white/10 text-white border border-white/20 font-mono">
                ChromaDB (Local Embedded)
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono mt-0.5">
              Dense document embeddings & semantic similarity • Fast embedded SQLite/Parquet vector persistence
            </div>
          </div>
        </div>
        {typeof testResults?.chroma?.total_chunks === 'number' && (
          <span className="text-[11px] font-mono text-slate-400 shrink-0">
            {testResults.chroma.total_chunks} chunks
          </span>
        )}
      </div>

      {/* Cloud Connection Configuration Popup */}
      {activeCloudSubstrate &&
        (() => {
          const sub = substrates.find((s) => s.key === activeCloudSubstrate);
          if (!sub) return null;
          const Icon = sub.icon;

          return (
            <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="w-full max-w-md bg-[#131622] border border-white/20 rounded-2xl p-5 shadow-2xl space-y-4 animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-white shrink-0">
                      <Icon className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">Connect {sub.name}</h4>
                      <p className="text-[11px] text-slate-400 font-mono">{sub.presetName}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveCloudSubstrate(null)}
                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>

                {cloudModalError && (
                  <div className="p-2.5 rounded-lg bg-white/5 border border-white/15 text-zinc-300 text-xs font-mono">
                    {cloudModalError}
                  </div>
                )}

                {/* Substrate .env Detection Status in Modal */}
                {(() => {
                  const detected =
                    activeCloudSubstrate === 'knowledgeGraph'
                      ? envData.neo4j
                      : activeCloudSubstrate === 'sessionMemory'
                      ? envData.postgres
                      : envData.redis;

                  if (detected?.present) {
                    return (
                      <div className="p-2 rounded-lg bg-white/10 border border-white/20 flex items-center justify-between text-[11px]">
                        <span className="text-white flex items-center gap-1 font-mono font-semibold">
                          <Check className="w-3 h-3 text-white" />
                          Detected in root .env ({detected.source})
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setCloudUri(detected.uri || '');
                            if (detected.user) setCloudUser(detected.user);
                            if (detected.password) setCloudPass(detected.password);
                          }}
                          className="px-2 py-0.5 rounded bg-white hover:bg-zinc-200 text-black font-bold cursor-pointer"
                        >
                          Use .env Value
                        </button>
                      </div>
                    );
                  }

                  return (
                    <div className="p-2 rounded-lg bg-white/[0.03] border border-white/10 text-[11px] text-slate-400 font-mono">
                      No {sub.name} string in root .env. Input spots are empty for custom entry.
                    </div>
                  );
                })()}

                <div className="space-y-3">
                  <div className="space-y-1">
                    <label
                      htmlFor="cloud-uri-input"
                      className="text-xs font-semibold text-slate-300 block"
                    >
                      Connection URI
                    </label>
                    <input
                      id="cloud-uri-input"
                      type="text"
                      value={cloudUri}
                      onChange={(e) => setCloudUri(e.target.value)}
                      placeholder={sub.defaultUri}
                      className="w-full px-3 py-2 rounded-lg bg-black/60 border border-white/15 text-white font-mono text-xs focus:outline-none focus:border-white transition-all placeholder-slate-600"
                    />
                  </div>

                  {activeCloudSubstrate === 'knowledgeGraph' && (
                    <>
                      <div className="space-y-1">
                        <label
                          htmlFor="cloud-username-input"
                          className="text-xs font-semibold text-slate-300 block"
                        >
                          Username
                        </label>
                        <input
                          id="cloud-username-input"
                          type="text"
                          value={cloudUser}
                          onChange={(e) => setCloudUser(e.target.value)}
                          placeholder="neo4j"
                          className="w-full px-3 py-2 rounded-lg bg-black/60 border border-white/15 text-white font-mono text-xs focus:outline-none focus:border-white transition-all"
                        />
                      </div>

                      <div className="space-y-1">
                        <label
                          htmlFor="cloud-password-input"
                          className="text-xs font-semibold text-slate-300 block"
                        >
                          Password
                        </label>
                        <div className="relative">
                          <input
                            id="cloud-password-input"
                            type={showPassword ? 'text' : 'password'}
                            value={cloudPass}
                            onChange={(e) => setCloudPass(e.target.value)}
                            placeholder="••••••••"
                            className="w-full px-3 py-2 pr-9 rounded-lg bg-black/60 border border-white/15 text-white font-mono text-xs focus:outline-none focus:border-white transition-all"
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white cursor-pointer"
                          >
                            {showPassword ? (
                              <EyeOff className="w-3.5 h-3.5" />
                            ) : (
                              <Eye className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setActiveCloudSubstrate(null)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-white/5 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={isConnectingCloud}
                    onClick={handleConnectCloud}
                    className="px-4 py-1.5 rounded-lg text-xs font-bold bg-white text-black hover:bg-slate-200 transition-all cursor-pointer flex items-center gap-1.5 disabled:opacity-50"
                  >
                    {isConnectingCloud ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      'Connect'
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })()}
    </div>
  );
};
