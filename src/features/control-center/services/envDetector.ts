/**
 * Real-time Environment Variable Detector for RAISE Control Center
 * Scans runtime client-side environment (loaded by Vite from root .env)
 * for active LLM keys, database credentials, and storage endpoints.
 */

import { detectProviderFromKey, type DetectedProvider } from './keyDetector';

export interface DetectedLlmKey {
  id: string;
  key: string;
  provider: DetectedProvider;
  providerName: string;
  sourceEnvVar: string;
  fromEnv: boolean;
}

export interface DetectedDatabaseConfig {
  present: boolean;
  isCloud: boolean;
  uri?: string;
  user?: string;
  password?: string;
  database?: string;
  host?: string;
  port?: string;
  source: string;
}

export interface DetectedEnvState {
  hasAnyEnvKeys: boolean;
  llmKeys: DetectedLlmKey[];
  postgres: DetectedDatabaseConfig;
  redis: DetectedDatabaseConfig;
  neo4j: DetectedDatabaseConfig;
}

/**
 * Filter out dummy placeholders or empty values
 */
function isValidSecret(val?: string): boolean {
  if (!val) return false;
  const trimmed = val.trim();
  if (trimmed.length === 0) return false;
  if (trimmed.startsWith('your_') || trimmed.startsWith('<your-') || trimmed.includes('placeholder')) {
    return false;
  }
  return true;
}

export function detectEnvCredentials(): DetectedEnvState {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) ? import.meta.env : ({} as Record<string, string>);

  const llmEnvDefinitions: Array<{ envKey: string; defaultProvider: DetectedProvider; displayName: string }> = [
    { envKey: 'GEMINI_API_KEY', defaultProvider: 'gemini', displayName: 'Google Gemini' },
    { envKey: 'GROQ_API_KEY', defaultProvider: 'groq', displayName: 'Groq LPU' },
    { envKey: 'DEEPSEEK_API_KEY', defaultProvider: 'deepseek', displayName: 'DeepSeek' },
    { envKey: 'NVIDIA_API_KEY', defaultProvider: 'nvidia', displayName: 'NVIDIA NIM' },
    { envKey: 'COHERE_API_KEY', defaultProvider: 'cohere', displayName: 'Cohere Command' },
    { envKey: 'OPENROUTER_API_KEY', defaultProvider: 'openrouter', displayName: 'OpenRouter' },
    { envKey: 'OPENAI_API_KEY', defaultProvider: 'openai', displayName: 'OpenAI' },
    { envKey: 'ANTHROPIC_API_KEY', defaultProvider: 'anthropic', displayName: 'Anthropic Claude' },
    { envKey: 'MISTRAL_API_KEY', defaultProvider: 'mistral', displayName: 'Mistral AI' },
  ];

  const detectedLlmKeys: DetectedLlmKey[] = [];

  for (const def of llmEnvDefinitions) {
    const rawVal = env[def.envKey] || env[`VITE_${def.envKey}`];
    if (isValidSecret(rawVal)) {
      const keyStr = rawVal.trim();
      const detected = detectProviderFromKey(keyStr);
      detectedLlmKeys.push({
        id: `env-${def.envKey.toLowerCase()}`,
        key: keyStr,
        provider: detected.provider !== 'unknown' ? detected.provider : def.defaultProvider,
        providerName: detected.displayName !== 'Unconfigured Key' ? detected.displayName : def.displayName,
        sourceEnvVar: def.envKey,
        fromEnv: true,
      });
    }
  }

  // --- PostgreSQL Detection ---
  const pgUri = env.POSTGRES_URI || env.VITE_POSTGRES_URI;
  const pgHost = env.POSTGRES_HOST || env.VITE_POSTGRES_HOST;
  const pgPort = env.POSTGRES_PORT || env.VITE_POSTGRES_PORT || '5432';
  const pgUser = env.POSTGRES_USER || env.VITE_POSTGRES_USER;
  const pgPass = env.POSTGRES_PASSWORD || env.VITE_POSTGRES_PASSWORD;
  const pgDb = env.POSTGRES_DB || env.VITE_POSTGRES_DB || 'raise_db';

  const hasPgUri = isValidSecret(pgUri);
  const hasPgHost = isValidSecret(pgHost);
  const pgPresent = hasPgUri || hasPgHost;

  let resolvedPgUri = '';
  if (hasPgUri && pgUri) {
    resolvedPgUri = pgUri.trim();
  } else if (hasPgHost && pgHost) {
    const userPass = pgUser ? `${pgUser}${pgPass && isValidSecret(pgPass) ? `:${pgPass}` : ''}@` : '';
    resolvedPgUri = `postgresql://${userPass}${pgHost}:${pgPort}/${pgDb}`;
  }

  const isPgCloud =
    resolvedPgUri.includes('neon.tech') ||
    resolvedPgUri.includes('supabase.co') ||
    resolvedPgUri.includes('amazonaws.com') ||
    resolvedPgUri.includes('azure.com') ||
    (!resolvedPgUri.includes('localhost') && !resolvedPgUri.includes('127.0.0.1') && !resolvedPgUri.includes('postgres'));

  const postgres: DetectedDatabaseConfig = {
    present: pgPresent,
    isCloud: isPgCloud,
    uri: resolvedPgUri,
    host: pgHost,
    port: pgPort,
    user: pgUser,
    password: isValidSecret(pgPass) ? pgPass : undefined,
    database: pgDb,
    source: hasPgUri ? 'POSTGRES_URI' : 'POSTGRES_HOST',
  };

  // --- Redis Detection ---
  const redisUri = env.REDIS_URI || env.VITE_REDIS_URI;
  const redisHost = env.REDIS_HOST || env.VITE_REDIS_HOST;
  const redisPort = env.REDIS_PORT || env.VITE_REDIS_PORT || '6379';
  const redisPass = env.REDIS_PASSWORD || env.VITE_REDIS_PASSWORD;

  const hasRedisUri = isValidSecret(redisUri);
  const hasRedisHost = isValidSecret(redisHost);
  const redisPresent = hasRedisUri || hasRedisHost;

  let resolvedRedisUri = '';
  if (hasRedisUri && redisUri) {
    resolvedRedisUri = redisUri.trim();
  } else if (hasRedisHost && redisHost) {
    const passPrefix = isValidSecret(redisPass) ? `:${redisPass}@` : '';
    resolvedRedisUri = `redis://${passPrefix}${redisHost}:${redisPort}`;
  }

  const isRedisCloud =
    resolvedRedisUri.includes('upstash.io') ||
    resolvedRedisUri.includes('redislabs.com') ||
    (!resolvedRedisUri.includes('localhost') && !resolvedRedisUri.includes('127.0.0.1') && !resolvedRedisUri.includes('redis'));

  const redis: DetectedDatabaseConfig = {
    present: redisPresent,
    isCloud: isRedisCloud,
    uri: resolvedRedisUri,
    host: redisHost,
    port: redisPort,
    password: isValidSecret(redisPass) ? redisPass : undefined,
    source: hasRedisUri ? 'REDIS_URI' : 'REDIS_HOST',
  };

  // --- Neo4j Detection ---
  const neo4jUri = env.NEO4J_URI || env.VITE_NEO4J_URI;
  const neo4jUser = env.NEO4J_USER || env.VITE_NEO4J_USER || 'neo4j';
  const neo4jPass = env.NEO4J_PASSWORD || env.VITE_NEO4J_PASSWORD;
  const neo4jDb = env.NEO4J_DATABASE || env.VITE_NEO4J_DATABASE || 'neo4j';

  const hasNeo4jUri = isValidSecret(neo4jUri);
  const neo4jPresent = hasNeo4jUri;
  const resolvedNeo4jUri = hasNeo4jUri && neo4jUri ? neo4jUri.trim() : '';

  const isNeo4jCloud =
    resolvedNeo4jUri.includes('databases.neo4j.io') ||
    resolvedNeo4jUri.startsWith('neo4j+s://') ||
    resolvedNeo4jUri.startsWith('neo4j+ssc://');

  const neo4j: DetectedDatabaseConfig = {
    present: neo4jPresent,
    isCloud: isNeo4jCloud,
    uri: resolvedNeo4jUri,
    user: neo4jUser,
    password: isValidSecret(neo4jPass) ? neo4jPass : undefined,
    database: neo4jDb,
    source: 'NEO4J_URI',
  };

  const hasAnyEnvKeys = detectedLlmKeys.length > 0 || pgPresent || redisPresent || neo4jPresent;

  return {
    hasAnyEnvKeys,
    llmKeys: detectedLlmKeys,
    postgres,
    redis,
    neo4j,
  };
}
