"""
RAISE Docling Layout & Table Parsing Engine
============================================
Purpose:
  Provides neural layout, column, and table parsing using Docling (TableFormer & LayoutFormer).
  Preserves complex multi-column reading orders, tabular structures, and recovers
  partially scanned pages via targeted page-level GPU OCR.

Architecture:
  - DoclingParserEngine:
      1. Converter Factory: Configures CUDA/CPU acceleration and TableFormer accurate mode.
      2. Neural Layout Conversion: Extracts section headers, tables, and paragraphs.
      3. Markdown Section Coalescing: Assembles micro-sections into high-entropy semantic chunks.
      4. Targeted Page-Level GPU OCR: Fills in graphic/scanned pages without stalling the pipeline.
      5. Continuity Validation: Guarantees sequential 1-to-N page completeness.

Author: RAISE Core Architecture Team
Maintainability: Keep under 300 lines with thorough docstrings and clean exception handling.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Suppress harmless TableFormer orphan cell recovery logs in runtime console
logging.getLogger("MatchingPostProcessor").setLevel(logging.ERROR)
logging.getLogger("docling").setLevel(logging.ERROR)

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.datamodel.base_models import InputFormat
    HAS_DOCLING = True
except Exception:
    HAS_DOCLING = False

try:
    import pymupdf
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

from src.parsers.text_quality import normalize_text, coalesce_markdown_sections


class DoclingParserEngine:
    """
    Neural document parser leveraging Docling's LayoutFormer & TableFormer.
    """

    def __init__(self):
        self._docling_converter_no_ocr = None
        self._docling_converter_ocr = None
        self._easyocr_reader = None

    def _get_ocr_reader(self):
        if self._easyocr_reader is None:
            try:
                import easyocr
                self._easyocr_reader = easyocr.Reader(['en'], gpu=True)
            except Exception:
                self._easyocr_reader = False
        return self._easyocr_reader if self._easyocr_reader is not False else None

    def _create_converter(self, do_ocr: bool = False):
        if not HAS_DOCLING:
            return None
        try:
            from docling.datamodel.pipeline_options import AcceleratorOptions, AcceleratorDevice
            import torch
            use_cuda = torch.cuda.is_available()
            acc_dev = AcceleratorDevice.CUDA if use_cuda else AcceleratorDevice.CPU

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = do_ocr
            pipeline_options.do_table_structure = True
            pipeline_options.generate_page_images = True
            pipeline_options.accelerator_options = AcceleratorOptions(device=acc_dev)
            
            try:
                pipeline_options.table_structure_options.do_cell_matching = True
                pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
            except Exception:
                pass

            return DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
            )
        except Exception as e:
            print(f" [DoclingEngine] Notice initializing Docling (do_ocr={do_ocr}): {e}")
            return None

    def get_converter(self, do_ocr: bool = False):
        """Lazy-initializes and caches DocumentConverter instances."""
        if do_ocr:
            if self._docling_converter_ocr is None:
                self._docling_converter_ocr = self._create_converter(do_ocr=True)
            return self._docling_converter_ocr
        else:
            if self._docling_converter_no_ocr is None:
                self._docling_converter_no_ocr = self._create_converter(do_ocr=False)
            return self._docling_converter_no_ocr

    def parse(
        self,
        pdf_path: Path | str,
        max_pages: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Parses a PDF document using Docling.
        Returns a list of structured page dictionaries, or None if parsing failed/fallback is needed.
        """
        if not HAS_DOCLING:
            return None

        converter = self.get_converter(do_ocr=False)
        if not converter:
            return None

        pdf_path = Path(pdf_path)
        t_parse_start = time.time()
        temp_slice_path = None

        try:
            cap_label = f"max_pages={max_pages}" if (max_pages and int(max_pages) > 0) else "full document, no cap"
            print(f" [SmartParser] Routing '{pdf_path.name}' -> Docling (TableFormer Accurate, Page-Level OCR, {cap_label})...")
            doc_pages = int(max_pages) if (max_pages and int(max_pages) > 0) else None
            convert_path = pdf_path

            # Only slice if caller explicitly requested a partial page limit
            if doc_pages and HAS_PYMUPDF:
                try:
                    with pymupdf.open(str(pdf_path)) as _chk_doc:
                        if len(_chk_doc) > doc_pages:
                            temp_slice_path = pdf_path.parent / f"_temp_docling_slice_{doc_pages}_{pdf_path.name}"
                            sub_doc = pymupdf.open()
                            for p in range(doc_pages):
                                sub_doc.insert_pdf(_chk_doc, from_page=p, to_page=p)
                            sub_doc.save(str(temp_slice_path))
                            sub_doc.close()
                            convert_path = temp_slice_path
                except Exception:
                    pass

            doc = converter.convert(str(convert_path))
            pages_data: List[Dict[str, Any]] = []
            page_items_map: Dict[int, List[str]] = {}
            page_headings_map: Dict[int, str] = {}
            table_count = 0

            try:
                for item, _level in doc.document.iterate_items():
                    prov = getattr(item, "prov", None)
                    p_no = prov[0].page_no if (prov and len(prov) > 0) else 1
                    item_type = type(item).__name__
                    if item_type in ["PictureItem"]:
                        continue
                    txt = ""
                    if item_type == "TableItem":
                        table_count += 1
                    if hasattr(item, "export_to_markdown"):
                        try:
                            txt = item.export_to_markdown(doc=doc.document)
                        except Exception:
                            txt = getattr(item, "text", "") or ""
                    elif hasattr(item, "text"):
                        txt = item.text or ""
                    txt = txt.strip()
                    if not txt:
                        continue
                    if p_no not in page_items_map:
                        page_items_map[p_no] = []
                    page_items_map[p_no].append(txt)
                    if item_type == "SectionHeaderItem" and p_no not in page_headings_map:
                        page_headings_map[p_no] = txt.replace("#", "").strip()[:70]
            except Exception as iter_err:
                print(f" [DoclingEngine] Notice during Docling iteration: {iter_err}")

            for p_no, lines in sorted(page_items_map.items()):
                h_default = page_headings_map.get(p_no)
                coalesced_chunks = coalesce_markdown_sections(lines, target_words=450, min_words=100, max_words=700)
                if not coalesced_chunks:
                    raw_combined = normalize_text("\n\n".join(lines))
                    if raw_combined and len(raw_combined) >= 15:
                        coalesced_chunks = [raw_combined]
                
                for sub_idx, chunk_text in enumerate(coalesced_chunks):
                    norm_text = normalize_text(chunk_text)
                    if not norm_text or len(norm_text) < 15:
                        continue
                    chunk_h = h_default
                    if not chunk_h:
                        first_l = norm_text.split("\n")[0].replace("#", "").strip()[:70]
                        chunk_h = first_l if len(first_l) > 3 else f"Section (Page {p_no})"
                    if len(coalesced_chunks) > 1:
                        chunk_h = f"{chunk_h} (Part {sub_idx+1})"
                    
                    has_tbl = "|" in norm_text and "-|-" in norm_text
                    pages_data.append({
                        "page_number": p_no,
                        "heading": chunk_h,
                        "text": norm_text,
                        "engine": "Docling LayoutFormer",
                        "tables_count": table_count if has_tbl else 0,
                        "has_table": has_tbl
                    })

            if not pages_data:
                md_text = doc.document.export_to_markdown()
                if md_text.strip():
                    pages_data.append({
                        "page_number": 1,
                        "heading": "Document Content",
                        "text": normalize_text(md_text),
                        "engine": "Docling LayoutFormer",
                        "tables_count": len(doc.document.tables) if hasattr(doc.document, "tables") else 0,
                        "has_table": bool(hasattr(doc.document, "tables") and doc.document.tables)
                    })

            # Page-Continuity & Targeted Page-Level GPU OCR
            if pages_data and HAS_PYMUPDF:
                try:
                    with pymupdf.open(str(pdf_path)) as _vdoc:
                        target_total = min(len(_vdoc), int(max_pages)) if (max_pages and int(max_pages) > 0) else len(_vdoc)
                        existing_pages = {p["page_number"] for p in pages_data}
                        ocr_reader = self._get_ocr_reader()

                        for p_num in range(1, target_total + 1):
                            if p_num not in existing_pages:
                                fb_page = _vdoc[p_num - 1]
                                fb_text = normalize_text(fb_page.get_text("text").strip())
                                if len(fb_text) < 40 and len(fb_page.get_images()) > 0 and ocr_reader is not None:
                                    try:
                                        import numpy as np
                                        pix = fb_page.get_pixmap(dpi=150)
                                        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                                        ocr_lines = ocr_reader.readtext(img, detail=0)
                                        if ocr_lines:
                                            fb_text = normalize_text("\n".join(ocr_lines))
                                    except Exception:
                                        pass
                                pages_data.append({
                                    "page_number": p_num,
                                    "heading": f"Section (Page {p_num})",
                                    "text": fb_text if fb_text else f"[Page {p_num}]",
                                    "engine": "PyMuPDF Continuity Fallback",
                                    "tables_count": 0,
                                    "has_table": False
                                })
                        
                        # Check Docling pages with minimal text that are scanned images
                        for p in pages_data:
                            if len(p.get("text", "").strip()) < 40:
                                p_idx = p["page_number"] - 1
                                if 0 <= p_idx < len(_vdoc):
                                    cpage = _vdoc[p_idx]
                                    if len(cpage.get_images()) > 0 and ocr_reader is not None:
                                        try:
                                            import numpy as np
                                            pix = cpage.get_pixmap(dpi=150)
                                            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                                            ocr_lines = ocr_reader.readtext(img, detail=0)
                                            if ocr_lines:
                                                p["text"] = normalize_text("\n".join(ocr_lines))
                                                p["engine"] = "Docling + Page-Level GPU OCR"
                                        except Exception:
                                            pass
                        pages_data.sort(key=lambda p: p["page_number"])
                except Exception as _val_err:
                    print(f" [DoclingEngine] Continuity validator notice: {_val_err}")

            if pages_data:
                duration = round(time.time() - t_parse_start, 2)
                tables_total = sum(p.get("tables_count", 0) for p in pages_data)
                print(f" [SmartParser] Completed '{pdf_path.name}' via Docling: {len(pages_data)} pages in {duration}s ({len(pages_data)/max(duration, 0.01):.1f} p/s, {tables_total} tables)")
                return pages_data

            return None
        except Exception as e:
            print(f" [DoclingEngine] Docling parse notice ({e}). Falling back to fast PyMuPDF parser.")
            return None
        finally:
            if temp_slice_path and temp_slice_path.exists():
                try:
                    temp_slice_path.unlink()
                except Exception:
                    pass
