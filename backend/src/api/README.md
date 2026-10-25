# 🔌 API Subsystem (`backend/src/api/`)

> **FastAPI Gateway, Route Handlers, Schemas & Streaming Controllers**

---

## 🌟 Overview

The `src/api/` package provides the external HTTP REST and Server-Sent Events (SSE) interfaces for the RAISE platform. It acts as the orchestration bridge connecting frontend user actions with internal retrieval, ingestion, and reasoning engines.

---

## 🔄 Data Movement & Request Flow

```mermaid
flowchart TD
    %% Entrances
    subgraph Inbound ["📥 Client Requests"]
        direction LR
        ReqREST["REST HTTP Request"]:::node
        ReqSSE["SSE Stream Request"]:::node
        ReqREST ~~~ ReqSSE
    end

    %% API Subsystem
    subgraph APISubsystem ["🔌 src/api/ Subsystem"]
        direction TB
        DepInjection["dependencies.py<br/>Service Injection & Context Resolution"]
        Validation["schemas.py<br/>Pydantic v2 Strict Payload Validation"]
        
        subgraph Routers ["API Routers (routers/)"]
            direction TB
            R_Chat["chat.py & chat_streaming.py<br/>Conversational Reasoning & Token Streaming"]
            R_Docs["documents.py<br/>PDF Upload, Status & Deletion"]
            R_Graph["graph.py<br/>Internal Graph Validation & Probes"]
            R_Sessions["sessions.py<br/>Thread History & Drawer Scoping"]
            R_Health["health.py<br/>Substrate Health Diagnostics"]
        end

        AbortManager["context.py (ACTIVE_ABORTS)<br/>Thread Cancellation & Signal Watchdog"]
    end

    %% Internal Targets
    subgraph Downstream ["⚙️ Downstream Business Modules"]
        direction LR
        Features["src/features/<br/>Domain Engines"]
        Retrieval["src/retrieval/<br/>Fusion Search"]
        Parsers["src/parsers/<br/>Docling / PyMuPDF"]
    end

    ReqREST --> DepInjection
    ReqSSE --> DepInjection
    DepInjection --> Validation
    Validation --> Routers
    R_Chat <--> AbortManager

    R_Chat --> Features
    R_Chat --> Retrieval
    R_Docs --> Parsers
    R_Graph --> Features

    classDef node fill:#1e1b4b,stroke:#818cf8,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`schemas.py`** | Central Pydantic v2 schemas (`ChatRequest`, `ChatResponse`, `DocumentMetadata`, `SystemTelemetryFrame`). Enforces strict typing and JSON schema contracts. |
| **`dependencies.py`** | FastAPI dependency injection hub. Injects database sessions (`PostgresManager`), cache instances (`RedisCacheManager`), and services into route handlers. |
| **`context.py`** | Manages global thread contexts, local IP detection, and `ACTIVE_ABORTS` dictionary for non-blocking stream cancellation. |
| **`routers/chat.py`** | Orchestrates synchronous and streaming conversational GraphRAG queries. |
| **`routers/chat_streaming.py`** | Implements the Server-Sent Events (SSE) generator, emitting real-time tokens and lifecycle traces (`planning` → `retrieving` → `fusing` → `synthesizing` → `verifying`). |
| **`routers/documents.py`** | Multi-part upload handler, PDF status tracker, and document drawer management. |
| **`routers/graph.py`** | Internal graph validation and read-only Cypher query execution for diagnostics. |
| **`routers/health.py`** | Subsystem liveness and readiness diagnostic checks (Neo4j, Redis, PostgreSQL, ChromaDB, LLM backend). |
| **`routers/sessions.py`** | Conversation lifecycle manager, session persistence, and message history retrieval. |
