import {
  Check,
  ChevronDown,
  ChevronUp,
  Cpu,
  HardDrive,
  Laptop,
  RefreshCw,
  Terminal,
  Zap,
} from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useBackendConnection } from '../../../hooks/useBackendConnection';
import { Tooltip } from '../components/Tooltip';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { TargetPlatform } from '../types';

export const PlatformStep: React.FC = () => {
  const { hardware, config, updateConfig } = useControlCenterStore();
  const { appMode, latencyMs } = useModeStore();
  const isConnected = appMode === 'connected';
  const { connect, scanLocalPorts, isConnecting } = useBackendConnection();
  const [isSelectorOpen, setIsSelectorOpen] = useState(false);
  const [probeNotice, setProbeNotice] = useState<string | null>(null);

  const handleQuickLocalDetect = async () => {
    setProbeNotice('Probing 127.0.0.1:8000...');
    const res = await connect('http://127.0.0.1:8000');
    if (res.success) {
      setProbeNotice('Connected to 127.0.0.1:8000!');
      setTimeout(() => setProbeNotice(null), 3000);
    } else {
      const found = await scanLocalPorts();
      if (found) {
        setProbeNotice(`Connected to ${found}!`);
        setTimeout(() => setProbeNotice(null), 3000);
      } else {
        setProbeNotice('Backend offline on 127.0.0.1:8000. Start backend via ./START_RAISE.sh');
        setTimeout(() => setProbeNotice(null), 4000);
      }
    }
  };

  // Dynamic local time formatting (e.g., 7:25 PM)
  const [currentTime, setCurrentTime] = useState('');
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 30000);
    return () => clearInterval(interval);
  }, []);

  const clientOSLabel =
    hardware?.platform === 'macos'
      ? 'macOS'
      : hardware?.platform === 'windows'
        ? 'Windows'
        : hardware?.platform === 'linux'
          ? 'Linux'
          : 'Desktop';

  const platforms: {
    id: TargetPlatform;
    label: string;
    sub: string;
    icon: React.ComponentType<{ className?: string }>;
  }[] = [
    {
      id: 'macos',
      label: 'macOS',
      sub: 'Apple Silicon / Intel (Metal acceleration)',
      icon: Laptop,
    },
    {
      id: 'windows',
      label: 'Windows',
      sub: 'DirectML / CUDA acceleration',
      icon: Laptop,
    },
    {
      id: 'linux',
      label: 'Linux',
      sub: 'CUDA / ROCm Desktop',
      icon: Terminal,
    },
  ];

  const currentPlatform = platforms.find((p) => p.id === config.targetPlatform) || platforms[0];
  const CurrentIcon = currentPlatform.icon;

  return (
    <div className="space-y-4 animate-in fade-in-50 duration-150">
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">Device & Operating System</h3>
        <p className="text-xs text-slate-400 mt-0.5">
          Auto-detected local workstation environment with hardware acceleration.
        </p>
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
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400 font-mono">Active Target:</span>
                <span className="text-xs font-bold text-white">{currentPlatform.label}</span>
                <Tooltip
                  content={
                    <div className="space-y-1 font-mono text-[11px]">
                      <div className="font-bold text-white text-xs border-b border-white/10 pb-1">
                        {currentPlatform.label} Workstation
                      </div>
                      <div className="text-slate-300">{currentPlatform.sub}</div>
                    </div>
                  }
                />
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">{currentPlatform.sub}</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              className="text-xs font-semibold px-2.5 py-1 rounded-md border border-white/20 bg-white/10 hover:bg-white/15 text-white transition-all cursor-pointer"
            >
              {isSelectorOpen ? 'Close' : 'Switch OS'}
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

      {/* Hardware Telemetry Specs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Laptop className="w-3.5 h-3.5 text-indigo-400" />
            <span>Platform</span>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {hardware?.osName || clientOSLabel}
          </div>
        </div>

        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <HardDrive className="w-3.5 h-3.5 text-emerald-400" />
            <span>Host RAM</span>
          </div>
          <div className="text-xs font-bold text-white">
            {hardware?.totalRamGb ? `${hardware.totalRamGb} GB` : '8+ GB'}
          </div>
        </div>

        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span>CPU Cores</span>
          </div>
          <div className="text-xs font-bold text-white">
            {hardware?.cpuCores ? `${hardware.cpuCores} Cores` : '8 Cores'}
          </div>
        </div>

        <div className="p-3 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            <span>Acceleration</span>
          </div>
          <div className="text-xs font-bold text-white">
            {hardware?.hasMetalOrCuda ? 'Active' : 'CPU Mode'}
          </div>
        </div>
      </div>

      {/* Local Backend Engine Service Card */}
      <div className="p-4 rounded-xl bg-[#131622] border border-white/10 space-y-3">
        <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-white">Local Backend Gateway</span>
            <span
              data-testid="connection-status-dot"
              className={`relative inline-flex rounded-full h-2 w-2 shrink-0 transition-colors ${
                isConnected
                  ? 'bg-emerald-500 ring-2 ring-emerald-500/20'
                  : isConnecting
                    ? 'bg-amber-500 animate-pulse ring-2 ring-amber-500/20'
                    : 'bg-rose-500 ring-2 ring-rose-500/20'
              }`}
            />
            {isConnected ? (
              <span className="text-[11px] font-mono font-medium text-emerald-400">
                • Active (127.0.0.1:8000) {latencyMs ? `(${latencyMs}ms)` : ''}
              </span>
            ) : (
              <span className="text-[11px] font-mono font-medium text-rose-400">
                • Offline (127.0.0.1:8000)
              </span>
            )}
          </div>

          <button
            type="button"
            disabled={isConnecting}
            onClick={handleQuickLocalDetect}
            className="px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/15 text-slate-200 hover:text-white border border-white/15 text-[11px] font-mono transition-all cursor-pointer flex items-center gap-1.5"
            title="Probe local machine for port 8000"
          >
            <RefreshCw className={`w-3 h-3 ${isConnecting ? 'animate-spin' : ''}`} />
            <span>{isConnecting ? 'Probing...' : 'Probe Localhost'}</span>
          </button>
        </div>

        <div className="text-xs text-slate-300 leading-relaxed">
          {isConnected ? (
            <p className="text-emerald-300/90 font-mono text-[11.5px]">
              Connected to local RAISE backend engine on 127.0.0.1:8000. Low-latency loopback active.
            </p>
          ) : (
            <p className="text-amber-300/90 text-xs">
              {probeNotice ||
                'Local backend service is not detected on 127.0.0.1:8000. Start it via ./START_RAISE.sh (Mac/Linux) or START_RAISE.bat (Windows), then click Probe Localhost.'}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 pt-0.5 border-t border-white/5">
          <div className="font-mono text-[11px] text-slate-300">
            <span className="text-slate-400">Active System: </span>
            <strong>
              {clientOSLabel} • {currentTime || 'Active'}
            </strong>
          </div>
          <div className="font-mono text-[11px] text-slate-400">
            Port: <span className="text-slate-200">8000</span> (Loopback)
          </div>
        </div>
      </div>
    </div>
  );
};
