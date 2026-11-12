import {
  type Citation,
  type PipelineInfo,
  type SubgraphQueryRequest,
  type SubgraphQueryResponse,
  SubgraphQueryResponseSchema,
  type TopChunk,
  type VerifiedClaim,
} from '../../types';
import { normalizeCitation } from '../../utils/citationParser';
import { sanitizeStreamText } from '../../api/client';

export const FATAL_HTTP_STATUSES = new Set([401, 402, 403, 429, 500, 502, 503, 504]);

export function isRefusalAnswer(answerText: string): boolean {
  if (!answerText) return false;
  return (
    answerText.includes('INSUFFICIENT_EVIDENCE') ||
    answerText.toLowerCase().includes('do not contain sufficient evidence') ||
    answerText.toLowerCase().includes('unable to verify')
  );
}

export function synthesizeSubgraphResponse(
  meta: Record<string, unknown>,
  rawAnswerText: string,
  req: SubgraphQueryRequest,
  startTime: number
): SubgraphQueryResponse {
  const durationSec = Number(((Date.now() - startTime) / 1000).toFixed(2));
  const cleanAnswer = sanitizeStreamText(rawAnswerText);

  let citations: Citation[] = Array.isArray(meta.citations)
    ? meta.citations.map((c: unknown, idx: number) =>
        normalizeCitation(c, idx + 1, req.active_docs?.[0])
      )
    : [];

  if (citations.length === 0 && Array.isArray(meta.top_chunks) && meta.top_chunks.length > 0) {
    citations = (meta.top_chunks as unknown[]).map((chk: unknown, idx: number) => {
      const chkObj = chk && typeof chk === 'object' ? (chk as Record<string, unknown>) : {};
      const chkMeta =
        chkObj.metadata && typeof chkObj.metadata === 'object'
          ? (chkObj.metadata as Record<string, unknown>)
          : {};
      return normalizeCitation(
        {
          chunk_id: chkObj.chunk_id || chkObj.id,
          pdf_filename:
            chkObj.pdf_filename ||
            chkObj.filename ||
            chkMeta.pdf_filename ||
            chkMeta.filename,
          primary_page:
            chkObj.primary_page ?? chkObj.page ?? chkMeta.primary_page ?? chkMeta.page,
          heading: chkObj.heading || chkMeta.heading,
          plain_text: chkObj.plain_text || chkObj.text || chkObj.content,
          similarity: typeof chkObj.similarity === 'number' ? chkObj.similarity : 0.9,
        },
        idx + 1,
        req.active_docs?.[0]
      );
    });
  }

  const subgraph =
    meta.subgraph && typeof meta.subgraph === 'object'
      ? (meta.subgraph as SubgraphQueryResponse['subgraph'])
      : { nodes: [], edges: [] };

  const isRefusal = isRefusalAnswer(cleanAnswer);
  const normalizedDecision: SubgraphQueryResponse['quality_gate_decision'] =
    meta.quality_gate_decision && meta.quality_gate_decision !== 'accept'
      ? (meta.quality_gate_decision as SubgraphQueryResponse['quality_gate_decision'])
      : isRefusal
        ? 'unable_to_verify'
        : ((meta.quality_gate_decision as SubgraphQueryResponse['quality_gate_decision']) || 'accept');

  // Pipeline Substrates & Neural Model Provenance Extraction
  const rawPipelineInfo =
    meta.pipeline_info && typeof meta.pipeline_info === 'object'
      ? (meta.pipeline_info as Record<string, unknown>)
      : {};

  const storageUsed =
    typeof rawPipelineInfo.storage_used === 'string' && rawPipelineInfo.storage_used
      ? rawPipelineInfo.storage_used
      : typeof meta.storage_used === 'string' && meta.storage_used
        ? meta.storage_used
        : 'ChromaDB (Vector) + Neo4j (Graph)';

  const llmProvider =
    typeof rawPipelineInfo.llm_provider === 'string' && rawPipelineInfo.llm_provider
      ? rawPipelineInfo.llm_provider
      : typeof meta.llm_provider === 'string' && meta.llm_provider
        ? meta.llm_provider
        : 'gemini';

  const llmModel =
    typeof rawPipelineInfo.llm_model === 'string' && rawPipelineInfo.llm_model
      ? rawPipelineInfo.llm_model
      : typeof meta.llm_model === 'string' && meta.llm_model
        ? meta.llm_model
        : 'gemini-3.5-flash-lite';

  const encoderModel =
    typeof rawPipelineInfo.encoder_model === 'string' && rawPipelineInfo.encoder_model
      ? rawPipelineInfo.encoder_model
      : typeof meta.encoder_model === 'string' && meta.encoder_model
        ? meta.encoder_model
        : 'google/embeddinggemma-2';

  const rerankerModel =
    typeof rawPipelineInfo.reranker_model === 'string' && rawPipelineInfo.reranker_model
      ? rawPipelineInfo.reranker_model
      : typeof meta.reranker_model === 'string' && meta.reranker_model
        ? meta.reranker_model
        : 'jinaai/jina-reranker-v3.5';

  const nliVerifierModel =
    typeof rawPipelineInfo.nli_verifier_model === 'string' && rawPipelineInfo.nli_verifier_model
      ? rawPipelineInfo.nli_verifier_model
      : typeof meta.nli_verifier_model === 'string' && meta.nli_verifier_model
        ? meta.nli_verifier_model
        : 'dleemiller/finecat-nli-ultra-l';

  const pipelineInfo: PipelineInfo = {
    storage_used: storageUsed,
    llm_provider: llmProvider,
    llm_model: llmModel,
    encoder_model: encoderModel,
    reranker_model: rerankerModel,
    nli_verifier_model: nliVerifierModel,
  };

  const synthesizedResp: SubgraphQueryResponse = {
    query: req.query,
    grounded_answer: cleanAnswer,
    answer: cleanAnswer,
    reply: cleanAnswer,
    response: cleanAnswer,
    content: cleanAnswer,
    text: cleanAnswer,
    pipeline_info: pipelineInfo,
    storage_used: storageUsed,
    llm_provider: llmProvider,
    llm_model: llmModel,
    encoder_model: encoderModel,
    reranker_model: rerankerModel,
    nli_verifier_model: nliVerifierModel,
    latency_sec:
      typeof meta.latency_sec === 'number' && meta.latency_sec > 0
        ? meta.latency_sec
        : durationSec,
    execution_time:
      typeof meta.execution_time === 'number' && meta.execution_time > 0
        ? meta.execution_time
        : durationSec,
    traceability_score:
      typeof meta.traceability_score === 'number' ? meta.traceability_score : 0.95,
    subgraph,
    citations,
    verified_claims: (Array.isArray(meta.verified_claims)
      ? meta.verified_claims
      : []) as VerifiedClaim[],
    quality_gate_decision: normalizedDecision,
    selected_tools: (Array.isArray(meta.selected_tools)
      ? meta.selected_tools
      : []) as string[],
    cypher_repair_count:
      typeof meta.cypher_repair_count === 'number' ? meta.cypher_repair_count : 0,
    path_critic_expanded: Boolean(meta.path_critic_expanded),
    top_chunks: (Array.isArray(meta.top_chunks) ? meta.top_chunks : []) as TopChunk[],
    retry_count: typeof meta.retry_count === 'number' ? meta.retry_count : 0,
    decomposed_queries: (Array.isArray(meta.decomposed_queries)
      ? meta.decomposed_queries
      : []) as string[],
    follow_up_inquiries: Array.isArray(meta.follow_up_inquiries)
      ? (meta.follow_up_inquiries as string[])
      : Array.isArray(meta.suggestions)
        ? (meta.suggestions as string[])
        : [],
    suggestions: Array.isArray(meta.suggestions)
      ? (meta.suggestions as string[])
      : Array.isArray(meta.follow_up_inquiries)
        ? (meta.follow_up_inquiries as string[])
        : [],
    persisted: typeof meta.persisted === 'boolean' ? meta.persisted : undefined,
    saved: typeof meta.saved === 'boolean' ? meta.saved : undefined,
    persistence_status:
      typeof meta.persistence_status === 'string' ? meta.persistence_status : undefined,
    persistence_error:
      typeof meta.persistence_error === 'string' ? meta.persistence_error : null,
  };

  const parsed = SubgraphQueryResponseSchema.safeParse(synthesizedResp);
  return parsed.success ? parsed.data : synthesizedResp;
}
