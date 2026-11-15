"""
Update Page 9 Nature Index Table Chunk and Sync ChromaDB
=========================================================
Formats the infographic table on Page 9 into standard Markdown table syntax
with both Global and India rank columns, updates both child chunk and parent
chunk, and syncs ChromaDB vector store.
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.infrastructure.vector.chroma import LocalVectorEngine
import src.retrieval.macro_hydration as macro_hydration

def main():
    chunks_path = BACKEND_DIR / "data" / "processed" / "chunks" / "NIPGR_BRIC_Annual_Report_2025_chunks.json"
    parents_path = BACKEND_DIR / "data" / "processed" / "chunks" / "NIPGR_BRIC_Annual_Report_2025_parent_chunks.json"
    
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    parents = json.loads(parents_path.read_text(encoding="utf-8"))

    nature_index_table_markdown = """### Nature Index – iBRIC+ India Profile (1 April 2024 – 31 March 2025)

The positions in the table below reflect the iBRIC+'s positions overall, domestically; within their sectors and various subject areas based on their research output share.

| Research Category | Global Position | India Position |
| :--- | :--- | :--- |
| **Overall** | 665 | 21 |
| **Government** | 66 | 4 |
| **Biological Sciences** | 227 | 1 |
| **Chemistry** | 1067 | 49 |
| **Earth & Environmental Sciences** | 1893 | 54 |
| **Health Sciences** | 648 | 3 |
| **Physical Sciences** | 1649 | 72 |

The data indicates that iBRIC+ India holds the 1st position in India in Biological Sciences, 3rd in Health Sciences, and 4th in Government research output.
According to the Nature Index 2025 profile for iBRIC+ India, covering the reporting period 1 April 2024 to 31 March 2025 (includes iBRIC RCB + ICGEB).
Time frame: 1 April 2024 – 31 March 2025."""

    # 1. Update child chunk
    updated_child = False
    for c in chunks:
        if c.get("chunk_id") == "NIPGR_BRIC_Annual_Report_2025_p009_c10_01":
            c["plain_text"] = nature_index_table_markdown
            c["text"] = nature_index_table_markdown
            c["enriched_text"] = nature_index_table_markdown
            c["contextualized_content"] = f"[Document: NIPGR_BRIC_Annual_Report_2025.pdf | Section: RESEARCH HIGHLIGHTS | Page: 9]\nInstitution: Biotechnology Research and Innovation Council (BRIC)\nReporting Period: 2024-25\n\n{nature_index_table_markdown}"
            c["is_table"] = True
            c["has_table"] = True
            c["tables_count"] = 1
            c["heading"] = "Nature Index – iBRIC+ India Profile (1 April 2024 – 31 March 2025)"
            updated_child = True
            print("Successfully updated chunk NIPGR_BRIC_Annual_Report_2025_p009_c10_01")
            break

    if updated_child:
        chunks_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")
        print(f"Persisted updated child chunks to {chunks_path}")

    # 2. Update parent chunk
    updated_parent = False
    for p in parents:
        cid = p.get("chunk_id") or p.get("id")
        if cid == "NIPGR_BRIC_Annual_Report_2025_parent_010":
            p["plain_text"] = f"RESEARCH HIGHLIGHTS\n\n{nature_index_table_markdown}"
            p["text"] = f"RESEARCH HIGHLIGHTS\n\n{nature_index_table_markdown}"
            p["enriched_text"] = f"[Document: NIPGR_BRIC_Annual_Report_2025.pdf | Section: RESEARCH HIGHLIGHTS | Page: 9]\n\n{nature_index_table_markdown}"
            p["contextualized_content"] = f"[Document: NIPGR_BRIC_Annual_Report_2025.pdf | Section: RESEARCH HIGHLIGHTS | Page: 9]\n\n{nature_index_table_markdown}"
            p["heading"] = "Nature Index – iBRIC+ India Profile (1 April 2024 – 31 March 2025)"
            updated_parent = True
            print("Successfully updated parent chunk NIPGR_BRIC_Annual_Report_2025_parent_010")
            break

    if updated_parent:
        parents_path.write_text(json.dumps(parents, indent=2), encoding="utf-8")
        print(f"Persisted updated parent chunks to {parents_path}")

    # Clear memory cache
    macro_hydration._PARENT_CHUNKS_CACHE = {}

    # 3. Sync ChromaDB Vector Store
    engine = LocalVectorEngine()
    doc_id = "NIPGR_BRIC_Annual_Report_2025"
    cnt = engine.ingest_chunks(chunks, doc_id=doc_id)
    print(f"Re-ingested {cnt} chunks into ChromaDB for {doc_id}")

if __name__ == "__main__":
    main()
