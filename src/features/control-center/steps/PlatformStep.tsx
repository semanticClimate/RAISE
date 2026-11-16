import {
  Check,
  ChevronDown,
  ChevronUp,
  Laptop,
  Terminal,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useState } from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { TargetPlatform } from '../types';

export const PlatformStep: React.FC = () => {
  const { hardware, config, updateConfig } = useControlCenterStore();
  const { appMode, latencyMs } = useModeStore();
  const isConnected = appMode === 'connected' || appMode === 'degraded';
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);

  const clientOSLabel =
    hardware?.platform === 'macos'
      ? 'macOS (Apple Silicon)'
      : hardware?.platform === 'windows'
        ? 'Windows'
        : hardware?.platform === 'linux'
          ? 'Linux'
          : 'macOS (Apple Silicon)';

  const platforms: {
    id: TargetPlatform;
    label: string;
    sub: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    {
      id: 'macos',
      label: 'macOS',
      sub: 'Metal',
      icon: Laptop,
    },
    {
      id: 'windows',
      label: 'Windows',
      sub: 'CUDA / DirectML',
      icon: Laptop,
    },
    {
      id: 'linux',
      label: 'Linux',
      sub: 'CUDA / ROCm',
      icon: Terminal,
    },
  ];

  const currentPlatform = platforms.find((p) => p.id === config.targetPlatform) || platforms[0];
  const CurrentIcon = currentPlatform.icon;

  return (
    <div className="space-y-2.5 animate-in fade-in-50 duration-150">
      <div>
        <h3 className="text-sm font-bold text-white tracking-tight">Device & Platform</h3>
      </div>

      {/* Target Operating System Selector */}
      <div className="rounded-xl bg-[#111111] border border-[#292929] overflow-hidden">
        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsSelectorOpen(!isSelectorOpen)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              setIsSelectorOpen(!isSelectorOpen);
            }
          }}
          className="p-2.5 sm:p-3 flex items-center justify-between cursor-pointer hover:bg-[#171717] transition-colors"
        >
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#171717] border border-[#292929] flex items-center justify-center text-[#FFFFFF] shrink-0">
              <CurrentIcon className="w-3.5 h-3.5 text-[#FFFFFF]" />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[#FFFFFF]">{currentPlatform.label}</span>
              <span className="text-[11px] text-[#A3A3A3] font-mono">({currentPlatform.sub})</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-xs font-semibold px-2 py-0.5 rounded-md border border-[#292929] bg-[#171717] hover:bg-[#292929] text-[#FFFFFF] transition-all cursor-pointer"
            >
              {isSelectorOpen ? 'Close' : 'Switch'}
            </button>
            {isSelectorOpen ? (
              <ChevronUp className="w-3.5 h-3.5 text-[#A3A3A3]" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 text-[#A3A3A3]" />
            )}
          </div>
        </div>

        {isSelectorOpen && (
          <div className="border-t border-[#292929] bg-[#0A0A0A] p-2 space-y-1 animate-in slide-in-from-top-2 duration-150">
            <div className="text-[11px] font-mono text-[#A3A3A3] px-2 pb-0.5">
              Select deployment environment:
            </div>
            {platforms.map((p) => {
              const Icon = p.icon;
              const isSelected = config.targetPlatform === p.id;
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    updateConfig({ targetPlatform: p.id });
                    setIsSelectorOpen(false);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      updateConfig({ targetPlatform: p.id });
                      setIsSelectorOpen(false);
                    }
                  }}
                  className={`p-2 rounded-lg border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-[#FFFFFF] text-[#000000] border-[#FFFFFF] font-bold'
                      : 'bg-[#171717] border-[#292929] text-[#A3A3A3] hover:border-[#FFFFFF]/20 hover:text-[#FFFFFF]'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <Icon className={`w-3.5 h-3.5 ${isSelected ? 'text-[#000000]' : 'text-[#A3A3A3]'}`} />
                    <div>
                      <div className="text-xs font-bold">{p.label}</div>
                      <div
                        className={`text-[10px] ${isSelected ? 'text-[#000000]/80' : 'text-[#A3A3A3]'}`}
                      >
                        {p.sub}
                      </div>
                    </div>
                  </div>

                  {isSelected && <Check className="w-3.5 h-3.5 text-[#000000] stroke-[3]" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Hardware Telemetry Specs: Clean 2-Card Layout (Platform & Acceleration) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="p-2.5 sm:p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-0.5">
          <div className="flex items-center gap-1.5 text-[11px] text-[#A3A3A3]">
            <Laptop className="w-3.5 h-3.5 text-[#FFFFFF]" />
            <span>Platform</span>
          </div>
          <div className="text-xs font-bold text-[#FFFFFF] truncate">
            {hardware?.osName || clientOSLabel}
          </div>
        </div>

        <div className="p-2.5 sm:p-3 rounded-xl bg-[#111111] border border-[#292929] space-y-0.5">
          <div className="flex items-center gap-1.5 text-[11px] text-[#A3A3A3]">
            <Zap className="w-3.5 h-3.5 text-[#FFFFFF]" />
            <span>Acceleration</span>
          </div>
          <div className="text-xs font-bold text-[#FFFFFF]">
            {config.targetPlatform === 'macos' ? 'Metal Active' : hardware?.hasMetalOrCuda ? 'CUDA / ROCm' : 'CPU'}
          </div>
        </div>
      </div>

      {/* Local Backend Engine Service Card */}
      <div className="p-2.5 sm:p-3 rounded-xl bg-[#111111] border border-[#292929] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            data-testid="connection-status-dot"
            className={`relative inline-flex rounded-full h-2 w-2 shrink-0 transition-colors ${
              isConnected
                ? 'bg-[#FFFFFF] shadow-[0_0_8px_rgba(255,255,255,0.8)]'
                : 'bg-[#292929] ring-1 ring-[#FFFFFF]/10'
            }`}
          />
          <div>
            <div className="text-xs font-bold text-[#FFFFFF] flex items-center gap-2">
              <span>Backend Gateway</span>
              <span className="text-[11px] font-mono text-[#A3A3A3] font-normal">
                {isConnected ? '127.0.0.1:8000' : 'Offline (:8000)'}
              </span>
              {isConnected && latencyMs ? (
                <span className="text-[10px] font-mono text-[#A3A3A3]">({latencyMs}ms)</span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-[#FFFFFF] animate-pulse' : 'bg-[#292929]'}`} />
          <span className={isConnected ? 'text-[#FFFFFF] font-semibold' : 'text-[#A3A3A3] font-semibold'}>
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </div>
  );
};
