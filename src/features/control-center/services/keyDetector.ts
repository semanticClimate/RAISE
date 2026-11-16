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
      defaultModel: 'llama-3.3-70b-versatile',
    };
  }

  // Google Gemini keys typically start with 'AIzaSy' or 'AIza'
  if (trimmed.startsWith('AIzaSy') || trimmed.startsWith('AIza')) {
    return {
      provider: 'gemini',
      displayName: 'Gemini',
      defaultModel: 'gemini-2.0-flash',
    };
  }

  // NVIDIA keys start with 'nvapi-'
  if (trimmed.startsWith('nvapi-')) {
    return {
      provider: 'nvidia',
      displayName: 'NVIDIA',
      defaultModel: 'meta/llama-3.2-11b-vision-instruct',
    };
  }

  // Anthropic keys start with 'sk-ant-'
  if (trimmed.startsWith('sk-ant-')) {
    return {
      provider: 'anthropic',
      displayName: 'Anthropic',
      defaultModel: 'claude-3-5-sonnet',
    };
  }

  // Cohere keys
  if (trimmed.startsWith('co-') || trimmed.length === 40) {
    return {
      provider: 'cohere',
      displayName: 'Cohere',
      defaultModel: 'command-r-plus-08-2024',
    };
  }

  // OpenRouter
  if (trimmed.startsWith('sk-or-')) {
    return {
      provider: 'openrouter',
      displayName: 'OpenRouter',
      defaultModel: 'anthropic/claude-3-haiku',
    };
  }

  if (trimmed.startsWith('sk-')) {
    return {
      provider: 'openai',
      displayName: 'OpenAI',
      defaultModel: 'gpt-4o-mini',
    };
  }

  // Mistral keys are 32 chars alphanumeric hex
  if (/^[a-zA-Z0-9]{32}$/.test(trimmed)) {
    return {
      provider: 'mistral',
      displayName: 'Mistral',
      defaultModel: 'open-mistral-nemo',
    };
  }

  // Hugging Face keys start with 'hf_'
  if (trimmed.startsWith('hf_')) {
    return {
      provider: 'huggingface',
      displayName: 'Hugging Face',
      defaultModel: 'sentence-transformers/all-MiniLM-L6-v2',
    };
  }

  return {
    provider: 'custom',
    displayName: 'Custom API',
    defaultModel: 'default',
  };
}
