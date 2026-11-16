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
    <div className="space-y-5 animate-in fade-in duration-150">
      <div>
        <h3 className="text-base font-bold text-white tracking-tight">Intelligence Engine</h3>
        <p className="text-xs text-slate-400 mt-1">
          Select deployment mode and configure keys or local models.
        </p>
      </div>

      {/* LLM Mode Selection: Two Large Selectable Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
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
          className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3.5 ${
            isCloud
              ? 'bg-white text-black border-white font-bold shadow-lg scale-[1.01]'
              : 'bg-[#131622] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
          }`}
        >
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              isCloud ? 'bg-black text-white' : 'bg-white/10 text-slate-400'
            }`}
          >
            <Cloud className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold tracking-tight">Cloud LLM</div>
            <div className={`text-xs mt-0.5 leading-relaxed ${isCloud ? 'text-slate-800' : 'text-slate-400'}`}>
              Use hosted AI providers through API keys.
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
          className={`p-4 rounded-2xl border text-left transition-all cursor-pointer flex items-start gap-3.5 ${
            !isCloud
              ? 'bg-white text-black border-white font-bold shadow-lg scale-[1.01]'
              : 'bg-[#131622] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
          }`}
        >
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              !isCloud ? 'bg-black text-white' : 'bg-white/10 text-slate-400'
            }`}
          >
            <HardDrive className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-bold tracking-tight">Local LLM</div>
            <div className={`text-xs mt-0.5 leading-relaxed ${!isCloud ? 'text-slate-800' : 'text-slate-400'}`}>
              Run AI models on your own machine.
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
      <div className="mt-5 pt-4 border-t border-white/10">
        <LLMRoutingOrchestrator />
      </div>
    </div>
  );
};
