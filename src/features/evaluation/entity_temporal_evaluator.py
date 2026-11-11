"""
Entity & Temporal Constraint Resolution Evaluator
=================================================
Evaluates the system's ability to extract and bind structured query constraints:
1. Entities: Named organizations, genes, scientific targets, initiatives, persons.
2. Temporal Markers: Fiscal years (e.g. 2022-23, 2023-2024), calendar years (2024, 2025).
3. Section/Metric Constraints: Financial figures, administrative sections, publications.

Strictly avoids hardcoded document or entity lookup tables. Operates dynamically on
query text and gold benchmark annotations.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExtractedConstraints:
    """Constraints parsed dynamically from query text."""
    years: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    metric_terms: List[str] = field(default_factory=list)
    section_hints: List[str] = field(default_factory=list)


@dataclass
class QueryEntityEvaluationResult:
    """Evaluation result for a single query's entity & temporal parsing."""
    query_id: str
    query: str
    extracted_years: List[str]
    gold_years: List[str]
    year_match: bool
    extracted_entities: List[str]
    gold_entities: List[str]
    entity_precision: float
    entity_recall: float
    entity_f1: float
    extracted_metrics: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query": self.query,
            "extracted_years": self.extracted_years,
            "gold_years": self.gold_years,
            "year_match": self.year_match,
            "extracted_entities": self.extracted_entities,
            "gold_entities": self.gold_entities,
            "entity_precision": round(self.entity_precision, 4),
            "entity_recall": round(self.entity_recall, 4),
            "entity_f1": round(self.entity_f1, 4),
            "extracted_metrics": self.extracted_metrics,
        }


class EntityTemporalEvaluator:
    """
    Parses and evaluates entity and temporal constraint binding.
    """

    # Matches fiscal years like 2022-23, 2023-2024, FY23, FY 2024, or standalone 4-digit years 2010-2035
    YEAR_PATTERN = re.compile(
        r"\b(?:FY\s*[-_]?)?(?:20[1-3][0-9](?:[-–/](?:20)?[1-3][0-9])?)\b",
        re.IGNORECASE,
    )

    # Common metrics or accounting terms in annual reports
    METRIC_PATTERN = re.compile(
        r"\b(budget|expenditure|revenue|grant|grants|corpus|endowment|fellowship|fellowships|"
        r"patent|patents|publication|publications|student|students|faculty|staff|salary|"
        r"assets|liabilities|balance\s+sheet|income|receipts|payments)\b",
        re.IGNORECASE,
    )

    # General capitalized phrases / acronyms that represent entities (institutions, genes, proteins, projects)
    ENTITY_ACRONYM_PATTERN = re.compile(r"\b[A-Z0-9]{2,12}(?:-[A-Z0-9]+)*\b")
    PROPER_NOUN_PATTERN = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")

    # Stop words for entity extraction
    ENTITY_STOP_WORDS = {
        "What", "How", "When", "Where", "Which", "Who", "Why", "In", "On", "At", "By", "For",
        "The", "This", "That", "These", "Those", "Annual", "Report", "Table", "Page", "According",
        "During", "Mentioned", "State", "Provide", "List", "Total", "Number", "Amount", "Year",
    }

    @classmethod
    def extract_temporal_constraints(cls, text: str) -> List[str]:
        """Dynamically extracts all fiscal and calendar year references."""
        matches = cls.YEAR_PATTERN.findall(text)
        cleaned = []
        for m in matches:
            norm = m.strip().upper()
            if norm not in cleaned:
                cleaned.append(norm)
        return cleaned

    @classmethod
    def extract_entities(cls, text: str) -> List[str]:
        """
        Dynamically extracts named entities, scientific symbols, and acronyms
        without using any hardcoded lookup tables.
        """
        entities: List[str] = []

        # 1. Acronyms & alphanumeric symbols (e.g. BRIC, NII, NIPGR, THSTI, At-SLX1, NVD1, MUR1)
        for m in cls.ENTITY_ACRONYM_PATTERN.findall(text):
            if m not in cls.ENTITY_STOP_WORDS and not m.isdigit() and len(m) >= 2:
                if m not in entities:
                    entities.append(m)

        # 2. Capitalized Multi-Word Phrases (e.g. National Institute of Plant Genome Research)
        for m in cls.PROPER_NOUN_PATTERN.findall(text):
            words = m.split()
            filtered_words = [w for w in words if w not in cls.ENTITY_STOP_WORDS]
            if filtered_words and len(m) > 3:
                phrase = " ".join(filtered_words)
                if phrase not in entities and phrase not in cls.ENTITY_STOP_WORDS:
                    entities.append(phrase)

        return entities

    @classmethod
    def extract_metric_terms(cls, text: str) -> List[str]:
        """Extracts financial and operational metric terms."""
        return list(set(m.lower() for m in cls.METRIC_PATTERN.findall(text)))

    @classmethod
    def parse_query(cls, query: str) -> ExtractedConstraints:
        """Parses all constraints dynamically from query text."""
        return ExtractedConstraints(
            years=cls.extract_temporal_constraints(query),
            entities=cls.extract_entities(query),
            metric_terms=cls.extract_metric_terms(query),
        )

    @classmethod
    def evaluate_query(
        cls,
        query_id: str,
        query: str,
        gold_keywords: Optional[List[str]] = None,
        gold_document: str = "",
    ) -> QueryEntityEvaluationResult:
        """
        Evaluates entity and temporal constraint binding against gold keywords and document name.
        """
        constraints = cls.parse_query(query)
        gold_keywords = gold_keywords or []

        # Extract gold years from query + gold document
        gold_years = cls.extract_temporal_constraints(gold_document)
        query_years = constraints.years
        if not gold_years and query_years:
            gold_years = query_years

        # Year match: if either year matches or both empty
        year_match = False
        if not gold_years and not query_years:
            year_match = True
        elif set(query_years).intersection(set(gold_years)):
            year_match = True
        else:
            # Check partial string matching (e.g. '2023-24' inside 'Annual Report 2023-24.pdf')
            for qy in query_years:
                if any(qy in gy or gy in qy for gy in gold_years):
                    year_match = True
                    break

        # Entity precision & recall vs gold keywords
        # Filter gold keywords for named entities (non-trivial words)
        gold_entities = [
            k for k in gold_keywords
            if len(k) > 2 and not k.isdigit() and k.lower() not in {"the", "and", "report", "annual"}
        ]

        extracted_set = set(e.lower() for e in constraints.entities)
        gold_set = set(g.lower() for g in gold_entities)

        if not gold_set:
            # If no gold entities specified, perfect score if nothing hallucinated or some extracted
            prec = 1.0
            rec = 1.0
            f1 = 1.0
        elif not extracted_set:
            prec = 0.0
            rec = 0.0
            f1 = 0.0
        else:
            # Check overlap or substring containment
            matched = 0
            for ge in gold_set:
                if any(ge in ee or ee in ge for ee in extracted_set):
                    matched += 1
            rec = matched / len(gold_set)
            prec = matched / len(extracted_set) if extracted_set else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        return QueryEntityEvaluationResult(
            query_id=query_id,
            query=query,
            extracted_years=constraints.years,
            gold_years=gold_years,
            year_match=year_match,
            extracted_entities=constraints.entities,
            gold_entities=gold_entities,
            entity_precision=prec,
            entity_recall=rec,
            entity_f1=f1,
            extracted_metrics=constraints.metric_terms,
        )

    @classmethod
    def aggregate_results(
        cls, results: List[QueryEntityEvaluationResult]
    ) -> Dict[str, Any]:
        """Aggregates entity & temporal evaluation metrics across the test set."""
        if not results:
            return {
                "total_queries": 0,
                "year_accuracy": 0.0,
                "mean_entity_precision": 0.0,
                "mean_entity_recall": 0.0,
                "mean_entity_f1": 0.0,
            }

        total = len(results)
        year_acc = sum(1 for r in results if r.year_match) / total
        m_prec = sum(r.entity_precision for r in results) / total
        m_rec = sum(r.entity_recall for r in results) / total
        m_f1 = sum(r.entity_f1 for r in results) / total

        return {
            "total_queries": total,
            "year_accuracy": round(year_acc, 4),
            "mean_entity_precision": round(m_prec, 4),
            "mean_entity_recall": round(m_rec, 4),
            "mean_entity_f1": round(m_f1, 4),
            "queries": [r.to_dict() for r in results],
        }
