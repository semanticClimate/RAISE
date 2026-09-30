import { useQuery } from '@tanstack/react-query';
import {
  hardwareTelemetryQueryOptions,
  neo4jStatusQueryOptions,
  backendCapabilitiesQueryOptions,
} from '../api/queryOptions';
import { useModeStore } from '../stores/modeStore';

export interface UseBackendTelemetryOptions {
  enabled?: boolean;
  refetchIntervalMs?: number;
}

/**
 * Modern React Query v5 hook for live system telemetry:
 * GPU model & allocation, RAM statistics, Neo4j property graph node counts,
 * and capability matrix health checks.
 */
export function useBackendTelemetry(options: UseBackendTelemetryOptions = {}) {
  const { enabled = true, refetchIntervalMs = 20_000 } = options;
  const isConnected = useModeStore((s) => s.appMode === 'connected');

  const shouldFetch = enabled && isConnected;

  const telemetryQuery = useQuery({
    ...hardwareTelemetryQueryOptions(),
    enabled: shouldFetch,
    refetchInterval: refetchIntervalMs,
  });

  const neo4jStatusQuery = useQuery({
    ...neo4jStatusQueryOptions(),
    enabled: shouldFetch,
    refetchInterval: refetchIntervalMs,
  });

  const capabilitiesQuery = useQuery({
    ...backendCapabilitiesQueryOptions(),
    enabled: shouldFetch,
    staleTime: 60_000,
  });

  return {
    telemetry: telemetryQuery.data ?? null,
    neo4j: neo4jStatusQuery.data ?? null,
    capabilities: capabilitiesQuery.data ?? null,
    isLoading: telemetryQuery.isLoading || neo4jStatusQuery.isLoading,
    isError: telemetryQuery.isError || neo4jStatusQuery.isError,
    refetchAll: async () => {
      await Promise.all([
        telemetryQuery.refetch(),
        neo4jStatusQuery.refetch(),
        capabilitiesQuery.refetch(),
      ]);
    },
  };
}
