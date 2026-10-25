# 📑 Document Parsers Subsystem (`backend/src/parsers/`)

> **Multi-Modal Document Parsing, Table Geometry Recovery & Optical Layout Understanding**

---

## 🌟 Overview

The `src/parsers/` package provides the layout-aware document ingestion engines for the RAISE platform. It bridges unstructured binary PDF files and structured Markdown/AST hierarchies, ensuring complex multi-column reports, financial statements, and academic research papers are faithfully digitized.

---

## 🔄 Parsing Pipeline & Data Movement

```mermaid
flowchart TD
    %% Input
    RawPDF(["📄 Raw Binary PDF Upload<br/>(from src/api/routers/documents.py)"]):::inNode

    %% Parser Subsystem
    subgraph ParsersSubsystem ["📑 src/parsers/ Subsystem"]
        direction TB
        DocRouter["document_parser.py<br/>Layout Density & Feature Inspector"]

        subgraph Engines ["Extraction Engines"]
            direction LR
            PyMuPDF["pymupdf_engine.py<br/>Fast Stream: Plain Text, Headers & Page Bounding Boxes"]
            Docling["docling_engine.py<br/>Vision Stream: IBM Docling TableFormer Layout OCR"]
            PyMuPDF ~~~ Docling
        end

        TextQuality["text_quality.py<br/>Hyphenation Repair, OCR Artifact Cleansing & Unicode Normalization"]
    end

    %% Output
    ParsedAST(["🧩 Structured AST, Markdown Tables & Geometry Boxes<br/>(Forwarded to src/chunking/)"]):::outNode

    RawPDF --> DocRouter
    DocRouter -->|"Text-Heavy Documents"| PyMuPDF
    DocRouter -->|"Complex Tables & Scanned PDFs"| Docling
    PyMuPDF --> TextQuality
    Docling --> TextQuality
    TextQuality --> ParsedAST

    classDef inNode fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef outNode fill:#022c22,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    linkStyle default interpolate basis
```

---

## 📁 Key Components & Module Responsibilities

| File | Primary Responsibility |
| :--- | :--- |
| **`document_parser.py`** | Master ingestion facade. Inspects incoming PDF characteristics and routes files to either the fast text engine or deep layout model. |
| **`pymupdf_engine.py`** | High-throughput PyMuPDF (fitz) parser. Extracts textual blocks, font weight metrics, heading tags (H1-H4), and exact page-level coordinate bounding boxes. |
| **`docling_engine.py`** | Deep vision parser powered by IBM Docling and TableFormer. Reconstructs multi-cell financial tables, headers, and footnotes into Markdown format. |
| **`text_quality.py`** | Forensic text sanitization. Removes line-break hyphenations, repairs corrupted ligatures, and filters control characters. |
