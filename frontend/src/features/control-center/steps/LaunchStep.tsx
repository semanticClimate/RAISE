import { AlertTriangle, CheckCircle2, Cpu, Laptop, Layers, Sparkles, Zap } from 'lucide-react';
import type React from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useControlCenterStore } from '../store/useControlCenterStore';

export const LaunchStep: React.FC = () => {
  const { config, hardware, setActiveTab } = useControlCenterStore();
  const { appMode, apiBaseUrl } = useModeStore();
  const isConnected = appMode === 'connected';

  const isCloud = config.llmDeployment
    ? config.llmDeployment === 'cloud'
    : !config.llmMode || config.llmMode.startsWith('cloud');

  const validKeys = (config.apiKeys || []).filter(
    (k) => k?.key && k.key.trim().length > 0 && k.provider !== 'unknown'
  );
  const providers =
    Array.from(new Set(validKeys.map((k) => k.providerName))).join(', ') ||
    'Default / Auto-detected';
  const hasConfiguredKey = isCloud ? validKeys.length > 0 : Boolean(config.selectedLocalModel);

  const clientOSLabel =
    hardware?.osName ||
    (config.targetPlatform === 'macos'
      ? 'macOS (Apple Silicon)'
      : config.targetPlatform === 'windows'
        ? 'Windows 11'
        : config.targetPlatform === 'linux'
          ? 'Linux'
          : 'macOS (Desktop)');

  return (
    <div
      className="space-y-5 animate-in fade-in duration-200"
      data-testid="control-center-launch-step"
    >
      {/* Ready / Incomplete Status Banner */}
      {hasConfiguredKey ? (
        <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <div>
            <h4 className="text-sm font-bold text-white">Ready to Launch</h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Workstation configured. Click Launch below to start.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-white">API Key Required</h4>
              <p className="text-xs text-slate-300 mt-0.5">
                Add an API key in Models to begin.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setActiveTab('models')}
            className="text-xs font-bold text-amber-300 hover:text-white underline underline-offset-2 cursor-pointer shrink-0"
          >
            Configure &rarr;
          </button>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Device & Platform */}
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Laptop className="w-3.5 h-3.5 text-indigo-400" />
            <span>Target Platform</span>
          </div>
          <div className="text-sm font-bold text-white">{clientOSLabel}</div>
        </div>

        {/* Backend Gateway */}
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Zap className="w-3.5 h-3.5 text-emerald-400" />
            <span>Backend Gateway</span>
          </div>
          <div className="text-sm font-bold text-white flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected
                  ? 'bg-emerald-400 ring-2 ring-emerald-400/20'
                  : 'bg-amber-400 animate-pulse'
              }`}
            />
            <span>{isConnected ? 'Active' : 'Offline'}</span>
            <span className="text-xs font-mono text-slate-400 font-normal">
              ({apiBaseUrl || '127.0.0.1:8000'})
            </span>
          </div>
        </div>

        {/* Intelligence Engine */}
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            <span>Model Provider</span>
          </div>
          <div className="text-sm font-bold text-white truncate">
            {isCloud ? providers : config.selectedLocalModel || 'Local'}
          </div>
        </div>

        {/* Neural Pipeline Substrates */}
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span>Neural Retrieval</span>
          </div>
          <div className="text-sm font-bold text-white truncate">
            {config.embeddingModel?.split('/').pop() || 'Embedding Gemma'} &bull; {config.rerankerModel?.split('/').pop() || 'BGE Reranker'}
          </div>
        </div>

        {/* Workstation Features */}
        <div className="p-3.5 rounded-xl bg-[#131622] border border-white/10 space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            <span>Capabilities</span>
          </div>
          <div className="text-sm font-bold text-white">GraphRAG & Citations</div>
        </div>
      </div>

      {/* Clean Launch Advice Notice */}
      <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 text-xs text-slate-300 flex items-center justify-between">
        <span className="leading-relaxed">
          Click <strong>Launch App</strong> below to start your research session.
        </span>
        <span className="text-[11px] font-mono text-slate-400 hidden sm:inline">
          Cmd/Ctrl + K to focus inquiry box
        </span>
      </div>
    </div>
  );
};
