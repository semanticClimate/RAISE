import { useState } from 'react';
import { platformAdapter } from '../services/platformAdapter';
import { isValidSecret } from '../services/envDetector';
import type { ControlCenterConfig } from '../types';

export function useControlCenterSave(
  config: ControlCenterConfig,
  completeFirstRun: () => void,
  setOpen: (open: boolean) => void
) {
  const [isSaving, setIsSaving] = useState(false);
  const [connectNotice, setConnectNotice] = useState<string | null>(null);

  const handleFinalStart = async () => {
    setIsSaving(true);
    try {
      const isCloud = config.llmDeployment === 'cloud';
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

      // Trigger background pre-warming for neural embedding, reranker, and verifier models
      if (config.embeddingModel || config.rerankerModel || config.nliVerifierModel || config.huggingfaceToken) {
        platformAdapter.triggerModelPrewarm({
          embedder_id: config.embeddingModel,
          embedding_model: config.embeddingModel,
          reranker_id: config.rerankerModel,
          reranker_model: config.rerankerModel,
          verifier_id: config.nliVerifierModel,
          nli_verifier_model: config.nliVerifierModel,
          hf_token: sanitizeSecret(config.huggingfaceToken),
          huggingface_token: sanitizeSecret(config.huggingfaceToken),
        }).catch(() => {
          // Non-blocking prewarm
        });
      }

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
    }
  };

  return {
    isSaving,
    connectNotice,
    setConnectNotice,
    handleFinalStart,
  };
}
