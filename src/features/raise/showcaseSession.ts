import type { ChatSession } from './types';

export const DEMO_SHOWCASE_SESSION_ID = 'demo-showcase-capabilities';

export const DEMO_SHOWCASE_SESSION: ChatSession = {
  id: DEMO_SHOWCASE_SESSION_ID,
  thread_id: DEMO_SHOWCASE_SESSION_ID,
  session_id: DEMO_SHOWCASE_SESSION_ID,
  title: 'Showcase: Math, Tables & Code',
  timestamp: 'Showcase Demo',
  is_saved: true,
  messages: [
    {
      id: 'demo-msg-1',
      role: 'user',
      text: 'Showcase all workstation capabilities: LaTeX formulas, structured comparison tables, code blocks, and citations.',
      content: 'Showcase all workstation capabilities: LaTeX formulas, structured comparison tables, code blocks, and citations.',
      timestamp: 'Just now',
    },
    {
      id: 'demo-msg-2',
      role: 'assistant',
      text: `### RAISE Research Workstation Capabilities

Welcome to the **RAISE Advanced Research Interface**! This workstation is engineered to render high-precision scientific formulas, interactive tables, structured citations, and syntax-highlighted code.

---

#### 1. Mathematical Formulas (KaTeX & LaTeX)

Inline equations blend naturally into text:
- The mass-energy equivalence principle is defined as $E = mc^2$.
- Sigmoidal activation function: $\\sigma(z) = \\frac{1}{1 + e^{-z}}$.
- Cosine vector similarity: $\\text{sim}(\\mathbf{u}, \\mathbf{v}) = \\frac{\\mathbf{u} \\cdot \\mathbf{v}}{\\|\\mathbf{u}\\|_2 \\|\\mathbf{v}\\|_2}$.

Block / display equations format with centered alignment:

$$\\mathcal{L}_{\\text{InfoNCE}} = -\\log \\frac{\\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_+}{\\tau}\\right)}{\\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_+}{\\tau}\\right) + \\sum_{j=1}^{K} \\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_j^-}{\\tau}\\right)}$$

$$\\text{MultiHead}(Q, K, V) = \\text{Concat}(\\text{head}_1, \\dots, \\text{head}_h)W^O \\quad \\text{where} \\quad \\text{head}_i = \\text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$$

---

#### 2. Comparative Structured Tables

| Substrate Architecture | Storage Backend | Average Latency | Graph Traversal | Operational Mode |
| :--- | :--- | :--- | :--- | :--- |
| **In-Memory NetworkX** | RAM / Heap | \`0.4 ms\` | Breadth-First Search | Zero-Cost Local |
| **Neo4j Enterprise** | Bolt (\`:7687\`) | \`4.2 ms\` | Cypher Graph Match | Dedicated Cluster |
| **ChromaDB Vector** | Persistent Parquet | \`12.8 ms\` | HNSW Cosine Search | Dual-Index Vault |
| **PostgreSQL Memory** | SQL (\`:5432\`) | \`2.1 ms\` | Relational Turn Log | ACID Compliant |

---

#### 3. Code Execution & Syntax Highlighting

\`\`\`python
import numpy as np

def compute_grounding_score(citations: list[dict], threshold: float = 0.85) -> float:
    """Calculates weighted factual grounding score across retrieved citations."""
    if not citations:
        return 0.0
    similarities = np.array([c.get("similarity", 0.0) for c in citations])
    return float(np.mean(similarities >= threshold))
\`\`\`

---

> [!TIP]
> You can copy snippets using the copy button on each code block, or export the entire response to Markdown, JSON, or Plaintext via the **Export** menu below.`,
      content: `### RAISE Research Workstation Capabilities

Welcome to the **RAISE Advanced Research Interface**! This workstation is engineered to render high-precision scientific formulas, interactive tables, structured citations, and syntax-highlighted code.

---

#### 1. Mathematical Formulas (KaTeX & LaTeX)

Inline equations blend naturally into text:
- The mass-energy equivalence principle is defined as $E = mc^2$.
- Sigmoidal activation function: $\\sigma(z) = \\frac{1}{1 + e^{-z}}$.
- Cosine vector similarity: $\\text{sim}(\\mathbf{u}, \\mathbf{v}) = \\frac{\\mathbf{u} \\cdot \\mathbf{v}}{\\|\\mathbf{u}\\|_2 \\|\\mathbf{v}\\|_2}$.

Block / display equations format with centered alignment:

$$\\mathcal{L}_{\\text{InfoNCE}} = -\\log \\frac{\\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_+}{\\tau}\\right)}{\\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_+}{\\tau}\\right) + \\sum_{j=1}^{K} \\exp\\left(\\frac{\\mathbf{q} \\cdot \\mathbf{k}_j^-}{\\tau}\\right)}$$

$$\\text{MultiHead}(Q, K, V) = \\text{Concat}(\\text{head}_1, \\dots, \\text{head}_h)W^O \\quad \\text{where} \\quad \\text{head}_i = \\text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$$

---

#### 2. Comparative Structured Tables

| Substrate Architecture | Storage Backend | Average Latency | Graph Traversal | Operational Mode |
| :--- | :--- | :--- | :--- | :--- |
| **In-Memory NetworkX** | RAM / Heap | \`0.4 ms\` | Breadth-First Search | Zero-Cost Local |
| **Neo4j Enterprise** | Bolt (\`:7687\`) | \`4.2 ms\` | Cypher Graph Match | Dedicated Cluster |
| **ChromaDB Vector** | Persistent Parquet | \`12.8 ms\` | HNSW Cosine Search | Dual-Index Vault |
| **PostgreSQL Memory** | SQL (\`:5432\`) | \`2.1 ms\` | Relational Turn Log | ACID Compliant |

---

#### 3. Code Execution & Syntax Highlighting

\`\`\`python
import numpy as np

def compute_grounding_score(citations: list[dict], threshold: float = 0.85) -> float:
    """Calculates weighted factual grounding score across retrieved citations."""
    if not citations:
        return 0.0
    similarities = np.array([c.get("similarity", 0.0) for c in citations])
    return float(np.mean(similarities >= threshold))
\`\`\`

---

> [!TIP]
> You can copy snippets using the copy button on each code block, or export the entire response to Markdown, JSON, or Plaintext via the **Export** menu below.`,
      durationSec: 0.8,
      isThinking: false,
      response: {
        query: 'Showcase all workstation capabilities: LaTeX formulas, structured comparison tables, code blocks, and citations.',
        grounded_answer: 'Mathematical formulas, structured comparison tables, and code blocks.',
        execution_time: 0.8,
        latency_sec: 0.8,
        traceability_score: 0.98,
        quality_gate_decision: 'accept',
        citations: [
          {
            citation_index: 1,
            chunk_id: 'chk-demo-1',
            document_id: 'doc-demo-1',
            university: 'RAISE Research Group',
            document_name: 'RAISE Architecture Whitepaper.pdf',
            pdf_filename: 'RAISE Architecture Whitepaper.pdf',
            primary_page: 4,
            heading: 'Dual-Track Retrieval Architecture',
            plain_text: 'Hybrid retrieval combines vector similarity search via ChromaDB with knowledge graph traversals.',
            similarity: 0.98,
          },
        ],
      },
    },
  ],
};
