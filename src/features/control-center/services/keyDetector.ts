export type DetectedProvider =
  | 'groq'
  | 'gemini'
  | 'nvidia'
  | 'mistral'
  | 'cohere'
  | 'anthropic'
  | 'openai'
  | 'deepseek'
  | 'openrouter'
  | 'huggingface'
  | 'universal'
  | 'custom'
  | 'unknown';

export interface ProviderDetectionResult {
  provider: DetectedProvider;
  displayName: string;
  defaultModel: string;
}

export function detectProviderFromKey(key: string): ProviderDetectionResult {
  const trimmed = key.trim();
  if (!trimmed) {
    return {
      provider: 'unknown',
      displayName: 'Empty Key',
      defaultModel: '',
    };
  }

  // Groq keys start with 'gsk_'
  if (trimmed.startsWith('gsk_')) {
    return {
      provider: 'groq',
      displayName: 'Groq',
      defaultModel: '',
    };
  }

  // Google Gemini keys typically start with 'AIzaSy' or 'AIza'
  if (trimmed.startsWith('AIzaSy') || trimmed.startsWith('AIza')) {
    return {
      provider: 'gemini',
      displayName: 'Gemini',
      defaultModel: '',
    };
  }

  // NVIDIA keys start with 'nvapi-'
  if (trimmed.startsWith('nvapi-')) {
    return {
      provider: 'nvidia',
      displayName: 'NVIDIA',
      defaultModel: '',
    };
  }

  // Anthropic keys start with 'sk-ant-'
  if (trimmed.startsWith('sk-ant-')) {
    return {
      provider: 'anthropic',
      displayName: 'Anthropic',
      defaultModel: '',
    };
  }

  // Cohere keys
  if (trimmed.startsWith('co-') || trimmed.length === 40) {
    return {
      provider: 'cohere',
      displayName: 'Cohere',
      defaultModel: '',
    };
  }

  // OpenRouter
  if (trimmed.startsWith('sk-or-')) {
    return {
      provider: 'openrouter',
      displayName: 'OpenRouter',
      defaultModel: '',
    };
  }

  if (trimmed.startsWith('sk-')) {
    return {
      provider: 'openai',
      displayName: 'OpenAI',
      defaultModel: '',
    };
  }

  // Mistral keys are 32 chars alphanumeric hex
  if (/^[a-zA-Z0-9]{32}$/.test(trimmed)) {
    return {
      provider: 'mistral',
      displayName: 'Mistral',
      defaultModel: '',
    };
  }

  // Hugging Face keys start with 'hf_'
  if (trimmed.startsWith('hf_')) {
    return {
      provider: 'huggingface',
      displayName: 'Hugging Face',
      defaultModel: '',
    };
  }

  return {
    provider: 'custom',
    displayName: 'Custom API',
    defaultModel: '',
  };
}
