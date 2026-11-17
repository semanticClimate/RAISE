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

### 2.6 Bug 6: Document Deletion Resurrection Bug (`auto_scan_and_reconcile_documents` Ignores `deleted_documents`)
* **Location**: `src/api/context.py` (lines 82–120), `src/features/documents/service.py` (lines 317–343), and `src/retrieval/purger.py` (lines 115–135)
* **Description**:
  When a user clicks the trash icon in the Library modal, the frontend issues `DELETE /api/documents/{doc_id}` (falling back to `POST /api/documents/delete`).
  The deletion pipeline fails to permanently remove documents due to a cyclical resurrection loop:
  1. **Delegation Failure without Direct Fallback**: In `DocumentService.delete_document()`, filesystem purging is delegated exclusively to `self.rag_engine.purge_document(filename)`. If `self.rag_engine` is `None` (e.g., lazy initialization or fast gateway boot without full neural pipelines), `purger.py` is skipped entirely. Neither the physical PDF in `data/documents/`, chunk JSONs in `data/processed/chunks/`, nor extracted markdown in `data/library/` are unlinked.
  2. **Silent Unlink Failures**: In `purger.py:116-123`, `cand_path.unlink()` is wrapped in `try...except Exception: pass`. If an OS file lock (e.g., PyMuPDF/fitz handle open during page streaming) prevents unlinking, the error is swallowed and the file remains on disk.
  3. **Auto-Scan Manifest Resurrection**: Immediately after deletion, `delete_document_by_id` calls `document_service.list_library_documents()`, which triggers `auto_scan_and_reconcile_documents()`. This function scans `data/documents/*.pdf`:
     ```python
     if pdf_file.name not in registered_files and (real_chunks_count > 0 or extracted_file.exists()):
         record_ready_document(...)
     ```
     Because `auto_scan_and_reconcile_documents` **does not consult `manifest.get("deleted_documents", [])`**, it immediately classifies the remaining PDF/chunks as an unmanifested ready document and re-registers it into `manifest["ready_documents"]`.
  4. **Active Session Drawer Desync**: The deletion routine never updates the `chat_sessions` table or in-memory session drawers. Sessions with the deleted document in `active_docs` retain dead pointers, triggering retrieval errors on subsequent user prompts.
* **Impact**:
  Documents appear to delete briefly in the UI, then immediately reappear upon page reload or library re-open. Sessions referencing deleted documents fail during retrieval synthesis.
* **Recommended Backend Fix**:
  1. In `auto_scan_and_reconcile_documents()`, parse `deleted_docs = set(manifest.get("deleted_documents", []))` and never re-register any filename in that set:
     ```python
     deleted_files = set(manifest.get("deleted_documents", []))
     if pdf_file.name in deleted_files or stem in deleted_files:
         continue
     ```
  2. In `DocumentService.delete_document()`, ensure direct unlinking of files from `self.documents_dir`, `CHUNKS_DIR`, `LIBRARY_DIR`, and `CATALOGS_DIR` regardless of whether `self.rag_engine` is populated.
  3. Purge the deleted document name from `active_docs` across all active sessions in `postgres_manager` or session memory.

---

### 2.7 Bug 7: Session Title Sync Silent Discard on Empty Messages
* **Location**: `src/features/sessions/service.py` (line 144) & `src/infrastructure/database/mixins/chat_mixin.py` (line 225)
* **Description**:
  When `rename_session` falls back to `sync_chat_history(session_id=target_id, messages=[], title=clean_title)`, `chat_mixin.py` executes:
  ```python
  if not session_id or not messages:
      return 0
  ```
  Since `messages` is an empty list, it discards the rename operation immediately without updating `session_metadata.title`.
* **Impact**:
  Session renaming fails silently in fallback mode.
* **Recommended Fix**:
  Allow `sync_chat_history` to update metadata (`title`, `attached_docs`, `preferences`) even when `messages` is empty, or ensure `postgres_manager` implements `rename_session` natively across all database backends.

---

### 2.8 Bug 8: Legacy Font Mojibake (Kruti Dev / Non-Unicode Hindi) Ingestion
* **Location**: `src/parsers/text_quality.py` (`normalize_text`, `TextQualityGate`) & `src/parsers/document_parser.py`
* **Description**:
  In Indian governmental and institutional PDFs (such as NIPGR Annual Reports), sections detailing official language implementation (राजभाषा) are historically typed using legacy non-Unicode 8-bit fonts (e.g., Kruti Dev 010, Chanakya, Shusha, Walkman-Chanakya) without embedded Unicode CMaps.
  When Docling or PyMuPDF extracts text, it maps glyph codes directly to ASCII characters instead of Devanagari Unicode. For example:
  `^ AvkWuykbu fganh "kCndks"k ,oa fofHkUu fganh VwYI***`
  is the raw ASCII glyph representation of:
  `ऑनलाइन हिंदी शब्दकोश एवं विभिन्न हिंदी टूल्स` (*"Online Hindi Dictionary and various Hindi tools"*).
* **Root Cause**:
  `TextQualityGate.assess()` in `src/parsers/text_quality.py` evaluates `garbled_token_ratio` using standard non-printable ASCII checks. Because Kruti Dev strings consist of printable ASCII letters (`A-Z`, `a-z`, `"`, `,`), they pass the quality gate and are embedded into ChromaDB vectors.
* **Impact**:
  When users query institutional functioning or language sections, the RAG pipeline retrieves these raw ASCII chunks, and the LLM outputs gibberish text like `"titled '^ AvkWuykbu fganh "kCndks"k...'"`.
* **Recommended Backend Fix**:
  1. In `src/parsers/text_quality.py`, add a Kruti Dev detection heuristic (e.g., signature trigrams like `fganh`, `kCndks`, `AvkW`, `fofHkUu`).
  2. Implement a standard KrutiDev-to-Unicode conversion mapping to transform ASCII glyphs back to clean Devanagari (`ऑनलाइन हिंदी शब्दकोश...`), OR
  3. Filter out un-converted legacy font chunks before vector embedding so corrupted glyph strings do not contaminate retrieval indices.

---

### 2.9 Bug 9: Diagnostic Slash Commands `/audit` and `/help` Omit `is_dev_only=True`
* **Location**: `src/features/commands/__init__.py` (lines 48–75)
* **Description**:
  When registering system slash commands in `_init_default_commands(registry)`:
  - `/audit` is registered with `is_dev_only=False` (line 54).
  - `/help` is registered with `is_dev_only=False` (line 74).
* **Root Cause**:
  The discovery endpoint `GET /api/commands?include_dev=false` (`src/api/routers/commands.py:18`) relies on `registry.list_commands(include_dev=include_dev)`, which evaluates `cmds = [m for m in self._metadata.values() if include_dev or not m.is_dev_only]`.
  Because `/audit` and `/help` were marked `is_dev_only=False`, both were always returned even when `include_dev=false`. Furthermore, each command's serialized payload reported `"is_dev_only": false`.
* **Impact**:
  The frontend UI toggle *"Developer Diagnostic Commands: Show diagnostic commands (/audit, /help) in the / autocomplete menu"* was rendered ineffective. Turning the toggle OFF still kept `/audit` and `/help` in the user's slash command palette because the backend payload falsely asserted they were standard user commands.
* **Recommended Backend Fix**:
  In `src/features/commands/__init__.py`, set `is_dev_only=True` for both diagnostic handlers:
  ```python
  registry.register(
      name="audit",
      description="Strict anti-hallucination factual audit with numerical cross-checking.",
      syntax="/audit [claim or section]",
      examples=["/audit", "/audit patents and publications", "/audit budget expenditures"],
      aliases=["verify", "factcheck"],
      category="Verification",
      is_dev_only=True,
  )(handle_audit_command)

  registry.register(
      name="help",
      description="Show all available slash commands and usage syntax.",
      syntax="/help",
      examples=["/help"],
      aliases=["commands", "?"],
      category="Help",
      is_dev_only=True,
  )(handle_help_command)
  ```

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

4. **Strict Monochrome Popup Overhaul**:
   Restyled the three primary popups—Sources Drawer (`SourcesDrawer.tsx`), Knowledge Base Library Picker (`LibraryPickerModal.tsx`), and Search All Chats (`SearchModal.tsx`)—into a strict black-and-white theme (`#000000`, `#0A0A0A`, `#111111`, `#171717`, `#292929`, `#A3A3A3`, `#FFFFFF`). Eliminated colorful badges, gradients, and icons to match the Control Center.

5. **Dynamic Error Model Resolution**:
   In `BackendErrorCard.tsx`, removed all hardcoded model names (`'google/embeddinggemma-2'`, `'BAAI/bge-reranker-v2-m3'`, `'dleemiller/finecat-nli-ultra-l'`). Now extracts model names dynamically from the raw error string or `useControlCenterStore` config, gracefully falling back to clean generic messaging.

6. **Strict Authoritative Library Filtering**:
   Updated the library picker to display only documents that have been parsed and indexed successfully (`status === 'ready' | 'indexed'`), and added instant query cache invalidation on document deletion.

7. **Sources Drawer & Search Modal UI Simplification**:
   - Merged the search filter bar directly with the list view in `SourcesDrawer.tsx`, removing redundant horizontal divider lines.
   - Removed the dashed outer box container from the empty state for a minimalist presentation.
   - Removed secondary subheader text from the drawer header and attached-count from the footer.
   - Removed 'Click any chat to open' hint from `SearchModal.tsx`.
   - Replaced heavy pitch-black backdrop (`bg-black/80`) with a lighter, visible backdrop (`bg-black/40 backdrop-blur-md`) across all popups.

8. **Dynamic System Platform Telemetry**:
   - Replaced hardcoded `'macos'` checks in `ControlCenterModal.tsx`, `PlatformStep.tsx`, `LaunchStep.tsx`, and `useControlCenterStore.ts` with dynamic host detection and backend telemetry (`hw.platform`, `hw.os_name`, `detectHostOS()`).

---

## 6. Action Items for Backend Team

- [ ] **Mark `/audit` and `/help` as `is_dev_only=True`**: In `src/features/commands/__init__.py:54,74`, set `is_dev_only=True` so `GET /api/commands?include_dev=false` only returns public research commands.
- [ ] **Fix Document Deletion Resurrection**: In `src/api/context.py:auto_scan_and_reconcile_documents()`, do not re-register documents listed in `manifest["deleted_documents"]`. In `src/features/documents/service.py:delete_document()`, delete/archive physical files from `data/documents/` and `data/cache/chunks/`.
- [ ] **Legacy Font Mojibake Handling**: In `src/parsers/text_quality.py`, intercept legacy Kruti Dev / non-Unicode Devanagari text patterns and map to clean Unicode before chunk vectorization.
- [ ] **Fix Session Rename Fallback**: In `src/infrastructure/database/mixins/chat_mixin.py:sync_chat_history()`, allow metadata updates (`title`) even when `messages` is empty.
- [ ] **Patch `postgres.py`**: Apply adaptive TCP probe timeout (`3.0s` for remote hosts, `0.03s` for local) and support `POSTGRES_URL` in cloud resolution.
- [ ] **Patch `redis.py`**: Support `REDIS_URL` for Upstash/cloud endpoints when `REDIS_MODE == "cloud"`.
- [ ] **Patch `config_service.py`**: Decouple substrate fallback flags so one cloud substrate does not disable local fallbacks for other substrates.
- [ ] **Harmonize Cloud Storage (`r2.py` / `schemas.py`)**: Add R2 endpoint and credentials to `SystemConfigRequest` and reconcile bucket environment variables.
- [ ] **Expose Docker Status**: Add `docker_installed` and `docker_running` booleans to `/api/system/hardware`.
- [ ] **Async Model Warmup**: Wrap Reranker and NLI pre-warming in a non-blocking daemon thread.
