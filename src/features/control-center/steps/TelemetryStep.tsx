import { Check, Copy, Play, Radio, Terminal, Trash2 } from 'lucide-react';
import type React from 'react';
import { useTelemetryLogs } from '../hooks/useTelemetryLogs';
import { TelemetryMetricCards } from './TelemetryMetricCards';

export const TelemetryStep: React.FC = () => {
  const {
    stats,
    isConnected,
    logs,
    copied,
    handleTestPing,
    handleCopy,
    handleClearLogs,
  } = useTelemetryLogs();

  return (
    <div className="space-y-3.5 animate-in fade-in duration-150 text-[#FFFFFF] max-w-4xl">
      <div>
        <h3 className="text-sm font-semibold text-[#FFFFFF] flex items-center gap-2">
          <span>System Telemetry & Live Status</span>
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium ${
              isConnected
                ? 'bg-[#171717] text-[#FFFFFF] border border-[#292929]'
                : 'bg-[#171717] text-[#A3A3A3] border border-[#292929]'
            }`}
          >
            <Radio
              className={`w-2.5 h-2.5 ${isConnected ? 'text-[#FFFFFF]' : 'text-[#A3A3A3]'}`}
            />
            {isConnected ? 'Connected' : 'Standalone'}
          </span>
        </h3>
        <p className="text-xs text-[#A3A3A3] mt-0.5">
          Real-time server communication health, request throughput, and background events.
        </p>
      </div>

      <TelemetryMetricCards isConnected={isConnected} stats={stats} />

      <div className="rounded-xl border border-[#292929] bg-[#0A0A0A] overflow-hidden">
        <div className="h-9 px-3.5 bg-[#111111] border-b border-[#292929] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-[#A3A3A3]" />
            <span className="text-xs font-medium text-[#A3A3A3]">
              Live Event Feed ({logs.length})
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleTestPing}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-[#FFFFFF] hover:bg-[#1C1C1C] transition-colors cursor-pointer border border-[#292929]"
            >
              <Play className="w-2.5 h-2.5 text-[#FFFFFF]" />
              <span>Send Ping</span>
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#1C1C1C] transition-colors cursor-pointer border border-[#292929]"
            >
              {copied ? (
                <Check className="w-2.5 h-2.5 text-[#FFFFFF]" />
              ) : (
                <Copy className="w-2.5 h-2.5" />
              )}
              <span>{copied ? 'Copied' : 'Export'}</span>
            </button>
            <button
              type="button"
              onClick={handleClearLogs}
              className="w-6 h-6 flex items-center justify-center rounded text-[#A3A3A3] hover:text-[#FFFFFF] hover:bg-[#1C1C1C] transition-colors cursor-pointer"
              title="Clear log feed"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>

        <div className="h-44 overflow-y-auto p-2.5 space-y-1 font-mono text-[11px] bg-[#050505]">
          {logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-[#A3A3A3] gap-1 select-none">
              <span className="text-xs">Listening for live pipeline events...</span>
              <span className="text-[10px]">
                Events stream automatically during research queries
              </span>
            </div>
          ) : (
            logs.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-2 px-2 py-1 rounded hover:bg-[#111111] transition-colors"
              >
                <span className="text-[#A3A3A3] shrink-0 text-[10px]">
                  {log.timestamp}
                </span>
                <span
                  className={`text-[9px] px-1 py-0.2 rounded shrink-0 font-semibold ${
                    log.type === 'PIPELINE'
                      ? 'bg-[#1F1F1F] text-[#FFFFFF] border border-[#333333]'
                      : log.type === 'SERVER'
                        ? 'bg-[#171717] text-[#D4D4D4] border border-[#292929]'
                        : log.type === 'CHECK'
                          ? 'bg-[#262626] text-[#FFFFFF] border border-[#383838]'
                          : 'bg-[#141414] text-[#A3A3A3] border border-[#242424]'
                  }`}
                >
                  {log.type}
                </span>
                <span
                  className={`break-all leading-tight ${
                    log.level === 'ERROR'
                      ? 'text-[#FFFFFF] underline decoration-neutral-500'
                      : log.level === 'WARN'
                        ? 'text-[#E5E5E5]'
                        : 'text-[#A3A3A3]'
                  }`}
                >
                  {log.message}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
