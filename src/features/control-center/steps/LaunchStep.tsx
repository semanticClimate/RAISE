import { AlertTriangle, CheckCircle2, Cpu, Laptop, Sparkles, Zap } from 'lucide-react';
import type React from 'react';
import { useModeStore } from '../../../stores/modeStore';
import { useControlCenterStore } from '../store/useControlCenterStore';

export const LaunchStep: React.FC = () => {
  const { config, hardware, setActiveTab } = useControlCenterStore();
  const { appMode, apiBaseUrl, latencyMs } = useModeStore();
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
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="text-sm font-bold text-white">Research Workstation Ready to Launch</h4>
            <p className="text-xs text-slate-300 leading-relaxed">
              Your text-first research environment is configured. All comparative matrix analysis,
              citation audits, and document retrieval are ready for execution.
            </p>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl border border-amber-500/30 bg-amber-500/10 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1 flex-1">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white">AI Engine Configuration Required</h4>
              <button
                type="button"
                onClick={() => setActiveTab('models')}
                className="text-xs font-bold text-amber-300 hover:text-white underline underline-offset-2 cursor-pointer"
              >
                Configure Now &rarr;
              </button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Please enter your API key (Gemini, Groq, Mistral, OpenAI) or select a local model in
              Step 2 before launching.
            </p>
          </div>
        </div>
      )}

      {/* Summary Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Device & Platform */}
        <div className="p-4 rounded-xl bg-[#131622] border border-white/10 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Laptop className="w-4 h-4 text-indigo-400" />
            <span>Target Platform</span>
          </div>
          <div className="text-sm font-bold text-white">{clientOSLabel}</div>
          <div className="text-[11px] font-mono text-slate-400">
            Native Local Environment (Low Latency)
          </div>
        </div>

        {/* Backend Gateway */}
        <div className="p-4 rounded-xl bg-[#131622] border border-white/10 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Zap className="w-4 h-4 text-emerald-400" />
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
            <span>{isConnected ? 'Active & Connected' : 'Local Loopback'}</span>
          </div>
          <div className="text-[11px] font-mono text-slate-400">
            {apiBaseUrl || 'http://127.0.0.1:8000'} {latencyMs ? `(${latencyMs}ms)` : ''}
          </div>
        </div>

        {/* Intelligence Engine */}
        <div className="p-4 rounded-xl bg-[#131622] border border-white/10 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Cpu className="w-4 h-4 text-purple-400" />
            <span>Intelligence Model</span>
          </div>
          <div className="text-sm font-bold text-white truncate">
            {isCloud
              ? `Cloud Inference (${providers})`
              : config.selectedLocalModel || 'On-Device LLM'}
          </div>
          <div className="text-[11px] font-mono text-slate-400">
            Zero-hallucination factual grounding active
          </div>
        </div>

        {/* Workstation Features */}
        <div className="p-4 rounded-xl bg-[#131622] border border-white/10 space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>Workstation Capabilities</span>
          </div>
          <div className="text-sm font-bold text-white">Slash Commands & Auditing</div>
          <div className="text-[11px] font-mono text-slate-400">
            /compare, /browser, /audit, /help
          </div>
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
