import { Cloud, HardDrive } from 'lucide-react';
import type React from 'react';
import { useEffect, useState } from 'react';
import { useDynamicModels } from '../../../hooks/useDynamicModels';
import { platformAdapter } from '../services/platformAdapter';
import { useControlCenterStore } from '../store/useControlCenterStore';
import type { DynamicLLMModel } from '../types';
import { CloudKeysSection } from './CloudKeysSection';
import { LocalModelSection } from './LocalModelSection';

export const EngineStep: React.FC = () => {
  const { config, updateConfig, syncEnvCredentials } = useControlCenterStore();

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
              sizeGb: m.model.includes('3b') ? 2.0 : m.model.includes('7b') ? 4.7 : 4.9,
              ramGb: m.model.includes('3b') ? 4.0 : m.model.includes('7b') ? 8.0 : 16.0,
              isInstalled: false,
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

      {/* Deployment Strategy Switcher */}
      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() =>
            updateConfig({
              llmDeployment: 'cloud',
              llmMode: 'cloud_groq',
            })
          }
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
            isCloud
              ? 'bg-white text-black border-white font-bold shadow-md'
              : 'bg-[#131622] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
          }`}
        >
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
              isCloud ? 'bg-black text-white' : 'bg-white/10 text-slate-400'
            }`}
          >
            <Cloud className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold">Cloud Inference</div>
            <div className={`text-[11px] mt-0.5 ${isCloud ? 'text-slate-700' : 'text-slate-400'}`}>
              Groq, Gemini, DeepSeek, OpenAI
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
          className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer flex items-start gap-3 ${
            !isCloud
              ? 'bg-white text-black border-white font-bold shadow-md'
              : 'bg-[#131622] border-white/10 text-slate-300 hover:border-white/20 hover:bg-white/5'
          }`}
        >
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
              !isCloud ? 'bg-black text-white' : 'bg-white/10 text-slate-400'
            }`}
          >
            <HardDrive className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold">Local Engine</div>
            <div className={`text-[11px] mt-0.5 ${!isCloud ? 'text-slate-700' : 'text-slate-400'}`}>
              On-device Ollama &amp; Metal/CUDA
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
    </div>
  );
};
