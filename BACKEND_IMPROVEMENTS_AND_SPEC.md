# RAISE Backend Integration & Improvement Specification

> **Target Audience:** RAISE Backend Developer  
> **Author:** Frontend Lead  
> **Date:** November 2026  
> **Scope:** Model routing (`/api/system/dynamic-llms`), model ingestion/download (`/api/models/pull`), variable name contracts, hardware telemetry, greeting intent classification, and chat latency persistence.

---

## 1. Executive Summary

This document specifies the critical backend corrections and enhancements required to ensure seamless integration between the RAISE React frontend (Control Center workstation) and the FastAPI backend gateway.

### Core Problems Identified
1. **Hardcoded Models in `/api/system/dynamic-llms`:** The backend router statically hardcodes `"Local GPU (In-Process PyTorch/CUDA, RTX 3090)"` with `"Qwen/Qwen2.5-1.5B-Instruct"` and `"Local vLLM Container (Docker)"` with `"Qwen2.5-14B"`. On macOS (Apple Silicon / Metal) or systems without an RTX 3090, this misrepresents the system.
2. **Missing Real-Time Model Download Pipeline:** Clicking download buttons in the Control Center requires an active streaming endpoint to download dense embeddings, cross-encoders, and LLMs with progress updates.
3. **Variable Name Mismatches:** Discrepancies exist between telemetry keys (`ram_total_gb` vs `total_ram_gb`) and chat session identifiers (`session_id` vs `thread_id`).
4. **Health Check Strictness:** `/api/health` must always guarantee a standard JSON payload so the frontend never encounters ambiguous connection states.
5. **Greeting Typo Tolerance:** Greetings with typos like `"hekko"`, `"helo"`, `"heyy"` bypass conversational handling, triggering an empty workspace document warning or heavy RAG pipeline invocation.
6. **Chat Latency Persistence:** `get_messages()` in PostgreSQL does not persist or return execution time, causing restored chat turns to lose their measured latency.
7. **Empty Workspace Fallback Phrasing:** Line 199 in `src/api/routers/chat.py` says *"from the frontend"* instead of *"to RAISE"*.

---

## 2. Issue 1: Hardcoded Model Catalog in `/api/system/dynamic-llms`

### File Affected
- `backend/src/infrastructure/providers/router.py` (lines 212–233)
- `backend/src/api/routers/system.py` (lines 59–65)

### Current Problematic Code
In `backend/src/infrastructure/providers/router.py`:
```python
# PROBLEM: Static dictionaries hardcode RTX 3090 and Qwen2.5 regardless of actual host OS
if "local" in self.providers and "local" not in self.disabled_providers:
    available.append({
        "provider": "local",
        "display_name": "Local GPU (In-Process PyTorch/CUDA, RTX 3090)",
        "model": getattr(self.providers["local"], "model_name", "Qwen/Qwen2.5-1.5B-Instruct"),
        "status": "READY",
        "is_active": self.mode == ExecutionMode.LOCAL,
        "tier": "Local Zero-Cost (24GB VRAM)",
    })

if "vllm" in self.providers and "vllm" not in self.disabled_providers:
    vllm_alive = self.providers["vllm"].is_available()
    available.append({
        "provider": "vllm",
        "display_name": "Local vLLM Container (Docker)",
        "model": getattr(self.providers["vllm"], "model_name", "Qwen2.5-14B"),
        "status": "READY" if (vllm_alive or self.mode == ExecutionMode.LOCAL) else "LOCAL_OFFLINE",
        "is_active": vllm_alive or self.mode == ExecutionMode.LOCAL,
        "tier": "Docker Local Inference",
    })
```

### Why This Fails
- On a Mac running Apple Silicon, it still advertises an RTX 3090 with 24GB VRAM.
- It reports Qwen 2.5 even if the user has Ollama running with Llama 3.2 or Mistral, or if no local model is loaded.

### Required Backend Fix
Replace the static dictionary with dynamic hardware and service queries:
1. **Dynamic Hardware Inspection:**
   ```python
   import torch
   import platform

   def get_device_info():
       if torch.backends.mps.is_available():
           return "Apple Silicon (Metal / MPS)", "macOS Accelerated"
       elif torch.cuda.is_available():
           gpu_name = torch.cuda.get_device_name(0)
           vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
           return f"NVIDIA GPU ({gpu_name})", f"{vram_gb}GB VRAM"
       return f"CPU ({platform.processor() or 'Native'})", "Host System Memory"
   ```
2. **Query Ollama for Installed Models:**
   If `http://localhost:11434/api/tags` returns 200, parse `models` array and register each installed model dynamically (`llama3.2`, `mistral`, `gemma2`).
3. **Validate Docker / vLLM Only When Truly Live:**
   Only return `"status": "READY"` if a socket handshake to the vLLM port actually succeeds.

---

## 3. Issue 2: Model Downloads & Control Center Ingestion API

The Control Center provides download actions for:
- **Dense Embedding Model:** `google/embeddinggemma-2` (2048-dim), `BAAI/bge-large-en-v1.5`
- **Cross-Encoder Reranker:** `BAAI/bge-reranker-large`, `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **NLI Claim Verifier:** `FineCat-NLI-DeBERTa`
- **Local LLM:** `llama3.2:3b`, `mistral:7b`

### Required Endpoint: `POST /api/models/pull`
**Files to update:**
- `backend/src/api/routers/system.py`

#### Request Payload
```json
{
  "model_name": "google/embeddinggemma-2",
  "provider": "huggingface",
  "model_type": "embedding"
}
```
*Allowed `model_type` values:* `'embedding' | 'reranker' | 'nli' | 'llm'`  
*Allowed `provider` values:* `'huggingface' | 'ollama' | 'sentence_transformers'`

#### Streaming Response (`text/event-stream`)
The endpoint must return an SSE stream so the frontend can display live percentage, speed, and ETA:
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: progress
data: {"status": "downloading", "percent": 24, "speed": "18.4 MB/s", "eta_seconds": 32}

event: progress
data: {"status": "downloading", "percent": 88, "speed": "22.1 MB/s", "eta_seconds": 4}

event: complete
data: {"status": "ready", "model_name": "google/embeddinggemma-2", "disk_size_gb": 4.6}
```

#### Python Implementation Blueprint
```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json, asyncio

class ModelPullRequest(BaseModel):
    model_name: str
    provider: str = "huggingface"
    model_type: str = "embedding"

@router.post("/models/pull")
async def pull_model_stream(req: ModelPullRequest):
    async def event_generator():
        yield f"event: progress\ndata: {json.dumps({'status': 'initializing', 'percent': 0})}\n\n"
        
        if req.provider == "ollama":
            # Stream from http://localhost:11434/api/pull
            pass
        elif req.provider in ("huggingface", "sentence_transformers"):
            # Use huggingface_hub snapshot_download with tqdm progress callback
            pass
            
        yield f"event: complete\ndata: {json.dumps({'status': 'ready', 'model_name': req.model_name})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 4. Issue 3: Variable Name Mismatches & Payload Standardization

Please verify and align the following variable names across the FastAPI models:

### 1. Hardware Telemetry (`GET /api/hardware-telemetry`)
Ensure both naming styles are supported in the response JSON to prevent client parsing errors:
```json
{
  "ram_total_gb": 16.0,
  "total_ram_gb": 16.0,
  "ram_available_gb": 8.2,
  "free_ram_gb": 8.2,
  "ram_percent_used": 48.7,
  "cpu_cores": 8,
  "gpu_model": "Apple Metal / MPS",
  "has_metal_or_cuda": true
}
```

### 2. Chat Request Payload (`POST /api/chat`)
Accept both `session_id` and `thread_id` aliases:
```python
class ChatRequest(BaseModel):
    message: Optional[str] = None
    query: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    mode: Optional[str] = "fast"
    stream: Optional[bool] = False
    active_docs: Optional[List[str]] = None
    document_filter: Optional[str] = None
    hops: Optional[int] = 1
    top_k: Optional[int] = 4
```

### 3. Chat Response Contract (`POST /api/chat`)
Always return `grounded_answer` alongside `reply` and `answer`:
```json
{
  "reply": "Synthesized research answer...",
  "grounded_answer": "Synthesized research answer...",
  "answer": "Synthesized research answer...",
  "citations": [],
  "session_id": "session-123",
  "status": "completed"
}
```

### 4. Configuration Save (`POST /api/system/config`)
Accept neural pipeline substrate selections and optional Hugging Face access token:
```json
{
  "llm_mode": "cloud_gemini",
  "llm_backend": "gemini",
  "embedding_model": "google/embeddinggemma-2",
  "reranker_model": "BAAI/bge-reranker-large",
  "nli_verifier_model": "FineCat-NLI-DeBERTa",
  "neural_device": "auto",
  "huggingface_token": "hf_...",
  "groq_api_key": "...",
  "gemini_api_key": "..."
}
```

---

## 5. Issue 4: Health Check Response Standardization

Ensure `GET /api/health` always returns strict `Content-Type: application/json` with 200 OK:
```json
{
  "status": "online",
  "service": "RAISE Master Agentic GraphRAG API",
  "version": "1.0.0",
  "api_version": "1.0.0",
  "subsystems": {
    "postgres": true,
    "redis": true,
    "neo4j": false,
    "chroma": true,
    "vllm": false,
    "llm": {
      "active_backend": "gemini",
      "ready": true
    }
  }
}
```

---

## 6. Issue 5: Conversational Greeting Intent & Typo Handling

### Problem
When a user writes greetings with common typos like `"hekko"` (instead of `"hello"`), `"helo"`, `"heyy"`, `"hlo"`, or `"sup"`, the backend classifier in `src/api/context.py` fails to recognize it as conversational:
1. It rejects it as conversational and treats it as an academic GraphRAG query.
2. If no workspace documents are loaded, it delivers the fallback notice *"No documents have been uploaded to the workspace yet..."* via a simulated word-by-word streaming loop.
3. If documents are present, it invokes the entire 15-node LangGraph RAG pipeline (query decomposition, ChromaDB search, Neo4j graph traversal), resulting in unnecessary latency.

### Required Backend Fix
In `backend/src/api/context.py` (`is_conversational_or_memory_query`):
```python
# Include common greeting typos and informal greetings:
patterns = [
    r"^(he|hi|hello|hey|hekko|helo|heyo|heyy+|hii+|hie|hlo|hlw|greetings|howdy|hola|yo|sup|wassup)\b",
    ...
]
```

---

## 7. Issue 6: Persisting Execution Latency in Chat History

### Problem
`GET /api/chat/history` returns messages stored in PostgreSQL, but columns currently omit `execution_time` / `latency_sec`. When a page is reloaded or a chat session is switched, the frontend cannot display the exact elapsed time next to `"Thought for X.Xs"`.

### Required Backend Fix
In `backend/src/infrastructure/database/mixins/chat_mixin.py`:
1. Save `execution_time` or `latency_sec` on assistant message records.
2. Return `"latency_sec"` and `"execution_time"` in the message objects returned by `get_messages()`.

---

## 8. Issue 7: Empty Workspace Fallback Message Phrasing

### File Affected
- `backend/src/api/routers/chat.py` (line 199)

### Problem
The current message reads:
`"No documents have been uploaded to the workspace yet. Please upload an academic PDF or report from the frontend to begin research and analysis."`
Referencing *"from the frontend"* leaks architectural jargon to the user instead of referring to the product name.

### Required Backend Fix
Update line 199 in `backend/src/api/routers/chat.py`:
```python
immediate_reply = "No documents have been uploaded to the workspace yet. Please upload an academic PDF or report to RAISE to begin research and analysis."
```

---

## 9. Summary Checklist for Backend Developer

- [ ] **Dynamic Models:** Replace static RTX 3090 / Qwen 2.5 dictionary in `src/infrastructure/providers/router.py` with dynamic host GPU/MPS and Ollama tags detection.
- [ ] **Model Pull API:** Implement streaming SSE download endpoint `POST /api/models/pull` in `src/api/routers/system.py`.
- [ ] **Variable Aliases:** In `GET /api/hardware-telemetry`, provide both `ram_total_gb` and `total_ram_gb`.
- [ ] **Chat Aliases:** In `POST /api/chat`, accept both `session_id` and `thread_id`; return both `grounded_answer` and `reply`.
- [ ] **Config Persistence:** In `POST /api/system/config`, persist `embedding_model`, `reranker_model`, `nli_verifier_model`, and `huggingface_token`.
- [ ] **Greeting Typo Tolerance:** In `src/api/context.py`, recognize typo greetings (`"hekko"`, `"helo"`, `"heyy"`, `"sup"`) in `is_conversational_or_memory_query`.
- [ ] **Duration Persistence:** In `src/infrastructure/database/mixins/chat_mixin.py`, store and return `latency_sec` in `get_messages()`.
- [ ] **Fallback Phrasing:** In `src/api/routers/chat.py` line 199, change *"from the frontend"* to *"to RAISE"*.

---
*For questions or contract coordination, refer to `frontend/src/features/control-center/types.ts` and `frontend/src/api/client.ts`.*
