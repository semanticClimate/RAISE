/**
 * ═══════════════════════════════════════════════════════════════════════════
 * RAISE SETTINGS: ABOUT & ARCHITECTURE CONTENT CONFIGURATION
 * ═══════════════════════════════════════════════════════════════════════════
 * Sid says: Reflects the full 7 architecture stages and tri-substrate specifications from README.md
 */

export interface ModeFeatureItem {
  title: string;
  description: string;
}

export interface ArchitectureModeCard {
  testId: string;
  title: string;
  badge: string;
  badgeType: 'amber' | 'emerald';
  description: string;
  features: ModeFeatureItem[];
}

export interface SubstrateSpecItem {
  label: string;
  value: string;
  detail: string;
}

export interface AboutContentConfig {
  header: {
    title: string;
    version: string;
    description: string;
    showAsciiText: string;
    hideAsciiText: string;
  };
  asciiBlueprint: {
    sectionTitle: string;
    diagram: string;
  };
  routerNode: {
    category: string;
    title: string;
  };
  modes: {
    fastMode: ArchitectureModeCard;
    expertMode: ArchitectureModeCard;
  };
  substrateSpecs: {
    sectionTitle: string;
    items: SubstrateSpecItem[];
  };
}

export const aboutContent: AboutContentConfig = {
  // Main title, version badge, and intro text
  header: {
    title: 'About RAISE GraphRAG',
    version: 'v1.0.0',
    description:
      'Tri-substrate retrieval (Vectors, Lexical BM25, Neo4j Graph) with 7-stage verifiable reasoning and interactive citations.',
    showAsciiText: 'Show ASCII Blueprint',
    hideAsciiText: 'Hide ASCII Blueprint',
  },

  // Expandable ASCII architectural pipeline diagram
  asciiBlueprint: {
    sectionTitle: 'Architectural Pipeline Routing Tree',
    diagram: `                      ┌─────────────────────────────────────────┐
                      │    LangGraph Intent Router & Intake     │
                      └────────────────────┬────────────────────┘
                                           │
                       ┌───────────────────┴───────────────────┐
                       ▼                                       ▼
        ┌───────────────────────────┐   ┌───────────────────────────┐
        │         FAST MODE         │   │        EXPERT MODE        │
        │  • BM25 + Vector (k=4)    │   │  • Table Chunk Boosting   │
        │  • 1-Hop Subgraph         │   │  • 2-3 Hop Neo4j Graph    │
        │  • Low-Latency Synthesis  │   │  • Cross-Encoder Rerank   │
        │  • Streaming Sub-1.5s     │   │  • Multi-Hop Claim Critic │
        └───────────────────────────┘   └───────────────────────────┘`,
  },

  // Central Router node above the dual mode tree
  routerNode: {
    category: 'Query Intake & Intent Router',
    title: '15-Node Cyclical LangGraph State Machine',
  },

  // Dual Routing Mode specifications
  modes: {
    // 1. FAST MODE
    fastMode: {
      testId: 'architecture-fast-mode-card',
      title: 'Fast Mode',
      badge: 'Speed Optimized',
      badgeType: 'amber',
      description:
        'Rapid direct retrieval for conversational inquiries, simple factual questions, and low-latency interaction.',
      features: [
        {
          title: 'BM25 + Vector (k=4)',
          description: 'Dense ChromaDB semantic embeddings fused with lexical BM25 token matching.',
        },
        {
          title: '1-Hop Subgraph',
          description: 'Immediate entity relations from local Neo4j graph without deep recursion.',
        },
        {
          title: 'Sub-1.5s Stream',
          description: 'Direct token streaming synthesis for instant answers.',
        },
      ],
    },

    // 2. EXPERT MODE
    expertMode: {
      testId: 'architecture-expert-mode-card',
      title: 'Expert Mode',
      badge: 'Deep Reasoning',
      badgeType: 'emerald',
      description:
        'Exhaustive graph traversal, structured table prioritization, and cross-encoder reranking for complex research.',
      features: [
        {
          title: 'Table Chunk Boosting',
          description:
            'Priority scoring for structured IBM Docling tables, CSV matrices, and financial disclosures.',
        },
        {
          title: '2-3 Hop Neo4j Graph',
          description:
            'Deep multi-step relational exploration across interconnected entity clusters.',
        },
        {
          title: 'Cross-Encoder Rerank',
          description: 'BGE/Cohere re-scoring to eliminate noisy context before LLM generation.',
        },
      ],
    },
  },

  // System Substrate Specifications grid (7-stage pipeline)
  substrateSpecs: {
    sectionTitle: 'System Substrate Specifications',
    items: [
      {
        label: 'Vector Substrate',
        value: 'ChromaDB Dense Vectors',
        detail: 'BGE-Large-EN (1024-dim dense embeddings)',
      },
      {
        label: 'Knowledge Graph',
        value: 'Neo4j 5.x Property Graph',
        detail: 'Bolt Protocol • Cypher Multi-Hop Traversal',
      },
      {
        label: 'Lexical Search',
        value: 'BM25 Inverted Index',
        detail: 'Exact Grant IDs, Monetary & Alphanumeric Codes',
      },
      {
        label: 'Document Ingestion',
        value: 'IBM Docling Engine (GGAHC)',
        detail: 'Graph-Guided Adaptive Hierarchical Chunking preserving tables',
      },
      {
        label: 'Dual-Tier Memory',
        value: 'Redis Cache & Postgres',
        detail: 'Sub-millisecond fast cache + multi-turn session context',
      },
      {
        label: 'Reasoning & Quality Gate',
        value: 'Entailment Verification Gate',
        detail: 'Grounded citation check & 2-pass query retry loop',
      },
    ],
  },
};

export default aboutContent;
