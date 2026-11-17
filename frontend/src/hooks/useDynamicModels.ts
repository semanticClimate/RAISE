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
  id?: string;
  downloadSizeGb?: number;
  minRamGb?: number;
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
 * Dynamic Model Registry Hook
 * ============================
 * Consumes /api/system/models dynamically from the live backend provider router
 * and catalog services. Zero hardcoded labels or static model lists.
 */
export function useDynamicModels(): UseDynamicModelsResult {
  const isConnected = useModeStore((s) => s.appMode === 'connected' || s.appMode === 'degraded');
  const queryClient = useQueryClient();

  // Query 1: Dynamic Models Registry (/api/system/models)
  const systemModelsQuery = useQuery({
    queryKey: ['system', 'models'],
    queryFn: async ({ signal }) => {
      // Primary: /api/system/models?include_catalog=true
      const res = await systemService.getSystemModels(true, signal);
      const raw = res.data;

      // Extract array of active models from either list or dictionary response
      const list: any[] = Array.isArray(raw)
        ? raw
        : Array.isArray((raw as any)?.models)
          ? (raw as any).models
          : Array.isArray((raw as any)?.dynamic_llms)
            ? (raw as any).dynamic_llms
            : [];

      // If /api/system/models returned nothing, try fallback to /api/system/dynamic-llms
      if (list.length === 0) {
        const fallbackRes = await systemService.getDynamicLLMs(signal);
        if (Array.isArray(fallbackRes.data)) {
          return fallbackRes.data.map(parseDynamicModelItem);
        }
      }

      return list.map(parseDynamicModelItem);
    },
    enabled: isConnected,
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  // Query 2: Discovered models catalog across all configured providers
  const discoveredQuery = useQuery({
    queryKey: ['system', 'models-discovered'],
    queryFn: async ({ signal }) => {
      // Check if primary query already cached providers
      const cached = queryClient.getQueryData<any>(['system', 'models']);
      if (cached && typeof cached === 'object' && cached.providers && typeof cached.providers === 'object') {
        return cached.providers as Record<string, string[]>;
      }

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

  const models = useMemo(() => systemModelsQuery.data ?? [], [systemModelsQuery.data]);
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
      queryClient.invalidateQueries({ queryKey: ['system', 'models'] }),
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
    isLoading: systemModelsQuery.isLoading,
    isError: systemModelsQuery.isError,
    refetch,
  };
}

/**
 * Pure dynamic mapper: extracts fields directly from backend response without hardcoded labels.
 */
function parseDynamicModelItem(item: any): DynamicModelItem {
  const obj = item && typeof item === 'object' ? item : {};
  const provider = String(obj.provider || obj.provider_id || obj.service || 'unknown');
  const model = String(obj.model || obj.id || obj.model_name || obj.name || '');
  const displayName = String(
    obj.displayName ||
    obj.display_name ||
    obj.name ||
    obj.title ||
    model ||
    provider
  );
  const status = String(obj.status || (obj.online ? 'READY' : 'LOCAL_OFFLINE'));
  const isActive = Boolean(obj.isActive ?? obj.is_active ?? obj.active);
  const tier = obj.tier ? String(obj.tier) : undefined;
  const downloadSizeGb = typeof obj.download_size_gb === 'number' ? obj.download_size_gb : undefined;
  const minRamGb = typeof obj.min_ram_gb === 'number' ? obj.min_ram_gb : undefined;

  return {
    provider,
    displayName,
    model,
    status,
    isActive,
    tier,
    id: obj.id ? String(obj.id) : model,
    downloadSizeGb,
    minRamGb,
  };
}
