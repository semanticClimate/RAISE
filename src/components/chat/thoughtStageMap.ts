/**
 * Mapping table from backend LangGraph stages to user-friendly thoughts.
 * Part of RAISE Chat Observability.
 */
export const STAGE_THOUGHT_MAP: Record<string, string> = {
  RECEIVED: 'Thinking...',
  QUERY_INTAKE: 'Analyzing query intent & entities...',
  INTAKE: 'Analyzing query intent & entities...',
  CACHE_PROBE: 'Probing semantic cache...',
  GLINER_NER: 'Extracting entities via GLiNER...',
  ROUTING: 'Routing query strategy...',
  CONVERSATIONAL: 'Conversational dialogue...',
  PERSONA: 'Persona memory synthesis...',
  COREFERENCE_RESOLUTION: 'Resolving entities & context...',
  QUERY_DECOMPOSITION: 'Decomposing sub-questions...',
  VECTOR_RETRIEVAL: 'Dense vector retrieval (ChromaDB)...',
  VECTOR: 'Dense vector retrieval...',
  RETRIEVAL: 'Dense vector retrieval...',
  RETRIEVE: 'Dense vector retrieval...',
  BM25_RETRIEVAL: 'Keyword & lexical indexing (BM25)...',
  BM25: 'Keyword & lexical indexing (BM25)...',
  GRAPH_RETRIEVAL: 'Traversing knowledge graph (Cypher)...',
  GRAPH: 'Traversing knowledge graph (Cypher)...',
  MULTIHOP: 'Executing multi-hop graph reasoning...',
  FUSION: 'Reciprocal rank fusion...',
  RERANKING: 'Cross-encoder reranking (BGE-M3)...',
  RERANK: 'Cross-encoder reranking (BGE-M3)...',
  RERANKER: 'Cross-encoder reranking (BGE-M3)...',
  SYNTHESIS: 'Synthesizing verified response...',
  SYNTHESIZE: 'Synthesizing verified response...',
  LLM_SYNTHESIS: 'Synthesizing verified response...',
  GENERATE: 'Synthesizing verified response...',
  GENERATION: 'Synthesizing verified response...',
  QUALITY_GATE: 'Verifying factual grounding...',
  EVALUATION: 'Verifying factual grounding...',
  NLI_VERIFIER: 'Verifying factual grounding (FineCat NLI)...',
  COMPLETED: 'Response finalized',
};

/**
 * Resolves the active friendly status phrase from either an explicit stage
 * or the elapsed time during autonomous pipeline execution.
 */
export function getFriendlyThought(stage?: string, elapsedSec = 0): string {
  if (stage) {
    const normalized = stage.toUpperCase().trim();
    if (STAGE_THOUGHT_MAP[normalized]) {
      return STAGE_THOUGHT_MAP[normalized];
    }
  }

  if (elapsedSec >= 3.5) return STAGE_THOUGHT_MAP.SYNTHESIS;
  if (elapsedSec >= 2.8) return STAGE_THOUGHT_MAP.FUSION;
  if (elapsedSec >= 2.1) return STAGE_THOUGHT_MAP.GRAPH_RETRIEVAL;
  if (elapsedSec >= 1.4) return STAGE_THOUGHT_MAP.VECTOR_RETRIEVAL;
  if (elapsedSec >= 0.7) return STAGE_THOUGHT_MAP.QUERY_DECOMPOSITION;
  return STAGE_THOUGHT_MAP.ROUTING;
}
