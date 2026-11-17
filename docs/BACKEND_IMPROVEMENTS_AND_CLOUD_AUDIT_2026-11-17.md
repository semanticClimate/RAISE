# Backend Architecture Improvements & Cloud Substrate Audit Report

**Date**: November 17, 2026  
**Audience**: Backend Engineering Team, Platform Leads & System Architects  
**Author**: Frontend Engineering & Integration Team  
**Subject**: Cloud Substrate Failures, Latency Probe Bugs, Docker Telemetry, and RAG Pipeline Improvements  

---

## 1. Executive Summary

Following a joint audit of the RAISE codebase across `origin/backend` (up to commit `12eb9ec`) and `origin/frontend`, this document outlines critical architectural bugs, root-cause analyses, and recommended fixes for the backend engineering team.

Most critically, an in-depth code trace has identified a **fatal cascading failure in the cloud substrate pipeline** (`postgres.py`, `redis.py`, and `config_service.py`) that prevents remote databases (Supabase, Neon, AWS RDS, Upstash) from ever connecting, forcing silent fallback to SQLite and FakeRedis even when credentials are valid.

---

## 2. Critical Priority: The Cloud Substrate System Logical Errors

### 2.1 Bug 1: The 30ms TCP Socket Timeout on Remote Cloud PostgreSQL
* **Location**: `src/infrastructure/database/postgres.py` (lines 160–175)
* **Description**:
  When a cloud PostgreSQL database is configured, `get_postgres_engine` attempts a fast TCP connectivity probe:
  ```python
  if _fast_port_open(local_host, local_port, timeout=0.03):
  ```
* **Root Cause**:
  `timeout=0.03` is **30 milliseconds**. While 30ms is appropriate for a local Docker container running on `127.0.0.1`, a managed cloud database over the public internet (e.g. Supabase, AWS RDS, GCP Cloud SQL) typically has a round-trip network latency of **40ms to 250ms**.
* **Impact**:
  The TCP probe *always* times out for remote databases. The backend concludes the database is offline and falls back immediately to local SQLite (`backend/data/raise_local.db`). The user believes they are using Cloud PostgreSQL, but their data is written to a local SQLite file.
* **Recommended Fix**:
  Distinguish between local hosts (`127.0.0.1`, `localhost`) and remote hostnames. Use a 2.5s–3.0s timeout for remote cloud endpoints, reserving 30ms strictly for loopback addresses:
  ```python
  is_local = local_host in ("127.0.0.1", "localhost", "::1")
  probe_timeout = 0.03 if is_local else 3.0
  if _fast_port_open(local_host, local_port, timeout=probe_timeout):
  ```

---

### 2.2 Bug 2: Environment Variable Desynchronization in Postgres & Redis
* **Location**: `src/features/system/config_service.py` vs. `src/infrastructure/database/postgres.py`
* **Description**:
  When the user inputs cloud database credentials in the Control Center, `config_service.py` saves them as:
  ```python
  # src/features/system/config_service.py (lines 515-519)
  if cfg.postgres_mode == "cloud" and pg_val:
      env_map["POSTGRES_URL"] = pg_val
      env_map["DATABASE_URL"] = pg_val
      os.environ["POSTGRES_URL"] = pg_val
  ```
  However, `postgres.py` explicitly looks for cloud URLs under different variable names:
  ```python
  # src/infrastructure/database/postgres.py (line 138)
  cloud_url = cloud_url or os.getenv("CLOUD_DB_URL") or os.getenv("POSTGRES_CLOUD_URL") or os.getenv("DATABASE_CLOUD_URL")
  ```
* **Root Cause**:
  `cloud_url` evaluates to `None` because `config_service.py` set `POSTGRES_URL`, not `POSTGRES_CLOUD_URL`. Consequently:
  - `if storage_mode == "cloud" and cloud_url:` evaluates to `False`.
  - The cloud preference branch is skipped entirely.
  - The connection string is assigned to `local_url`, which then fails the 30ms local TCP check.
* **Recommended Fix**:
  In `postgres.py`, include `POSTGRES_URL` and `DATABASE_URL` in the cloud URL resolution when `storage_mode == "cloud"` or when the URL contains remote indicators:
  ```python
  if not cloud_url:
      candidate = os.getenv("POSTGRES_CLOUD_URL") or os.getenv("CLOUD_DB_URL") or os.getenv("DATABASE_CLOUD_URL")
      if not candidate and (storage_mode == "cloud" or os.getenv("POSTGRES_MODE") == "cloud"):
          candidate = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
      cloud_url = candidate
  ```
  Apply the identical fix in `src/infrastructure/cache/redis.py` for `CLOUD_REDIS_URL` vs. `REDIS_URL`.

---

### 2.3 Bug 3: Cascading Substrate Corruption in `config_service.py`
* **Location**: `src/features/system/config_service.py` (lines 532–562)
* **Description**:
  When resolving the runtime storage mode across substrates:
  ```python
  modes = [cfg.neo4j_mode, cfg.redis_mode, cfg.postgres_mode]
  if any(m == "cloud" for m in modes):
      resolved_storage = "cloud"
  ```
  And then:
  ```python
  elif resolved_storage == "cloud":
      env_map["USE_FAKEREDIS"] = "false"
      os.environ["USE_FAKEREDIS"] = "false"
      env_map["USE_CLOUD_STORAGE"] = "true"
      os.environ["USE_CLOUD_STORAGE"] = "true"
  ```
* **Root Cause**:
  Substrates in RAISE are hybrid and decoupled. A user may legitimately configure **Upstash Cloud Redis** while keeping **NetworkX In-Memory** and **Local SQLite**.
  By checking `if any(m == "cloud")` and setting `resolved_storage = "cloud"` globally, the system turns off `USE_FAKEREDIS = "false"` and disables `USE_LOCAL_FALLBACKS` for *all* substrates.
* **Impact**:
  Configuring cloud for a single substrate corrupts the fallback mechanisms of the remaining substrates, leading to unhandled connection exceptions on boot.
* **Recommended Fix**:
  Track substrate modes per-channel rather than enforcing an all-or-nothing global flag:
  ```python
  # Only disable FakeRedis if Redis itself is explicitly non-fallback
  if cfg.redis_mode == "in_memory_fallback":
      env_map["USE_FAKEREDIS"] = "true"
      os.environ["USE_FAKEREDIS"] = "true"
  ```

---

### 2.4 Bug 4: Phantom Badges in `src/core/substrate_router.py`
* **Location**: `src/core/substrate_router.py` (lines 68–77)
* **Description**:
  ```python
  if mode == SubstrateMode.CLOUD:
      aura_uri = os.getenv("NEO4J_URI", "neo4j+s://aura.databases.neo4j.io")
      return {
          "mode_badge": "[CLOUD MODE] Managed Cloud Storage & Remote Clusters",
          "neo4j": f"[CLOUD-GRAPH] {aura_uri}",
          "redis": "[CLOUD-REDIS] Managed TLS Cache active",
          "postgres": "[CLOUD-PG]    Managed Cloud PostgreSQL active",
          "storage": f"[CLOUD-OBJ]   {bucket}",
      }
  ```
* **Root Cause**:
  If the mode is set to `cloud`, the telemetry summary hardcodes active status strings for all substrates without verifying if socket handshakes or authentications actually succeeded.
* **Impact**:
  The CLI dashboard and status banners display `[CLOUD-PG] Managed Cloud PostgreSQL active` even if the database is completely offline or unreachable.
* **Recommended Fix**:
  Reference live connection states from `postgres_mgr.is_connected`, `redis_mgr.is_connected`, and `neo4j_mgr.is_connected` before displaying active status.

---

### 2.5 Bug 5: Cloudflare R2 / S3 Object Storage Environment & Schema Disconnect
* **Location**: `src/infrastructure/storage/r2.py` vs. `src/core/substrate_router.py` vs. `src/features/system/schemas.py`
* **Description**:
  1. `substrate_router.py` defaults to reading `CLOUD_STORAGE_BUCKET` with a fallback of `"s3://raise-academic-vault"`.
  2. In contrast, `r2.py` reads `CLOUDFLARE_R2_BUCKET_NAME` with a default of `"raise-documents"`, alongside `CLOUDFLARE_R2_ENDPOINT_URL`, `CLOUDFLARE_R2_ACCESS_KEY_ID`, and `CLOUDFLARE_R2_SECRET_ACCESS_KEY`.
  3. Meanwhile, `SystemConfigRequest` in `src/features/system/schemas.py` and `config_service.py` completely lacks fields for R2 / S3 credentials and bucket names.
* **Root Cause**:
  There is no unified configuration contract for cloud document storage. The telemetry router displays one bucket name (`raise-academic-vault`), the storage manager reads a completely different variable (`CLOUDFLARE_R2_BUCKET_NAME`), and the frontend Control Center has no API fields to transmit cloud storage credentials.
* **Impact**:
  Cloud object storage can never be configured through the UI/API, and telemetry reports a phantom S3 bucket that is disconnected from the actual storage manager.
* **Recommended Fix**:
  Add `r2_endpoint_url`, `r2_access_key`, `r2_secret_key`, and `r2_bucket` to `SystemConfigRequest` in `schemas.py`, synchronize them in `config_service.py`, and align `substrate_router.py` to inspect `CLOUDFLARE_R2_BUCKET_NAME`.

---

## 3. High Priority: Missing Docker Availability Detection

### 3.1 Docker False-Assumption on Clean Developer Laptops
* **Problem**:
  On developer machines where Docker Desktop is not installed or running (e.g., standard Apple Silicon MacBooks), the Control Center allows selecting "Docker Local".
  The backend attempts container commands, fails silently, and falls back to in-memory/SQLite. This causes confusion because the UI says "Docker Local Selected" while the system is actually running on in-memory fallbacks.
* **Recommended Backend Change**:
  In `/api/system/hardware` or `/api/system/diagnostics`, return an explicit capability flag:
  ```python
  import shutil
  import subprocess

  def check_docker_available() -> Dict[str, Any]:
      docker_bin = shutil.which("docker")
      if not docker_bin:
          return {"available": False, "running": False, "reason": "Docker CLI not found"}
      try:
          res = subprocess.run([docker_bin, "info"], capture_output=True, timeout=1.5)
          return {"available": True, "running": res.returncode == 0}
      except Exception:
          return {"available": True, "running": False, "reason": "Daemon not responding"}
  ```
* **Frontend Action**:
  Once surfaced in `/api/system/hardware`, the frontend will automatically mark "Docker Local" as `Disabled (Docker Not Installed)` and highlight `Fast Local (Embedded)` as the recommended preset.

---

## 4. Performance & Reliability Improvements

### 4.1 Non-Blocking Pre-Warm for Cross-Encoder Reranker & FineCat-NLI
* **Current State**:
  In `src/infrastructure/model_warmup.py`, `warmup_all_neural_models()` runs synchronously in the server lifespan. While commit `2003791` successfully made ChromaDB chunk ingestion non-blocking (`ChromaAutoIndexer`), loading `BAAI/bge-reranker-v2-m3` (560MB) and `dleemiller/finecat-nli-ultra-l` (1.7GB) can still take 10–25 seconds on CPU.
* **Recommendation**:
  Spawn the reranker and NLI model warmups in a background thread during gateway startup so that `/api/health` and the Swagger UI respond in **< 500ms**. Fast lexical fallbacks can handle any prompt sent during the first 5 seconds of boot.

### 4.2 Generalized Table Intent Detection in RAG Pipeline
* **Current State**:
  In `src/features/agent/nodes/retrieval_nodes.py`, commit `d5d01cf` introduced table intent boosting with hardcoded strings:
  ```python
  table_intent_keywords = [..., "nature index", "ranking", "rankings", "position", "positions", "rank", "profile"]
  ```
* **Recommendation**:
  Abstract this keyword list into a regex pattern or intent classifier (`r"\b(rank(ings?|ed)?|top\s+\d+|standings?|scorecards?|breakdowns?)\b"`) so all academic and benchmark reports with tabular data benefit from table boosting without needing custom keyword lists.

### 4.3 Missing `pytest` in Default Developer `.venv`
* **Current State**:
  Running `.venv/bin/python -m pytest` on the local developer setup throws:
  `No module named pytest`
* **Recommendation**:
  Include `pytest` and `pytest-asyncio` in `requirements-core.txt` or ensure developer setup scripts install them by default.

---

## 5. Frontend Enhancements Completed in Parallel

Following the user's instructions, the following improvements have been landed on `origin/frontend`:

1. **Source Attachment & Library Integration**:
   Preserved the minimal, distraction-free hero layout while ensuring the document library picker seamlessly connects pre-scanned research corpora (e.g., NIPGR Annual Reports) directly into chat session contexts.

2. **Viewport Auto-Scroll Overhaul**:
   In `useSmartAutoScroll.ts` and `useRaiseController.ts`:
   - Resolved cyclic dependency using proxy refs.
   - Guaranteed event listeners are always attached on mount regardless of conversation length.
   - Disabled `content-visibility: auto` on chat message cards to eliminate scroll jumping.
   - Replaced smooth sliding animations with instant positioning on session restore.

3. **CI Pipeline Hardening**:
   In `frontend/.github/workflows/frontend-ci.yml`, pinned all jobs to `ubuntu-24.04` and verified Node 24 action compatibility. Fixed the Biome `useIterableCallbackReturn` lint error in `useSessionSources.ts`.

---

## 6. Action Items for Backend Team

- [ ] **Patch `postgres.py`**: Apply adaptive TCP probe timeout (`3.0s` for remote hosts, `0.03s` for local) and support `POSTGRES_URL` in cloud resolution.
- [ ] **Patch `redis.py`**: Support `REDIS_URL` for Upstash/cloud endpoints when `REDIS_MODE == "cloud"`.
- [ ] **Patch `config_service.py`**: Decouple substrate fallback flags so one cloud substrate does not disable local fallbacks for other substrates.
- [ ] **Harmonize Cloud Storage (`r2.py` / `schemas.py`)**: Add R2 endpoint and credentials to `SystemConfigRequest` and reconcile bucket environment variables.
- [ ] **Expose Docker Status**: Add `docker_installed` and `docker_running` booleans to `/api/system/hardware`.
- [ ] **Async Model Warmup**: Wrap Reranker and NLI pre-warming in a non-blocking daemon thread.
