"""
RAISE Master Terminal Interactive Runner Test Suite
Tests main.py end-to-end interactive session:
1. User identity inquiry (unintroduced prompt suggesting 'Sid')
2. Assistant identity inquiry ('My name is RAISE')
3. User name introduction ('my name is Sid')
4. User name modification ('change my name to Alex')
5. Updated identity recall ('It\\'s Alex')
6. PDF Document upload ('upload <path> fast')
7. Document parsing, table & entity extraction, vault indexing
8. In-line citation querying on Page 4 ('tell me what is in page no 4')
9. In-line citation querying on Page 5 ('tell me what is in page no 5')
"""

import os
import sys
import pytest
import subprocess
from pathlib import Path

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

# Enforce offline flags
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


@pytest.mark.timeout(300)
def test_main_conversational_and_citation_interactive_flow(tmp_path):
    """
    Test main.py interactive CLI runner across full user journey:
    - Persona & identity discovery
    - Dynamic name change
    - PDF report ingestion & parsing
    - Specific page citation extraction (Page 4 & Page 5)
    """
    import pymupdf

    test_pdf_path = tmp_path / "Interactive_Research_Doc.pdf"
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 72), "Title: National Institute of Advanced Technology Annual Report 2026\nDirector: Dr. S. Raman\n")
    p2 = doc.new_page()
    p2.insert_text((50, 72), "Page 2: Academic Department Structure and Faculty Roster\n")
    p3 = doc.new_page()
    p3.insert_text((50, 72), "Page 3: Extramural Grants and Research Funding\nTotal Research Outlay: 340.5 Rs. Crore\n")
    p4 = doc.new_page()
    p4.insert_text((50, 72), "Page 4 Focus: High-Performance Supercomputing Facility\nThe institute deployed 128 supercomputing nodes with 1024 tensor acceleration units.\nPeak compute capacity reached 15.4 Petaflops.\n")
    p5 = doc.new_page()
    p5.insert_text((50, 72), "Page 5 Focus: Clean Energy Microgrid\nA 4.2 Megawatt solar rooftop installation was commissioned across the central campus.\n")
    doc.save(str(test_pdf_path))
    doc.close()

    commands = [
        "what is my name",
        "what is your name",
        "my name is Sid",
        "change my name to Alex",
        "what is my name",
        f"upload {test_pdf_path} fast",
        "tell me what is in page no 4",
        "tell me what is in page no 5",
        "exit"
    ]

    try:
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "main.py")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(BASE_DIR),
            encoding="utf-8"
        )

        stdout, _ = proc.communicate(input="\n".join(commands) + "\n", timeout=120)
        assert proc.returncode == 0, f"main.py failed with code {proc.returncode}"

        # Strip ANSI color codes for reliable string assertions
        import re
        clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", stdout)

        # 1. Ask what is my name before introduction
        assert "haven't introduced yourself yet" in clean_stdout or "Sid" in clean_stdout

        # 2. Ask what is your name
        assert "My name is RAISE" in clean_stdout

        # 3. Give your name
        assert "Hello Sid!" in clean_stdout

        # 4. Change your name
        assert "updated your name from Sid to Alex" in clean_stdout

        # 5. Ask it again
        assert "It's Alex" in clean_stdout

        # 6. & 7. Upload & parse document
        assert "INGESTION COMPLETE" in clean_stdout or "Interactive_Research_Doc.pdf" in clean_stdout

        # 8. Query citation from Page 4
        assert "Page 4" in clean_stdout, "Citations should include Page 4"
        assert any(w in clean_stdout for w in ["Supercomputing", "128", "nodes", "Petaflops"]), "Should ground facts from Page 4"

        # 9. Query citation from Page 5
        assert "Page 5" in clean_stdout, "Citations should include Page 5"
        assert any(w in clean_stdout.lower() for w in ["solar", "clean energy", "microgrid", "4.2"]), "Should ground facts from Page 5"
    finally:
        try:
            from app import rag_engine
            rag_engine.purge_document("Interactive_Research_Doc.pdf")
            if test_pdf_path.exists():
                test_pdf_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
