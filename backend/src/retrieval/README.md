# 🔍 Retrieval Subsystem (`backend/src/retrieval/`)

> **Tri-Substrate Hybrid Retrieval, Reciprocal Rank Fusion (RRF) & Cross-Encoder Re-Ranking**

---

## 🌟 Overview

The `src/retrieval/` package coordinates the search across three heterogeneous knowledge substrates (Dense Vectors, Lexical Inverted Index, and Multi-Hop Property Graph). It normalizes candidate scores using Reciprocal Rank Fusion (RRF) and filters the most relevant evidence passages using deep cross-attention re-ranking.

---

## 🔄 Retrieval & Fusion Data Flow

```mermaid
flowchart TD
    %% Input
    Query["🧭 Research Query & Extracted Entities<br/>(from src/features/query/)"]:::inNode

    %% Retrieval Subsystem
    subgraph RetrievalSubsystem ["🔍 src/retrieval/ Subsystem"]
        direction TB
        ParallelExec["parallel_retriever.py<br/>Scatter-Gather Asynchronous Concurrency Coordinator"]

        subgraph SubstratesQuery ["Concurrent Tri-Substrate Execution"]
            direction LR
            Q_Dense["Dense Vector Search<br/>(ChromaDB / LanceDB - Cosine)"]
            Q_Lex["Okapi BM25 Lexical<br/>(bm25.py - Exact Term Match)"]
            Q_Graph["Property Graph Traversal<br/>(Neo4j 5.26 / Kuzu - APOC)"]
            Q_Dense ~~~ Q_Lex ~~~ Q_Graph
        end

        Fusion["fusion.py (Reciprocal Rank Fusion)<br/>RRF Score = Sum 1 / (60 + Rank)"]
        
        ChainGate["chain_gate.py<br/>Pre-Synthesis Chain Completeness & Coverage Verification"]

        Reranker["reranker.py<br/>Cross-Encoder Scoring via BAAI/bge-reranker-large"]
    end

    %% Output
    FinalEvidence(["📑 Top-K High-Density Grounded Evidence Passages<br/>(Forwarded to src/reasoning/)"]):::outNode

    Query --> ParallelExec
    ParallelExec --> Q_Dense
    ParallelExec --> Q_Lex
    ParallelExec --> Q_Graph
    Q_Dense --> Fusion
    Q_Lex --> Fusion
    Q_Graph --> Fusion
    Fusion --> ChainGate
    ChainGate --> Reranker
    Reranker --> FinalEvidence

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`parallel_retriever.py`** | Dispatches concurrent async tasks across Vector, Lexical, and Graph databases, applying drawer-scoping filters and timeout guards. |
| **`bm25.py`** | High-performance in-memory Okapi BM25 index. Preserves exact matches for alphanumeric project IDs, patent codes, and grant identifiers. |
| **`fusion.py`** | Implements Reciprocal Rank Fusion (RRF) to blend heterogeneous rank distributions without needing manual calibration of raw vector vs lexical distance scores. |
| **`reranker.py`** | Cross-attention re-scoring using `BAAI/bge-reranker-large`. Ranks tabular content higher when numerical values in the query match table cells. |
| **`chain_gate.py`** | Validates that multi-hop dependency chains are unbroken before evidence is passed to generative synthesis. |
| **`entity_filtering.py`** | Applies metadata drawer constraints (e.g., scoping search exclusively to selected PDF IDs). |
