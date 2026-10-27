# Architectural Safeguards & Hard Rules (NEVER_DO_THESE_MISTAKES.md)
================================================================================
**Project:** RAISE (Research Assessment Intelligence & Semantic Extraction)  
**Applies to:** Frontend (React 19 + Vite), Backend (FastAPI + LangGraph), Hybrid LLM Routing  
**Status:** MANDATORY ARCHITECTURAL POLICY

This document outlines critical failure modes identified during integration testing, their exact root causes, line-by-line before/after patterns, and mandatory engineering rules to prevent regressions.

---

## 1. The SSE Token Swallow Bug (Event State Bleed)

### The Failure:
During GraphRAG execution, intermediate stage progression events (e.g. `event: stage\ndata: {"stage": "QUERY_INTAKE"}`) set `currentEvent = 'stage'`. When answer tokens arrived (`data: {"token": "..."}` or `event: token`), the parser checked `if (currentEvent === 'stage')` and routed all answer tokens to `onStageUpdate()`, dropping them silently. The UI showed an empty response box with a spinning loader, never displaying the answer.

### The Mistake:
```typescript
// ❌ WRONG (State bleed: currentEvent is never reset):
if (line.startsWith('event:')) {
  currentEvent = line.substring(6).trim();
}
// ...
if (currentEvent === 'stage' || p?.stage) {
  options.onStageUpdate?.(p);
  return; // <-- ALL subsequent tokens treated as stage updates and DROPPED!
}
```

### The Rule & Fix:
1. Always reset `currentEvent = ''` on blank SSE lines (`\n\n`) and upon consuming a typed event or data token.
2. Only process `stage` updates if the payload actually contains stage/node metadata (`p?.stage !== undefined || p?.node !== undefined`).
3. Always implement metadata answer recovery: if `fullText` is empty when the final metadata packet arrives, immediately unpack `p.grounded_answer || p.answer || p.reply`.

```typescript
// ✅ CORRECT:
if (!trimmed) {
  currentEvent = ''; // Reset event boundary on empty separator line
  return;
}
// ...
if (
  (currentEvent === 'node_update' || currentEvent === 'stage' || p?.node || p?.stage) &&
  (p?.node !== undefined || p?.stage !== undefined)
) {
  currentEvent = '';
  if (p) options.onStageUpdate?.(p);
  return;
}
if (typeof token === 'string') {
  currentEvent = '';
  fullText += token;
  onChunk?.(token, fullText);
}
```

---

## 2. Schema Contract Asymmetry (`content` vs `text`)

### The Failure:
PostgreSQL `chat_messages` table and Redis store messages with the standard LLM specification: `{"role": "assistant", "content": "..."}`. The React message renderer strictly evaluated `Boolean(msg.text)` and passed `<AnswerMarkdown content={msg.text} />`. When loading saved conversations from the database, `msg.text` was `undefined`, causing the entire conversation feed to render completely blank.

### The Mistake:
```tsx
// ❌ WRONG (Assuming frontend-only property name):
{(((!isCurrentlyActive || Boolean(msg.text)) && Boolean(msg.text)) && (
  <AnswerMarkdown content={msg.text} />
))}
```

### The Rule & Fix:
1. All message interfaces must support both `text` and `content`.
2. Normalize intake symmetrically at all API service boundaries:
   ```typescript
   text: m?.text || m?.content || '',
   content: m?.content || m?.text || ''
   ```
3. Message renderers must check both properties:
   ```tsx
   // ✅ CORRECT:
   const resolvedText = msg.text || (msg as any).content || '';
   {Boolean(resolvedText) && <AnswerMarkdown content={resolvedText} />}
   ```

---

## 3. Accidental Database Wipe on "New Chat"

### The Failure:
Clicking "New Chat" in the sidebar sent a request to `POST /api/chat/clear` without a `session_id`. The backend handler interpreted missing `session_id` as a request to wipe the entire database, calling `postgres_manager.clear_all_sessions()` and purging all past conversations across the entire platform.

### The Mistake:
```python
# ❌ WRONG (Defaulting to destructive action):
session_id = request.query_params.get("session_id")
if session_id:
    postgres_manager.clear_session(session_id)
else:
    postgres_manager.clear_all_sessions() # Purged everything!
```

### The Rule & Fix:
1. Destructive global purges must NEVER be the default fallback.
2. Require explicit query/body confirmation: `all=true` or `confirm=true`.
3. If `session_id` is omitted and `confirm_all` is false, return a safe `200 no-op`.
4. "New Chat" on the frontend must only generate a new client thread ID; it must NEVER invoke remote deletion.

```python
# ✅ CORRECT:
if session_id:
    postgres_manager.clear_session(session_id)
    return {"status": "success", "message": f"Session '{session_id}' cleared"}

confirm_all = (
    request.query_params.get("all") == "true"
    or request.query_params.get("confirm") == "true"
    or (isinstance(body, dict) and body.get("all") is True)
)
if not confirm_all:
    return {"status": "no-op", "message": "No session_id specified. Pass all=true to clear all sessions."}

postgres_manager.clear_all_sessions()
```

---

## 4. Premature Session Invalidation on Page Reload

### The Failure:
When the user refreshed the browser (F5), `currentSessionId` was initialized by checking whether the stored ID existed in a local cache array (`raise_recent_sessions_v2`). Because PostgreSQL is the authoritative store and local cache might be empty or stale on mount, the check failed, defaulted `currentSessionId` to `null`, and immediately purged `localStorage.removeItem('raise_current_session_id')`. The user was kicked out of their active conversation.

### The Mistake:
```typescript
// ❌ WRONG (Purging stored ID before database sync):
const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => {
  const savedCurrentId = localStorage.getItem('raise_current_session_id');
  const cached = localStorage.getItem('raise_recent_sessions_v2');
  if (cached && JSON.parse(cached).some(s => s.id === savedCurrentId)) {
    return savedCurrentId;
  }
  return null; // Purged before PostgreSQL could respond!
});
```

### The Rule & Fix:
1. If `localStorage.getItem('raise_current_session_id')` exists, preserve it directly on mount.
2. Do not validate against ephemeral local cache before backend Stale-While-Revalidate completes.
3. Only remove `raise_current_session_id` when the user explicitly clicks "New Chat" or "Delete Session".

```typescript
// ✅ CORRECT:
const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => {
  try {
    const saved = localStorage.getItem('raise_current_session_id');
    return (saved && saved.trim()) ? saved.trim() : null;
  } catch {
    return null;
  }
});
```

---

## 5. Reactive Loopback & In-Flight Query Clobbering

### The Failure:
`useEffect` for session restoration had `currentSessionId` in its dependency array. When a user submitted a query from the front page, a new `currentSessionId` was generated. This triggered `restoreSessionAndHistory()` in the middle of query execution. The background fetch retrieved incomplete state from PostgreSQL and clobbered the in-flight conversation, resulting in duplicate user inquiries and lost streaming text.

### The Mistake:
```typescript
// ❌ WRONG (Effect re-runs mid-query when session ID is assigned):
useEffect(() => {
  restoreSessionAndHistory();
}, [isTunnelConfigured, isOnline, currentSessionId]);
```

### The Rule & Fix:
1. Background session hydration must only trigger on connectivity transitions (`[isTunnelConfigured, isOnline]`), NEVER on `currentSessionId`.
2. Session switching from UI is explicitly handled by `handleSelectSession()`.
3. In-flight queries manage their own optimistic turn state and must not be interrupted by background polling.

---

## 6. Modal Traps and Local Model Discrimination

### The Failure:
`ControlCenterModal` hid its close button (`X`) whenever `!hasConfiguredKey`. However, `hasConfiguredKey` only checked for cloud API keys (Groq, Gemini, etc.). Users running zero-cost local models (vLLM, Ollama) had no cloud keys, so the modal evaluated them as "Setup Required", hid the close button, and trapped them in a fullscreen modal on every page reload.

### The Mistake:
```typescript
// ❌ WRONG (Only cloud keys recognized):
const hasConfiguredKey = (config.apiKeys || []).some(k => k?.key?.trim().length > 0);
// ...
{isSetupMode && !hasConfiguredKey ? <span>Setup Required</span> : <CloseButton />}
```

### The Rule & Fix:
1. Modals must ALWAYS be dismissable. Never trap the user without an exit path.
2. Local models (`vllm`, `local`, `ollama`) are first-class execution backends and satisfy setup requirements.
3. Once the user enters the workstation, persist `raise_onboarding_completed = 'true'` so reload stays on the workstation.

---

## 7. Blind Round-Robin Provider Failover

### The Failure:
`router.py` implemented a multi-model round-robin rotation across `fallback_chain`. However, `healthy_chain` explicitly excluded local models (`cand not in ("vllm", "local")`) and failed to verify if cloud candidates had valid credentials configured. When cloud keys were expired or unconfigured, the router selected broken cloud APIs and crashed, completely ignoring a healthy, running local vLLM instance.

### The Mistake:
```python
# ❌ WRONG (Excludes local models and doesn't check credentials):
healthy_chain = [
    cand for cand in self.fallback_chain
    if cand not in self.disabled_providers
    and cand not in ("vllm", "local") # Excluded local vLLM!
]
# Blindly returns first candidate without verifying credentials:
return self.providers[target_name]
```

### The Rule & Fix:
1. Every candidate in `healthy_chain` must verify that it is either:
   - A local provider with endpoint alive (`self.providers[cand].is_available()`), OR
   - A cloud provider with status `"configured"`.
2. If no cloud keys exist, the router must seamlessly fall back to local vLLM without throwing an error.
3. Setting `EXECUTION_MODE=LOCAL` or `LLM_BACKEND=vllm` must strictly bypass all external cloud calls.

---

## Verification Checklist Before Committing Changes:

- [ ] **Typecheck**: `npm run typecheck` passes with **0 errors**.
- [ ] **Build**: `npm run build` generates production bundle cleanly.
- [ ] **SSE Streaming**: Verify tokens stream in real time; check that `onChunk` updates state without page reload.
- [ ] **Persistence**: Refresh page (F5) on an active chat; verify exact conversation, citations, and drawer are retained.
- [ ] **New Chat**: Verify clicking "New Chat" leaves database history intact and only creates a new thread.
- [ ] **Local LLM**: Disconnect internet or remove cloud keys; verify local vLLM answers queries without prompting for cloud credentials.
- [ ] **Process Windows**: Verify `START_RAISE.bat` launches with a single clean console window.
