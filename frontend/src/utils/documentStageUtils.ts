/**
 * Document Ingestion Pipeline Stage Utilities
 * Maps ingestion progress percentage and phase to descriptive human-readable pipeline stages.
 */
export function getDocumentStageLabel(progress: number, phase?: string): string {
  if (phase === 'failed') return 'Ingestion failed';
  if (phase === 'ready' || progress >= 100) return 'Ready';

  if (phase === 'embedding' || progress >= 85) {
    return 'Indexing embeddings & graph...';
  }
  if (phase === 'chunking' || progress >= 65) {
    return 'Extracting semantic chunks...';
  }
  if (phase === 'parsing' || progress >= 35) {
    return 'Parsing layout & tables (Docling)...';
  }
  return 'Uploading file...';
}
