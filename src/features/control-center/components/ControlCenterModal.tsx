import {
  Cpu,
  Database,
  Laptop,
  Layers,
  LayoutDashboard,
  RefreshCw,
  RotateCcw,
  X,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useScrollLock } from '../../../hooks';
import { useModeStore } from '../../../stores/modeStore';
import { detectHostOS, platformAdapter } from '../services/platformAdapter';
import { DatabaseStep } from '../steps/DatabaseStep';
import { EngineStep } from '../steps/EngineStep';
import { NeuralStep } from '../steps/NeuralStep';
import { OverviewStep } from '../steps/OverviewStep';
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

  // Load live hardware telemetry and accurately synchronize host OS on mount/open
  useEffect(() => {
    if (isOpen) {
      useModeStore.getState().runCapabilityProbe();
      const hostOS = detectHostOS();
      if (hostOS && config.targetPlatform !== hostOS && !useControlCenterStore.getState().isDirty) {
        updateConfig({ targetPlatform: hostOS });
      }

      useControlCenterStore.getState().syncBackendConfig();
      useControlCenterStore.getState().syncEnvCredentials();
      platformAdapter.getHardware().then((hw) => {
        const detected = hw.platform ? (hw.platform as any) : hostOS;
        const displayOs = hw.os_name || (detected === 'macos' ? 'macOS (Apple Silicon)' : detected === 'windows' ? 'Windows' : 'Linux');
        setHardware({
          platform: detected,
          osName: displayOs,
          totalRamGb: hw.total_ram_gb || 16.0,
          cpuCores: hw.cpu_cores || 8,
          freeRamGb: hw.free_ram_gb,
          gpuName: hw.gpu?.details || (hw as any).gpu_name || (detected === 'macos' ? 'Apple MPS' : detected === 'windows' ? 'DirectML / NVIDIA' : 'ROCm / NVIDIA / CPU'),
          hasMetalOrCuda: Boolean(hw.has_metal_or_cuda ?? (detected === 'macos' || detected === 'windows')),
        });
        if (!useControlCenterStore.getState().isDirty) {
          updateConfig({ targetPlatform: detected });
        }
      });
    }
  }, [isOpen]);

  useScrollLock(isOpen);
  if (!isOpen) return null;

  // Track completion state of each step
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
    },
    {
      id: 'models' as const,
      label: 'Inference',
      icon: Cpu,
    },
    {
      id: 'neural' as const,
      label: 'Neural',
      icon: Layers,
    },
    {
      id: 'databases' as const,
      label: 'Storage',
      icon: Database,
    },
    {
      id: 'overview' as const,
      label: 'Overview',
      icon: LayoutDashboard,
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
      case 'overview':
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
      setActiveTab('overview');
    } else {
      handleFinalStart();
    }
  };

  const handleBack = () => {
    if (currentTabIdx > 0) {
      setActiveTab(tabs[currentTabIdx - 1].id);
    }
  };

  const contentWrapperRef = useRef<HTMLDivElement>(null);
  const [modalHeight, setModalHeight] = useState<number | undefined>(undefined);

  useLayoutEffect(() => {
    const el = contentWrapperRef.current;
    if (!el) return;

    const updateHeight = () => {
      // Natural content height + fixed chrome (56px header + 44px tabs + 56px footer = 156px)
      const contentH = el.scrollHeight;
      const chromeH = 156;
      const totalH = contentH + chromeH;
      const maxH = typeof window !== 'undefined' ? window.innerHeight * 0.92 : 780;
      const minH = 440;
      const finalH = Math.min(maxH, Math.max(minH, totalH));
      setModalHeight(Math.round(finalH));
    };

    updateHeight();

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        updateHeight();
      });
      resizeObserver.observe(el);
    }

    window.addEventListener('resize', updateHeight);

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      window.removeEventListener('resize', updateHeight);
    };
  }, [activeTab]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#000000]/40 backdrop-blur-md p-3 sm:p-5 animate-in fade-in duration-150">
      <div
        style={modalHeight ? { height: `${modalHeight}px` } : undefined}
        className="relative w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl bg-[#0A0A0A] border border-[#292929] shadow-2xl overflow-hidden text-[#FFFFFF] font-sans shrink-0 transition-[height] duration-300 ease-out"
      >
        {/* Top Header - Strict Monochrome */}
        <div className="h-14 px-5 sm:px-6 border-b border-[#292929] bg-[#0A0A0A] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
              <Zap className="w-3.5 h-3.5 text-[#FFFFFF]" />
            </div>
            <div>
              <h1 className="text-lg sm:text-xl font-semibold tracking-tight text-[#FFFFFF] leading-tight">
                Control Center
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {isDirty ? (
              <button
                type="button"
                onClick={resetToBaseline}
                className="w-8 h-8 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer flex items-center justify-center border border-[#292929] group"
                aria-label="Reset Changes"
                title="Reset all changes to server baseline"
              >
                <RotateCcw className="w-4 h-4 transition-transform group-hover:-rotate-45 text-[#FFFFFF]" />
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
                className="w-8 h-8 rounded-lg text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer flex items-center justify-center border border-transparent hover:border-[#292929]"
                aria-label="Close Control Center"
                title="Close Control Center"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Segmented Navigation Tab Bar - Strict Monochrome */}
        <div className="h-11 border-b border-[#292929] bg-[#0A0A0A] px-4 sm:px-6 flex items-center gap-1.5 overflow-x-auto scrollbar-none no-scrollbar [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden shrink-0">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`h-7.5 flex items-center gap-2 px-3 rounded-lg transition-all shrink-0 cursor-pointer text-xs ${
                  isActive
                    ? 'bg-[#FFFFFF] text-[#000000] font-semibold shadow-sm'
                    : 'text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717]'
                }`}
              >
                <Icon
                  className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-[#000000]' : 'text-[#A3A3A3]'}`}
                />
                <span className="truncate">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Step Content Body (Compact, hidden scrollbar with preserved scroll functionality) */}
        <div className="flex-1 overflow-y-auto overscroll-contain px-5 sm:px-6 bg-[#0A0A0A] min-h-0 no-scrollbar scrollbar-none [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          <div ref={contentWrapperRef} className="py-3.5 sm:py-4 space-y-3.5">
            {activeTab === 'overview' && <OverviewStep />}
            {activeTab === 'models' && <EngineStep />}
            {activeTab === 'neural' && <NeuralStep />}
            {activeTab === 'databases' && <DatabaseStep />}
            {activeTab === 'platform' && <PlatformStep />}
          </div>
        </div>

        {/* Refined Navigation Footer - Strict Monochrome */}
        <div className="h-14 flex items-center justify-between px-5 sm:px-6 border-t border-[#292929] bg-[#0A0A0A] shrink-0">
          <div>
            {currentTabIdx > 0 && (
              <button
                type="button"
                onClick={handleBack}
                className="px-4 py-2 rounded-lg border border-[#292929] bg-[#111111] text-xs font-medium text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#171717] transition-colors cursor-pointer"
              >
                &larr; Back
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {stepBlockReason && (
              <span className="text-xs font-mono text-[#A3A3A3] hidden sm:inline-flex items-center gap-1.5 bg-[#171717] border border-[#292929] px-2.5 py-1 rounded-md">
                <span className="w-1.5 h-1.5 rounded-full bg-[#FFFFFF]" />
                <span>{stepBlockReason}</span>
              </span>
            )}

            {connectNotice && (
              <span className="text-xs font-mono text-[#A3A3A3] max-w-[240px] truncate">
                {connectNotice}
              </span>
            )}

            {/* Navigation Buttons: Next &rarr; on prior steps, Start ONLY on overview */}
            {activeTab !== 'overview' ? (
              <button
                type="button"
                disabled={!isCurrentStepReady}
                onClick={handleNext}
                className={`px-4 py-2 rounded-lg text-xs font-medium border border-[#292929] bg-[#111111] hover:bg-[#171717] text-[#FFFFFF] transition-all cursor-pointer ${
                  isCurrentStepReady ? '' : 'opacity-40 cursor-not-allowed'
                }`}
              >
                <span>Next &rarr;</span>
              </button>
            ) : (
              <button
                type="button"
                disabled={isSaving || isWarmingUp || !hasConfiguredKey || !isConnected}
                onClick={handleFinalStart}
                className={`px-5 py-2 rounded-lg font-semibold text-xs transition-all active:scale-95 shadow-sm flex items-center gap-2 ${
                  hasConfiguredKey && isConnected && !isSaving && !isWarmingUp
                    ? 'bg-[#FFFFFF] hover:bg-[#FFFFFF]/90 text-[#000000] cursor-pointer'
                    : 'bg-[#171717] text-[#A3A3A3] border border-[#292929] cursor-not-allowed opacity-50'
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
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#000000]" />
                ) : (
                  <Zap className="w-3.5 h-3.5 fill-[#000000] text-[#000000]" />
                )}
                <span>
                  {isWarmingUp
                    ? 'Warming Up...'
                    : isSaving
                    ? 'Saving...'
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
