import type { ApiError } from '../types';
import { sanitizeStreamText } from '../utils/sanitizeStreamText';
import type { RequestOptions } from './client';

export interface StreamLineParserContext {
  options: RequestOptions;
  endpoint: string;
  responseStatus: number;
  onChunk?: (chunk: string, accumulated: string) => void;
}

export interface StreamLineParserState {
  fullText: string;
  currentEvent: string;
  streamMetadata?: Record<string, unknown>;
  streamError: ApiError | null;
  isStreamComplete: boolean;
}

export function createStreamLineParser(
  ctx: StreamLineParserContext,
  state: StreamLineParserState
) {
  const asRecord = (v: unknown): Record<string, unknown> | null =>
    v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;

  const getStringField = (obj: Record<string, unknown> | null, key: string): string | undefined =>
    obj && typeof obj[key] === 'string' ? (obj[key] as string) : undefined;

  return (line: string) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(':')) {
      if (!trimmed) state.currentEvent = '';
      return;
    }

    if (trimmed.startsWith('event:')) {
      state.currentEvent = trimmed.slice(6).trim();
      return;
    }

    let payload = line;
    let isData = false;
    if (payload.startsWith('data:')) {
      isData = true;
      payload = payload.slice(5).replace(/^[ \t]/, '');
    }

    if (!payload) return;

    if (payload.trim() === '[DONE]') {
      state.currentEvent = '';
      state.isStreamComplete = true;
      return;
    }

    const trimmedPayload = payload.trim();
    if (
      (trimmedPayload.startsWith('{') && trimmedPayload.endsWith('}')) ||
      (trimmedPayload.startsWith('[') && trimmedPayload.endsWith(']'))
    ) {
      try {
        const parsed: unknown = JSON.parse(trimmedPayload);
        const p = asRecord(parsed);

        if (
          (state.currentEvent === 'node_update' || state.currentEvent === 'stage' || p?.node || p?.stage) &&
          (p?.node !== undefined || p?.stage !== undefined)
        ) {
          state.currentEvent = '';
          if (p) ctx.options.onStageUpdate?.(p);
          return;
        }

        if (p?.error !== undefined) {
          state.currentEvent = '';
          const errObj = asRecord(p.error) || { message: String(p.error) };
          const code = getStringField(errObj, 'code') || 'STREAM_ERROR';
          const message =
            getStringField(errObj, 'message') || 'An error occurred during streaming';
          state.streamError = {
            code,
            message,
            status: ctx.responseStatus,
            endpoint: ctx.endpoint,
            retryable: code !== 'CANCELLED',
            timestamp: new Date().toISOString(),
          };
          return;
        }

        if (
          state.currentEvent === 'citations' ||
          (Array.isArray(parsed) &&
            parsed.length > 0 &&
            asRecord(parsed[0])?.citation_index !== undefined)
        ) {
          state.streamMetadata = {
            ...state.streamMetadata,
            citations: parsed,
          };
          ctx.options.onMetadata?.({ citations: parsed });
          return;
        }

        const isMetadataObject = Boolean(
          p &&
            (p.citations !== undefined ||
              p.subgraph !== undefined ||
              p.sources !== undefined ||
              p.verified_claims !== undefined ||
              p.status === 'completed' ||
              p.status === 'SUCCESS' ||
              p.quality_gate_decision !== undefined)
        );

        if (isMetadataObject && p) {
          state.currentEvent = '';
          state.streamMetadata = {
            ...state.streamMetadata,
            ...p,
          };
          ctx.options.onMetadata?.(p);

          const candArr = Array.isArray(p?.candidates) ? (p.candidates as any[]) : [];
          const candText =
            candArr[0]?.content?.parts?.[0]?.text ||
            (candArr[0]?.delta?.parts?.[0]?.text as string | undefined);

          const answerInMeta =
            getStringField(p, 'grounded_answer') ??
            getStringField(p, 'answer') ??
            getStringField(p, 'reply') ??
            getStringField(p, 'response') ??
            getStringField(p, 'output') ??
            getStringField(p, 'result') ??
            candText;
          if (answerInMeta && (!state.fullText.trim() || answerInMeta.length > state.fullText.length)) {
            state.fullText = sanitizeStreamText(answerInMeta);
            ctx.onChunk?.(state.fullText, state.fullText);
          }
          return;
        }

        const deltaObj = asRecord(p?.delta);
        const candArr = Array.isArray(p?.candidates) ? (p.candidates as any[]) : [];
        const candText =
          candArr[0]?.content?.parts?.[0]?.text ||
          (candArr[0]?.delta?.parts?.[0]?.text as string | undefined) ||
          (Array.isArray(deltaObj?.parts) && (deltaObj.parts as any[])[0]?.text);

        const token =
          getStringField(p, 'token') ??
          getStringField(p, 'text') ??
          getStringField(p, 'content') ??
          getStringField(deltaObj, 'content') ??
          (typeof candText === 'string' ? candText : undefined) ??
          (typeof p?.delta === 'string' ? p.delta : undefined) ??
          (!state.fullText.trim()
            ? (getStringField(p, 'grounded_answer') ??
              getStringField(p, 'answer') ??
              getStringField(p, 'response') ??
              getStringField(p, 'reply') ??
              getStringField(p, 'output') ??
              getStringField(p, 'result'))
            : undefined) ??
          null;
        if (typeof token === 'string') {
          state.currentEvent = '';
          if (token.length > 0) {
            state.fullText += token;
            ctx.onChunk?.(token, state.fullText);
          }
          return;
        }

        return;
      } catch {
        const unpacked = sanitizeStreamText(trimmedPayload);
        if (unpacked && !unpacked.startsWith('{')) {
          state.fullText += unpacked;
          ctx.onChunk?.(unpacked, state.fullText);
          return;
        }
        return;
      }
    }

    if (isData) {
      state.fullText += `${payload}\n`;
      ctx.onChunk?.(`${payload}\n`, state.fullText);
      return;
    }

    if (!trimmedPayload.startsWith('{') && !trimmedPayload.startsWith('[')) {
      state.fullText += `${line}\n`;
      ctx.onChunk?.(`${line}\n`, state.fullText);
    }
  };
}
