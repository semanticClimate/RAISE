/**
 * Document Ingestion Pipeline Stage Utilities
 * Maps ingestion progress percentage and phase to descriptive human-readable pipeline stages:
 * parsing ➔ chunking ➔ vectorizing ➔ graph_extraction ➔ completed
 */
export function getDocumentStageLabel(progress: number, phase?: string): string {
  const normPhase = (phase || '').toLowerCase().trim();
  if (normPhase === 'failed' || normPhase === 'error') return 'Ingestion failed';
  if (normPhase === 'ready' || normPhase === 'completed' || progress >= 100) return 'Completed';

  if (
    normPhase === 'graph_extraction' ||
    normPhase.includes('graph') ||
    (progress >= 85 && normPhase !== 'vectorizing' && normPhase !== 'embedding')
  ) {
    return 'Extracting knowledge graph & entities...';
  }
  if (
    normPhase === 'vectorizing' ||
    normPhase === 'embedding' ||
    normPhase.includes('vector') ||
    progress >= 70
  ) {
    return 'Dense vector indexing (ChromaDB)...';
  }
  if (normPhase === 'chunking' || normPhase.includes('chunk') || progress >= 45) {
    return 'Extracting semantic chunks (GGAHC)...';
  }
  if (normPhase === 'parsing' || normPhase.includes('parse') || progress >= 20) {
    return 'Parsing layout & tables (Docling)...';
  }
  return 'Uploading document...';
}
