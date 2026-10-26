/**
 * ═══════════════════════════════════════════════════════════════════════════
 * RAISE SETTINGS: HELP CONTENT CONFIGURATION
 * ═══════════════════════════════════════════════════════════════════════════
 * Sid says: Synchronized with master 7-stage architecture specifications from README.md
 */

export interface KeyboardShortcutItem {
  label: string;
  keys: string[];
  separator?: string;
}

export interface KeyCapabilityItem {
  title: string;
  description: string;
}

export interface HelpContentConfig {
  header: {
    title: string;
    description: string;
  };
  shortcuts: {
    sectionTitle: string;
    items: KeyboardShortcutItem[];
  };
  capabilities: {
    sectionTitle: string;
    items: KeyCapabilityItem[];
  };
  architecture: {
    sectionTitle: string;
    linkText: string;
    asciiDiagram: string;
  };
  platform: {
    title: string;
    description: string;
    version: string;
  };
}

export const helpContent: HelpContentConfig = {
  // Top Header section
  header: {
    title: 'Help & Quick Reference',
    description: 'Keyboard navigation shortcuts, functional capabilities, and architecture reference.',
  },

  // Keyboard Shortcuts section
  shortcuts: {
    sectionTitle: 'Keyboard Shortcuts',
    items: [
      {
        label: 'Focus query input',
        keys: ['⌘/Ctrl + K'],
      },
      {
        label: 'Open settings',
        keys: ['⌘/Ctrl + /'],
      },
      {
        label: 'Find in PDF viewer',
        keys: ['⌘/Ctrl + F'],
      },
      {
        label: 'Close modal / drawer',
        keys: ['Esc'],
      },
      {
        label: 'Navigate suggestions',
        keys: ['↑', '↓'],
        separator: '/',
      },
      {
        label: 'Send research query',
        keys: ['Enter'],
      },
    ],
  },

  // Key Capabilities section (grounded in README.md)
  capabilities: {
    sectionTitle: 'Core Research Capabilities',
    items: [
      {
        title: 'Interactive Citations & Google Drive-Style PDF Viewer',
        description:
          'Click citation chips ([1], [2]) directly inside AI responses to open the Google Drive-style PDF viewer with zoom (+/-), page navigation, in-document search, and page downloads.',
      },
      {
        title: 'Session-Scoped Attached Documents',
        description:
          'Attach PDFs and reports to your workspace. The sources drawer scopes documents strictly to the active thread for grounded reasoning.',
      },
      {
        title: 'Tri-Substrate Knowledge Base & Subgraph Explorer',
        description:
          'Simultaneously searches dense ChromaDB vectors, lexical BM25 indices, and Neo4j knowledge graphs. Explore multi-hop entity relationships via the interactive Subgraph Explorer.',
      },
      {
        title: 'Grounding Verification Quality Gate',
        description:
          'Evaluates generated text against retrieved evidence before emitting results. Automatically reformulates queries and triggers retries when evidence is incomplete.',
      },
    ],
  },

  // Pipeline Routing Architecture preview
  architecture: {
    sectionTitle: 'Pipeline Routing Architecture',
    linkText: 'Full Architecture & Specs',
    asciiDiagram: `┌───────────────────┴───────────────────┐
        ▼                                       ▼
 ┌───────────────────────────┐   ┌───────────────────────────┐
 │       FAST MODE           │   │       EXPERT MODE         │
 │  • BM25 + Vector (k=4)    │   │  • Table Chunk Boosting   │
 │  • 1-Hop Subgraph         │   │  • 2-3 Hop Neo4j Graph    │
 │  • Low-Latency (<1.5s)    │   │  • Cross-Encoder Rerank   │
 └───────────────────────────┘   └───────────────────────────┘`,
  },

  // Platform info footer banner
  platform: {
    title: 'RAISE GraphRAG Workstation',
    description: 'Hybrid Tri-Substrate Retrieval with 7-Stage Verifiable Reasoning',
    version: 'v1.0.0',
  },
};

export default helpContent;
