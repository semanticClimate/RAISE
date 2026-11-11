"""
RAISE Open Knowledge Format (OKF) & Document Knowledge Catalog System
====================================================================
Based on the Google Cloud Open Knowledge Format (OKF) specification:
Standardized, agent-ready Markdown bundles with YAML frontmatter that capture
institutional identity, temporal scope, academic domains, key entities, and acronyms.

Enables zero-hardcoding dynamic routing and retrieval for arbitrary uploaded PDFs.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("raise.features.catalog")

DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[3] / "data" / "catalogs"


@dataclass
class DocumentKnowledgeProfile:
    """
    Open Knowledge Format (OKF) Agent-Ready Document Profile.
    Conforms to open specification with structured YAML frontmatter and Markdown body.
    """
    document_id: str
    filename: str
    institution_name: str
    short_name: str = ""
    aliases: List[str] = field(default_factory=list)
    reporting_period: str = ""
    fiscal_years: List[str] = field(default_factory=list)
    document_type: str = "annual_report"
    total_pages: int = 0
    primary_domains: List[str] = field(default_factory=list)
    key_entities: List[str] = field(default_factory=list)
    key_acronyms: Dict[str, str] = field(default_factory=dict)
    overview_text: str = ""

    def to_okf_markdown(self) -> str:
        """Serializes profile to canonical OKF Markdown bundle with YAML frontmatter."""
        import yaml
        metadata = {
            "document_id": self.document_id,
            "filename": self.filename,
            "institution_name": self.institution_name,
            "short_name": self.short_name,
            "aliases": self.aliases,
            "reporting_period": self.reporting_period,
            "fiscal_years": self.fiscal_years,
            "document_type": self.document_type,
            "total_pages": self.total_pages,
            "primary_domains": self.primary_domains,
            "key_entities": self.key_entities,
            "key_acronyms": self.key_acronyms,
        }
        yaml_str = yaml.dump(metadata, sort_keys=False, allow_unicode=True).strip()
        body = self.overview_text.strip() if self.overview_text else f"# {self.institution_name} ({self.reporting_period})\n\nOperational knowledge catalog for {self.filename}."
        return f"---\n{yaml_str}\n---\n\n{body}\n"

    @classmethod
    def from_okf_markdown(cls, content: str) -> Optional["DocumentKnowledgeProfile"]:
        """Parses an OKF Markdown bundle with YAML frontmatter."""
        import yaml
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None
        frontmatter_raw, body_raw = match.group(1), match.group(2)
        try:
            meta = yaml.safe_load(frontmatter_raw) or {}
        except Exception as e:
            logger.error("Failed to parse YAML frontmatter: %s", e)
            return None

        return cls(
            document_id=meta.get("document_id", ""),
            filename=meta.get("filename", ""),
            institution_name=meta.get("institution_name", ""),
            short_name=meta.get("short_name", ""),
            aliases=list(meta.get("aliases") or []),
            reporting_period=str(meta.get("reporting_period") or ""),
            fiscal_years=[str(y) for y in (meta.get("fiscal_years") or [])],
            document_type=meta.get("document_type", "annual_report"),
            total_pages=int(meta.get("total_pages", 0)),
            primary_domains=list(meta.get("primary_domains") or []),
            key_entities=list(meta.get("key_entities") or []),
            key_acronyms=dict(meta.get("key_acronyms") or {}),
            overview_text=body_raw.strip(),
        )


class KnowledgeCatalogRegistry:
    """
    Central in-memory & file-persisted registry of all active document profiles.
    Resolves queries dynamically without any hardcoded logic in application nodes.
    """
    _instance: Optional["KnowledgeCatalogRegistry"] = None

    def __init__(self, catalog_dir: Optional[Path] = None):
        self.catalog_dir = catalog_dir or DEFAULT_CATALOG_DIR
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, DocumentKnowledgeProfile] = {}
        self.reload_catalogs()

    @classmethod
    def get_instance(cls, catalog_dir: Optional[Path] = None) -> "KnowledgeCatalogRegistry":
        if cls._instance is None:
            cls._instance = cls(catalog_dir=catalog_dir)
        return cls._instance

    def reload_catalogs(self) -> None:
        """Loads or reloads all .okf.md files from the catalog directory."""
        self.profiles.clear()
        if not self.catalog_dir.exists():
            return
        for f in self.catalog_dir.glob("*.okf.md"):
            try:
                content = f.read_text(encoding="utf-8")
                prof = DocumentKnowledgeProfile.from_okf_markdown(content)
                if prof and prof.filename:
                    self.profiles[prof.filename] = prof
                    logger.debug("Loaded OKF profile for: %s", prof.filename)
            except Exception as e:
                logger.warning("Failed to load catalog %s: %s", f.name, e)

    def register_profile(self, profile: DocumentKnowledgeProfile, persist: bool = True) -> None:
        """Registers a profile and optionally writes the .okf.md file to disk."""
        self.profiles[profile.filename] = profile
        if persist:
            safe_stem = Path(profile.filename).stem.replace(" ", "_").replace("-", "_")
            out_path = self.catalog_dir / f"{safe_stem}.okf.md"
            out_path.write_text(profile.to_okf_markdown(), encoding="utf-8")
            logger.info("Persisted OKF profile to %s", out_path)

    def remove_profile(self, filename_or_id: str) -> List[str]:
        """
        Deletes the catalog profile for a document from memory and unlinks its .okf.md file from disk.
        Matches by filename, document_id, or base stem.
        """
        removed_files: List[str] = []
        target_keys: List[str] = []
        clean_target = filename_or_id.lower().replace(".pdf", "").replace(".okf.md", "").strip()

        for fn, prof in list(self.profiles.items()):
            fn_clean = fn.lower().replace(".pdf", "").strip()
            doc_id_clean = prof.document_id.lower().strip()
            if clean_target in (fn_clean, doc_id_clean) or fn.lower() == filename_or_id.lower():
                target_keys.append(fn)

        for k in target_keys:
            self.profiles.pop(k, None)

        if self.catalog_dir.exists():
            for f in self.catalog_dir.glob("*.okf.md"):
                f_stem = f.name.replace(".okf.md", "").lower()
                matches_key = clean_target in f_stem or any(
                    k.lower().replace(".pdf", "").replace(" ", "_").replace("-", "_") in f_stem
                    for k in target_keys
                )
                if matches_key:
                    try:
                        f.unlink()
                        removed_files.append(f.name)
                        logger.info("Purged OKF catalog file: %s", f.name)
                    except Exception as e:
                        logger.warning("Failed to delete catalog file %s: %s", f.name, e)
                else:
                    try:
                        prof = DocumentKnowledgeProfile.from_okf_markdown(f.read_text(encoding="utf-8"))
                        if prof and (
                            prof.filename.lower() == filename_or_id.lower()
                            or prof.document_id.lower() == clean_target
                        ):
                            f.unlink()
                            removed_files.append(f.name)
                            logger.info("Purged OKF catalog file by frontmatter match: %s", f.name)
                    except Exception:
                        pass

        return removed_files

    def clear_all_catalogs(self) -> int:
        """
        Completely clears all in-memory catalog profiles and deletes all .okf.md files from disk.
        """
        self.profiles.clear()
        deleted_count = 0
        if self.catalog_dir.exists():
            for f in self.catalog_dir.glob("*.okf.md"):
                try:
                    f.unlink()
                    deleted_count += 1
                    logger.info("Purged OKF catalog file: %s", f.name)
                except Exception as e:
                    logger.warning("Failed to delete catalog file %s: %s", f.name, e)
        return deleted_count

    def get_profile(self, filename: str) -> Optional[DocumentKnowledgeProfile]:
        return self.profiles.get(filename)

    def get_all_profiles(self) -> List[DocumentKnowledgeProfile]:
        return list(self.profiles.values())

    def match_document_for_query(self, query: str) -> Optional[str]:
        """
        Dynamically resolves the single target document for a query using registered OKF profiles.
        Returns None if query is cross-document, comparative, multi-target, or ambiguous.
        ZERO hardcoding: dynamically evaluates fiscal years, institution aliases, and unique entities.
        """
        if not query or not self.profiles:
            return None

        q_lower = query.lower()

        # Step 1: Detect Cross-Document or Comparative Intent
        cross_doc_markers = [
            "both", "compare", "difference between", "differ between",
            "across both", "across reports", "trace the", "change between",
            "over time", "higher than", "versus", " vs ", "relative to"
        ]
        if any(marker in q_lower for marker in cross_doc_markers):
            return None

        # Step 2: Temporal Match (Fiscal Years & Reporting Periods from Catalogs)
        matched_temporal_docs: Set[str] = set()

        # 2a. Check compound year ranges first (e.g. 2022-23, 2023-24, 2024-25)
        for doc_name, prof in self.profiles.items():
            if prof.reporting_period:
                rp_clean = prof.reporting_period.replace("–", "-").replace("/", "-")
                if re.search(r"\b" + re.escape(rp_clean) + r"\b", q_lower) or re.search(r"\b" + re.escape(prof.reporting_period.lower()) + r"\b", q_lower):
                    matched_temporal_docs.add(doc_name)
            for yr in prof.fiscal_years:
                if "-" in yr or "/" in yr:
                    yr_clean = yr.replace("–", "-").replace("/", "-")
                    if re.search(r"\b" + re.escape(yr_clean) + r"\b", q_lower):
                        matched_temporal_docs.add(doc_name)

        # 2b. If no compound year matched, check standalone 4-digit years with lookaround
        if not matched_temporal_docs:
            for doc_name, prof in self.profiles.items():
                for yr in prof.fiscal_years:
                    if yr.isdigit() and len(yr) == 4:
                        pat = rf"(?<![-–/0-9]){yr}(?![-–/0-9])"
                        if re.search(pat, q_lower):
                            matched_temporal_docs.add(doc_name)

        if len(matched_temporal_docs) == 1:
            return next(iter(matched_temporal_docs))
        elif len(matched_temporal_docs) > 1:
            # Query mentions multiple distinct years/documents -> cross-document
            return None

        # Step 3: Institution Name & Alias Match
        matched_inst_docs: Set[str] = set()
        for doc_name, prof in self.profiles.items():
            if prof.short_name and len(prof.short_name) >= 3:
                if re.search(r"\b" + re.escape(prof.short_name.lower()) + r"\b", q_lower):
                    matched_inst_docs.add(doc_name)
                    continue
            for alias in prof.aliases:
                if len(alias) >= 3 and alias.lower() in q_lower:
                    matched_inst_docs.add(doc_name)
                    break

        if len(matched_inst_docs) == 1:
            return next(iter(matched_inst_docs))
        elif len(matched_inst_docs) > 1:
            # Query mentions multiple institutions -> cross-document
            return None

        # Step 4: Key Entity & Acronym Matching
        # Checks if query contains specific named entities/acronyms cataloged in exactly one document
        entity_hits: Dict[str, int] = {doc_name: 0 for doc_name in self.profiles}
        for doc_name, prof in self.profiles.items():
            for ent in prof.key_entities:
                if len(ent) >= 3:
                    pattern = r"\b" + re.escape(ent.lower()) + r"\b"
                    if re.search(pattern, q_lower):
                        entity_hits[doc_name] += 2

            for acr in prof.key_acronyms:
                if len(acr) >= 3:
                    pattern = r"\b" + re.escape(acr.lower()) + r"\b"
                    if re.search(pattern, q_lower):
                        entity_hits[doc_name] += 1

        scored_docs = [(doc_name, count) for doc_name, count in entity_hits.items() if count > 0]
        if scored_docs:
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            top_doc, top_count = scored_docs[0]
            # Must have distinct winner (at least 2 score and strictly higher than second place)
            if top_count >= 2 and (len(scored_docs) == 1 or top_count > scored_docs[1][1]):
                return top_doc

        return None
