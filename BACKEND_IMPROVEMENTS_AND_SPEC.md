# RAISE Backend Integration & Engineering Specification

> **Target Audience:** RAISE Backend Developer  
> **Author:** Frontend Lead  
> **Branch:** `origin/frontend`  
> **Date:** November 2026  
> **Scope:** Dynamic Model Routing, Real Model Weights Ingestion, Neural Pipeline Configuration Persistence, Hardware Telemetry Engine, Conversational Greeting & Typo Classification, Chat Latency Persistence, and SSE Streaming Reliability.

---

## 1. Executive Summary

During our integration audit between the RAISE React 19 Frontend (Control Center workstation) and the FastAPI backend gateway, we identified **10 critical discrepancies** causing UI inaccuracies, failed weight downloads, dropped configuration settings, and conversational query stalls.

This document provides exact file paths, line numbers, analysis of why each failure occurs, and drop-in Python code replacements to resolve every issue.

### Summary of Issues

| # | Subsystem | File Affected | Summary of Failure |
|---|---|---|---|
| 1 | Dynamic LLM Catalog | `backend/src/infrastructure/providers/router.py` (L212–233) | Hardcodes NVIDIA RTX 3090 (24GB VRAM) and Qwen2.5 on macOS Apple Silicon / CPU hosts. |
| 2 | Model Weight Download | `backend/src/features/system/preflight_service.py` (L247–272) | `stream_model_pull()` runs a mock loop with `asyncio.sleep(0.2)`. It never downloads model weights from Hugging Face or Ollama. |
| 3 | System Config Schemas | `backend/src/features/system/schemas.py` (L14–50) | `SystemConfigRequest` omits `embedding_model`, `reranker_model`, `nli_verifier_model`, `neural_device`, and `huggingface_token`. Pydantic drops them upon receipt. |
| 4 | Config Persistence | `backend/src/features/system/config_service.py` (L150–250) | `save_configuration()` never writes `EMBEDDING_MODEL`, `RERANKER_MODEL`, `NLI_VERIFIER_MODEL`, `NEURAL_DEVICE`, or `HUGGINGFACE_TOKEN` to `.env`. |
| 5 | Telemetry Engine | `backend/src/features/system/telemetry_service.py` (L34–47) & `backend/src/api/routers/developer.py` (L86–134) | Ignores Apple Silicon Metal (`torch.backends.mps.is_available()`); hardcodes NVIDIA GPU and offline BAAI embedding. |
| 6 | Greeting Intent Typos | `backend/src/api/context.py` (L261), `backend/src/api/routers/chat_conversational.py` (L137), `backend/src/cli/persona_classifier.py` (L121) | Strict keyword checking rejects typos (`"hekko"`, `"helo"`, `"heyy"`, `"sup"`), routing greetings into the 15-node GraphRAG pipeline or empty workspace warning. |
| 7 | Chat Message Persistence | `backend/src/infrastructure/database/mixins/chat_mixin.py` (L23–101, L148–174) | Database schema and `get_messages()` omit `latency_sec` / `execution_time`. Restoring chat history wipes the duration next to `"Thought for X.Xs"`. |
| 8 | Empty Workspace SSE Meta | `backend/src/api/routers/chat_streaming.py` (L100–118) | `create_empty_drawer_sse_stream`'s `meta_payload` omits `latency_sec` and `execution_time`. |
| 9 | Architectural Jargon | `backend/src/api/routers/chat.py` (L199) | Fallback message hardcodes `"from the frontend to begin"`. Should read `"to RAISE to begin"`. |
| 10 | Contract Aliases | `backend/src/api/routers/chat.py` & `developer.py` | Chat requests must accept both `session_id` and `thread_id`; hardware telemetry must provide both `ram_total_gb` and `total_ram_gb`. |

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
- On macOS Apple Silicon (M1/M2/M3/M4) or systems without an NVIDIA RTX 3090, it falsely displays *"RTX 3090 (24GB VRAM)"*.
- It displays Qwen 2.5 even if Ollama is running Llama 3.2, Mistral, or if no local container exists.
- In the frontend Control Center, local GPU options appear enabled even when the service is completely unreachable.

### Required Backend Fix
Import the hardware engine (`from src.infrastructure.hardware import get_gpu_info`) and dynamically check Ollama / vLLM:

```python
import socket
import urllib.request
import json
from src.infrastructure.hardware import get_gpu_info

def get_dynamic_local_providers(self):
    available = []
    gpu_info = get_gpu_info()
    device_label = "CPU Only"
    tier_label = "Host System Memory"

    if gpu_info.get("mps_available"):
        device_label = "Apple Silicon Metal (MPS)"
        tier_label = "Unified Memory (Zero-Cost)"
    elif gpu_info.get("cuda_available") and gpu_info.get("devices"):
        primary_gpu = gpu_info["devices"][0]
        device_label = f"NVIDIA GPU ({primary_gpu.get('name')})"
        tier_label = f"{primary_gpu.get('total_vram_gb', 0)}GB VRAM"

    # 1. In-process PyTorch Local Model
    if "local" in self.providers and "local" not in self.disabled_providers:
        model_name = getattr(self.providers["local"], "model_name", None) or os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
        is_ready = bool(getattr(self.providers["local"], "pipeline", None) is not None)
        available.append({
            "provider": "local",
            "display_name": f"Local Accelerator ({device_label})",
            "model": model_name,
            "status": "READY" if is_ready else "LOCAL_OFFLINE",
            "is_active": self.mode == ExecutionMode.LOCAL and is_ready,
            "tier": tier_label,
        })

    # 2. Probe Ollama dynamically (Port 11434)
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "RAISE"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                models = data.get("models", [])
                for m in models:
                    m_name = m.get("name")
                    available.append({
                        "provider": "ollama",
                        "display_name": f"Ollama ({device_label})",
                        "model": m_name,
                        "status": "READY",
                        "is_active": True,
                        "tier": "Ollama Local Engine",
                    })
    except Exception:
        pass

    # 3. Probe vLLM Container (Port 8002 / 8000)
    vllm_alive = False
    for port in (8002, 8000):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                vllm_alive = True
                break
        except Exception:
            pass

    if vllm_alive:
        available.append({
            "provider": "vllm",
            "display_name": f"Local vLLM Container ({device_label})",
            "model": os.getenv("VLLM_MODEL_NAME", "Qwen2.5-14B"),
            "status": "READY",
            "is_active": True,
            "tier": "Docker Local Inference",
        })

    return available
```

---

## 3. Issue 2: Fake Model Ingestion Loop (`stream_model_pull`)

### File Affected
- `backend/src/features/system/preflight_service.py` (lines 247–272)
- `backend/src/api/routers/system.py` (lines 100–107)

### Current Problematic Code
In `backend/src/features/system/preflight_service.py`:
```python
# PROBLEM: Hardcoded simulation loop yielding fake percentages
async def stream_model_pull(model_name: str) -> AsyncGenerator[str, None]:
    target = model_name
    is_cached = check_hf_model_cached(target)
    if is_cached:
        payload = json.dumps({"percent": 100, "status": f"Model {target} verified in cache (100% ~48 MB/s)"})
        yield f"data: {payload}\n\n"
        return

    # FAKE SIMULATION - DOES NOT ACTUALLY DOWNLOAD ANYTHING!
    for pct in [20, 45, 70, 90, 100]:
        await asyncio.sleep(0.2)
        payload = json.dumps({
            "percent": pct,
            "status": f"Downloading {target} ({pct}% ~48 MB/s)" if pct < 100 else f"Model {target} verified and active."
        })
        yield f"data: {payload}\n\n"
```

### Why This Fails
When a user clicks **Download** on Dense Embeddings (`google/embeddinggemma-2`), Rerankers (`BAAI/bge-reranker-large`), or Ollama models, the backend emits 5 simulated progress frames over 1.0 second and finishes, but **zero model weights are downloaded to disk**.

### Required Backend Fix
Implement genuine downloads using `huggingface_hub.snapshot_download` and `httpx` to stream Ollama pulls:

```python
import asyncio
import json
from typing import AsyncGenerator
import httpx
from huggingface_hub import snapshot_download

async def stream_model_pull(model_name: str, provider: str = "huggingface", hf_token: Optional[str] = None) -> AsyncGenerator[str, None]:
    token = hf_token or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")

    # 1. Ollama Model Pull
    if provider == "ollama" or not ("/" in model_name):
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", "http://127.0.0.1:11434/api/pull", json={"name": model_name}) as resp:
                    if resp.status_code == 200:
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                d = json.loads(line)
                                completed = d.get("completed", 0)
                                total = d.get("total", 1)
                                pct = min(100, int((completed / total) * 100)) if total > 0 else 0
                                status_msg = d.get("status", f"Downloading {model_name}...")
                                yield f"data: {json.dumps({'percent': pct, 'status': status_msg})}\n\n"
                            except Exception:
                                pass
                        yield f"data: {json.dumps({'percent': 100, 'status': f'Model {model_name} successfully downloaded and verified.'})}\n\n"
                        return
        except Exception as e:
            yield f"data: {json.dumps({'percent': 0, 'status': f'Ollama pull failed: {str(e)}', 'error': True})}\n\n"
            return

    # 2. Hugging Face / Sentence-Transformers Download
    yield f"data: {json.dumps({'percent': 5, 'status': f'Initiating Hugging Face download for {model_name}...' })}\n\n"
    
    loop = asyncio.get_running_loop()
    try:
        # Run blocking snapshot_download in default threadpool
        download_task = loop.run_in_executor(
            None,
            lambda: snapshot_download(
                repo_id=model_name,
                token=token,
                resume_download=True,
                local_files_only=False,
            )
        )
        
        # Emit progress heartbeats while background thread downloads weights
        pct = 10
        while not download_task.done():
            await asyncio.sleep(1.0)
            pct = min(95, pct + 5)
            yield f"data: {json.dumps({'percent': pct, 'status': f'Downloading neural weights for {model_name} ({pct}%)...' })}\n\n"

        target_dir = await download_task
        yield f"data: {json.dumps({'percent': 100, 'status': f'Model {model_name} cached at {target_dir}', 'disk_dir': str(target_dir)})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'percent': 0, 'status': f'Download failed: {str(exc)}', 'error': True})}\n\n"
```

---

## 4. Issue 3 & 4: Missing Neural Pipeline Fields & Config Persistence

### Files Affected
- `backend/src/features/system/schemas.py` (lines 14–50)
- `backend/src/features/system/config_service.py` (lines 150–250)

### Current Problematic Code
In `schemas.py`:
```python
class SystemConfigRequest(BaseModel):
    llm_mode: str = Field(default="cloud_groq")
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    # ... other cloud API keys ...
    # MISSING: embedding_model, reranker_model, nli_verifier_model, neural_device, huggingface_token!
```

In `config_service.py`:
`save_configuration(cfg)` never processes or writes `EMBEDDING_MODEL`, `RERANKER_MODEL`, `NLI_VERIFIER_MODEL`, `NEURAL_DEVICE`, or `HUGGINGFACE_TOKEN` to `.env`.

### Required Backend Fix

#### 1. In `backend/src/features/system/schemas.py`:
```python
class SystemConfigRequest(BaseModel):
    """Payload schema for system configuration updates and connection testing."""
    llm_mode: str = Field(default="cloud_groq")
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    nvidia_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    vercel_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_base_url: Optional[str] = None
    custom_model_name: Optional[str] = None
    selected_local_model: Optional[str] = "llama3.2:3b"

    # Neural Retrieval Pipeline Substrates
    embedding_model: Optional[str] = Field(default="google/embeddinggemma-2")
    reranker_model: Optional[str] = Field(default="BAAI/bge-reranker-large")
    nli_verifier_model: Optional[str] = Field(default="FineCat-NLI-DeBERTa")
    neural_device: Optional[str] = Field(default="auto")
    huggingface_token: Optional[str] = None

    # Database Substrates
    neo4j_mode: str = Field(default="cloud")
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    neo4j_database: Optional[str] = None
    redis_mode: str = Field(default="cloud")
    redis_url: Optional[str] = None
    redis_uri: Optional[str] = None
    postgres_mode: str = Field(default="cloud")
    postgres_url: Optional[str] = None
    postgres_uri: Optional[str] = None
    tunnel_url: Optional[str] = None

class ModelPullRequest(BaseModel):
    model_name: str = Field(default="google/embeddinggemma-2")
    provider: Optional[str] = Field(default="huggingface")
    model_type: Optional[str] = Field(default="embedding")
    huggingface_token: Optional[str] = None
```

#### 2. In `backend/src/features/system/config_service.py` (`save_configuration`):
```python
    # Persist Neural Substrate Selections into env_map
    if cfg.embedding_model:
        env_map["EMBEDDING_MODEL"] = cfg.embedding_model.strip()
        env_map["DEFAULT_EMBEDDING_MODEL"] = cfg.embedding_model.strip()
        os.environ["EMBEDDING_MODEL"] = cfg.embedding_model.strip()

    if cfg.reranker_model:
        env_map["RERANKER_MODEL"] = cfg.reranker_model.strip()
        os.environ["RERANKER_MODEL"] = cfg.reranker_model.strip()

    if cfg.nli_verifier_model:
        env_map["NLI_VERIFIER_MODEL"] = cfg.nli_verifier_model.strip()
        os.environ["NLI_VERIFIER_MODEL"] = cfg.nli_verifier_model.strip()

    if cfg.neural_device:
        env_map["NEURAL_DEVICE"] = cfg.neural_device.strip()
        os.environ["NEURAL_DEVICE"] = cfg.neural_device.strip()

    if cfg.huggingface_token and not is_masked_secret(cfg.huggingface_token):
        hf_clean = cfg.huggingface_token.strip()
        env_map["HUGGINGFACE_TOKEN"] = hf_clean
        env_map["HF_TOKEN"] = hf_clean
        os.environ["HUGGINGFACE_TOKEN"] = hf_clean
        os.environ["HF_TOKEN"] = hf_clean
```

---

## 5. Issue 5: Telemetry Duplication & Missing Apple Silicon MPS Support

### Files Affected
- `backend/src/features/system/telemetry_service.py` (lines 34–47)
- `backend/src/api/routers/developer.py` (lines 86–134)

### Current Problematic Code
In `backend/src/api/routers/developer.py`:
```python
# PROBLEM: Hardcoded NVIDIA CUDA fallback & static BAAI model
if not gpu_detected:
    gpu_detected = "NVIDIA CUDA GPU (or CPU Fallback)"

return {
    "gpu_model": gpu_detected,
    "ram_total_gb": total_gb,
    "ram_available_gb": avail_gb,
    "ram_percent": pct,
    "embedding_model": "BAAI/bge-large-en-v1.5 (1024-dim, Cached Offline)",
    "neo4j_endpoint": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
}
```

### Why This Fails
`backend/src/infrastructure/hardware.py` was created to be the authoritative source for system hardware, but `developer.py` and `telemetry_service.py` duplicate probes and hardcode `"NVIDIA CUDA GPU"`, reporting `gpu_detected: False` on Mac Apple Silicon.

### Required Backend Fix
Delegate `GET /api/hardware-telemetry` directly to `src/infrastructure/hardware.py`:

```python
from src.infrastructure.hardware import get_gpu_info, get_ram_info, get_cpu_info

@router.get("/api/hardware-telemetry")
async def get_hardware_telemetry():
    """Authoritative hardware telemetry: dynamically inspects RAM, CPU, and GPU/MPS."""
    ram = get_ram_info()
    gpu = get_gpu_info()
    cpu = get_cpu_info()

    gpu_label = gpu.get("primary_gpu_name") or ("Apple Silicon Metal (MPS)" if gpu.get("mps_available") else "CPU Execution")
    total_ram = ram.get("total_gb") or 16.0
    free_ram = ram.get("available_gb") or 8.0

    return {
        # Support both naming conventions for full frontend compatibility
        "gpu_model": gpu_label,
        "ram_total_gb": total_ram,
        "total_ram_gb": total_ram,
        "ram_available_gb": free_ram,
        "free_ram_gb": free_ram,
        "ram_percent": ram.get("percent_used") or 0.0,
        "cpu_cores": cpu.get("logical_cores") or 4,
        "has_metal_or_cuda": bool(gpu.get("cuda_available") or gpu.get("mps_available")),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-2"),
        "reranker_model": os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-large"),
        "neo4j_endpoint": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    }
```

---

## 6. Issue 6: Greeting Intent Classifiers Rejecting Common Typos

### Files Affected
- `backend/src/api/context.py` (line 261)
- `backend/src/api/routers/chat_conversational.py` (line 137)
- `backend/src/cli/persona_classifier.py` (line 121)

### Current Problematic Code
In `context.py`:
```python
# Exact pattern matching misses common keyboard typos
patterns = [r"^(hi|hello|hey)\b"]
```
In `chat_conversational.py`:
```python
or q_norm in {"hi", "hello", "hey", "greetings", "howdy", "yo", "sup"}
```
In `persona_classifier.py`:
```python
greeting_words = {"hi", "hello", "hey", "he", "hola", "howdy", "sup", "yo"}
```

### Why This Fails
When a user types `"hekko"` (transposed 'l' to 'k' on QWERTY keyboards), `"helo"`, `"heyy"`, `"hlo"`, or `"sup"`, all three classifiers fail.
1. The backend classifies it as an academic GraphRAG research query.
2. If no workspace documents are loaded, it delivers the fallback notice *"No documents have been uploaded to the workspace yet..."*.
3. If documents are loaded, it triggers query decomposition, ChromaDB search, and Neo4j traversal, causing a 15–20 second delay for a simple greeting!

### Required Backend Fix
In all three files, broaden greeting detection with a typo-tolerant pattern:

```python
GREETING_TYPO_REGEX = re.compile(
    r"^(hi+|hello+|helo+|hekko+|hey+|heyy+|heyo|howdy|hola|yo+|sup|hlo|hlw|greetings)(?:\s+there|\s+raise|\s+bot|\s*!|\s*\.|\s*\?)*$",
    re.IGNORECASE
)

# If matched, immediately return conversational greeting fastpath
if GREETING_TYPO_REGEX.match(message.strip()):
    return {"type": "greeting"}
```

---

## 7. Issue 7 & 8: Chat Latency Persistence in PostgreSQL & SSE Streams

### Files Affected
- `backend/src/infrastructure/database/mixins/chat_mixin.py` (lines 23–101, lines 148–174)
- `backend/src/api/routers/chat_streaming.py` (lines 100–118)

### Current Problematic Code
In `chat_mixin.py`:
```python
cur.execute("""
    INSERT INTO chat_messages (session_id, role, content, mode, sources, citations, message_hash)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""")
```
And in `get_messages()`:
```python
SELECT role, content, mode, sources, created_at FROM ...
```

### Why This Fails
When a message finishes streaming, the thought duration is visible. However, once the user refreshes the page or switches sessions, `get_messages()` fetches history from PostgreSQL where `latency_sec` was never stored. Consequently, the `"Thought for X.Xs"` duration badge disappears!

### Required Backend Fix

1. Add `latency_sec` column to `chat_messages` if not already present:
```sql
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS latency_sec NUMERIC DEFAULT 0.0;
```

2. In `backend/src/infrastructure/database/mixins/chat_mixin.py`:
Update `save_message()` to accept `latency_sec: float = 0.0`:
```python
def save_message(
    self,
    session_id: str,
    role: str,
    content: str,
    mode: str = "fast",
    sources: Optional[List[str]] = None,
    active_docs: Optional[List[str]] = None,
    latency_sec: float = 0.0
) -> bool:
    # Include latency_sec in INSERT
    cur.execute("""
        INSERT INTO chat_messages (session_id, role, content, mode, sources, citations, message_hash, latency_sec)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (session_id, message_hash) DO UPDATE SET latency_sec = EXCLUDED.latency_sec
    """, (session_id, role, content, mode, json.dumps(sources), json.dumps(sources), m_hash, latency_sec))
```

And in `get_messages()`:
```python
cur.execute("""
    SELECT role, content, mode, sources, created_at, latency_sec
    FROM chat_messages
    WHERE session_id = %s
    ORDER BY id ASC
""", (session_id,))
for r in rows:
    result.append({
        "role": r[0],
        "content": r[1] or "",
        "text": r[1] or "",
        "mode": r[2],
        "sources": raw_sources,
        "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
        "latency_sec": float(r[5] or 0.0),
        "durationSec": float(r[5] or 0.0),
    })
```

3. In `backend/src/api/routers/chat_streaming.py` (`create_empty_drawer_sse_stream`):
Include `latency_sec` in `meta_payload`:
```python
meta_payload = {
    "status": "SUCCESS",
    "query": message,
    "answer": reply,
    "thread_id": session_id,
    "session_id": session_id,
    "citations": [],
    "suggestions": [],
    "reply": reply,
    "sources": [],
    "latency_sec": round(time.time() - start_time, 2),
    "execution_time": round(time.time() - start_time, 2),
    "persisted": bool(session_id is not None),
    "saved": bool(session_id is not None),
}
```

---

## 8. Issue 9: Architectural Jargon in Fallback Text

### File Affected
- `backend/src/api/routers/chat.py` (line 199)

### Problem
The current message reads:
`"No documents have been uploaded to the workspace yet. Please upload an academic PDF or report from the frontend to begin research and analysis."`
Phrasing like *"from the frontend"* exposes implementation details to end users.

### Required Backend Fix
Update line 199 in `backend/src/api/routers/chat.py`:
```python
immediate_reply = "No documents have been uploaded to the workspace yet. Please upload an academic PDF or report to RAISE to begin research and analysis."
```

---

## 9. Issue 10: Variable Name Mismatches & Payload Aliases

Please ensure the backend routers support standard aliases:

1. **`POST /api/chat` Payload:** Accept both `session_id` and `thread_id`:
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

2. **`POST /api/chat` Response:** Return `grounded_answer` alongside `reply` and `answer`:
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

3. **`GET /api/health`:** Return strict JSON with `200 OK`:
```json
{
  "status": "online",
  "service": "RAISE Master Agentic GraphRAG API",
  "version": "1.0.0",
  "subsystems": {
    "postgres": true,
    "redis": true,
    "neo4j": false,
    "chroma": true,
    "vllm": false,
    "llm": { "ready": true, "active_backend": "gemini" }
  }
}
```

---

## 10. Verification & Handover Instructions for Backend Dev

To fetch the latest frontend contract and code updates from GitHub:

```bash
# 1. Fetch and inspect the frontend branch
git fetch origin frontend
git checkout frontend

# 2. View the full specification document
cat BACKEND_IMPROVEMENTS_AND_SPEC.md
```

### Backend Dev Action Checklist
- [ ] **Dynamic Models:** In `backend/src/infrastructure/providers/router.py`, replace static RTX 3090 with dynamic inspection of `torch.backends.mps` / `torch.cuda` and probe `http://127.0.0.1:11434/api/tags`.
- [ ] **Real Model Pulls:** In `backend/src/features/system/preflight_service.py`, replace mock loop in `stream_model_pull()` with `snapshot_download()` and `httpx` Ollama pull.
- [ ] **Schema Fields:** In `backend/src/features/system/schemas.py`, add `embedding_model`, `reranker_model`, `nli_verifier_model`, `neural_device`, and `huggingface_token` to `SystemConfigRequest`.
- [ ] **Config Persistence:** In `backend/src/features/system/config_service.py`, write `EMBEDDING_MODEL`, `RERANKER_MODEL`, `NLI_VERIFIER_MODEL`, `NEURAL_DEVICE`, and `HUGGINGFACE_TOKEN` to `.env`.
- [ ] **Hardware Telemetry:** In `backend/src/api/routers/developer.py`, route `GET /api/hardware-telemetry` through `src/infrastructure/hardware.py`.
- [ ] **Greeting Typos:** In `context.py`, `chat_conversational.py`, and `persona_classifier.py`, add `GREETING_TYPO_REGEX` to catch `"hekko"`, `"helo"`, `"heyy"`, `"sup"`.
- [ ] **Latency Persistence:** In `backend/src/infrastructure/database/mixins/chat_mixin.py`, store and return `latency_sec`.
- [ ] **Fallback Phrasing:** In `backend/src/api/routers/chat.py` L199, replace *"from the frontend"* with *"to RAISE"*.
