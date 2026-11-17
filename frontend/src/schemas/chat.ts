import { z } from 'zod';

export const SubgraphQueryRequestSchema = z.object({
  query: z.string().min(1, 'Query cannot be empty'),
  hops: z.number().int().min(0).max(3).default(2),
  top_k: z.number().int().min(0).max(10).default(4),
  mode: z.enum(['fast', 'expert', 'conversational', 'auto']).optional(),
  stream: z.boolean().optional(),
  document_filter: z.string().nullable().optional(),
  active_docs: z.array(z.string()).optional(),
  format: z.string().optional(),
  thread_id: z.string().optional(),
  request_id: z.string().optional(),
  chat_history: z.array(z.object({ human: z.string(), ai: z.string() })).optional(),
  parser: z.string().optional(),
  full_potential: z.boolean().optional(),
});

export type SubgraphQueryRequest = z.infer<typeof SubgraphQueryRequestSchema>;

export const AgentQueryRequestSchema = z.object({
  query: z.string().min(1, 'Query cannot be empty'),
});

export type AgentQueryRequest = z.infer<typeof AgentQueryRequestSchema>;

export const CitationSchema = z
  .object({
    citation_index: z.number().int().default(1),
    chunk_id: z.string().default(''),
    document_id: z.string().default(''),
    doc_id: z.string().nullish(),
    pdf_filename: z.string().default(''),
    filename: z.string().nullish(),
    primary_page: z
      .number()
      .int()
      .or(z.string().transform((v) => parseInt(v, 10)))
      .nullish(),
    page: z
      .number()
      .int()
      .or(z.string().transform((v) => parseInt(v, 10)))
      .nullish(),
    page_number: z
      .number()
      .int()
      .or(z.string().transform((v) => parseInt(v, 10)))
      .nullish(),
    heading: z.string().default(''),
    plain_text: z.string().default(''),
    snippet: z.string().nullish(),
    text: z.string().nullish(),
    university: z.string().default(''),
    similarity: z.number().default(0),
    score: z.number().nullish(),
    printed_page: z.union([z.string(), z.number()]).nullish(),
    page_url: z.string().nullish(),
    page_image_url: z.string().nullish(),
    page_view_url: z.string().nullish(),
    source_type: z.string().nullish(),
    url: z.string().nullish(),
    metadata: z.record(z.string(), z.any()).nullish(),
  })
  .passthrough();

export type Citation = z.infer<typeof CitationSchema>;

export const VerifiedClaimSchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      const isSupp =
        val.is_supported ??
        (val.status === 'VERIFIED' ||
          val.status === 'SUPPORTED' ||
          val.status === 'DIRECT' ||
          val.status === 'NLI_ENTAILED' ||
          (typeof val.confidence === 'number' && val.confidence >= 0.7));
      return {
        ...val,
        is_supported: Boolean(isSupp),
        notes: val.notes || val.verification_notes || [],
      };
    }
    return val;
  },
  z.object({
    claim_id: z.string(),
    text: z.string(),
    is_supported: z.boolean().default(true),
    status: z
      .enum(['SUPPORTED', 'NUMERICAL_MISMATCH', 'ENTITY_MISMATCH', 'UNSUPPORTED', 'CITATION_INVALID'])
      .or(z.string())
      .default('SUPPORTED'),
    extracted_numbers: z.array(z.string()).default([]),
    matched_numbers: z.array(z.string()).default([]),
    citations_found: z.array(z.number().int()).default([]),
    notes: z.array(z.string()).default([]),
  })
);

export type VerifiedClaim = z.infer<typeof VerifiedClaimSchema>;

export const GraphNodeSchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      const fallbackName = val.name || val.label || val.id || 'Entity';
      return {
        ...val,
        name: fallbackName,
        label: val.label || fallbackName,
      };
    }
    return val;
  },
  z.object({
    id: z.string(),
    name: z.string().default('Entity'),
    label: z.string().default(''),
    type: z.string().default('Entity'),
    color: z.string().optional(),
    provenance: z.record(z.string(), z.any()).default({}),
  })
);

export type GraphNode = z.infer<typeof GraphNodeSchema>;

export const GraphEdgeSchema = z.preprocess(
  (val: any) => {
    if (val && typeof val === 'object') {
      return {
        ...val,
        relationship: val.relationship || val.relation || val.type || 'RELATED_TO',
      };
    }
    return val;
  },
  z.object({
    source: z.string(),
    target: z.string(),
    relationship: z.string().default('RELATED_TO'),
    provenance: z.record(z.string(), z.any()).default({}),
  })
);

export type GraphEdge = z.infer<typeof GraphEdgeSchema>;

export const SubgraphDataSchema = z.preprocess(
  (val: any) => {
    if (!val || typeof val !== 'object') return { nodes: [], edges: [] };
    return {
      nodes: Array.isArray(val.nodes) ? val.nodes : [],
      edges: Array.isArray(val.edges) ? val.edges : [],
    };
  },
  z
    .object({
      nodes: z.array(GraphNodeSchema).catch([]),
      edges: z.array(GraphEdgeSchema).catch([]),
    })
    .passthrough()
);

export type SubgraphData = z.infer<typeof SubgraphDataSchema>;

export const TopChunkSchema = z.object({
  chunk_id: z.string(),
  text: z.string(),
  similarity: z.number().default(0),
  metadata: z.record(z.string(), z.any()).default({}),
});

export type TopChunk = z.infer<typeof TopChunkSchema>;

export const QualityGateReportSchema = z.object({
  evaluator_type: z.string().default('LocalHeuristicEvaluator'),
  faithfulness: z.number().default(0),
  answer_relevance: z.number().optional().default(0),
  context_precision: z.number().optional().default(0),
  context_recall: z.number().optional().default(0),
  overall_score: z.number().optional().default(0),
  supported_claims_count: z.number().int().default(0),
  total_claims_count: z.number().int().default(0),
  numerical_mismatches: z.number().int().default(0),
  citation_errors: z.number().int().default(0),
  is_acceptable: z.boolean().default(true),
  rejection_reason: z.string().nullable().default(null),
  claims: z.array(z.any()).optional().default([]),
});

export type QualityGateReport = z.infer<typeof QualityGateReportSchema>;

export const QualityGateDecisionSchema = z
  .enum(['accept', 'retry', 'unable_to_verify', 'empty_workspace'])
  .catch('accept');

export type QualityGateDecision = z.infer<typeof QualityGateDecisionSchema>;

export const PipelineInfoSchema = z
  .object({
    storage_used: z.string().default(''),
    llm_provider: z.string().default(''),
    llm_model: z.string().default(''),
    encoder_model: z.string().default(''),
    reranker_model: z.string().default(''),
    nli_verifier_model: z.string().default(''),
  })
  .passthrough();

export type PipelineInfo = z.infer<typeof PipelineInfoSchema>;

export const SubgraphQueryResponseSchema = z
  .object({
    query: z.string().catch(''),
    answer: z.string().nullish(),
    routing_strategy: z.string().nullish(),
    query_type: z.string().nullish(),
    selected_tools: z.array(z.string()).catch([]),
    cypher_status: z.string().nullish(),
    cypher_repair_count: z.number().int().default(0),
    path_critic_expanded: z.boolean().default(false),
    grounded_answer: z.string().default(''),
    traceability_score: z.number().default(0),
    verified_claims: z.array(VerifiedClaimSchema).catch([]),
    citations: z.array(CitationSchema).catch([]),
    answer_contract: z.record(z.string(), z.any()).nullish(),
    subgraph: SubgraphDataSchema.catch({ nodes: [], edges: [] }),
    top_chunks: z.array(TopChunkSchema).catch([]),
    quality_gate_decision: QualityGateDecisionSchema.catch('accept'),
    quality_gate_report: QualityGateReportSchema.nullish(),
    retry_count: z.number().int().default(0),
    execution_time: z.number().default(0),
    message: z.string().nullish(),
    command: z.string().nullish(),
    meta: z.record(z.string(), z.any()).nullish(),

    // Pipeline Substrates & Neural Model Provenance
    pipeline_info: PipelineInfoSchema.nullish(),
    storage_used: z.string().nullish(),
    llm_provider: z.string().nullish(),
    llm_model: z.string().nullish(),
    encoder_model: z.string().nullish(),
    reranker_model: z.string().nullish(),
    nli_verifier_model: z.string().nullish(),

    // Dynamic Follow-Up Inquiries & Suggestions from Gateway / LLM Node
    follow_up_inquiries: z.array(z.string()).nullish(),
    suggestions: z.array(z.string()).nullish(),

    // LangGraph Query Intake & Reformulation Pipeline State Fields
    standalone_query: z.string().nullish(),
    decomposed_queries: z.array(z.string()).catch([]),
    intent_route: z.string().nullish(),
    latency_sec: z.number().nullish(),
    error_log: z.string().nullish(),
    thread_id: z.string().nullish(),
    persisted: z.boolean().nullish(),
    saved: z.boolean().nullish(),
    persistence_status: z.string().nullish(),
    persistence_error: z.string().nullish(),
  })
  .passthrough();

export type SubgraphQueryResponse = z.infer<typeof SubgraphQueryResponseSchema>;

export const AgentQueryResponseSchema = z
  .object({
    query: z.string().nullish(),
    query_type: z.string().nullish(),
    selected_tools: z.array(z.string()).catch([]),
    grounded_answer: z.string().default(''),
    answer: z.string().nullish(),
    response: z.string().nullish(),
    tool_calls: z.array(z.any()).nullish(),
    traceability_score: z.number().default(0),
    verified_claims: z.array(VerifiedClaimSchema).catch([]),
    citations: z.array(CitationSchema).catch([]),
    answer_contract: z.record(z.string(), z.any()).nullish(),
    pipeline_info: PipelineInfoSchema.nullish(),
    storage_used: z.string().nullish(),
    llm_provider: z.string().nullish(),
    llm_model: z.string().nullish(),
    encoder_model: z.string().nullish(),
    reranker_model: z.string().nullish(),
    nli_verifier_model: z.string().nullish(),
  })
  .passthrough();

export type AgentQueryResponse = z.infer<typeof AgentQueryResponseSchema>;

// ─── Cross-Session Chat Persistence Schemas ─────────────────────────────────

export const PersistedChatSessionSchema = z
  .object({
    thread_id: z.string(),
    session_id: z.string().nullish(),
    username: z.string().default(''),
    title: z.string().default('New Chat'),
    messages: z.array(z.any()).catch([]),
    created_at: z.string().nullish(),
    updated_at: z.string().nullish(),
    selectedSourceIds: z.array(z.string()).nullish(),
    sources: z.array(z.any()).nullish(),
    attached_docs: z.array(z.string()).nullish(),
    is_saved: z.boolean().optional().default(false),
    forkedFromSessionId: z.string().nullish(),
    forkedFromTitle: z.string().nullish(),
    forkedAtTurnIndex: z.number().int().nullish(),
    forkedAtTimestamp: z.string().nullish(),
  })
  .passthrough();

export type PersistedChatSession = z.infer<typeof PersistedChatSessionSchema>;

export const ChatHistoryResponseSchema = z
  .object({
    thread_id: z.string(),
    session_id: z.string().nullish(),
    username: z.string().nullish().default(''),
    title: z.string().nullish().default('Chat Session'),
    messages: z.array(z.any()).default([]),
    created_at: z.string().nullish(),
    updated_at: z.string().nullish(),
    selectedSourceIds: z.array(z.string()).nullish(),
    sources: z.array(z.any()).nullish(),
    is_saved: z.boolean().optional().default(false),
  })
  .passthrough();

export type ChatHistoryResponse = z.infer<typeof ChatHistoryResponseSchema>;

export const ChatSessionSummarySchema = z
  .object({
    id: z.string(),
    thread_id: z.string().nullish(),
    session_id: z.string().nullish(),
    username: z.string().nullish().default(''),
    title: z.string(),
    timestamp: z.string().nullish(),
    created_at: z.string().nullish(),
    updated_at: z.string().nullish(),
    is_saved: z.boolean().optional().default(false),
    message_count: z.number().int().nullish(),
  })
  .passthrough();

export type ChatSessionSummary = z.infer<typeof ChatSessionSummarySchema>;

// ─── Session Drawer Contracts ───────────────────────────────────────────────

export const SessionDrawerResponseSchema = z
  .object({
    status: z.string().default('success'),
    session_id: z.string().optional(),
    drawer_documents: z.array(z.string()).default([]),
    total_documents: z.number().int().optional(),
    attached_docs: z.array(z.string()).default([]),
    active_docs: z.array(z.string()).default([]),
    documents: z.array(z.any()).default([]),
    count: z.number().int().default(0),
  })
  .passthrough();

export type SessionDrawerResponse = z.infer<typeof SessionDrawerResponseSchema>;

export const SessionDrawerAttachResponseSchema = z
  .object({
    status: z.string().default('success'),
    action: z.string().optional().default('attach'),
    session_id: z.string(),
    attached_document: z.string().optional(),
    attached_docs: z.array(z.string()).default([]),
    active_docs: z.array(z.string()).default([]),
    count: z.number().int().default(0),
  })
  .passthrough();

export type SessionDrawerAttachResponse = z.infer<typeof SessionDrawerAttachResponseSchema>;

export const SessionDrawerRemoveResponseSchema = z
  .object({
    status: z.string().default('success'),
    action: z.string().optional().default('remove'),
    session_id: z.string(),
    removed_document: z.string().optional(),
    attached_docs: z.array(z.string()).default([]),
    active_docs: z.array(z.string()).default([]),
    count: z.number().int().default(0),
  })
  .passthrough();

export type SessionDrawerRemoveResponse = z.infer<typeof SessionDrawerRemoveResponseSchema>;

export const SessionDrawerUpdateResponseSchema = z
  .object({
    status: z.string().default('success'),
    session_id: z.string(),
    attached_docs: z.array(z.string()).default([]),
    active_docs: z.array(z.string()).default([]),
  })
  .passthrough();

export type SessionDrawerUpdateResponse = z.infer<typeof SessionDrawerUpdateResponseSchema>;

export const FeedbackStatsSchema = z
  .object({
    thumbs_up: z.number().int().default(0),
    thumbs_down: z.number().int().default(0),
    satisfaction_ratio: z.number().default(0),
    total_feedback: z.number().int().default(0),
  })
  .passthrough();

export type FeedbackStats = z.infer<typeof FeedbackStatsSchema>;
