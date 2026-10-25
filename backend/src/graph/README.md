# 🕸️ Graph Subsystem (`backend/src/graph/`)

> **Entity Resolution, Knowledge Graph Construction & Epistemic Proof Trees**

---

## 🌟 Overview

The `src/graph/` package transforms extracted document chunks into semantic entities, relationships, and epistemic proof trees. It reconciles ambiguous institutional entity names and maintains property graph schemas across Neo4j and embedded Kùzu engines.

---

## 🔄 Graph Construction & Resolution Flow

```mermaid
flowchart TD
    %% Input
    Chunks["🧩 Semantic Document Chunks<br/>(from src/chunking/)"]:::inNode

    %% Graph Subsystem
    subgraph GraphSubsystem ["🕸️ src/graph/ Subsystem"]
        direction TB
        EntityResolver["entity_resolver.py<br/>Canonical Entity Extraction & Fuzzy Deduplication<br/>(e.g., 'NIPGR', 'National Institute of Plant Genome Research')"]

        RelationResolver["relation_resolver.py<br/>Semantic Triples Construction: (Subject, Predicate, Object)"]

        ProofGraph["proof_graph.py<br/>Epistemic Proof Tree Builder Linking Multi-Hop Deductions to Document Sources"]

        KuzuBridge["kuzu_graph.py<br/>Embedded In-Process Kuzu Graph Engine Integration"]
    end

    %% Output
    GraphStorage(["💾 Multi-Hop Property Graph<br/>(Neo4j 5.26 APOC / Embedded Kuzu Storage)"]):::outNode

    Chunks --> EntityResolver
    EntityResolver --> RelationResolver
    RelationResolver --> ProofGraph
    ProofGraph --> KuzuBridge
    KuzuBridge --> GraphStorage

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`entity_resolver.py`** | Extracts named institutional entities (faculty names, grant codes, labs, departments, patents) and merges synonyms into canonical entity records. |
| **`relation_resolver.py`** | Identifies semantic relationships between entities (e.g. `(Professor)-[:FUNDED_BY]->(Grant)`, `(Department)-[:PUBLISHED]->(Report)`). |
| **`proof_graph.py`** | Builds directed acyclic graphs (DAGs) representing multi-hop reasoning proofs, providing visual verification chains from answer back to primary source chunks. |
| **`kuzu_graph.py`** | In-process embedded graph database driver using Kùzu, allowing fast local graph traversal without running a standalone Neo4j instance. |
