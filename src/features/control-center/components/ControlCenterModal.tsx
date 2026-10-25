import { Check, CheckCircle2, Cpu, Laptop, RefreshCw, Sparkles, X, Zap } from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { useScrollLock } from '../../../hooks';
import { useModeStore } from '../../../stores/modeStore';
import { platformAdapter } from '../services/platformAdapter';
import { EngineStep } from '../steps/EngineStep';
import { LaunchStep } from '../steps/LaunchStep';
import { PlatformStep } from '../steps/PlatformStep';
import { useControlCenterStore } from '../store/useControlCenterStore';

export const ControlCenterModal: React.FC = () => {
  const {
    isOpen,
    setOpen,
    activeTab,
    setActiveTab,
    setHardware,
    config,
    updateConfig,
    completeFirstRun,
  } = useControlCenterStore();

  const [isSaving, setIsSaving] = useState(false);
  const [connectNotice, setConnectNotice] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const { testConnection, appMode } = useModeStore();
  const isConnected = appMode === 'connected';

  // Detect whether modal is rendered in first-time setup or onboarding context
  const isSetupMode = useMemo(() => {
    if (typeof window === 'undefined') return false;
    const url = new URLSearchParams(window.location.search);
    const hash = new URLSearchParams((window.location.hash || '').split('?')[1] || '');
    const isUrl =
      url.get('setup') === 'true' ||
      url.get('control_center') === 'true' ||
      hash.get('setup') === 'true' ||
      hash.get('control_center') === 'true';
    return (
      isUrl ||
      localStorage.getItem('raise_onboarding_completed') !== 'true' ||
      !config.firstRunCompleted
    );
  }, [config.firstRunCompleted]);

  // Load live hardware telemetry on mount or open
  useEffect(() => {
    if (isOpen) {
      useControlCenterStore.getState().syncEnvCredentials();
      platformAdapter.getHardware().then((hw) => {
        const detected = platformAdapter.normalizePlatform(
          hw.os_name ||
            hw.platform ||
            (typeof window !== 'undefined' ? window.navigator.platform : 'macos')
        );
        setHardware({
          platform: detected,
          osName: hw.os_name || (detected === 'macos' ? 'macOS (Apple Silicon)' : detected),
          totalRamGb: hw.total_ram_gb || 8.0,
          cpuCores: hw.cpu_cores || 8,
          hasMetalOrCuda: hw.has_metal_or_cuda ?? true,
        });
        if (
          config.targetPlatform === 'web' ||
          config.targetPlatform === 'ios' ||
          config.targetPlatform === 'android'
        ) {
          updateConfig({ targetPlatform: detected });
        }
      });
    }
  }, [isOpen]);

  useScrollLock(isOpen);
  if (!isOpen) return null;

  // Track completion state of each step for visual stepper badges
  const hasConfiguredKey =
    config.llmDeployment === 'local'
      ? Boolean(config.selectedLocalModel)
      : (config.apiKeys || []).some((k) => k.key && k.key.trim().length > 0);

  const tabs = [
    {
      id: 'platform' as const,
      stepNumber: 1,
      label: 'Platform & Device',
      icon: Laptop,
      isCompleted: Boolean(config.targetPlatform),
    },
    {
      id: 'models' as const,
      stepNumber: 2,
      label: 'Intelligence Engine',
      icon: Cpu,
      isCompleted: hasConfiguredKey,
    },
    {
      id: 'launch' as const,
      stepNumber: 3,
      label: 'Summary & Launch',
      icon: Zap,
      isCompleted: hasConfiguredKey,
    },
  ];

  const currentTabIdx = tabs.findIndex((t) => t.id === activeTab);

  const handleNext = () => {
    if (activeTab === 'platform') {
      setActiveTab('models');
    } else if (activeTab === 'models') {
      if (!hasConfiguredKey) {
        setConnectNotice('Configure an AI key or local model to proceed.');
        setTimeout(() => setConnectNotice(null), 4000);
        return;
      }
      setActiveTab('launch');
    } else {
      handleFinalStart();
    }
  };

  const handleBack = () => {
    if (currentTabIdx > 0) {
      setActiveTab(tabs[currentTabIdx - 1].id);
    }
  };

  const handleProbeBackend = async () => {
    setIsConnecting(true);
    setConnectNotice('Probing backend (127.0.0.1:8000)...');
    try {
      const result = await testConnection('http://127.0.0.1:8000');
      if (result.success) {
        setConnectNotice('Connected to local backend!');
        setTimeout(() => setConnectNotice(null), 2000);
      } else {
        setConnectNotice(result.error || 'Backend offline on 127.0.0.1:8000');
        setTimeout(() => setConnectNotice(null), 5000);
      }
    } catch (err: any) {
      setConnectNotice(err?.message || 'Connection attempt failed.');
      setTimeout(() => setConnectNotice(null), 5000);
    } finally {
      setIsConnecting(false);
    }
  };

  const handleFinalStart = async () => {
    setIsSaving(true);
    try {
      const isCloud = config.llmDeployment === 'cloud';
      const keyMap: Record<string, string> = {};
      for (const entry of config.apiKeys || []) {
        if (entry.key && entry.key.trim()) {
          keyMap[entry.provider] = entry.key.trim();
        }
      }

      const primaryCloudProvider =
        (config.apiKeys || []).find((k) => k?.key && k.key.trim())?.provider || 'groq';
      const activeBackend = isCloud ? primaryCloudProvider : 'ollama';
      const activeLlmMode = isCloud ? `cloud_${primaryCloudProvider}` : 'local_ollama';

      await platformAdapter.saveConfig({
        llm_mode: activeLlmMode,
        llm_backend: activeBackend,
        groq_api_key: keyMap['groq'] || config.groqApiKey,
        gemini_api_key: keyMap['gemini'] || config.geminiApiKey,
        openai_api_key: keyMap['openai'],
        anthropic_api_key: keyMap['anthropic'],
        deepseek_api_key: keyMap['deepseek'],
        nvidia_api_key: keyMap['nvidia'],
        mistral_api_key: keyMap['mistral'],
        cohere_api_key: keyMap['cohere'],
        openrouter_api_key: keyMap['openrouter'],
        selected_local_model: config.selectedLocalModel,
        ollama_model: config.selectedLocalModel,
        tunnel_url: config.tunnelUrl,
      });

      // Persist onboarding completion flag to localStorage
      try {
        localStorage.setItem('raise_onboarding_completed', 'true');
        if (typeof window !== 'undefined' && window.history?.replaceState) {
          const cleanUrl = window.location.pathname + (window.location.hash.split('?')[0] || '');
          window.history.replaceState({}, document.title, cleanUrl);
        }
      } catch {}
    } catch {
      // Do not block app launch even if config sync encounters offline endpoint
    } finally {
      setIsSaving(false);
      completeFirstRun();
      setOpen(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-3 sm:p-5 animate-in fade-in duration-200">
      {/* Centered Modal Container */}
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-[#0e1017] border border-white/10 shadow-[0_0_60px_-15px_rgba(99,102,241,0.35)] overflow-hidden text-slate-100 font-sans shrink-0 ring-1 ring-white/5">
        {/* Top Header */}
        <div className="h-16 px-6 border-b border-white/10 bg-[#131624] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner shrink-0">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-tight text-white uppercase font-mono leading-none">
                  Control Center
                </h2>
                {isSetupMode ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
                    <Sparkles className="w-2.5 h-2.5 text-indigo-400" />
                    First-Time Setup
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono">
                    Workstation Active
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 font-mono mt-1">
                Configure Cloud AI Providers (Groq, Gemini, Mistral) & Local Acceleration
              </p>
            </div>
          </div>
          {isSetupMode && !hasConfiguredKey ? (
            <span
              className="text-[10px] font-mono text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-md shrink-0"
              title="Configure an AI engine before launching"
            >
              Setup Required
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="w-8 h-8 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center shrink-0 border border-transparent hover:border-white/10"
              aria-label="Close Control Center"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* First-Time Setup Welcome Banner */}
        {isSetupMode && (
          <div className="bg-gradient-to-r from-indigo-950/60 via-purple-950/40 to-slate-900/60 border-b border-indigo-500/20 px-6 py-2.5 flex items-center justify-between text-xs shrink-0">
            <div className="flex items-center gap-2 text-indigo-200">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
              <span>
                <strong>Quick Start:</strong> Enter your free <strong>Gemini Flash</strong> or{' '}
                <strong>Groq</strong> API key in Step 2 to query academic papers immediately
                without downloading GPU weights.
              </span>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className="text-[11px] font-bold text-indigo-300 hover:text-white underline underline-offset-2 shrink-0 ml-3 cursor-pointer"
            >
              Configure Provider &rarr;
            </button>
          </div>
        )}

        {/* Enhanced Visual Stepper Navigation */}
        <div className="h-14 border-b border-white/10 bg-[#10131e] px-4 sm:px-6 flex items-center gap-2 overflow-x-auto scrollbar-none shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`group h-9 flex items-center gap-2.5 px-3.5 rounded-xl transition-all shrink-0 cursor-pointer text-xs ${
                  isActive
                    ? 'bg-white text-black font-bold shadow-md ring-1 ring-white/20'
                    : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                {/* Step status indicator pill */}
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono transition-colors ${
                    isActive
                      ? 'bg-black text-white font-bold'
                      : tab.isCompleted
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-white/10 text-slate-400 border border-white/10'
                  }`}
                >
                  {tab.isCompleted && !isActive ? (
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  ) : (
                    tab.stepNumber
                  )}
                </span>
                <Icon
                  className={`w-3.5 h-3.5 ${isActive ? 'text-black' : 'text-slate-400 group-hover:text-white'}`}
                />
                <span className="truncate">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Scrollable Step Content Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-5 sm:p-6 space-y-5 bg-[#0e1017] min-h-0">
          {activeTab === 'platform' && <PlatformStep />}
          {activeTab === 'models' && <EngineStep />}
          {activeTab === 'launch' && <LaunchStep />}
        </div>

        {/* Refined Navigation Footer */}
        <div className="h-16 flex items-center justify-between px-5 sm:px-6 border-t border-white/10 bg-[#131624] shrink-0">
          <div>
            {currentTabIdx > 0 && (
              <button
                type="button"
                onClick={handleBack}
                className="px-4 py-2 rounded-xl border border-white/15 bg-white/5 text-xs font-semibold text-slate-200 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              >
                &larr; Back
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {connectNotice && (
              <span
                className={`text-xs font-mono font-medium max-w-[220px] truncate ${
                  connectNotice.includes('Connected')
                    ? 'text-emerald-400'
                    : connectNotice.includes('Testing') || connectNotice.includes('Probing')
                      ? 'text-amber-400 animate-pulse'
                      : 'text-rose-400'
                }`}
              >
                {connectNotice}
              </span>
            )}

            {activeTab === 'platform' && !isConnected && (
              <button
                type="button"
                disabled={isConnecting}
                onClick={handleProbeBackend}
                className={`px-3.5 py-2 rounded-xl text-xs transition-all font-bold cursor-pointer active:scale-95 flex items-center gap-1.5 border border-white/20 bg-white/10 hover:bg-white/15 text-white ${
                  isConnecting ? 'opacity-70 cursor-wait' : ''
                }`}
              >
                {isConnecting ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Zap className="w-3.5 h-3.5 fill-white text-white" />
                )}
                <span>{isConnecting ? 'Probing...' : 'Probe Localhost (:8000)'}</span>
              </button>
            )}

            {activeTab !== 'launch' && hasConfiguredKey && (
              <button
                type="button"
                onClick={handleFinalStart}
                className="px-3.5 py-2 rounded-xl border border-white/20 bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs font-semibold transition-all cursor-pointer active:scale-95 flex items-center gap-1.5"
                title="Launch directly with current settings"
              >
                <Check className="w-3.5 h-3.5 text-emerald-400 stroke-[2.5]" />
                <span className="hidden sm:inline">Quick Launch</span>
              </button>
            )}

            {activeTab !== 'launch' ? (
              <button
                type="button"
                onClick={handleNext}
                className="px-5 py-2 rounded-xl text-xs transition-all font-bold bg-white hover:bg-slate-200 text-black cursor-pointer shadow-sm active:scale-95"
              >
                {activeTab === 'platform' ? 'Configure Engine \u2192' : 'Next \u2192'}
              </button>
            ) : !hasConfiguredKey ? (
              <button
                type="button"
                onClick={() => setActiveTab('models')}
                className="px-5 py-2 rounded-xl text-xs transition-all font-bold bg-amber-400 hover:bg-amber-300 text-black cursor-pointer shadow-sm active:scale-95 flex items-center gap-1.5"
              >
                <span>Configure Engine First &rarr;</span>
              </button>
            ) : (
              <button
                type="button"
                disabled={isSaving}
                onClick={handleFinalStart}
                className="px-6 py-2 rounded-xl bg-white hover:bg-slate-200 text-black font-bold text-xs transition-all cursor-pointer active:scale-95 shadow-sm flex items-center gap-2 disabled:opacity-50"
              >
                {isSaving ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                ) : (
                  <Zap className="w-3.5 h-3.5 fill-black text-black" />
                )}
                <span>Launch App</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
