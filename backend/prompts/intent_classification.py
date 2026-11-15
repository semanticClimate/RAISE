"""
RAISE Academic GraphRAG Studio - Query Intent Classification Prompt Module
Formats incoming natural language user queries for deterministic classification
into strategic GraphRAG retrieval modalities (Global, Local Cypher, Hybrid Vector, Table Math).
"""

import json
import re
from typing import Any, Dict, List

INTENT_TO_ROUTING_MAP: Dict[str, str] = {
    "INSTITUTIONAL_PROFILE": "GLOBAL_COMMUNITY",
    "MULTI_HOP_RELATION": "LOCAL_GRAPH_CYPHER",
    "ACADEMIC_RESEARCH": "LOCAL_GRAPH_CYPHER",
    "FINANCIAL_FACT": "HYBRID_VECTOR",
    "STATISTICAL_METRIC": "HYBRID_VECTOR",
    "OUT_OF_SCOPE": "NONE",
}

INTENT_CLASSIFICATION_PROMPT = """<system_role>
You are an intent classification and query planning model for the RAISE Academic GraphRAG Studio.
Your objective is to analyze the user's research query regarding institutional annual reports and classify it into one primary retrieval intent and execution strategy.
</system_role>

<classification_categories>
1. ACADEMIC_RESEARCH:
   - Inquiries about academic curricula, research programs, faculty publications, patents, labs, and sponsored grants.
2. FINANCIAL_FACT:
   - Specific queries about revenue, expenditure, balance sheets, budget allocations, academic fees, endowments, or financial statement line items.
3. INSTITUTIONAL_PROFILE:
   - Broad queries regarding organizational vision, leadership, departments, centres of excellence, boards of governors, or macro-level institutional summaries.
4. STATISTICAL_METRIC:
   - Specific quantitative counts, breakdowns, or rankings: student enrollments, faculty/staff appointment counts, graduation numbers, or placement statistics.
5. MULTI_HOP_RELATION:
   - Complex relational paths: startup incubation chains, technology licensing, investigator-to-grant-to-equipment links, or foreign university MoUs.
6. OUT_OF_SCOPE:
   - General trivia, conversational greetings, or questions unrelated to institutional documents.
</classification_categories>

<routing_strategies>
- GLOBAL_COMMUNITY: Broad thematic or multi-section institutional summaries.
- LOCAL_GRAPH_CYPHER: Entity-specific relationships, structural traversals, or multi-hop lookups.
- HYBRID_VECTOR: Direct factual, statistical, or tabular text/number extraction.
</routing_strategies>

<output_contract>
Respond strictly in valid JSON format with no markdown backticks or preamble:
{
  "intent": "ACADEMIC_RESEARCH | FINANCIAL_FACT | INSTITUTIONAL_PROFILE | STATISTICAL_METRIC | MULTI_HOP_RELATION | OUT_OF_SCOPE",
  "routing_strategy": "GLOBAL_COMMUNITY | LOCAL_GRAPH_CYPHER | HYBRID_VECTOR",
  "entities": ["entity1", "entity2"],
  "requires_graph": true,
  "requires_vector": true,
  "requires_tables": false,
  "reasoning": "Short justification for chosen intent and routing strategy"
}
</output_contract>
"""


def get_intent_classification_prompt() -> str:
    """Returns the intent classification system prompt."""
    return INTENT_CLASSIFICATION_PROMPT.strip()


def build_intent_classification_messages(query: str) -> List[Dict[str, str]]:
    """Builds chat messages for intent classification."""
    return [
        {"role": "system", "content": get_intent_classification_prompt()},
        {"role": "user", "content": f"Classify the following query:\n\n{query.strip()}"},
    ]


def parse_intent_response(raw_response: str, fallback_query: str = "") -> Dict[str, Any]:
    """
    Safely parses LLM JSON output (stripping markdown fences if present) and
    enforces deterministic fallback defaults for LangGraph routing and telemetry.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response.strip(), flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        parsed = json.loads(m.group(0)) if m else {}

    intent = str(parsed.get("intent", "ACADEMIC_RESEARCH")).upper()
    if intent not in INTENT_TO_ROUTING_MAP:
        intent = "ACADEMIC_RESEARCH"

    requires_graph = bool(
        parsed.get("requires_graph", intent in ("ACADEMIC_RESEARCH", "MULTI_HOP_RELATION", "INSTITUTIONAL_PROFILE"))
    )
    requires_vector = bool(parsed.get("requires_vector", intent != "OUT_OF_SCOPE"))
    requires_tables = bool(
        parsed.get("requires_tables", intent in ("FINANCIAL_FACT", "STATISTICAL_METRIC"))
    )

    routing_strategy = str(parsed.get("routing_strategy", "")).upper()
    if routing_strategy not in ("GLOBAL_COMMUNITY", "LOCAL_GRAPH_CYPHER", "HYBRID_VECTOR"):
        if requires_graph and intent == "INSTITUTIONAL_PROFILE":
            routing_strategy = "GLOBAL_COMMUNITY"
        elif requires_graph:
            routing_strategy = "LOCAL_GRAPH_CYPHER"
        else:
            routing_strategy = INTENT_TO_ROUTING_MAP.get(intent, "HYBRID_VECTOR")

    entities = parsed.get("entities")
    if not isinstance(entities, list):
        entities = [fallback_query] if fallback_query else []

    return {
        "intent": intent,
        "routing_strategy": routing_strategy,
        "entities": [str(e).strip() for e in entities if str(e).strip()],
        "requires_graph": requires_graph,
        "requires_vector": requires_vector,
        "requires_tables": requires_tables,
        "reasoning": str(parsed.get("reasoning", "Parsed with deterministic schema validation.")),
    }
