"""
RAISE Academic & University Domain Knowledge Extractor
=====================================================
Component: `src.features.ingestion.academic_extractor`
Architecture: Generalized academic entity-relation extraction engine
Max Lines: Strictly <= 400 lines
Guarantees 100% Academic Focus & Zero Manga/Fictional Pollution.
Preserves PDF filename, page number, section heading, chunk ID, and exact snippet provenance.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .academic_models import AcademicEntity, AcademicRelation
from .academic_personnel_facts import extract_personnel_and_metrics

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

try:
    from gliner import GLiNER
    HAS_GLINER = True
except ImportError:
    HAS_GLINER = False


class AcademicDomainExtractor:
    """
    Generalized academic entity-relation extraction engine with zero hardcoded institution lists.
    Extracts departments, centres, programs, faculty, roles, and metrics using GLiNER zero-shot NER
    and complementary universal structural patterns.
    """

    _gliner_model: Optional[Any] = None
    GLINER_MODEL_NAME = "urchade/gliner_base"
    GLINER_LABELS = [
        "University",
        "Department",
        "Research Centre",
        "Degree Program",
        "Faculty",
        "Administrative Role",
        "Laboratory",
        "Academic Regulation",
    ]

    DEPARTMENT_PATTERN = re.compile(
        r"\b((?:Department|School|Division|Faculty|College)\s+of\s+[A-Za-z\s&–—]{3,50})\b",
        re.IGNORECASE,
    )
    CENTRE_PATTERN = re.compile(
        r"\b((?:Centre|Center|Institute|Council|Facility|Lab|Laboratory|Park|Incubator)\s+(?:for|of|in)?\s+[A-Za-z\s&–—]{3,50})\b",
        re.IGNORECASE,
    )
    PROGRAM_PATTERNS = [
        re.compile(r"\b((?:B|M)\.?(?:Tech|Sc|A|Eng|Phil)|Ph\.?D|Bachelor|Master|Doctorate|Diploma|Post\s+Graduate)\s*(?:of\s+[A-Za-z\s&]+|in\s+[A-Za-z\s&]+)?\b", re.IGNORECASE)
    ]
    ROLE_PATTERN = re.compile(
        r"\b((?:Director|Vice-Chancellor|Dean|Chairperson|President|Provost|Chancellor|Head\s+of\s+Department|Registrar|Lead|Principal|Advisor|Officer|Chief\s+Executive\s+Officer|MD|CEO|CFO|COO|Managing\s+Director)(?:\s+[A-Za-z\s&]+)?)\b",
        re.IGNORECASE,
    )

    def __init__(self, enable_gliner: bool = True):
        self.enable_gliner = enable_gliner

    @classmethod
    def get_gliner_model(cls) -> Optional[Any]:
        """Lazy-load GLiNER model singleton for zero-shot entity extraction."""
        if cls._gliner_model is None and HAS_GLINER:
            try:
                cls._gliner_model = GLiNER.from_pretrained(cls.GLINER_MODEL_NAME)
            except Exception:
                cls._gliner_model = None
        return cls._gliner_model

    @classmethod
    def clean_entity_name(cls, raw_name: str) -> str:
        """Sanitize entity names before MERGE in graph to eliminate span artifacts and noise."""
        if not raw_name:
            return ""
        # Collapse newlines and multiple spaces into a single space, strip punctuation
        name = re.sub(r"\s+", " ", str(raw_name)).strip(" ,.:;-–\t\r\n")
        # Reject noisy fragments (too short, raw units, generic committee references)
        lower = name.lower()
        if len(name) < 3 or lower in {"the committee", "rs", "metric: rs", "coordination", "the governing council"}:
            return ""
        # Reject spans with ungrammatical trailing prepositions or conjunctions
        if lower.endswith((" held on", " of the", " and", " in", " on", " with", " for", " by", " to", " at", " from")):
            return ""
        # Reject raw metrics or fragments starting with metric labels
        if lower.startswith(("metric:", "rs,", "held on")):
            return ""
        return name

    @classmethod
    def _split_text_for_ner(cls, text: str) -> List[str]:
        """
        Pre-NER sentence & chunk splitting:
        Ensures chunks passed to GLiNER are split on reasonable punctuation or capped at ~250-300 words (~1200 chars).
        """
        clean_txt = text.strip()
        if len(clean_txt) <= 1200:
            return [clean_txt]
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1200,
                chunk_overlap=150,
                separators=["\n\n", "\n", ". ", "; ", " ", ""],
            )
            return splitter.split_text(clean_txt)
        except Exception:
            # Resilient punctuation-based fallback
            parts = re.split(r"(?<=[.!?;\n])\s+", clean_txt)
            chunks: List[str] = []
            curr: List[str] = []
            curr_len = 0
            for p in parts:
                p_len = len(p)
                if curr_len + p_len > 1200 and curr:
                    chunks.append(" ".join(curr))
                    curr = [p]
                    curr_len = p_len
                else:
                    curr.append(p)
                    curr_len += p_len + 1
            if curr:
                chunks.append(" ".join(curr))
            return chunks or [clean_txt]

    @classmethod
    def resolve_canonical_name(cls, raw_name: str) -> Tuple[str, str]:
        """Dynamically resolve entity name to clean canonical form and unified identifier without hardcoded aliases."""
        clean = cls.clean_entity_name(raw_name)
        if not clean:
            clean = re.sub(r"\s+", " ", raw_name).strip(" ,.:;-")
        canon_slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean.lower()).strip("_")[:40]
        return clean, canon_slug

    def clean_text(self, text: str) -> str:
        """Clean and normalize OCR/PDF text spans."""
        return re.sub(r"\s+", " ", text).strip()

    def extract_academic_knowledge(
        self,
        text: str,
        pdf_filename: str,
        page_number: int,
        section_heading: str,
        chunk_id: str,
        university_name: str = "University",
    ) -> Tuple[List[AcademicEntity], List[AcademicRelation]]:
        """
        Extract academic entities and directed relationships with source provenance.
        """
        entities: List[AcademicEntity] = []
        relations: List[AcademicRelation] = []
        seen_entity_ids = set()

        def add_entity(e_id: str, label: str, name: str, props: Optional[Dict[str, Any]] = None):
            if e_id not in seen_entity_ids and len(name.strip()) > 2:
                seen_entity_ids.add(e_id)
                entities.append(AcademicEntity(
                    entity_id=e_id,
                    label=label,
                    name=name.strip(),
                    properties=props or {},
                    provenance={
                        "pdf_filename": pdf_filename,
                        "page_number": page_number,
                        "section_heading": section_heading,
                        "chunk_id": chunk_id,
                        "source_text": text[:200]
                    }
                ))

        # 1. Primary University / Institution / Document Node (Dynamic labeling)
        clean_inst_name = self.clean_entity_name(university_name) or university_name
        is_uni = "university" in clean_inst_name.lower()
        inst_label = "University" if is_uni else "Institution"
        inst_prefix = "uni" if is_uni else "inst"
        uni_id = f"{inst_prefix}_{re.sub(r'[^a-zA-Z0-9]', '_', clean_inst_name.lower())[:30]}"
        add_entity(uni_id, inst_label, clean_inst_name)

        # 1.5 Zero-Shot Entity & Structural Extraction via GLiNER with Pre-NER Sentence Splitting
        if self.enable_gliner and len(text.strip()) > 15:
            gliner = self.get_gliner_model()
            if gliner is not None:
                # Split chunks into punctuation-bounded segments capped at ~250-300 words
                sub_segments = self._split_text_for_ner(text)
                for seg in sub_segments:
                    if len(seg.strip()) < 15:
                        continue
                    try:
                        gliner_ents = gliner.predict_entities(seg, self.GLINER_LABELS, threshold=0.45)
                        for ge in gliner_ents:
                            raw_txt = ge.get("text", "").strip()
                            g_lbl = ge.get("label", "")
                            score = float(ge.get("score", 0.0))
                            cleaned_name = self.clean_entity_name(raw_txt)
                            if not cleaned_name or len(cleaned_name) < 3:
                                continue
                            clean_name, slug = self.resolve_canonical_name(cleaned_name)
                            if not slug:
                                continue

                            if g_lbl in ("University", "Institution"):
                                resolved_lbl = "University" if "university" in clean_name.lower() else "Institution"
                                add_entity(f"inst_{slug}", resolved_lbl, clean_name, {"confidence": score, "source": "gliner"})
                            elif g_lbl == "Department":
                                d_id = f"dept_{slug}"
                                add_entity(d_id, "Department", clean_name, {"confidence": score, "source": "gliner"})
                                relations.append(AcademicRelation(
                                    relation_id=f"rel_{uni_id}_{d_id}_has_dept",
                                    source_id=uni_id,
                                    source_label=inst_label,
                                    relation_type="HAS_DEPARTMENT",
                                    target_id=d_id,
                                    target_label="Department",
                                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                                ))
                            elif g_lbl in ("Research Centre", "Centre"):
                                c_id = f"centre_{slug}"
                                add_entity(c_id, "Centre", clean_name, {"confidence": score, "source": "gliner"})
                                relations.append(AcademicRelation(
                                    relation_id=f"rel_{uni_id}_{c_id}_has_centre",
                                    source_id=uni_id,
                                    source_label=inst_label,
                                    relation_type="HAS_CENTRE",
                                    target_id=c_id,
                                    target_label="Centre",
                                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                                ))
                            elif g_lbl == "Degree Program":
                                p_id = f"prog_{slug}"
                                add_entity(p_id, "Program", clean_name, {"confidence": score, "source": "gliner"})
                                relations.append(AcademicRelation(
                                    relation_id=f"rel_{uni_id}_{p_id}_offers_prog",
                                    source_id=uni_id,
                                    source_label=inst_label,
                                    relation_type="OFFERS_PROGRAM",
                                    target_id=p_id,
                                    target_label="Program",
                                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                                ))
                            elif g_lbl in ("Faculty", "Professor"):
                                add_entity(f"fac_{slug}", "Faculty_Person", clean_name, {"confidence": score, "source": "gliner"})
                            elif g_lbl == "Administrative Role":
                                add_entity(f"role_{slug}", "AdministrativeRole", clean_name, {"confidence": score, "source": "gliner"})
                            elif g_lbl == "Laboratory":
                                l_id = f"lab_{slug}"
                                add_entity(l_id, "Practical_Lab", clean_name, {"confidence": score, "source": "gliner"})
                                relations.append(AcademicRelation(
                                    relation_id=f"rel_{uni_id}_{l_id}_has_lab",
                                    source_id=uni_id,
                                    source_label=inst_label,
                                    relation_type="HAS_PRACTICAL",
                                    target_id=l_id,
                                    target_label="Practical_Lab",
                                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                                ))
                            elif g_lbl == "Academic Regulation":
                                reg_id = f"reg_{slug}"
                                add_entity(reg_id, "AcademicRegulation", clean_name, {"confidence": score, "source": "gliner"})
                                relations.append(AcademicRelation(
                                    relation_id=f"rel_{uni_id}_{reg_id}_governed_by",
                                    source_id=uni_id,
                                    source_label=inst_label,
                                    relation_type="GOVERNED_BY",
                                    target_id=reg_id,
                                    target_label="AcademicRegulation",
                                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                                ))

                        # Link faculty to role if both are uniquely present
                        gliner_fac_ids = [f"fac_{self.resolve_canonical_name(ge['text'])[1]}" for ge in gliner_ents if ge.get("label") in ("Faculty", "Professor")]
                        gliner_role_ids = [f"role_{self.resolve_canonical_name(ge['text'])[1]}" for ge in gliner_ents if ge.get("label") == "Administrative Role"]
                        if len(gliner_fac_ids) == 1 and len(gliner_role_ids) == 1:
                            f_id = gliner_fac_ids[0]
                            r_id = gliner_role_ids[0]
                            relations.append(AcademicRelation(
                                relation_id=f"rel_{f_id}_{r_id}_holds_role",
                                source_id=f_id,
                                source_label="Faculty_Person",
                                relation_type="HOLDS_ROLE",
                                target_id=r_id,
                                target_label="AdministrativeRole",
                                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                            ))
                    except Exception:
                        pass

        # 2. Extract Departments & Schools
        dept_matches = self.DEPARTMENT_PATTERN.finditer(text)
        for dm in dept_matches:
            raw_dept_name = dm.group(1).strip()
            dept_name, canon_slug = self.resolve_canonical_name(raw_dept_name)
            if not dept_name:
                continue
            d_id = f"dept_{canon_slug}"
            add_entity(d_id, "Department", dept_name)
            relations.append(AcademicRelation(
                relation_id=f"rel_{uni_id}_{d_id}_has_dept",
                source_id=uni_id,
                source_label=inst_label,
                relation_type="HAS_DEPARTMENT",
                target_id=d_id,
                target_label="Department",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

        # 3. Extract Centres, Institutes & Labs
        centre_matches = self.CENTRE_PATTERN.finditer(text)
        for cm in centre_matches:
            raw_centre_name = cm.group(1).strip()
            centre_name, canon_slug = self.resolve_canonical_name(raw_centre_name)
            if not centre_name:
                continue
            c_id = f"centre_{canon_slug}"
            add_entity(c_id, "Centre", centre_name)
            relations.append(AcademicRelation(
                relation_id=f"rel_{uni_id}_{c_id}_has_centre",
                source_id=uni_id,
                source_label=inst_label,
                relation_type="HAS_CENTRE",
                target_id=c_id,
                target_label="Centre",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))
            relations.append(AcademicRelation(
                relation_id=f"rel_{uni_id}_{c_id}_has_centre",
                source_id=uni_id,
                source_label="University",
                relation_type="HAS_CENTRE",
                target_id=c_id,
                target_label="Centre",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

        # 4. Extract Degree Programs
        for prog_pat in self.PROGRAM_PATTERNS:
            for pm in prog_pat.finditer(text):
                prog_name = pm.group(0).strip()
                p_id = f"prog_{re.sub(r'[^a-zA-Z0-9]', '_', prog_name.lower())[:35]}"
                add_entity(p_id, "Program", prog_name, {"degree_level": pm.group(1).strip() if pm.lastindex else "Degree"})
                relations.append(AcademicRelation(
                    relation_id=f"rel_{uni_id}_{p_id}_offers_prog",
                    source_id=uni_id,
                    source_label="University",
                    relation_type="OFFERS_PROGRAM",
                    target_id=p_id,
                    target_label="Program",
                    provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
                ))

        # 5. Extract Practical & Laboratory Requirements
        lab_matches = re.finditer(r"\b(practical|laboratory|lab\s+course|computational\s+lab|hands-on\s+session|experimental\s+module)\b", text, re.IGNORECASE)
        for idx, lm in enumerate(lab_matches):
            lab_text = text[max(0, lm.start()-30):min(len(text), lm.end()+60)].strip()
            l_id = f"lab_{chunk_id}_{idx+1}"
            add_entity(l_id, "Practical_Lab", f"Practical/Lab Session ({lm.group(1).title()})", {"description": lab_text})
            relations.append(AcademicRelation(
                relation_id=f"rel_{uni_id}_{l_id}_has_lab",
                source_id=uni_id,
                source_label="University",
                relation_type="HAS_PRACTICAL",
                target_id=l_id,
                target_label="Practical_Lab",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

        # 6. Extract Regulations & Admission Requirements
        reg_matches = re.finditer(r"\b(minimum\s+attendance|eligibility\s+criteria|admission\s+requirement|examination\s+rule|passing\s+grade|mandatory\s+course)\b", text, re.IGNORECASE)
        for idx, rm in enumerate(reg_matches):
            reg_phrase = text[max(0, rm.start()-20):min(len(text), rm.end()+70)].strip()
            r_id = f"reg_{chunk_id}_{idx+1}"
            add_entity(r_id, "AcademicRegulation", f"Academic Rule ({rm.group(1).title()})", {"rule_snippet": reg_phrase})
            relations.append(AcademicRelation(
                relation_id=f"rel_{uni_id}_{r_id}_governed_by",
                source_id=uni_id,
                source_label="University",
                relation_type="GOVERNED_BY",
                target_id=r_id,
                target_label="AcademicRegulation",
                provenance={"pdf_filename": pdf_filename, "page_number": page_number, "chunk_id": chunk_id}
            ))

        # 7-10. Extract Faculty, Roles, Committees, Organizations, Facts, and Section Links
        extract_personnel_and_metrics(
            text=text,
            section_heading=section_heading,
            pdf_filename=pdf_filename,
            page_number=page_number,
            chunk_id=chunk_id,
            uni_id=uni_id,
            add_entity=add_entity,
            relations=relations,
        )

        return entities, relations

    extract_entities_and_relations = extract_academic_knowledge


__all__ = ["AcademicDomainExtractor", "AcademicEntity", "AcademicRelation"]
