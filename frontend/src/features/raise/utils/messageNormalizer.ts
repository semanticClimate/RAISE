import type { ChatMessage, SourceDocument } from '../types';

export function extractMessageText(m: ChatMessage): string {
  const t =
    m.text ||
    (m as any).content ||
    m.response?.grounded_answer ||
    m.response?.answer ||
    m.response?.reply ||
    m.response?.response ||
    m.response?.message ||
    m.response?.content ||
    m.response?.text ||
    m.response?.output ||
    (m.response as any)?.result ||
    (m.response as any)?.candidates?.[0]?.content?.parts?.[0]?.text ||
    (m.response as any)?.choices?.[0]?.message?.content ||
    (m.response as any)?.choices?.[0]?.text ||
    '';
  return typeof t === 'string' ? t.trim() : '';
}

export function deduplicateTurns(msgs: ChatMessage[]): ChatMessage[] {
  const result: ChatMessage[] = [];
  for (let i = 0; i < msgs.length; i++) {
    const cur = msgs[i];
    const curText = extractMessageText(cur);
    const hasContent = Boolean(
      curText ||
      cur.error ||
      cur.isThinking ||
      cur.response ||
      (cur.questionVersions &&
        cur.questionVersions.length > 0 &&
        cur.questionVersions[0].responseVersions?.length)
    );

    // Filter out orphaned empty assistant turns (neither thinking nor containing text/response)
    if (cur.role === 'assistant' && !hasContent) {
      continue;
    }

    const prev = result[result.length - 1];
    const prevText = prev ? extractMessageText(prev) : '';
    if (prev && prev.role === cur.role && prevText === curText && curText !== '') {
      continue;
    }
    if (
      prev &&
      prev.role === 'user' &&
      cur.role === 'user' &&
      prevText.toLowerCase() === curText.toLowerCase() &&
      curText !== ''
    ) {
      continue;
    }
    result.push(cur);
  }
  return result;
}

export function harvestSourcesFromMessagesAndDocs(
  messages: any[],
  existingDocs: SourceDocument[] = [],
  fallbackAttachedNames: string[] = [],
  libraryDocs: any[] = []
): SourceDocument[] {
  const docNames = new Set<string>();

  existingDocs.forEach((d) => {
    if (d.name) docNames.add(d.name);
  });

  fallbackAttachedNames.forEach((name) => {
    if (name && typeof name === 'string' && name.trim()) {
      docNames.add(name.trim());
    }
  });

  messages.forEach((msg) => {
    if (Array.isArray(msg?.sources)) {
      msg.sources.forEach((s: any) => {
        if (typeof s === 'string' && s.trim()) docNames.add(s.trim());
        else if (s?.pdf_filename) docNames.add(s.pdf_filename);
        else if (s?.filename) docNames.add(s.filename);
      });
    }
    if (Array.isArray(msg?.response?.sources)) {
      msg.response.sources.forEach((s: any) => {
        if (typeof s === 'string' && s.trim()) docNames.add(s.trim());
        else if (s?.pdf_filename) docNames.add(s.pdf_filename);
        else if (s?.filename) docNames.add(s.filename);
      });
    }
    if (Array.isArray(msg?.citations)) {
      msg.citations.forEach((c: any) => {
        const fn = c?.pdf_filename || c?.filename || (typeof c === 'string' ? c : null);
        if (fn && fn !== 'Audited Document' && fn !== 'Document') docNames.add(fn);
      });
    }
    if (Array.isArray(msg?.response?.citations)) {
      msg.response.citations.forEach((c: any) => {
        const fn = c?.pdf_filename || c?.filename;
        if (fn && fn !== 'Audited Document' && fn !== 'Document') docNames.add(fn);
      });
    }
  });

  if (docNames.size === 0) return existingDocs;

  const result: SourceDocument[] = [];
  const existingMap = new Map(existingDocs.map((d) => [d.name.toLowerCase(), d]));

  docNames.forEach((name) => {
    const lower = name.toLowerCase();
    if (existingMap.has(lower)) {
      result.push(existingMap.get(lower)!);
      return;
    }

    const matchedLibDoc = libraryDocs.find(
      (d: any) => d.filename?.toLowerCase() === lower || d.id === name
    );
    if (!matchedLibDoc) {
      return;
    }
    const szMb = matchedLibDoc?.size_mb || 1.0;

    result.push({
      id: matchedLibDoc?.id || matchedLibDoc?.doc_id || `src-${result.length}-${name}`,
      name,
      size: szMb >= 1 ? `${szMb.toFixed(1)} MB` : `${Math.round(szMb * 1024)} KB`,
      bytes: Math.round(szMb * 1024 * 1024),
      pages: matchedLibDoc?.pages || 1,
      color: name.endsWith('.pdf') ? 'rose' : 'indigo',
      selected: true,
      status: 'ready',
    });
  });

  return result;
}

export function getFormattedChatHistory(msgs: ChatMessage[]): { human: string; ai: string }[] {
  const history: { human: string; ai: string }[] = [];
  for (let idx = 0; idx < msgs.length; idx += 2) {
    const u = msgs[idx];
    const a = msgs[idx + 1];
    if (u && u.role === 'user' && a && a.role === 'assistant' && (a.text || a.content) && !a.error) {
      history.push({
        human: u.text || u.content || '',
        ai: a.text || a.content || '',
      });
    }
  }
  return history.slice(-6);
}

export function isResponsePersisted(data: any): boolean {
  if (!data) return false;
  if (
    data.persisted === false ||
    data.saved === false ||
    data.persistence_status === 'failed' ||
    data.persistence_status === 'error' ||
    data.persistence_error
  ) {
    return false;
  }
  return true;
}
