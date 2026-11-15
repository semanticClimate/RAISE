import { z } from 'zod';

export const HardwareTelemetrySchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      return {
        ...val,
        gpu_model: val.gpu_model || val.gpu_name || 'NVIDIA CUDA GPU (or CPU Fallback)',
        ram_total_gb: val.ram_total_gb ?? val.total_ram_gb ?? 0,
        ram_available_gb: val.ram_available_gb ?? val.free_ram_gb ?? 0,
        ram_percent: val.ram_percent ?? val.cpu_usage_pct ?? 0,
        embedding_model: val.embedding_model || 'BAAI/bge-large-en-v1.5',
        neo4j_endpoint: val.neo4j_endpoint || 'bolt://localhost:7687',
      };
    }
    return val;
  },
  z.object({
    gpu_model: z.string().default('Unknown GPU'),
    ram_total_gb: z.number().default(0),
    ram_available_gb: z.number().default(0),
    ram_percent: z.number().default(0),
    embedding_model: z.string().default('BAAI/bge-large-en-v1.5'),
    neo4j_endpoint: z.string().default('bolt://localhost:7687'),
  })
);

export type HardwareTelemetry = z.infer<typeof HardwareTelemetrySchema>;

export const Neo4jStatusSchema = z
  .object({
    connected: z.boolean().default(false),
    uri: z.string().default('bolt://localhost:7687'),
    user: z.string().optional(),
    database: z.string().optional(),
    total_nodes: z.number().int().optional(),
    error: z.string().optional(),
    hint: z.string().optional(),
  })
  .passthrough();

export type Neo4jStatus = z.infer<typeof Neo4jStatusSchema>;

export const AuthHandshakeResponseSchema = z
  .object({
    token: z.string(),
    expires_in: z.number().default(300),
    status: z.string().default('active'),
    mode: z.string().optional(),
    client_ip: z.string().optional(),
  })
  .passthrough();

export type AuthHandshakeResponse = z.infer<typeof AuthHandshakeResponseSchema>;

export const BackendCapabilitiesSchema = z
  .object({
    apiReachable: z.boolean().default(false),
    openApiReachable: z.boolean().default(false),
    handshakeAvailable: z.boolean().default(false),
    backendVersion: z.string().default('1.0.0'),
    chatAvailable: z.boolean().default(false),
    documentsAvailable: z.boolean().default(false),
    graphAvailable: z.boolean().default(false),
    searchAvailable: z.boolean().default(false),
    hardwareTelemetryAvailable: z.boolean().default(false),
    neo4jStatusAvailable: z.boolean().default(false),
    sseStreamingAvailable: z.boolean().default(false),
    serverAbortAvailable: z.boolean().default(false),
    asyncSourceStatusAvailable: z.boolean().default(false),
    lastProbeTime: z.string().optional(),
    latencyMs: z.number().default(0),
  })
  .passthrough();

export type BackendCapabilities = z.infer<typeof BackendCapabilitiesSchema>;

export interface ProviderRoutingInfo {
  configured: boolean;
  model: string;
  status: string;
  tier?: string;
  cooldown_until?: number | null;
  cooldown_reason?: string | null;
  is_primary: boolean;
  is_disabled: boolean;
  is_in_fallback_chain: boolean;
  order_rank: number;
}

export interface RoutingStatusResponse {
  status: string;
  message?: string;
  primary_provider: string;
  fallback_order: string[];
  disabled_providers: string[];
  routing_policy: string;
  providers: Record<string, ProviderRoutingInfo>;
}

export interface RoutingUpdateRequest {
  fallback_order?: string[];
  disabled_providers?: string[];
  primary_provider?: string;
  routing_policy?: string;
}
