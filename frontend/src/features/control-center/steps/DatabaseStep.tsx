import { Check, Cloud, Cpu, Database, Eye, EyeOff, Layers, RefreshCw, X, Zap } from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
import { Tooltip } from '../components/Tooltip';
import { platformAdapter } from '../services/platformAdapter';
import { detectEnvCredentials } from '../services/envDetector';
import { useControlCenterStore } from '../store/useControlCenterStore';

export const DatabaseStep: React.FC = () => {
  const { config, updateSubstrate, setAllSubstratesMode } = useControlCenterStore();
  const envData = detectEnvCredentials();

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

  const substrates = [
    {
      key: 'knowledgeGraph' as const,
      name: 'Knowledge Graph',
      role: 'Neo4j Graph Engine',
      icon: Layers,
      info: 'Neo4j Graph Database for semantic citations, concept nodes, and multi-hop reasoning.',
      defaultUri: 'neo4j+s://your-instance.databases.neo4j.io',
      presetName: 'Neo4j AuraDB',
    },
    {
      key: 'sessionMemory' as const,
      name: 'Session Memory',
      role: 'PostgreSQL Store',
      icon: Database,
      info: 'PostgreSQL with pgvector for cross-session chat persistence.',
      defaultUri: 'postgresql://user:password@ep-cool-fog.neon.tech/neondb',
      presetName: 'Neon Serverless Postgres',
    },
    {
      key: 'cacheAndSignals' as const,
      name: 'Response Cache',
      role: 'Redis Fast Bus',
      icon: Zap,
      info: 'Redis for ephemeral streaming state and semantic query caching.',
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
    const initialUser = existing?.user || (detected?.user || (key === 'knowledgeGraph' ? 'neo4j' : ''));
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
        setCloudModalError(errorMsg || 'Connection failed: Unable to reach database endpoint. Check URI/credentials.');
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

      setActiveCloudSubstrate(null);
    } catch (err: any) {
      setCloudModalError(err?.message || 'Connection test failed. Verify credentials.');
    } finally {
      setIsConnectingCloud(false);
    }
  };

  const kgMode = config.knowledgeGraph?.mode || config.neo4jMode || 'in_memory_fallback';
  const memMode = config.sessionMemory?.mode || config.postgresMode || 'in_memory_fallback';
  const cacheMode = config.cacheAndSignals?.mode || config.redisMode || 'in_memory_fallback';

  const isAllMemory =
    kgMode === 'in_memory_fallback' &&
    memMode === 'in_memory_fallback' &&
    cacheMode === 'in_memory_fallback';

  const isAllCloud =
    kgMode === 'cloud' &&
    memMode === 'cloud' &&
    cacheMode === 'cloud';

  const hasAnyDbInEnv =
    envData.postgres.present || envData.redis.present || envData.neo4j.present;

  return (
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">
          Storage Substrates
        </h3>
      </div>

      {/* Global Mode Quick-Toggle: Python In-Memory vs Cloud Infrastructure */}
      <div className="p-1.5 rounded-xl bg-[#131622] border border-white/10 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => setAllSubstratesMode('in_memory_fallback')}
          className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isAllMemory
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
          }`}
        >
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-emerald-400" />
            <span>In-Memory</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 text-slate-400">
            0 GB • Instant
          </span>
        </button>

        <button
          type="button"
          onClick={() => setAllSubstratesMode('cloud')}
          className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-between cursor-pointer ${
            isAllCloud
              ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
              : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
          }`}
        >
          <div className="flex items-center gap-2">
            <Cloud className="w-4 h-4 text-sky-400" />
            <span>Cloud</span>
          </div>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 text-slate-400">
            Remote Endpoints
          </span>
        </button>
      </div>

      {/* .env Detection Banner */}
      {hasAnyDbInEnv && (
        <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/25 flex items-center justify-between text-xs">
          <div>
            <div className="font-semibold text-sky-300 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-sky-400" />
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
            onClick={() => setAllSubstratesMode('cloud')}
            className="px-2.5 py-1 rounded bg-sky-500/20 hover:bg-sky-500/30 text-sky-200 text-xs font-semibold transition-all cursor-pointer shrink-0"
          >
            Apply
          </button>
        </div>
      )}

      {/* Modern Table Format (Single unified view, zero internal scrollbar) */}
      <div className="rounded-xl bg-[#131622] border border-white/10 overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-black/40 text-xs font-semibold text-slate-300">
              <th className="py-2.5 px-4">Substrate</th>
              <th className="py-2.5 px-3 text-center">In-Memory</th>
              <th className="py-2.5 px-3 text-center">Local</th>
              <th className="py-2.5 px-3 text-center">Cloud</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {substrates.map((sub) => {
              const legacyMode =
                sub.key === 'knowledgeGraph'
                  ? config.neo4jMode
                  : sub.key === 'sessionMemory'
                    ? config.postgresMode
                    : config.redisMode;
              const cfg = config[sub.key] || { mode: legacyMode || 'in_memory_fallback' };
              const currentMode = cfg.mode || 'in_memory_fallback';
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
                          {sub.role}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Python Memory Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => updateSubstrate(sub.key, { mode: 'in_memory_fallback' })}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isMemory
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                          : 'text-slate-500 hover:text-white hover:bg-white/5 font-mono text-base'
                      }`}
                      title="Select Python In-Memory"
                      aria-label={`Select Python In-Memory for ${sub.name}`}
                    >
                      {isMemory ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Python In-Memory</span>
                        </>
                      ) : (
                        <span>-</span>
                      )}
                    </button>
                  </td>

                  {/* Local Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => updateSubstrate(sub.key, { mode: 'local' })}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isLocal
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                          : 'text-slate-500 hover:text-white hover:bg-white/5 font-mono text-base'
                      }`}
                      title="Select Local Daemon"
                      aria-label={`Select Local for ${sub.name}`}
                    >
                      {isLocal ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Local</span>
                        </>
                      ) : (
                        <span>-</span>
                      )}
                    </button>
                  </td>

                  {/* Cloud Cell */}
                  <td className="py-3.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => handleOpenCloudModal(sub.key)}
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-lg transition-all cursor-pointer ${
                        isCloud && cfg?.online === true
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                          : isCloud && cfg?.tested && cfg?.online === false
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-sm'
                          : isCloud
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-sm'
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
                      aria-label={`Select Cloud for ${sub.name}`}
                    >
                      {isCloud && cfg?.online === true ? (
                        <>
                          <Check className="w-4 h-4 stroke-[2.5]" />
                          <span className="sr-only">Cloud</span>
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
                  <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
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
                      <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between text-[11px]">
                        <span className="text-emerald-300 flex items-center gap-1 font-mono">
                          <Check className="w-3 h-3" />
                          Detected in root .env ({detected.source})
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            setCloudUri(detected.uri || '');
                            if (detected.user) setCloudUser(detected.user);
                            if (detected.password) setCloudPass(detected.password);
                          }}
                          className="px-2 py-0.5 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 font-semibold cursor-pointer"
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
