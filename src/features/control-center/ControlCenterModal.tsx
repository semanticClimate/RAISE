import { Check, Cpu, Laptop, RefreshCw, X, Zap } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useScrollLock } from '../../hooks';
import { useModeStore } from '../../stores/modeStore';
import { platformAdapter } from './services/platformAdapter';
import { EngineStep } from './steps/EngineStep';
import { LaunchStep } from './steps/LaunchStep';
import { PlatformStep } from './steps/PlatformStep';
import { useControlCenterStore } from './store/useControlCenterStore';

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
        // Auto-correct if previously persisted as 'web', 'ios', or 'android'
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

  // Lock background body scroll while Control Center modal is open
  useScrollLock(isOpen);

  if (!isOpen) return null;

  // Streamlined 3-step setup: Platform -> Engine -> Launch
  const tabs: {
    id: 'platform' | 'models' | 'launch';
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    { id: 'platform', label: '1. Platform & Device', icon: Laptop },
    { id: 'models', label: '2. Intelligence Engine', icon: Cpu },
    { id: 'launch', label: '3. Summary & Launch', icon: Zap },
  ];

  const currentTabIdx = tabs.findIndex((t) => t.id === activeTab);

  const handleNext = () => {
    if (currentTabIdx < tabs.length - 1) {
      setActiveTab(tabs[currentTabIdx + 1].id);
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
    setConnectNotice('Probing local backend (127.0.0.1:8000)...');
    try {
      const result = await testConnection('http://127.0.0.1:8000');
      if (result.success) {
        setConnectNotice('Connected to local backend!');
        setTimeout(() => setConnectNotice(null), 1500);
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
    } catch {
      // Do not block app launch even if config sync encounters offline endpoint
    } finally {
      setIsSaving(false);
      completeFirstRun();
      setOpen(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-3 sm:p-4 animate-in fade-in duration-150">
      {/* Centered Modal Window */}
      <div className="relative w-full max-w-3xl max-h-[88vh] flex flex-col rounded-2xl bg-[#0e1017] border border-white/10 shadow-[0_0_50px_-10px_rgba(99,102,241,0.25)] overflow-hidden text-slate-100 font-sans shrink-0">
        {/* Top Header */}
        <div className="h-14 sm:h-16 px-5 sm:px-6 border-b border-white/10 bg-[#131622] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-tight text-white uppercase font-mono leading-none">
                Control Center
              </h2>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                Research Workstation Setup
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="w-8 h-8 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center shrink-0"
            aria-label="Close Control Center"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Stepper Navigation */}
        <div className="h-12 border-b border-white/10 bg-[#10121b] px-4 sm:px-6 flex items-center gap-2 overflow-x-auto scrollbar-none shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`h-8 flex items-center gap-2 px-3.5 text-xs font-semibold rounded-lg transition-all shrink-0 cursor-pointer ${
                  isActive
                    ? 'bg-white text-black font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/10'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Scrollable Step Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-4 sm:space-y-6 bg-[#0e1017] min-h-0">
          {activeTab === 'platform' && <PlatformStep />}
          {activeTab === 'models' && <EngineStep />}
          {activeTab === 'launch' && <LaunchStep />}
        </div>

        {/* Bottom Navigation Footer */}
        <div className="h-16 flex items-center justify-between px-4 sm:px-6 border-t border-white/10 bg-[#131622] shrink-0">
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

          <div className="flex items-center gap-2.5 sm:gap-3">
            {connectNotice && (
              <span
                className={`text-xs font-mono font-medium max-w-[200px] truncate ${
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

            {/* Quick Launch shortcut available on all steps */}
            {activeTab !== 'launch' && (
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
