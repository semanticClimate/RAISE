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
  const isConnected = useModeStore((s) => s.appMode === 'connected');
  const queryClient = useQueryClient();

  // Query 1: Actively configured LLM providers & their preferred models
  const dynamicLLMsQuery = useQuery({
    queryKey: ['system', 'dynamic-llms'],
    queryFn: async ({ signal }) => {
      const res = await systemService.getDynamicLLMs(signal);
      if (res.data && Array.isArray(res.data)) {
        return res.data.map((m: any) => ({
          provider: String(m.provider || 'unknown'),
          displayName: String(m.displayName || m.display_name || m.provider || 'Model'),
          model: String(m.model || 'default'),
          status: String(m.status || 'READY'),
          isActive: Boolean(m.isActive ?? m.is_active),
          tier: m.tier ? String(m.tier) : undefined,
        })) as DynamicModelItem[];
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
      if (res.data?.providers && typeof res.data.providers === 'object') {
        return res.data.providers as Record<string, string[]>;
      }
      return {} as Record<string, string[]>;
    },
    enabled: isConnected,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const models = useMemo(() => dynamicLLMsQuery.data ?? [], [dynamicLLMsQuery.data]);
  const discoveredProviders = useMemo(() => discoveredQuery.data ?? {}, [discoveredQuery.data]);

  const activeItem = useMemo(() => {
    return models.find((m) => m.isActive) || (models.length > 0 ? models[0] : null);
  }, [models]);

  const activeModel = activeItem?.model ?? null;
  const activeProvider = activeItem?.provider ?? null;
  const hasActiveModel = models.some((m) => m.status === 'READY' || m.isActive);

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
