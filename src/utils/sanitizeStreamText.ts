import { sanitizeMultilingualText } from './krutiDevConverter';

const MD_TABLE_BLOCK_RE = /(?:^|\n)(\|[^\n]+\|\s*\n\|[ \t:|-]+\|(?:[ \t]*\n\|[^\n]+\|)*)/g;

/**
 * Protects pipe-delimited Markdown table blocks while running prose formatting transforms
 * (such as bullet expansion or blank-line normalization) so multi-column tables stay intact.
 */
export function preserveMarkdownTables(
  text: string,
  transform: (prose: string) => string
): string {
  if (!text) return text;
  const tables: string[] = [];
  const masked = text.replace(MD_TABLE_BLOCK_RE, (fullMatch, tableBlock: string) => {
    const leadingNewline = fullMatch.startsWith('\n') ? '\n' : '';
    const token = `__MD_TABLE_BLOCK_${tables.length}__`;
    tables.push(tableBlock);
    return `${leadingNewline}${token}`;
  });

  const transformed = transform(masked);
  if (tables.length === 0) return transformed;

  return transformed.replace(/__MD_TABLE_BLOCK_(\d+)__/g, (placeholder, idx) => {
    const index = Number.parseInt(idx, 10);
    return tables[index] !== undefined ? tables[index] : placeholder;
  });
}

/**
 * Sanitizes stream output by stripping SSE artifacts and unpacking any leaked JSON token fragments.
 * Handles cases where network chunk boundary anomalies or legacy strings contain raw JSON blocks:
 *   Hello! Ask me any{"token": " question "} {"token": "regarding"} research
 *   -> Hello! Ask me any question regarding research
 */
export function sanitizeStreamText(text: string): string {
  if (!text) return '';
  let cleaned = text;

  // 1. Unpack nested delta content if present: {"delta": {"content": "..."}}
  cleaned = cleaned.replace(/\{"delta":\s*\{"content":\s*"((?:[^"\\]|\\.)*)"\}\}/g, (_, inner) => {
    try {
      return JSON.parse(`"${inner}"`);
    } catch {
      return inner;
    }
  });

  // 2. Unpack standard JSON tokens: {"token": "..."} / {"text": "..."} / {"content": "..."}
  cleaned = cleaned.replace(
    /\{"(?:token|text|content|response|reply)":\s*"((?:[^"\\]|\\.)*)"\}/g,
    (_, inner) => {
      try {
        return JSON.parse(`"${inner}"`);
      } catch {
        return inner;
      }
    }
  );

  // 3. Strip stray SSE line artifacts, event headers, and leaked protocol objects
  cleaned = cleaned
    // Strip stray SSE event declarations e.g. "event: stage" or "event: token"
    .replace(/^[ \t]*event:\s*[a-zA-Z0-9_\-]+\s*$/gm, '')
    // Strip intermediate pipeline stage progression objects e.g. {"stage": "VECTOR_RETRIEVAL", ...}
    .replace(/\{"(?:stage|node)":\s*"[^"]*".*?\}\n?/g, '')
    // Strip stream error packets e.g. {"error": {"code": "...", "message": "..."}}
    .replace(/\{"error":\s*\{.*?\}\}\n?/g, '')
    // Strip leaked terminal status metadata objects e.g. {"status": "SUCCESS", "citations": ...}
    .replace(/\{"status":\s*"(?:SUCCESS|completed|error)".*?\}\n?/g, '')
    // Strip SSE data prefixes
    .replace(/^[ \t]*data:\s*/gm, '')
    // Strip keepalive comments
    .replace(/^[ \t]*:\s*keepalive\s*$/gm, '')
    // Strip terminal SSE stream marker
    .replace(/\[DONE\]/g, '');

  // 4. Strip non-printable control characters (except \t, \n, \r) without allocating arrays
  cleaned = cleaned.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');

  // 5. Strip literal escaped control character sequences from PDF/OCR extractors (e.g. \x08, \u0008)
  cleaned = cleaned.replace(
    /\\x0[0-8bBcCeEfF]|\\x1[0-9a-fA-F]|\\x7[fF]|\\u000[0-8bBcCeEfF]|\\u001[0-9a-fA-F]/g,
    ''
  );

  // 6-7. Expand glued bullets onto distinct lines and normalize blank lines without splitting Markdown tables
  cleaned = preserveMarkdownTables(cleaned, (prose) =>
    prose.replace(/([^\n])\s*•\s*/g, '$1\n\n• ').replace(/\n{3,}/g, '\n\n')
  );

  // 8. Strip robotic introductory meta-filler in scientific RAG responses
  cleaned = cleaned.replace(
    /^(?:Examining the (?:text|document|context|provided text)[,:]?\s*(?:the core issue appears to be\s*)?|Based on the (?:provided|attached) (?:text|documents?|sources?|context)[,:]?\s*|Looking at the (?:provided|attached) (?:text|documents?|sources?|context)[,:]?\s*|According to the (?:provided|attached) (?:text|documents?|sources?|context)[,:]?\s*)/i,
    ''
  );
  if (cleaned.length > 0 && /^[a-z]/.test(cleaned)) {
    cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }

  // 9. Replace internal phrasing: "from the frontend to begin" -> "to RAISE to begin"
  cleaned = cleaned.replace(/from the frontend to begin/gi, 'to RAISE to begin');

  // 10. Normalize legacy Kruti Dev non-Unicode font mojibake and zero-width spaces (\u200B)
  cleaned = sanitizeMultilingualText(cleaned);

  return cleaned;
}
