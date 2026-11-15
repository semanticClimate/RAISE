import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { systemService } from '../services/SystemService';
import { useModeStore } from '../stores/modeStore';

export interface DynamicModelItem {
  provider: string;
  displayName: string;
  model: string;
  status: string;
  isActive: boolean;
  tier?: string;
}

export interface UseDynamicModelsResult {
  models: DynamicModelItem[];
  discoveredProviders: Record<string, string[]>;
  activeModel: string | null;
  activeProvider: string | null;
  hasActiveModel: boolean;
  isLoading: boolean;
  isError: boolean;
  refetch: () => Promise<void>;
}

/**
 * Dynamic Model Catalog Hook
 * =========================
 * Subscribes to live backend endpoints (/api/system/dynamic-llms and /api/system/models/discovered)
 * backed by ModelDiscoveryEngine.
 * Model options update in real time based on active API keys without hardcoding model lists.
 */
export function useDynamicModels(): UseDynamicModelsResult {
  const isConnected = useModeStore((s) => s.appMode === 'connected' || s.appMode === 'degraded');
  const queryClient = useQueryClient();

  // Query 1: Actively configured LLM providers & their preferred models
  const dynamicLLMsQuery = useQuery({
    queryKey: ['system', 'dynamic-llms'],
    queryFn: async ({ signal }) => {
      const res = await systemService.getDynamicLLMs(signal);
      if (res.data && Array.isArray(res.data)) {
        return (res.data as unknown[]).map((m: unknown) => {
          const item = m && typeof m === 'object' ? (m as Record<string, unknown>) : {};
          return {
            provider: String(item.provider || 'unknown'),
            displayName: String(item.displayName || item.display_name || item.provider || 'Model'),
            model: String(item.model || 'default'),
            status: String(item.status || 'READY'),
            isActive: Boolean(item.isActive ?? item.is_active),
            tier: item.tier ? String(item.tier) : undefined,
          };
        }) as DynamicModelItem[];
      }
      return [] as DynamicModelItem[];
    },
    enabled: isConnected,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  // Query 2: Discovered models catalog across all configured providers
  const discoveredQuery = useQuery({
    queryKey: ['system', 'models-discovered'],
    queryFn: async ({ signal }) => {
      const res = await systemService.getDiscoveredModels(undefined, signal);
      const resData = res.data && typeof res.data === 'object' ? (res.data as Record<string, unknown>) : null;
      if (resData?.providers && typeof resData.providers === 'object') {
        return resData.providers as Record<string, string[]>;
      }
      return {} as Record<string, string[]>;
    },
    enabled: isConnected,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const models = useMemo(() => dynamicLLMsQuery.data ?? [], [dynamicLLMsQuery.data]);
  const discoveredProviders = useMemo(() => discoveredQuery.data ?? {}, [discoveredQuery.data]);

  const readyModels = useMemo(() => {
    return models.filter((m) => m.status === 'READY');
  }, [models]);

  const activeItem = useMemo(() => {
    return readyModels.find((m) => m.isActive) || (readyModels.length > 0 ? readyModels[0] : null);
  }, [readyModels]);

  const activeModel = activeItem?.model ?? null;
  const activeProvider = activeItem?.provider ?? null;
  const hasActiveModel = readyModels.length > 0;

  const refetch = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['system', 'dynamic-llms'] }),
      queryClient.invalidateQueries({ queryKey: ['system', 'models-discovered'] }),
    ]);
  }, [queryClient]);

  return {
    models,
    discoveredProviders,
    activeModel,
    activeProvider,
    hasActiveModel,
    isLoading: dynamicLLMsQuery.isLoading,
    isError: dynamicLLMsQuery.isError,
    refetch,
  };
}
