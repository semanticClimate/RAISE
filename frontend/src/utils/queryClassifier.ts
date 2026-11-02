/**
 * Query Intent Classifier
 * =======================
 * Differentiates fast conversational chat (greetings, identity, pleasantries)
 * from deep academic GraphRAG queries.
 *
 * Sid says: Fast conversational queries return in <5ms from the backend and
 * must NOT mount the multi-step research pipeline skeleton or stage loading bars.
 */

export function isConversationalQuery(query?: string | null): boolean {
  if (!query) return false;
  const qClean = query.trim();
  if (!qClean) return false;
  const qLower = qClean.toLowerCase();

  const patterns = [
    /^(he|hi|hello|hey|hekko|helo|heyo|heyy+|hii+|hie|hlo|hlw|greetings|howdy|hola|yo|sup|wassup)\b/i,
    /^good\s+(morning|afternoon|evening|day|night)\b/i,
    /\b(?:my\s+name\s+is|call\s+me)\b/i,
    /\b(?:do\s+you\s+know|what\s+is|what's)\s+my\s+name\b/i,
    /\bwho\s+am\s+i\b/i,
    /\bdo\s+you\s+remember\b/i,
    /\b(?:what\s+is|what's)\s+your\s+name\b/i,
    /\bwho\s+are\s+you\b/i,
    /\bwhat\s+can\s+you\s+do\b/i,
    /\bhow\s+are\s+you\b/i,
    /\b(?:thank\s+you|thanks|nice\s+to\s+meet\s+you)\b/i,
    /\b(?:what\s+did\s+i\s+(?:just\s+)?(?:say|ask))\b/i,
    /^(test|hello\s+test|ping)\b/i,
  ];

  for (const pat of patterns) {
    if (pat.test(qClean)) {
      return true;
    }
  }

  // Short queries with identity or chit-chat phrases
  if (qClean.split(/\s+/).length <= 6) {
    const conversationalTokens = [
      'who are you',
      'who r u',
      'whats your name',
      'what is your name',
      'my name',
      'your name',
      'hello',
      'hekko',
      'helo',
      'heyo',
      'hi raise',
      'hey there',
    ];
    if (conversationalTokens.some((tok) => qLower.includes(tok))) {
      return true;
    }
  }

  return false;
}
