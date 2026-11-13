"""
RAISE PyMuPDF High-Speed Document Parser Engine
================================================
Purpose:
  Provides fast, layout-aware geometric PDF parsing utilizing PyMuPDF,
  supplemented with targeted OCR for scanned graphics/pages and markdown table extraction.

Architecture:
  - PyMuPDFParserEngine:
      1. Geometric text block sorting (top-to-bottom, left-to-right).
      2. Targeted page-level EasyOCR fallback when block character density is minimal.
      3. Printed document page number extraction from footer margin zones.
      4. Embedded vector table parsing via `page.find_tables()` converted into clean Markdown.
      5. Multi-section detection and sub-page splitting for complex multi-topic pages.
      6. 100% Page-continuity enforcement ensuring zero missed pages.

Author: RAISE Core Architecture Team
Maintainability: Keep under 300 lines with clean error resilience and resource management.
"""

from __future__ import annotations
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pymupdf
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from src.parsers.text_quality import normalize_text, coalesce_markdown_sections


class PyMuPDFParserEngine:
    """
    High-speed, geometric-aware PDF parsing engine.
    Extracts text blocks, recognizes headers, converts tables, and preserves page continuity.
    """

    def __init__(self):
        self._easyocr_reader = None

    def _get_ocr_reader(self):
        if self._easyocr_reader is None:
            try:
                import easyocr
                self._easyocr_reader = easyocr.Reader(['en'], gpu=True)
            except Exception:
                self._easyocr_reader = False
        return self._easyocr_reader if self._easyocr_reader is not False else None

    def has_scanned_pages(self, pdf_path: Path, max_check: int = 20) -> bool:
        """Checks if a PDF document contains predominantly scanned pages."""
        if not HAS_PYMUPDF:
            return True
        try:
            with pymupdf.open(str(pdf_path)) as doc:
                total = len(doc)
                step = max(1, total // max_check)
                indices = range(0, total, step)
                scanned_count = 0
                for idx in indices:
                    if len(doc[idx].get_text("text").strip()) < 20:
                        scanned_count += 1
                return scanned_count > (len(indices) // 2)
        except Exception:
            return True

    def parse(
        self,
        pdf_path: Path | str,
        max_pages: Optional[int] = None,
        extract_tables: bool = True,
        do_ocr: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Executes high-speed geometric parsing on the target PDF.
        Returns a list of structured page dictionaries.
        """
        pdf_path = Path(pdf_path)
        t_parse_start = time.time()
        pages_label = f"max_pages={max_pages}" if (max_pages and int(max_pages) > 0) else "full document, no cap"
        print(f" [SmartParser] Routing '{pdf_path.name}' -> Fast PyMuPDF Structure Parser ({pages_label})...")
        
        pages_data: List[Dict[str, Any]] = []
        if not HAS_PYMUPDF:
            return []

        doc = pymupdf.open(str(pdf_path))
        pages_to_process = min(len(doc), int(max_pages)) if (max_pages and int(max_pages) > 0) else len(doc)

        prev_page_raw = ""
        for pno in range(pages_to_process):
            page = doc[pno]
            
            # Extract embedded tables geometrically
            table_count = 0
            table_blocks = []
            table_bboxes = []
            if extract_tables:
                try:
                    tables = page.find_tables()
                    if tables and len(tables.tables) > 0:
                        table_count = len(tables.tables)
                        for t in tables:
                            df = t.extract()
                            if df and len(df) > 1:
                                header = [str(c or '').replace('\n', ' ').strip() for c in df[0]]
                                t_md = "\n| " + " | ".join(header) + " |\n"
                                t_md += "| " + " | ".join(["---"] * len(header)) + " |\n"
                                for row in df[1:]:
                                    clean_row = [str(c or '').replace('\n', ' ').strip() for c in row]
                                    t_md += "| " + " | ".join(clean_row) + " |\n"
                                table_blocks.append((t.bbox[0], t.bbox[1], t.bbox[2], t.bbox[3], t_md.strip()))
                                table_bboxes.append(t.bbox)
                except Exception:
                    pass

            # Extract text blocks geometrically (x0, y0, x1, y1), filtering out cell fragments inside table bboxes
            blocks = page.get_text("blocks")
            filtered_blocks = []
            for b in blocks:
                if len(b) >= 5 and b[4] and b[4].strip():
                    bx_center = (b[0] + b[2]) / 2
                    by_center = (b[1] + b[3]) / 2
                    in_table = any(tb[0] <= bx_center <= tb[2] and tb[1] <= by_center <= tb[3] for tb in table_bboxes)
                    if not in_table:
                        filtered_blocks.append(b)

            all_items = filtered_blocks + table_blocks
            all_items.sort(key=lambda item: (item[1], item[0]))
            raw_text = "\n\n".join(item[4].strip() for item in all_items) if all_items else page.get_text("text").strip()
            
            # 1. OCR fallback for scanned report pages BEFORE length filtering (only when requested)
            if do_ocr and len(raw_text.strip()) < 80 and len(page.get_images()) > 0:
                ocr_reader = self._get_ocr_reader()
                if ocr_reader is not None:
                    try:
                        import numpy as np
                        pix = page.get_pixmap(dpi=150)
                        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                        ocr_lines = ocr_reader.readtext(img, detail=0)
                        if ocr_lines:
                            raw_text = "\n".join(ocr_lines)
                    except Exception:
                        pass

            # Normalize text
            raw_text = normalize_text(raw_text)
            if not raw_text or len(raw_text) < 15:
                raw_text = f"[Page {pno+1} Graphic / Form]"

            # Extract printed document page number from footer zone (bottom 65pt)
            doc_page_number = None
            H = page.rect.height
            for b in reversed(blocks):
                if len(b) >= 5 and (b[1] > H - 65 or b[3] > H - 45):
                    txt_b = b[4].strip()
                    m_p = re.match(r"^(?:page\s*)?([ivxlcdm]+|\d{1,4})$", txt_b, re.IGNORECASE)
                    if m_p:
                        doc_page_number = m_p.group(1)
                        break

            # Fallback check for printed page number in the last two text lines
            if not doc_page_number and raw_text:
                for line_cand in reversed([l.strip() for l in raw_text.split("\n") if l.strip()][-2:]):
                    m_p = re.match(r"^(?:page\s*)?([ivxlcdm]+|\d{1,4})$", line_cand, re.IGNORECASE)
                    if m_p:
                        doc_page_number = m_p.group(1)
                        break

            has_table = table_count > 0 or ("| --- |" in raw_text)
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

            # Detect multiple distinct section headings on the same physical page
            sec_matches = list(re.finditer(
                r'\b1[1-9]\s+(?:Board of Governors|Finance Committee|The Senate|Administration|Historical Purview|List of the Departments)|\b\d+\.\d+\s+[A-Z][A-Za-z\s&–—,()]{3,55}',
                raw_text,
                re.IGNORECASE
            ))
            
            is_toc = (
                any(line.lower() in {"contents", "table of contents", "index"} for line in lines[:5])
                or len(sec_matches) > 4
            )

            if not is_toc and 2 <= len(sec_matches) <= 4:
                sub_slices = []
                for s_i, s_m in enumerate(sec_matches):
                    s_start = 0 if s_i == 0 else s_m.start()
                    s_end = sec_matches[s_i + 1].start() if s_i + 1 < len(sec_matches) else len(raw_text)
                    sub_text = raw_text[s_start:s_end].strip()
                    sub_slices.append((s_m, sub_text))

                if all(len(st) >= 180 for _, st in sub_slices):
                    prev_page_raw = raw_text
                    for s_i, (s_m, sub_text) in enumerate(sub_slices):
                        raw_h = s_m.group(0).strip()
                        ocr_m = re.match(r'^1([1-9])\s+(.*)', raw_h)
                        if ocr_m and "." not in raw_h[:4]:
                            sub_heading = f"1.{ocr_m.group(1)} {ocr_m.group(2)}"
                        else:
                            sub_heading = raw_h
                        sub_heading = re.sub(r"\s+", " ", sub_heading).strip()[:70]

                        pages_data.append({
                            "page_number": pno + 1,
                            "doc_page_number": doc_page_number,
                            "heading": sub_heading,
                            "text": sub_text,
                            "engine": "PyMuPDF High-Speed Parser",
                            "tables_count": table_count if s_i == len(sub_slices) - 1 else 0,
                            "has_table": has_table if s_i == len(sub_slices) - 1 else False
                        })
                    continue

            heading = "Table of Contents" if is_toc else f"Section (Page {pno+1})"

            # Numbered section headers
            sec_num_match = re.search(r"\b([1-9]\d{0,1}\.\d{1,2}(?:\.\d{1,2})?\s+[A-Z][A-Za-z\s&–—,()]{3,55})\b", raw_text)
            if sec_num_match and any(kw in sec_num_match.group(0).lower() for kw in ("fee", "payment", "rupee", "inr", "usd", "amount", "paid", "due", "total", "confirm", "declaration")):
                sec_num_match = None
            if not is_toc and sec_num_match:
                heading = re.sub(r"\s+", " ", sec_num_match.group(1)).strip()[:70]
            elif not is_toc:
                ocr_sec_match = re.search(r"\b1([1-9])\s+((?:Board of Governors|Finance Committee|The Senate|Administration|Historical Purview|List of the Departments)[A-Za-z\s&–—,()]*)\b", raw_text, re.IGNORECASE)
                gov_match = re.search(r"\b((?:Board of Governors|Finance Committee|The Senate|Council Nominees|Senate Nominees|Administration|Historical Purview))\b", raw_text, re.IGNORECASE)
                if ocr_sec_match:
                    clean_sec_name = re.sub(r"\s+", " ", ocr_sec_match.group(2)).strip()[:60]
                    heading = f"1.{ocr_sec_match.group(1)} {clean_sec_name}"
                elif gov_match and any(lead in raw_text.lower() for lead in ("the visitor", "board of governors", "council nominees")):
                    clean_gov = gov_match.group(1).strip()
                    first_l = lines[0].strip()[:30] if lines else ""
                    if first_l.lower() != clean_gov.lower() and len(first_l) > 3:
                        heading = f"{first_l} & {clean_gov}"[:70]
                    else:
                        heading = clean_gov
                elif lines:
                    if lines[0].startswith("#"):
                        heading = lines[0].lstrip("#").strip()[:70]
                    else:
                        detected_h = None
                        first_line = lines[0].strip() if lines else ""
                        if (
                            3 <= len(first_line) <= 65
                            and not first_line.lower().startswith("annual report")
                            and not re.match(r"^PAGE\s*\d+$", first_line, re.IGNORECASE)
                            and not first_line.startswith(("-", "•", "–", "—", "&", "and "))
                            and not (first_line.startswith("(") and first_line.endswith(")"))
                        ):
                            detected_h = first_line[:70]
                        else:
                            for line in lines[:5]:
                                if (line.isupper() or line.istitle()) and 4 <= len(line) <= 65 and not re.match(r"^PAGE\s*\d+$", line) and not line.startswith("ANNUAL REPORT") and not (line.startswith("(") and line.endswith(")")):
                                    detected_h = line[:70]
                                    break
                        
                        first_line = lines[0]
                        is_frag = (
                            first_line[0].islower()
                            or first_line.startswith(("-", "•", "–", "—", "&", "and "))
                            or bool(re.match(r"^[a-zA-Z\s]+-\s*\d{4}$", first_line))
                        )
                        if is_frag and prev_page_raw:
                            prev_lines = [l.strip() for l in prev_page_raw.split("\n") if l.strip()]
                            for pl in reversed(prev_lines):
                                if pl.isupper() and 4 <= len(pl) <= 65 and not re.match(r"^PAGE\s*\d+$", pl):
                                    subheads = [l for l in lines if l.isupper() and 4 <= len(l) <= 50 and not re.match(r"^PAGE\s*\d+$", l)]
                                    if subheads:
                                        detected_h = f"{pl} & {subheads[0]}"[:70]
                                    else:
                                        detected_h = f"{pl} (Contd.)"[:70]
                                    break

                        if not detected_h:
                            for line in lines:
                                if line.isupper() and 4 <= len(line) <= 50 and not re.match(r"^PAGE\s*\d+$", line) and not line.startswith("ANNUAL REPORT"):
                                    detected_h = line[:70]
                                    break

                        if not detected_h and first_line and not first_line.lower().startswith("annual report") and len(first_line) > 5:
                            detected_h = first_line[:70]

                        heading = detected_h if detected_h else f"Section (Page {pno+1})"

            prev_page_raw = raw_text

            # Dense text handling: split into coherent sub-page chunks
            word_list = raw_text.split()
            if len(word_list) > 350:
                para_blocks = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
                coalesced_paras = coalesce_markdown_sections(para_blocks, target_words=350, min_words=80, max_words=600)
                if len(coalesced_paras) > 1:
                    for s_i, p_chunk in enumerate(coalesced_paras):
                        sub_h = f"{heading} (Part {s_i+1})"
                        pages_data.append({
                            "page_number": pno + 1,
                            "doc_page_number": doc_page_number,
                            "heading": sub_h,
                            "text": p_chunk,
                            "engine": "PyMuPDF High-Speed Parser",
                            "tables_count": 1 if ("| --- |" in p_chunk) else 0,
                            "has_table": bool("| --- |" in p_chunk)
                        })
                    continue

            pages_data.append({
                "page_number": pno + 1,
                "doc_page_number": doc_page_number,
                "heading": heading,
                "text": raw_text,
                "engine": "PyMuPDF High-Speed Parser",
                "tables_count": table_count,
                "has_table": has_table
            })

        # Final Page-Continuity Validator for PyMuPDF (ensures 100% of pages are present)
        existing_pages = {p["page_number"] for p in pages_data}
        for p_idx in range(pages_to_process):
            p_num = p_idx + 1
            if p_num not in existing_pages:
                fb_page = doc[p_idx]
                fb_txt = normalize_text(fb_page.get_text("text").strip())
                pages_data.append({
                    "page_number": p_num,
                    "heading": f"Section (Page {p_num})",
                    "text": fb_txt if fb_txt else f"[Page {p_num} Graphic / Blank]",
                    "engine": "PyMuPDF Continuity Fallback",
                    "tables_count": 0,
                    "has_table": False
                })
        pages_data.sort(key=lambda p: p["page_number"])

        doc.close()
        duration = round(time.time() - t_parse_start, 2)
        tables_total = sum(p.get("tables_count", 0) for p in pages_data)
        print(f" [SmartParser] Completed '{pdf_path.name}' via PyMuPDF: {len(pages_data)} pages in {duration}s ({len(pages_data)/max(duration, 0.01):.1f} p/s, {tables_total} tables)")
        return pages_data
