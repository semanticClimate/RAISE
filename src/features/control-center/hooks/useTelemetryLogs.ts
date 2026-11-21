import { useEffect, useState } from 'react';
import { getApiBaseUrl } from '../../../app/config';
import { telemetryBridge } from '../../../services/telemetryBridge';
import type { TelemetryBusSnapshot } from '../../../types/telemetry';

export interface SimpleLogEntry {
  id: string;
  timestamp: string;
  type: string;
  message: string;
  level: string;
}

export function useTelemetryLogs() {
  const [stats, setStats] = useState<TelemetryBusSnapshot | null>(() =>
    telemetryBridge.getStats()
  );
  const [isConnected, setIsConnected] = useState<boolean>(() =>
    telemetryBridge.getIsConnected()
  );
  const [logs, setLogs] = useState<SimpleLogEntry[]>([]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setStats(telemetryBridge.getStats());
      setIsConnected(telemetryBridge.getIsConnected());
    }, 1000);

    const handleStage = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setLogs((prev) => [
        {
          id: `stage-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          timestamp: new Date().toLocaleTimeString(),
          type: 'PIPELINE',
          message: `Stage [${detail.stage}]: ${detail.status} (${detail.duration_ms ?? 0}ms)`,
          level: detail.status === 'failed' ? 'ERROR' : 'INFO',
        },
        ...prev.slice(0, 99),
      ]);
    };

    const handleBackendLog = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setLogs((prev) => [
        {
          id: `backend-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
          timestamp: new Date().toLocaleTimeString(),
          type: 'SERVER',
          message: `${detail.logger_name || 'backend'}: ${detail.message}`,
          level: detail.level || 'INFO',
        },
        ...prev.slice(0, 99),
      ]);
    };

    const handleConn = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.stats) {
        setStats(detail.stats);
      }
      setIsConnected(true);
      setLogs((prev) => [
        {
          id: `conn-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          type: 'SYSTEM',
          message: `Connected to server telemetry stream (Client: ${detail?.client_ip || 'local'})`,
          level: 'INFO',
        },
        ...prev.slice(0, 99),
      ]);
    };

    window.addEventListener('raise:pipeline_stage', handleStage);
    window.addEventListener('raise:backend_log', handleBackendLog);
    window.addEventListener('raise:connection_ready', handleConn);

    return () => {
      clearInterval(timer);
      window.removeEventListener('raise:pipeline_stage', handleStage);
      window.removeEventListener('raise:backend_log', handleBackendLog);
      window.removeEventListener('raise:connection_ready', handleConn);
    };
  }, []);

  const handleTestPing = () => {
    telemetryBridge.send({
      subtype: 'console',
      level: 'INFO',
      message: `Manual telemetry health check (${new Date().toLocaleTimeString()})`,
    });
    setLogs((prev) => [
      {
        id: `ping-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString(),
        type: 'CHECK',
        message: 'Dispatched test message to telemetry stream',
        level: 'INFO',
      },
      ...prev,
    ]);
  };

  const handleCopy = () => {
    const report = {
      timestamp: new Date().toISOString(),
      serverUrl: getApiBaseUrl(),
      isConnected,
      stats,
      recentEvents: logs.slice(0, 30),
    };
    navigator.clipboard.writeText(JSON.stringify(report, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClearLogs = () => {
    setLogs([]);
  };

  return {
    stats,
    isConnected,
    logs,
    copied,
    handleTestPing,
    handleCopy,
    handleClearLogs,
  };
}
