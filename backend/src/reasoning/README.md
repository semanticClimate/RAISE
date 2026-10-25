# 🤖 Reasoning Subsystem (`backend/src/reasoning/`)

> **Multi-Hop Query Planning, Table Logic, Temporal Reasoning & Evidence-Bound Synthesis**

---

## 🌟 Overview

The `src/reasoning/` package handles the generation of answers strictly bound to retrieved evidence. It structures multi-hop logical paths, executes table calculations, aligns chronological events, and delegates token generation to your configured local or cloud LLM.

---

## 🔄 Reasoning & Synthesis Data Movement

```mermaid
flowchart TD
    %% Input
    Evidence["📑 Top-K Re-Ranked Evidence Passages<br/>(from src/retrieval/)"]:::inNode
    HistoryContext["🧠 Sliding Session History Context<br/>(from src/features/memory/)"]:::inNode
    Evidence ~~~ HistoryContext

    %% Reasoning Subsystem
    subgraph ReasoningSubsystem ["🤖 src/reasoning/ Subsystem"]
        direction TB
        Planner["query_planner.py<br/>Multi-Hop Step Decomposition & Reasoning Tree"]

        subgraph Operators ["Specialized Operators"]
            direction LR
            Numerical["numerical.py & tables.py<br/>Cell Extraction & Aggregation"]
            Temporal["temporal.py<br/>Chronological Sequence Validation"]
            Numerical ~~~ Temporal
        end

        Synthesizer["synthesizer.py<br/>Prompt Compilation with Bounded Evidence Invariants"]

        InferenceBridge["Flexible LLM Integration<br/>(Local or Cloud LLM of your choice)"]

        SurfaceAdapter["surface_adapter.py<br/>Inline Citation Insertion ([1], [2]) & Markdown Formatting"]
    end

    %% Output
    DraftAnswer(["💬 Draft Answer with Inline Citation Badges<br/>(Transmitted to src/features/verification/)"]):::outNode

    Evidence --> Planner
    HistoryContext --> Planner
    Planner --> Operators
    Operators --> Synthesizer
    Synthesizer --> InferenceBridge
    InferenceBridge --> SurfaceAdapter
    SurfaceAdapter --> DraftAnswer

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`query_planner.py`** | Constructs the execution plan for complex queries. Determines whether an inquiry requires single-step extraction or cross-chapter multi-hop deduction. |
| **`synthesizer.py`** | Compiles prompt contexts, injects evidence passages, enforces refusal rules when evidence is missing, and streams responses token-by-token. |
| **`tables.py` & `numerical.py`** | Interprets tabular structures, extracts cell values, and formats numerical contexts for financial and metric comparisons. |
| **`temporal.py`** | Resolves dates, fiscal years (e.g., FY 2023-24 vs FY 2024-25), and enforces chronological consistency across multi-year institutional reports. |
| **`surface_adapter.py`** | Attaches bracketed citation references (`[1]`, `[2]`) to verified sentences, ensuring each claim is mapped to an identifiable evidence source. |
