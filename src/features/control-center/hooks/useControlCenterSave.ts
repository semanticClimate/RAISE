import { useState } from 'react';
import { platformAdapter } from '../services/platformAdapter';
import { isValidSecret } from '../services/envDetector';
import type { ControlCenterConfig } from '../types';
import { useModeStore } from '../../../stores/modeStore';
import { useControlCenterStore } from '../store/useControlCenterStore';

export function useControlCenterSave(
  config: ControlCenterConfig,
  completeFirstRun: () => void,
  setOpen: (open: boolean) => void
) {
  const [isSaving, setIsSaving] = useState(false);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [connectNotice, setConnectNotice] = useState<string | null>(null);

  const handleFinalStart = async () => {
    // 1. Verify backend gateway is connected
    const currentMode = useModeStore.getState().appMode;
    if (currentMode === 'offline') {
      await useModeStore.getState().runCapabilityProbe();
      const freshMode = useModeStore.getState().appMode;
      if (freshMode === 'offline') {
        setConnectNotice('Backend Gateway is offline. Start the backend on port 8000 before launching.');
        setTimeout(() => setConnectNotice(null), 6000);
        return;
      }
    }

    // 2. Verify an inference engine / API key is configured
    const isCloud = config.llmDeployment === 'cloud';
    const validKeys = (config.apiKeys || []).filter(
      (k) => k?.key && k.key.trim().length > 0 && k.provider !== 'unknown'
    );
    const hasConfiguredKey = isCloud ? validKeys.length > 0 : Boolean(config.selectedLocalModel);
    if (!hasConfiguredKey) {
      setConnectNotice('Please configure an inference engine or API key before launching.');
      setTimeout(() => setConnectNotice(null), 5000);
      return;
    }

    // 3. Verify models are not actively downloading
    const isDownloading = useControlCenterStore.getState().isDownloading;
    if (isDownloading) {
      setConnectNotice('Neural model weights are currently downloading. Please wait for download to finish.');
      setTimeout(() => setConnectNotice(null), 5000);
      return;
    }

    setIsSaving(true);
    try {
      const keyMap: Record<string, string> = {};
      for (const entry of config.apiKeys || []) {
        if (entry.key && entry.key.trim()) {
          keyMap[entry.provider] = entry.key.trim();
        }
      }

      const primaryCloudProvider =
        (config.apiKeys || []).find(
          (k) => k?.key && k.key.trim() && k.provider !== 'unknown'
        )?.provider || 'groq';
      const activeBackend = isCloud ? primaryCloudProvider : 'ollama';
      const activeLlmMode = isCloud ? `cloud_${primaryCloudProvider}` : 'local_ollama';

      const sanitizeSecret = (val?: string): string | undefined => {
        if (!val) return undefined;
        const trimmed = val.trim();
        if (!isValidSecret(trimmed)) return undefined;
        return trimmed;
      };

      const saveRes = await platformAdapter.saveConfig({
        llm_mode: activeLlmMode,
        llm_backend: activeBackend,
        groq_api_key: sanitizeSecret(keyMap['groq'] || config.groqApiKey),
        gemini_api_key: sanitizeSecret(keyMap['gemini'] || config.geminiApiKey),
        openai_api_key: sanitizeSecret(keyMap['openai']),
        anthropic_api_key: sanitizeSecret(keyMap['anthropic']),
        deepseek_api_key: sanitizeSecret(keyMap['deepseek']),
        nvidia_api_key: sanitizeSecret(keyMap['nvidia']),
        mistral_api_key: sanitizeSecret(keyMap['mistral']),
        cohere_api_key: sanitizeSecret(keyMap['cohere']),
        openrouter_api_key: sanitizeSecret(keyMap['openrouter']),
        custom_api_key: sanitizeSecret(keyMap['custom']),
        selected_local_model: config.selectedLocalModel,
        ollama_model: config.selectedLocalModel,
        tunnel_url: config.tunnelUrl,
        huggingface_token: sanitizeSecret(config.huggingfaceToken),
        hf_token: sanitizeSecret(config.huggingfaceToken),
        embedding_model: config.embeddingModel,
        embedder_id: config.embeddingModel,
        reranker_model: config.rerankerModel,
        reranker_id: config.rerankerModel,
        nli_verifier_model: config.nliVerifierModel,
        verifier_id: config.nliVerifierModel,
        neo4j_mode: config.knowledgeGraph?.mode || config.neo4jMode,
        neo4j_uri: config.knowledgeGraph?.uri || config.neo4jUri,
        neo4j_user: config.knowledgeGraph?.user,
        neo4j_password: sanitizeSecret(config.knowledgeGraph?.password || config.neo4jPassword),
        postgres_mode: config.sessionMemory?.mode || config.postgresMode,
        postgres_uri: config.sessionMemory?.uri,
        redis_mode: config.cacheAndSignals?.mode || config.redisMode,
        redis_uri: config.cacheAndSignals?.uri,
      });

      if (!saveRes.success) {
        setConnectNotice(saveRes.message || 'Configuration rejected by backend');
        setTimeout(() => setConnectNotice(null), 6000);
        setIsSaving(false);
        return;
      }

      // 4. Prewarm and warm up neural pipeline in backend before launching
      setIsWarmingUp(true);
      setConnectNotice('Warming up neural models (Embedding, Reranker, Verifier)...');

      if (config.embeddingModel || config.rerankerModel || config.nliVerifierModel || config.huggingfaceToken) {
        try {
          const prewarmRes = await platformAdapter.triggerModelPrewarm({
            embedder_id: config.embeddingModel,
            embedding_model: config.embeddingModel,
            reranker_id: config.rerankerModel,
            reranker_model: config.rerankerModel,
            verifier_id: config.nliVerifierModel,
            nli_verifier_model: config.nliVerifierModel,
            hf_token: sanitizeSecret(config.huggingfaceToken),
            huggingface_token: sanitizeSecret(config.huggingfaceToken),
          });

          if (!prewarmRes.success && prewarmRes.message) {
            console.warn('Prewarm notice from backend:', prewarmRes.message);
          }
        } catch (err) {
          console.warn('Model prewarming non-fatal error:', err);
        }
      }

      // 5. Verify backend is live and ready to answer queries
      await useModeStore.getState().runCapabilityProbe();
      const readyMode = useModeStore.getState().appMode;
      if (readyMode === 'offline') {
        setConnectNotice('Backend Gateway unreachable. Check backend terminal before launching.');
        setTimeout(() => setConnectNotice(null), 6000);
        setIsSaving(false);
        setIsWarmingUp(false);
        return;
      }

      // 6. Successful Launch: Mark onboarding completed & close modal
      try {
        localStorage.setItem('raise_onboarding_completed', 'true');
        if (typeof window !== 'undefined' && window.history?.replaceState) {
          const cleanUrl = window.location.pathname + (window.location.hash.split('?')[0] || '');
          window.history.replaceState({}, document.title, cleanUrl);
        }
      } catch {}

      completeFirstRun();
      setOpen(false);
    } catch (err) {
      setConnectNotice(`Connection error: ${err instanceof Error ? err.message : String(err)}`);
      setTimeout(() => setConnectNotice(null), 6000);
    } finally {
      setIsSaving(false);
      setIsWarmingUp(false);
    }
  };

  return {
    isSaving,
    isWarmingUp,
    connectNotice,
    setConnectNotice,
    handleFinalStart,
  };
}
