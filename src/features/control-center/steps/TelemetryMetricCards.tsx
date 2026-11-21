import type React from 'react';
import type { TelemetryBusSnapshot } from '../../../types/telemetry';

export interface TelemetryMetricCardsProps {
  isConnected: boolean;
  stats: TelemetryBusSnapshot | null;
}

export const TelemetryMetricCards: React.FC<TelemetryMetricCardsProps> = ({
  isConnected,
  stats,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
      <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between">
        <span className="text-xs font-medium text-[#A3A3A3]">
          Connection Status
        </span>
        <div className="my-2">
          <span className="text-base font-semibold text-[#FFFFFF]">
            {isConnected ? 'WebSocket Active' : 'HTTP Fallback'}
          </span>
          <span className="text-[11px] text-[#A3A3A3] block font-mono mt-0.5">
            :8000/ws/telemetry
          </span>
        </div>
        <span className="text-[10px] text-[#A3A3A3]">
          {isConnected
            ? 'Direct bi-directional stream'
            : 'Auto-reconnecting every 4s'}
        </span>
      </div>

      <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between">
        <span className="text-xs font-medium text-[#A3A3A3]">Throughput</span>
        <div className="my-2 flex items-baseline gap-3">
          <div>
            <span className="text-base font-semibold text-[#FFFFFF] font-mono">
              {stats?.http_req_count ?? 0}
            </span>
            <span className="text-[11px] text-[#A3A3A3] ml-1">requests</span>
          </div>
          <div>
            <span className="text-base font-semibold text-[#FFFFFF] font-mono">
              {stats?.query_count ?? 0}
            </span>
            <span className="text-[11px] text-[#A3A3A3] ml-1">queries</span>
          </div>
        </div>
        <span className="text-[10px] text-[#A3A3A3]">
          Total processed since server launch
        </span>
      </div>

      <div className="p-3 rounded-xl bg-[#111111] border border-[#292929] flex flex-col justify-between">
        <span className="text-xs font-medium text-[#A3A3A3]">
          System Health
        </span>
        <div className="my-2 flex items-baseline gap-3">
          <div>
            <span className="text-base font-semibold text-[#FFFFFF] font-mono">
              {stats?.err_count ?? 0}
            </span>
            <span className="text-[11px] text-[#A3A3A3] ml-1">errors</span>
          </div>
          <div>
            <span className="text-base font-semibold text-[#FFFFFF] font-mono">
              {stats?.warn_count ?? 0}
            </span>
            <span className="text-[11px] text-[#A3A3A3] ml-1">warnings</span>
          </div>
        </div>
        <span className="text-[10px] text-[#A3A3A3]">
          Live anomaly counts from event bus
        </span>
      </div>
    </div>
  );
};
