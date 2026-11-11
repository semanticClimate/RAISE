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

  // 4. Strip non-printable control characters (except \t, \n, \r) like \x08 backspaces
  cleaned = cleaned
    .split('')
    .filter((char) => {
      const code = char.charCodeAt(0);
      return (code >= 32 && code !== 127) || code === 9 || code === 10 || code === 13;
    })
    .join('');

  // 5. Strip literal escaped control character sequences from PDF/OCR extractors (e.g. \x08, \u0008)
  cleaned = cleaned.replace(
    /\\x0[0-8bBcCeEfF]|\\x1[0-9a-fA-F]|\\x7[fF]|\\u000[0-8bBcCeEfF]|\\u001[0-9a-fA-F]/g,
    ''
  );

  // 6. Ensure double newlines before bullets so glued list items (e.g. "...text• **Title**") are properly spaced
  cleaned = cleaned.replace(/([^\n])\s*•\s*/g, '$1\n\n• ');

  // 7. Normalize excess blank lines
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  // 8. Replace internal phrasing: "from the frontend to begin" -> "to RAISE to begin"
  cleaned = cleaned.replace(/from the frontend to begin/gi, 'to RAISE to begin');

  return cleaned;
}
