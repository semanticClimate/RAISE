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
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">Device & Platform</h3>
      </div>

      {/* Target Operating System Selector */}
      <div className="rounded-xl bg-[#131622] border border-white/10 overflow-hidden">
        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsSelectorOpen(!isSelectorOpen)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              setIsSelectorOpen(!isSelectorOpen);
            }
          }}
          className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center text-white shrink-0">
              <CurrentIcon className="w-4 h-4 text-white" />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white">{currentPlatform.label}</span>
              <span className="text-[11px] text-slate-400 font-mono">({currentPlatform.sub})</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-xs font-semibold px-2.5 py-1 rounded-md border border-white/20 bg-white/10 hover:bg-white/15 text-white transition-all cursor-pointer"
            >
              {isSelectorOpen ? 'Close' : 'Switch'}
            </button>
            {isSelectorOpen ? (
              <ChevronUp className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            )}
          </div>
        </div>

        {isSelectorOpen && (
          <div className="border-t border-white/10 bg-[#0e1017] p-2.5 space-y-1.5 animate-in slide-in-from-top-2 duration-150">
            <div className="text-[11px] font-mono text-slate-400 px-2 pb-1">
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
                  className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-white text-black border-white font-bold'
                      : 'bg-white/5 border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isSelected ? 'text-black' : 'text-slate-300'}`} />
                    <div>
                      <div className="text-xs font-bold">{p.label}</div>
                      <div
                        className={`text-[10px] ${isSelected ? 'text-slate-800' : 'text-slate-400'}`}
                      >
                        {p.sub}
                      </div>
                    </div>
                  </div>

                  {isSelected && <Check className="w-4 h-4 text-black stroke-[3]" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Hardware Telemetry Specs: Clean 2-Card Layout (Platform & Acceleration) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Laptop className="w-3.5 h-3.5 text-white" />
            <span>Platform</span>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {hardware?.osName || clientOSLabel}
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Zap className="w-3.5 h-3.5 text-white" />
            <span>Acceleration</span>
          </div>
          <div className="text-xs font-bold text-white">
            {config.targetPlatform === 'macos' ? 'Metal Active' : hardware?.hasMetalOrCuda ? 'CUDA / ROCm' : 'CPU'}
          </div>
        </div>
      </div>

      {/* Local Backend Engine Service Card: Clean live status display */}
      <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            data-testid="connection-status-dot"
            className={`relative inline-flex rounded-full h-2.5 w-2.5 shrink-0 transition-colors ${
              isConnected
                ? 'bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)]'
                : 'bg-zinc-600 ring-2 ring-white/10'
            }`}
          />
          <div>
            <div className="text-xs font-bold text-white flex items-center gap-2">
              <span>Backend Gateway</span>
              <span className="text-[11px] font-mono text-slate-400 font-normal">
                {isConnected ? '127.0.0.1:8000' : 'Offline (Port 8000)'}
              </span>
              {isConnected && latencyMs ? (
                <span className="text-[10px] font-mono text-zinc-300">({latencyMs}ms)</span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-white animate-pulse' : 'bg-zinc-600'}`} />
          <span className={isConnected ? 'text-white font-semibold' : 'text-zinc-500 font-semibold'}>
            {isConnected ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>
    </div>
  );
};
