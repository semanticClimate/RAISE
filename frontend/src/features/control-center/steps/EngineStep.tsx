import { Cloud, HardDrive } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useDynamicModels } from '../../../hooks/useDynamicModels';
import { platformAdapter } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { DynamicLLMModel } from '../types';
import { CloudKeysSection } from './CloudKeysSection';
import { LocalModelSection } from './LocalModelSection';
import { LLMRoutingOrchestrator } from '../../../components/settings/LLMRoutingOrchestrator';

export const EngineStep: React.FC = () => {
  const { config, updateConfig, syncEnvCredentials, syncBackendConfig } = useControlCenterStore();

  const {
    models: liveDiscoveredLLMs,
    activeModel: liveActiveModel,
    isLoading: isLoadingLiveModels,
    refetch: refetchLiveModels,
  } = useDynamicModels();

  const [dynamicModels, setDynamicModels] = useState<DynamicLLMModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);

  const isCloud = config.llmDeployment === 'cloud';

  const isLocalProvider = (provider: string) =>
    provider === 'local' || provider === 'vllm' || provider === 'ollama';

  const cloudDiscoveredLLMs = liveDiscoveredLLMs.filter((m) => !isLocalProvider(m.provider));
  const localDiscoveredLLMs = liveDiscoveredLLMs.filter((m) => isLocalProvider(m.provider));

  // Load available models dynamically from backend API (zero hardcoding)
  const fetchModels = () => {
    setIsLoadingModels(true);
    platformAdapter
      .getModelCatalog()
      .then((catalog) => {
        if (catalog && catalog.length > 0) {
          const formatted: DynamicLLMModel[] = catalog.map((m) => {
            const isInstalled = m.source === 'ollama_local' || m.tier === 'Installed (Local Engine)';
            return {
              provider: m.source || 'ollama',
              displayName: m.name || m.id,
              model: m.id,
              status: isInstalled ? 'READY' : 'AVAILABLE_FOR_PULL',
              isActive: isInstalled,
              tier: isInstalled ? 'Installed Locally' : 'Available for Pull (Not Downloaded)',
              sizeGb: m.download_size_gb,
              ramGb: m.min_ram_gb,
              isInstalled,
              source: m.source,
            };
          });
          setDynamicModels(formatted);
          if (!config.selectedLocalModel && formatted.length > 0) {
            updateConfig({ selectedLocalModel: formatted[0].model });
          }
        } else {
          return platformAdapter.getDynamicLLMs().then((models) => {
            const formatted: DynamicLLMModel[] = models.map((m) => ({
              provider: m.provider,
              displayName: m.displayName || m.provider,
              model: m.model,
              status: m.status,
              isActive: m.status === 'READY',
              tier: m.tier,
              sizeGb: undefined,
              ramGb: undefined,
              isInstalled: m.status === 'READY' && (m.provider === 'ollama' || m.provider === 'local'),
              source: m.provider,
            }));
            setDynamicModels(formatted);
            if (!config.selectedLocalModel && formatted.length > 0) {
              updateConfig({ selectedLocalModel: formatted[0].model });
            }
          });
        }
      })
      .catch(() => {
        setDynamicModels([]);
      })
      .finally(() => {
        setIsLoadingModels(false);
      });
  };

  useEffect(() => {
    syncBackendConfig();
    syncEnvCredentials();
    fetchModels();
  }, []);

  return (
    <div className="space-y-3 animate-in fade-in duration-150">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white tracking-tight">Intelligence Engine</h3>
        <span className="text-xs text-slate-400">Select mode & configure keys</span>
      </div>

      {/* LLM Mode Selection: Two Compact Selectable Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        <button
          type="button"
          onClick={() => {
            const firstConfigured = (config.apiKeys || []).find(
              (k) => (k?.key && k.key.trim().length > 0 && k.provider !== 'unknown') || k?.verified === true
            );
            const prov = firstConfigured?.provider || 'gemini';
            updateConfig({
              llmDeployment: 'cloud',
              llmMode: `cloud_${prov}`,
            });
          }}
          className={`p-2.5 sm:p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-2.5 ${
            isCloud
              ? 'bg-[#FFFFFF] text-[#000000] border-[#FFFFFF] font-bold shadow-sm'
              : 'bg-[#111111] border-[#292929] text-[#A3A3A3] hover:border-[#FFFFFF]/20 hover:bg-[#171717]'
          }`}
        >
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
              isCloud ? 'bg-[#000000] text-[#FFFFFF]' : 'bg-[#171717] text-[#A3A3A3]'
            }`}
          >
            <Cloud className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold tracking-tight">Cloud LLM</div>
            <div className={`text-[10.5px] leading-tight ${isCloud ? 'text-[#000000]/80' : 'text-[#A3A3A3]'}`}>
              Hosted AI providers (Gemini, Groq, OpenAI)
            </div>
          </div>
        </button>

        <button
          type="button"
          onClick={() =>
            updateConfig({
              llmDeployment: 'local',
              llmMode: 'local_ollama',
            })
          }
          className={`p-2.5 sm:p-3 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-2.5 ${
            !isCloud
              ? 'bg-[#FFFFFF] text-[#000000] border-[#FFFFFF] font-bold shadow-sm'
              : 'bg-[#111111] border-[#292929] text-[#A3A3A3] hover:border-[#FFFFFF]/20 hover:bg-[#171717]'
          }`}
        >
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
              !isCloud ? 'bg-[#000000] text-[#FFFFFF]' : 'bg-[#171717] text-[#A3A3A3]'
            }`}
          >
            <HardDrive className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-bold tracking-tight">Local LLM</div>
            <div className={`text-[10.5px] leading-tight ${!isCloud ? 'text-slate-800' : 'text-slate-400'}`}>
              Self-hosted engine (Ollama, vLLM)
            </div>
          </div>
        </button>
      </div>

      {isCloud ? (
        <CloudKeysSection
          cloudDiscoveredLLMs={cloudDiscoveredLLMs}
          liveActiveModel={liveActiveModel}
          isLoadingLiveModels={isLoadingLiveModels}
          refetchLiveModels={refetchLiveModels}
          isLocalProvider={isLocalProvider}
        />
      ) : (
        <LocalModelSection
          dynamicModels={dynamicModels}
          localDiscoveredLLMs={localDiscoveredLLMs}
          isLoadingModels={isLoadingModels}
          fetchModels={fetchModels}
        />
      )}

      {/* Interactive LLM Routing Orchestrator & Fallback Priority */}
      <div className="mt-3 pt-3 border-t border-white/10">
        <LLMRoutingOrchestrator />
      </div>
    </div>
  );
};
