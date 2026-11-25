export interface ParsedReasoningAndAnswer {
  /** Reasoning scratchpad content extracted from <think>/<thought>/<reasoning> tags, if any. */
  thoughtText: string | null;
  /** Final answer text to render as structured Markdown. */
  answerText: string;
  /** True when a reasoning tag opened in the buffer has not closed yet (active token streaming). */
  isStreamingThought: boolean;
  /** True when the rendered answerText was rescued/promoted from a reasoning trace. */
  rescuedFromThought: boolean;
}

const HAS_MEANINGFUL_TEXT_RE = /[a-zA-Z0-9\u00C0-\u024F\u0370-\u1FFF\u2C00-\uD7FF]/;
const MARKDOWN_TABLE_RE = /(?:^|\n)\|.+\|\s*\n\|[\s:|-]+\|/;

/**
 * Checks whether text contains meaningful alphanumeric/letter content beyond
 * whitespace, punctuation, and standalone bracketed citation markers like `[1]`.
 */
export function hasMeaningfulAnswerText(text: string): boolean {
  if (!text) return false;
  const withoutCitations = text.replace(/\[\^?\d+(?:\s*,\s*\d+)*\]/g, ' ').trim();
  return HAS_MEANINGFUL_TEXT_RE.test(withoutCitations);
}

/**
 * Extracts explicit concluding answer blocks from a reasoning monologue when a model
 * trapped its conclusion inside `<think>...</think>`. Returns null if no distinct
 * conclusion boundary is found (or if cutting there would drop a synthesized table),
 * signalling callers to promote the full trace instead.
 */
function rescueConclusionFromThought(
  thought: string
): { remainingThought: string | null; conclusion: string } | null {
  const trimmed = thought.trim();
  if (!trimmed) return null;

  // Match explicit conclusion labels/headers or strong conclusive transitions.
  // We evaluate matches from last to first so mid-scratchpad phrasing ("Wait, therefore let me check...")
  // does not override the true conclusion near the end of the trace.
  const explicitMarkerRe =
    /(?:^|\n)\s*(?:#{1,6}\s*)?(?:\*\*|__)?(?:Final Answer|Conclusion|Summary Answer|The answer is|Answer|Result|In conclusion|To conclude|To summarize|Therefore|Thus)\b(?:\*\*|__)?\s*[:\-–—,]?\s*/gi;

  const matches: Array<{ index: number; endIndex: number; label: string }> = [];
  for (const m of trimmed.matchAll(explicitMarkerRe)) {
    if (typeof m.index === 'number') {
      matches.push({
        index: m.index,
        endIndex: m.index + m[0].length,
        label: m[0],
      });
    }
  }

  for (let i = matches.length - 1; i >= 0; i--) {
    const match = matches[i];
    const before = trimmed.slice(0, match.index).trim();
    const afterLabel = trimmed.slice(match.endIndex).trim();
    if (!before || !hasMeaningfulAnswerText(afterLabel)) continue;

    // Guard: never discard an upstream Markdown table in favor of a tiny wrap-up sentence.
    if (
      MARKDOWN_TABLE_RE.test(before) &&
      !MARKDOWN_TABLE_RE.test(afterLabel) &&
      afterLabel.length < 220
    ) {
      return null;
    }

    // Normalize lowercase sentence fragment after transitional cue (e.g. "Therefore, the total is 38.")
    const normalizedConclusion = /^[a-z]/.test(afterLabel)
      ? afterLabel.charAt(0).toUpperCase() + afterLabel.slice(1)
      : afterLabel;

    return {
      remainingThought: before,
      conclusion: normalizedConclusion,
    };
  }

  // Secondary check: inline sentence boundary ("... Therefore, ...", "Final Answer:", "The answer is:").
  const inlineExplicitRe =
    /(?:^|[.!?]+\s+)(?:\*\*|__)?(?:Final Answer|The answer is|In conclusion|To conclude|Therefore)\b(?:\*\*|__)?\s*[:,-]\s+([\s\S]+)$/i;
  const inlineMatch = trimmed.match(inlineExplicitRe);
  if (inlineMatch && typeof inlineMatch.index === 'number') {
    const before = trimmed.slice(0, inlineMatch.index).trim();
    const rawConclusion = inlineMatch[1]?.trim() || '';
    const conclusion = /^[a-z]/.test(rawConclusion)
      ? rawConclusion.charAt(0).toUpperCase() + rawConclusion.slice(1)
      : rawConclusion;
    if (
      before &&
      hasMeaningfulAnswerText(conclusion) &&
      !(MARKDOWN_TABLE_RE.test(before) && !MARKDOWN_TABLE_RE.test(conclusion) && conclusion.length < 220)
    ) {
      return {
        remainingThought: before,
        conclusion,
      };
    }
  }

  return null;
}

/**
 * Separates reasoning monologue (`<think>...</think>`, `<thought>...</thought>`, `<reasoning>...</reasoning>`)
 * from the visible answer before markdown/citation formatting runs.
 *
 * Handles:
 * - Closed reasoning blocks + external answer
 * - Unclosed streaming reasoning tags (live token streaming UX)
 * - Orphan closing `</think>` tags when an upstream stream dropped the opening tag
 * - Trapped answers inside `<think>` when external text is empty or citations-only (via Conclusion
 *   Rescue or Direct Content Promotion)
 */
export function extractReasoningAndAnswer(
  rawText: string,
  options: { isStreaming?: boolean } = {}
): ParsedReasoningAndAnswer {
  if (!rawText) {
    return {
      thoughtText: null,
      answerText: '',
      isStreamingThought: false,
      rescuedFromThought: false,
    };
  }

  const closedThoughts: string[] = [];
  let working = rawText;

  // 1. Extract all closed <think> / <thought> / <reasoning> blocks cleanly.
  working = working.replace(
    /<(think|thought|reasoning)\b[^>]*>([\s\S]*?)<\/\1>/gi,
    (_full, _tag, inner: string) => {
      const cleaned = inner.trim();
      if (cleaned) closedThoughts.push(cleaned);
      return '\n';
    }
  );

  // 2. Check for an unclosed opening reasoning tag (active streaming or token truncation).
  let hasUnclosedTag = false;
  const openTagMatch = working.match(/<(think|thought|reasoning)\b[^>]*>([\s\S]*)$/i);
  if (openTagMatch && typeof openTagMatch.index === 'number') {
    hasUnclosedTag = true;
    const unclosedInner = openTagMatch[2]?.trim();
    if (unclosedInner) {
      closedThoughts.push(unclosedInner);
    }
    working = working.slice(0, openTagMatch.index);
  } else {
    // 3. Guard against orphan closing tag when opening tag was lost upstream.
    const orphanCloseMatch = working.match(/^([\s\S]*?)<\/(?:think|thought|reasoning)>/i);
    if (orphanCloseMatch && typeof orphanCloseMatch.index === 'number') {
      const orphanInner = orphanCloseMatch[1]?.trim();
      if (orphanInner) closedThoughts.push(orphanInner);
      working = working.slice(orphanCloseMatch[0].length);
    }
  }

  const combinedThought = closedThoughts.join('\n\n').trim() || null;
  const trimmedOutside = working.trim();

  // Preserve standalone outer citations (e.g. "[1] [2]") if the answer body itself is empty
  // and was trapped inside <think>.
  const isStreamingThought = Boolean(options.isStreaming && hasUnclosedTag && !hasMeaningfulAnswerText(trimmedOutside));

  if (hasMeaningfulAnswerText(trimmedOutside)) {
    return {
      thoughtText: combinedThought,
      answerText: trimmedOutside,
      isStreamingThought: false,
      rescuedFromThought: false,
    };
  }

  // While streaming an unclosed <think> trace, surface it live instead of rescuing a partial conclusion.
  if (isStreamingThought) {
    return {
      thoughtText: combinedThought,
      answerText: '',
      isStreamingThought: true,
      rescuedFromThought: false,
    };
  }

  // Outside answer is empty (or only citation brackets). Rescue from thoughtText if present!
  if (combinedThought) {
    const outerCitations = trimmedOutside.match(/\[\^?\d+(?:\s*,\s*\d+)*\]/g)?.join(' ') || '';
    const rescued = rescueConclusionFromThought(combinedThought);
    if (rescued) {
      const answerWithCitations =
        outerCitations && !/\[\^?\d+/.test(rescued.conclusion)
          ? `${rescued.conclusion} ${outerCitations}`
          : rescued.conclusion;
      return {
        thoughtText: rescued.remainingThought,
        answerText: answerWithCitations,
        isStreamingThought: false,
        rescuedFromThought: true,
      };
    }

    // Direct Content Promotion: promote full thought trace as structured Markdown,
    // clearing redundant collapsed accordion copy so the trace isn't duplicated twice.
    const promoted =
      outerCitations && !/\[\^?\d+/.test(combinedThought)
        ? `${combinedThought} ${outerCitations}`
        : combinedThought;
    return {
      thoughtText: null,
      answerText: promoted,
      isStreamingThought: false,
      rescuedFromThought: true,
    };
  }

  return {
    thoughtText: null,
    answerText: trimmedOutside,
    isStreamingThought: false,
    rescuedFromThought: false,
  };
}

/**
 * Returns clean user-facing answer text suitable for clipboard copy, speech synthesis,
 * and document export — stripping raw `<think>` tags while preserving rescued answers
 * whenever a model placed its final answer solely inside `<think>`.
 */
export function getCopyableAnswerText(rawText: string): string {
  const { answerText } = extractReasoningAndAnswer(rawText, { isStreaming: false });
  return answerText;
}
