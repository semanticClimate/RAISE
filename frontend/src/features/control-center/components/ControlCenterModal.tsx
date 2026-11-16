import {
  CheckCircle2,
  Cpu,
  Database,
  Laptop,
  Layers,
  RefreshCw,
  RotateCcw,
  Sparkles,
  X,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useMemo } from 'react';
import { useScrollLock } from '../../../hooks';
import { useModeStore } from '../../../stores/modeStore';
import { detectHostOS, platformAdapter } from '../services/platformAdapter';
import { DatabaseStep } from '../steps/DatabaseStep';
import { EngineStep } from '../steps/EngineStep';
import { LaunchStep } from '../steps/LaunchStep';
import { NeuralStep } from '../steps/NeuralStep';
import { PlatformStep } from '../steps/PlatformStep';
import { useControlCenterStore } from '../store/useControlCenterStore';
import { useControlCenterSave } from '../hooks/useControlCenterSave';

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
    isDirty,
    resetToBaseline,
  } = useControlCenterStore();

  const { appMode } = useModeStore();
  const isConnected = appMode === 'connected' || appMode === 'degraded';

  const { isSaving, isWarmingUp, connectNotice, setConnectNotice, handleFinalStart } = useControlCenterSave(
    config,
    completeFirstRun,
    setOpen
  );

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

  // Load live hardware telemetry and accurately synchronize host OS on mount/open
  useEffect(() => {
    if (isOpen) {
      useModeStore.getState().runCapabilityProbe();
      const hostOS = detectHostOS();
      if (hostOS === 'macos' && config.targetPlatform !== 'macos') {
        updateConfig({ targetPlatform: 'macos' });
      }

      useControlCenterStore.getState().syncBackendConfig();
      useControlCenterStore.getState().syncEnvCredentials();
      platformAdapter.getHardware().then((hw) => {
        const detected = detectHostOS();
        setHardware({
          platform: detected,
          osName: detected === 'macos' ? 'macOS (Apple Silicon)' : hw.os_name || detected,
          totalRamGb: hw.total_ram_gb || 16.0,
          cpuCores: hw.cpu_cores || 8,
          freeRamGb: hw.free_ram_gb,
          gpuName: hw.gpu?.details || (hw as any).gpu_name || 'Apple MPS',
          hasMetalOrCuda: true,
        });
        updateConfig({ targetPlatform: detected });
      });
    }
  }, [isOpen]);

  useScrollLock(isOpen);
  if (!isOpen) return null;

  // Track completion state of each step for visual stepper badges
  const hasConfiguredKey =
    config.llmDeployment === 'local' ||
    config.llmMode?.startsWith('local_') ||
    Boolean(config.selectedLocalModel) ||
    (config.apiKeys || []).some(
      (k) => k?.key && k.key.trim().length > 0 && k.provider !== 'unknown'
    );

  const tabs = [
    {
      id: 'platform' as const,
      label: 'Device',
      icon: Laptop,
      isCompleted: Boolean(config.targetPlatform),
    },
    {
      id: 'models' as const,
      label: 'Models',
      icon: Cpu,
      isCompleted: hasConfiguredKey,
    },
    {
      id: 'neural' as const,
      label: 'Neural',
      icon: Layers,
      isCompleted: Boolean(config.embeddingModel && config.rerankerModel),
    },
    {
      id: 'databases' as const,
      label: 'Storage',
      icon: Database,
      isCompleted: true,
    },
    {
      id: 'launch' as const,
      label: 'Launch',
      icon: Zap,
      isCompleted: hasConfiguredKey,
    },
  ];

  const currentTabIdx = tabs.findIndex((t) => t.id === activeTab);

  const isCurrentStepReady = useMemo(() => {
    switch (activeTab) {
      case 'platform':
        return Boolean(config.targetPlatform);
      case 'models':
        return true;
      case 'neural':
        return Boolean(config.embeddingModel && config.rerankerModel);
      case 'databases':
      case 'launch':
      default:
        return true;
    }
  }, [activeTab, config.targetPlatform, config.embeddingModel, config.rerankerModel]);

  const stepBlockReason = useMemo(() => {
    if (activeTab === 'neural' && (!config.embeddingModel || !config.rerankerModel)) {
      return 'Select embedding & reranker models';
    }
    return null;
  }, [activeTab, config.embeddingModel, config.rerankerModel]);

  const handleNext = () => {
    if (!isCurrentStepReady) {
      if (stepBlockReason) {
        setConnectNotice(stepBlockReason);
        setTimeout(() => setConnectNotice(null), 4000);
      }
      return;
    }

    if (activeTab === 'platform') {
      setActiveTab('models');
    } else if (activeTab === 'models') {
      setActiveTab('neural');
    } else if (activeTab === 'neural') {
      setActiveTab('databases');
    } else if (activeTab === 'databases') {
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-3 sm:p-5 animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-[#0a0a0c] border border-white/15 shadow-[0_0_60px_-15px_rgba(255,255,255,0.12)] overflow-hidden text-slate-100 font-sans shrink-0 ring-1 ring-white/10">
        {/* Top Header */}
        <div className="h-16 px-6 border-b border-white/10 bg-gradient-to-r from-zinc-900 via-zinc-950 to-black shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center text-white shadow-inner shrink-0">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold tracking-tight text-white uppercase font-mono leading-none">
                  Control Center
                </h2>
                {isSetupMode && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-white/10 text-white border border-white/20 font-mono">
                    <Sparkles className="w-2.5 h-2.5 text-white" />
                    Setup
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isSetupMode && !hasConfiguredKey && (
              <span className="text-[10px] font-mono text-zinc-300 bg-white/5 border border-white/15 px-2 py-1 rounded-md">
                Key Required
              </span>
            )}
            {isDirty ? (
              <button
                type="button"
                onClick={resetToBaseline}
                className="w-8 h-8 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-white/10 group"
                aria-label="Reset Changes"
                title="Reset all changes to server settings"
              >
                <RotateCcw className="w-4 h-4 transition-transform group-hover:-rotate-45" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  try {
                    localStorage.setItem('raise_onboarding_completed', 'true');
                  } catch {}
                  setOpen(false);
                }}
                className="w-8 h-8 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-white/10"
                aria-label="Close Control Center"
                title="Close Control Center"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* First-Time Setup Welcome Banner */}
        {isSetupMode && !hasConfiguredKey && (
          <div className="bg-gradient-to-r from-zinc-900 via-zinc-950 to-black border-b border-white/10 px-6 py-2 flex items-center justify-between text-xs shrink-0">
            <div className="flex items-center gap-2 text-zinc-200">
              <Sparkles className="w-3.5 h-3.5 text-white shrink-0" />
              <span>Add an API key to start immediately.</span>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('models')}
              className="text-[11px] font-bold text-zinc-300 hover:text-white underline underline-offset-2 shrink-0 ml-3 cursor-pointer"
            >
              Configure &rarr;
            </button>
          </div>
        )}

        {/* Visual Stepper Navigation - NO step numbers (1, 2, 3, 4, 5) */}
        <div className="h-14 border-b border-white/10 bg-[#0c0d12] px-4 sm:px-6 flex items-center gap-2 overflow-x-auto scrollbar-none shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`group h-9 flex items-center gap-2 px-3.5 rounded-xl transition-all shrink-0 cursor-pointer text-xs ${
                  isActive
                    ? 'bg-white text-black font-bold shadow-md ring-1 ring-white/20'
                    : 'text-slate-400 hover:text-white hover:bg-white/5 border border-transparent'
                }`}
              >
                {tab.isCompleted && !isActive ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-zinc-300 shrink-0" />
                ) : (
                  <Icon
                    className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-black' : 'text-slate-400 group-hover:text-white'}`}
                  />
                )}
                <span className="truncate">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Scrollable Step Content Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-5 sm:p-6 space-y-5 bg-[#0a0a0c] min-h-0">
          {activeTab === 'platform' && <PlatformStep />}
          {activeTab === 'models' && <EngineStep />}
          {activeTab === 'neural' && <NeuralStep />}
          {activeTab === 'databases' && <DatabaseStep />}
          {activeTab === 'launch' && <LaunchStep />}
        </div>

        {/* Refined Navigation Footer */}
        <div className="h-16 flex items-center justify-between px-5 sm:px-6 border-t border-white/10 bg-gradient-to-r from-zinc-900 via-zinc-950 to-black shrink-0">
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
            {stepBlockReason && (
              <span className="text-[11px] font-mono text-zinc-300 hidden sm:inline-flex items-center gap-1.5 bg-white/5 border border-white/15 px-2.5 py-1 rounded-md">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                <span>{stepBlockReason}</span>
              </span>
            )}

            {connectNotice && (
              <span className="text-xs font-mono font-medium max-w-[240px] truncate text-zinc-300">
                {connectNotice}
              </span>
            )}

            {activeTab !== 'launch' ? (
              <button
                type="button"
                disabled={!isCurrentStepReady}
                onClick={handleNext}
                className={`px-5 py-2 rounded-xl text-xs transition-all font-bold shadow-sm active:scale-95 flex items-center gap-1.5 ${
                  isCurrentStepReady
                    ? 'bg-white hover:bg-zinc-200 text-black cursor-pointer'
                    : 'bg-white/10 text-slate-500 cursor-not-allowed opacity-50 border border-white/5'
                }`}
                title={stepBlockReason || undefined}
              >
                <span>
                  {activeTab === 'platform'
                    ? 'Configure Engine \u2192'
                    : activeTab === 'models'
                      ? 'Configure Neural \u2192'
                      : 'Next \u2192'}
                </span>
              </button>
            ) : !hasConfiguredKey ? (
              <button
                type="button"
                onClick={() => setActiveTab('models')}
                className="px-5 py-2 rounded-xl text-xs transition-all font-bold bg-white hover:bg-zinc-200 text-black cursor-pointer shadow-sm active:scale-95 flex items-center gap-1.5"
              >
                <span>Configure Engine First &rarr;</span>
              </button>
            ) : (
              <button
                type="button"
                disabled={isSaving || isWarmingUp || !hasConfiguredKey || !isConnected}
                onClick={handleFinalStart}
                className={`px-6 py-2 rounded-xl font-bold text-xs transition-all active:scale-95 shadow-sm flex items-center gap-2 ${
                  hasConfiguredKey && isConnected && !isSaving && !isWarmingUp
                    ? 'bg-white hover:bg-zinc-200 text-black cursor-pointer'
                    : 'bg-white/10 text-slate-500 cursor-not-allowed opacity-50'
                }`}
                title={
                  !isConnected
                    ? 'Backend Gateway is offline. Start backend on port 8000.'
                    : !hasConfiguredKey
                      ? 'Configure an inference engine or API key before starting.'
                      : isWarmingUp
                        ? 'Warming up neural models in backend...'
                        : isSaving
                          ? 'Saving configuration...'
                          : 'Start'
                }
              >
                {isSaving || isWarmingUp ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                ) : (
                  <Zap className="w-3.5 h-3.5 fill-black text-black" />
                )}
                <span>
                  {isWarmingUp
                    ? 'Warming Up Neural Stack...'
                    : isSaving
                      ? 'Saving Settings...'
                      : isConnected
                        ? 'Start'
                        : 'Backend Offline'}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
