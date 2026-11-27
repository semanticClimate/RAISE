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

export function isDocumentProcessingStatus(status?: string): boolean {
  const norm = (status || '').toLowerCase().trim();
  return (
    norm !== '' &&
    norm !== 'ready' &&
    norm !== 'indexed' &&
    norm !== 'completed' &&
    norm !== 'error' &&
    norm !== 'failed'
  );
}

export function isDocumentErrorStatus(status?: string): boolean {
  const norm = (status || '').toLowerCase().trim();
  return norm === 'error' || norm === 'failed';
}

export function extractProcessingReportKeys(data: unknown): Array<{ key: string; filename: string }> {
  if (!data || typeof data !== 'object') return [];
  const obj = data as Record<string, unknown>;
  const reports = Array.isArray(obj.reports) ? obj.reports : [];
  const keys: Array<{ key: string; filename: string }> = [];
  for (const rep of reports) {
    if (!rep || typeof rep !== 'object') continue;
    const r = rep as Record<string, unknown>;
    const status = typeof r.status === 'string' ? r.status : undefined;
    const isProcessing =
      isDocumentProcessingStatus(status) ||
      (status === undefined && obj.status === 'processing');
    if (!isProcessing) continue;
    const filename =
      (typeof r.filename === 'string' && r.filename) ||
      (typeof r.document === 'string' && r.document) ||
      '';
    const key =
      (typeof r.doc_id === 'string' && r.doc_id) ||
      (typeof r.document_id === 'string' && r.document_id) ||
      filename;
    if (key) {
      keys.push({ key, filename: filename || key });
    }
  }
  return keys;
}
