import {
  Activity,
  CheckCircle2,
  ChevronDown,
  Layers,
  Loader2,
  Radio,
  RefreshCw,
  Sliders,
  Wifi,
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useModeStore } from '../../stores/modeStore';
import { telemetryBridge } from '../../services/telemetryBridge';
import { useControlCenterStore } from '../control-center/store/useControlCenterStore';

export const GatewayStatusPill: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isRechecking, setIsRechecking] = useState(false);
  const [wsConnected, setWsConnected] = useState(() => telemetryBridge.getIsConnected());
  const popoverRef = useRef<HTMLDivElement>(null);

  const {
    appMode,
    isNeuralReady,
    readinessMessage,
    latencyMs,
    apiBaseUrl,
    isProbing,
    runCapabilityProbe,
    capabilities,
  } = useModeStore();

  const openControlCenter = useControlCenterStore((s) => s.setOpen);

  // Poll WebSocket telemetry status periodically
  useEffect(() => {
    const timer = setInterval(() => {
      setWsConnected(telemetryBridge.getIsConnected());
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  // Close popover on click outside or Escape
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const handleReprobe = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsRechecking(true);
    try {
      await runCapabilityProbe();
    } finally {
      setIsRechecking(false);
    }
  };

  const handleOpenCC = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsOpen(false);
    openControlCenter(true);
  };

  const isConnected = appMode === 'connected' || appMode === 'degraded';
  const isOffline = appMode === 'offline';
  const isWarming = isConnected && !isNeuralReady;

  return (
    <div className="relative inline-block" ref={popoverRef}>
      {/* Living Status Pill Button */}
      <button
        type="button"
        id="gatewayStatusPillBtn"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="Toggle Gateway Diagnostics"
        aria-expanded={isOpen}
        className={`group inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1 sm:py-1.2 rounded-full text-xs font-medium backdrop-blur-md transition-all cursor-pointer shadow-xs select-none active:scale-95 ${
          isOffline
            ? 'bg-rose-50/90 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border border-rose-200/80 dark:border-rose-800/50 hover:bg-rose-100/90 dark:hover:bg-rose-900/60'
            : isWarming
            ? 'bg-amber-50/90 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/50 hover:bg-amber-100/90 dark:hover:bg-amber-900/60'
            : 'bg-emerald-50/90 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/40 hover:bg-emerald-100/90 dark:hover:bg-emerald-900/50'
        }`}
        title={
          isOffline
            ? 'Backend Gateway offline. Click to view diagnostics and retry.'
            : isWarming
            ? readinessMessage || 'Warming up neural models on backend...'
            : `Gateway live: ${latencyMs}ms roundtrip latency`
        }
      >
        {/* Animated Pulse Indicator */}
        {isOffline ? (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500" />
          </span>
        ) : isWarming || isProbing ? (
          <Loader2 className="w-3 h-3 text-amber-500 animate-spin shrink-0" />
        ) : (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
        )}

        {/* Text Status Label */}
        <span className="tracking-tight whitespace-nowrap">
          {isOffline ? (
            <span>Gateway Offline · Retry</span>
          ) : isWarming ? (
            <span>Warming Neural Models...</span>
          ) : isProbing ? (
            <span>Connecting...</span>
          ) : (
            <span>
              {latencyMs > 0 && <span className="font-semibold">{latencyMs}ms · </span>}
              Gateway Ready
            </span>
          )}
        </span>

        {/* Subtle Dropdown Chevron */}
        <ChevronDown
          className={`w-3 h-3 text-slate-400 dark:text-slate-500 transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-slate-700 dark:text-slate-200' : 'group-hover:text-slate-600 dark:group-hover:text-slate-300'
          }`}
        />
      </button>

      {/* Floating Diagnostics Popover */}
      {isOpen && (
        <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 sm:left-auto sm:right-0 sm:translate-x-0 w-80 sm:w-88 rounded-2xl border border-slate-200/90 dark:border-white/10 bg-white/95 dark:bg-slate-900/95 shadow-xl backdrop-blur-xl z-50 p-4 animate-in fade-in zoom-in-95 duration-150">
          {/* Popover Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-white/10">
            <div className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-lg flex items-center justify-center border ${
                  isOffline
                    ? 'bg-rose-50 dark:bg-rose-950/60 border-rose-200 dark:border-rose-800 text-rose-600'
                    : isWarming
                    ? 'bg-amber-50 dark:bg-amber-950/60 border-amber-200 dark:border-amber-800 text-amber-600'
                    : 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200 dark:border-emerald-800 text-emerald-600'
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 dark:text-white leading-none">
                  Gateway Diagnostics
                </h4>
                <p className="text-[10px] text-slate-400 dark:text-slate-400 mt-0.5">
                  Real-time pipeline & telemetry status
                </p>
              </div>
            </div>

            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                isOffline
                  ? 'bg-rose-100/80 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 border-rose-300 dark:border-rose-800'
                  : isWarming
                  ? 'bg-amber-100/80 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                  : 'bg-emerald-100/80 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
              }`}
            >
              {isOffline ? 'Offline' : isWarming ? 'Warming' : 'Connected'}
            </span>
          </div>

          {/* Diagnostics Key-Value Grid */}
          <div className="py-3 space-y-2.5 text-xs">
            {/* Target Endpoint */}
            <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Wifi className="w-3.5 h-3.5" />
                <span>Target Gateway:</span>
              </span>
              <span className="font-mono text-[11px] font-medium text-slate-800 dark:text-slate-200 truncate max-w-[170px]">
                {apiBaseUrl || 'http://localhost:8000'}
              </span>
            </div>

            {/* WebSocket Telemetry Bus */}
            <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Radio className="w-3.5 h-3.5" />
                <span>WebSocket Bus:</span>
              </span>
              <span className="inline-flex items-center gap-1 font-medium">
                {wsConnected ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">Active</span>
                  </>
                ) : (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                    <span className="text-slate-400">Standby</span>
                  </>
                )}
              </span>
            </div>

            {/* Latency */}
            <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Activity className="w-3.5 h-3.5" />
                <span>Round-Trip Latency:</span>
              </span>
              <span className="font-semibold text-slate-800 dark:text-slate-200">
                {latencyMs > 0 ? `${latencyMs} ms` : isConnected ? '< 10 ms' : '—'}
              </span>
            </div>

            {/* Neural Inference Status */}
            <div className="flex items-center justify-between text-slate-600 dark:text-slate-300">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Layers className="w-3.5 h-3.5" />
                <span>Neural Pipeline:</span>
              </span>
              <span className="inline-flex items-center gap-1 font-medium">
                {isWarming ? (
                  <span className="text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Warming CUDA
                  </span>
                ) : isConnected ? (
                  <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    Ready
                  </span>
                ) : (
                  <span className="text-slate-400">Unavailable</span>
                )}
              </span>
            </div>

            {/* Server Details if available */}
            {capabilities && (
              <div className="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-white/5 space-y-1 text-[11px]">
                <div className="flex justify-between text-slate-500 dark:text-slate-400">
                  <span>SSE Streaming:</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {capabilities.sseStreamingAvailable ? 'Available' : 'Standard'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-500 dark:text-slate-400">
                  <span>Server Abort:</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {capabilities.serverAbortAvailable ? 'Supported' : 'Client-side'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Actions Footer */}
          <div className="flex items-center gap-2 pt-3 border-t border-slate-100 dark:border-white/10">
            <button
              type="button"
              onClick={handleReprobe}
              disabled={isRechecking || isProbing}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 transition-all cursor-pointer disabled:opacity-50 active:scale-95 shadow-2xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRechecking || isProbing ? 'animate-spin' : ''}`} />
              <span>{isRechecking || isProbing ? 'Probing...' : 'Re-probe'}</span>
            </button>

            <button
              type="button"
              onClick={handleOpenCC}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2.5 rounded-xl text-xs font-semibold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 border border-indigo-200 dark:border-indigo-800/60 transition-all cursor-pointer active:scale-95 shadow-2xs"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Control Center</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
