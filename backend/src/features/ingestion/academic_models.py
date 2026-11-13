"""
Academic Graph Entities and Relations Data Contracts
===================================================
Component: `src.features.ingestion.academic_models`
Architecture: Pure data definitions for academic ontology nodes & edges
Line Ceiling: Strictly <= 400 lines
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict


@dataclass
class AcademicEntity:
    entity_id: str
    label: str  # "University", "Department", "Centre", "Program", "Subject", "Practical_Lab", "AcademicRegulation", "EligibilityRequirement", "Faculty_Person", "AdministrativeRole", "ResearchProject", "Publication_Patent", "MetricFact"
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AcademicRelation:
    relation_id: str
    source_id: str
    source_label: str
    relation_type: str  # "HAS_DEPARTMENT", "HAS_CENTRE", "OFFERS_PROGRAM", "HAS_SUBJECT", "HAS_PRACTICAL", "TEACHES_SUBJECT", "HOLDS_ROLE", "REQUIRED_FOR", "GOVERNED_BY", "FUNDED_BY", "REPORTED_METRIC", "OWNS_PATENT"
    target_id: str
    target_label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = ["AcademicEntity", "AcademicRelation"]
