import { queryOptions } from '@tanstack/react-query';
import { sourceService } from '../services/SourceService';
import { systemService } from '../services/SystemService';
import type { BackendCapabilities, HardwareTelemetry, Neo4jStatus } from '../types';

/**
 * Declarative TanStack React Query v5 query definitions.
 * Centralizes query keys, async fetchers, and stale times.
 */

/**
 * Query options for fetching the authoritative document list from ChromaDB / SQLite vault.
 */
export const documentsQueryOptions = () =>
  queryOptions({
    queryKey: ['documents'] as const,
    queryFn: async ({ signal }) => {
      const resp = await sourceService.getDocuments(signal);
      return resp.data?.documents ?? [];
    },
    staleTime: 10_000,
    gcTime: 5 * 60_000,
  });

/**
 * Query options for fetching hardware telemetry (GPU VRAM, CPU RAM, active embedding model).
 */
export const hardwareTelemetryQueryOptions = () =>
  queryOptions<HardwareTelemetry | null>({
    queryKey: ['system', 'telemetry'] as const,
    queryFn: async ({ signal }) => {
      const resp = await systemService.getHardwareTelemetry(signal);
      return resp.data ?? null;
    },
    staleTime: 15_000,
    gcTime: 60_000,
  });

/**
 * Query options for fetching Neo4j graph substrate status and node count.
 */
export const neo4jStatusQueryOptions = () =>
  queryOptions<Neo4jStatus | null>({
    queryKey: ['system', 'neo4j'] as const,
    queryFn: async ({ signal }) => {
      const resp = await systemService.getNeo4jStatus(signal);
      return resp.data ?? null;
    },
    staleTime: 30_000,
    gcTime: 2 * 60_000,
  });

/**
 * Query options for full capability health check.
 */
export const backendCapabilitiesQueryOptions = () =>
  queryOptions<BackendCapabilities>({
    queryKey: ['system', 'capabilities'] as const,
    queryFn: async () => {
      return await systemService.probeCapabilities();
    },
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
