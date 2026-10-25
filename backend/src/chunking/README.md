# 🧩 Chunking Subsystem (`backend/src/chunking/`)

> **Graph-Guided Adaptive Hierarchical Chunking (GGAHC) & Rust CPU Acceleration Engine**

---

## 🌟 Overview

The `src/chunking/` package transforms layout-parsed PDF structures and Markdown tables into dense, semantic, verifiable text chunks. It coordinates with the native Rust `raise_engine` to execute high-speed SimHash deduplication, section boundary preservation, and hierarchical parent-child linking.

---

## 🔄 Data Movement & Transformation Flow

```mermaid
flowchart TD
    %% Input
    RawAST(["📄 Parsed Document Layout AST & Markdown Tables<br/>(from src/parsers/)"]):::inNode

    %% Chunking Subsystem
    subgraph ChunkingSubsystem ["🧩 src/chunking/ Subsystem"]
        direction TB
        StructureAnalysis["structure.py & signals.py<br/>Analyzes Heading Depths (H1-H6), Paragraph Lengths & Table Geometries"]
        
        HierarchicalEngine["hierarchical.py<br/>Constructs Parent-Child Context Trees (Macro Section -> Micro Chunks)"]
        
        TableChunker["table_chunker.py<br/>Preserves Table Column Headers with Every Embedded Row Chunk"]

        subgraph RustEngine ["🦀 Rust Acceleration Bridge (rust_bridge.py)"]
            direction LR
            SimHash["SimHash 64-bit<br/>Near-Duplicate Detection"]
            FNV["FNV-1a Token Hashing<br/>Cryptographic Fingerprints"]
            Boundaries["Hard Section Boundaries<br/>Prevents Cross-Chapter Bleed"]
            SimHash ~~~ FNV ~~~ Boundaries
        end

        ConstraintRunner["hard_constraints.py & boundary_runner.py<br/>Enforces Token Windows (256-512 Tokens) & Bounding Coordinate Bounds"]
    end

    %% Output
    OutChunks(["💾 Standardized DocumentChunk Records<br/>(Transmitted to src/infrastructure/vector/ & src/graph/)"]):::outNode

    RawAST --> StructureAnalysis
    StructureAnalysis --> HierarchicalEngine
    StructureAnalysis --> TableChunker
    HierarchicalEngine --> RustEngine
    TableChunker --> RustEngine
    RustEngine --> ConstraintRunner
    ConstraintRunner --> OutChunks

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`hierarchical.py`** | Builds multi-tier chunk hierarchies. Parent chunks retain high-level section context, while micro child chunks are used for pinpoint vector retrieval. |
| **`table_chunker.py`** | Specialized table parser. Re-attaches table headers to every individual chunk row, preventing floating numbers without labels. |
| **`rust_bridge.py`** | High-speed C-ABI / PyO3 interface to `raise_engine.dll` / `raise_engine.so`. Executes CPU-intensive hashing and string normalization with zero Python GIL contention. |
| **`hard_constraints.py`** | Enforces hard limits: maximum token lengths, minimum chunk sizes, and geometric paragraph containment. |
| **`boundary_runner.py`** | Ensures chunks strictly terminate at physical document boundaries (chapter ends, legal signature blocks, appendices). |
| **`signals.py`** | Emits adaptive semantic split signals based on punctuation density, lexical shifts, and table geometry transitions. |
