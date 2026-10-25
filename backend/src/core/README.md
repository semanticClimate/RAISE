# ⚙️ Core Subsystem (`backend/src/core/`)

> **Typed Configuration, Invariant Envelopes & Foundation Contracts**

---

## 🌟 Overview

The `src/core/` package defines the foundational data types, pipeline invariants, and runtime configuration settings for the entire backend application. It is the leaf dependency of the backend architecture: all other subfolders may import `src/core/`, but `src/core/` imports nothing else within `src/`.

---

## 🔄 Configuration Loading & Typing Architecture

```mermaid
flowchart TD
    %% Source
    EnvFile[".env / Environment Variables"]:::inNode

    %% Core Hub
    subgraph CoreHub ["⚙️ src/core/ Foundation"]
        direction TB
        ConfigSettings["config.py (Pydantic-Settings)<br/>• Validates Port, Hosts & DB Credentials<br/>• Enforces Free-Tier R2 Caps & LLM Parameters<br/>• Exposes Singleton settings Object"]

        DataTypes["types.py (Typed Envelopes)<br/>• DocumentChunk & ChunkMetadata<br/>• VerificationStatus & GroundingResult<br/>• TelemetryFrame & Execution Traces"]
    end

    %% Consumers
    subgraph Consumers ["Consumers Across Subsystems"]
        direction LR
        APIConsumer["src/api/"]
        InfraConsumer["src/infrastructure/"]
        FeaturesConsumer["src/features/"]
        ReasoningConsumer["src/reasoning/"]
        APIConsumer ~~~ InfraConsumer ~~~ FeaturesConsumer ~~~ ReasoningConsumer
    end

    EnvFile --> ConfigSettings
    ConfigSettings --> Consumers
    DataTypes --> Consumers

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`config.py`** | Type-safe configuration management using `pydantic-settings`. Loads `.env` values, validates connection strings, and provides immutable runtime constants across the entire engine. |
| **`types.py`** | Defines canonical data envelopes (`DocumentChunk`, `GroundingVerdict`, `TelemetryFrame`, `SessionContext`) used across ingestion, retrieval, synthesis, and verification. |
