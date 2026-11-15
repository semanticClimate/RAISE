"""
Automated Verification of User Benchmark Questions on NIPGR Annual Report 2025
==============================================================================
Runs Question 2 and Q1-Q8 through the RAISE GraphRAG Pipeline.
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.api.dependencies import get_rag_engine

test_questions = [
    {
        "id": "Q_ACK",
        "question": "names under ACKNOWLEDGEMENTS",
        "expected": "Dr. Ashwani Pareek, Executive Director BRIC-NABI; Dr. Kalaivani Ganesan, DBT & Nodal Officer BRIC; Dr. Richi V Mahajan, DBT & Additional Charge BRIC; Dr. Sumita Kumari, DBT & Additional Charge BRIC; Dr. Susmita Chaudhuri, BRIC-THSTI; Dr. Ketan Thorat, BRIC-INSTEM; Dr. Dhananjay Huilgol, BRIC-NBRC; Dr. Divya Mishra, BRIC-NIPGR; Dr. D K Vashist, BRIC-NII; Mr. Vaibhav Anil Argade, BRIC-NCCS; Dr. Shingar Sharma, Consultant, BRIC; Ms. Manisha Sharma, Consultant, BRIC; Mr. Debasish Debnath, Designer"
    },
    {
        "id": "Q_MAIN",
        "question": "What are the Nature Index rankings of iBRIC+ India for the overall research output, government research output, and individual scientific subject areas during the period 1 April 2024 to 31 March 2025? Provide both global and India rankings.",
        "expected": "Overall: 665 / 21; Government: 66 / 4; Biological Sciences: 227 / 1; Chemistry: 1067 / 49; Earth & Environmental Sciences: 1893 / 54; Health Sciences: 648 / 3; Physical Sciences: 1649 / 72. 1 April 2024 - 31 March 2025."
    },
    {
        "id": "Q1",
        "question": "What is the overall global Nature Index position of iBRIC+ India?",
        "expected": "665"
    },
    {
        "id": "Q2",
        "question": "What is the overall India position of iBRIC+ India?",
        "expected": "21"
    },
    {
        "id": "Q3",
        "question": "What is the global and India position of iBRIC+ in Biological Sciences?",
        "expected": "Global: 227; India: 1"
    },
    {
        "id": "Q4",
        "question": "Which subject area has the highest India position among the listed scientific disciplines?",
        "expected": "Biological Sciences (India position 1)"
    },
    {
        "id": "Q5",
        "question": "What are the Nature Index positions of iBRIC+ India in Chemistry?",
        "expected": "Global: 1067; India: 49"
    },
    {
        "id": "Q6",
        "question": "What is the global position of iBRIC+ India in Earth & Environmental Sciences?",
        "expected": "1893"
    },
    {
        "id": "Q7",
        "question": "What is the India position of iBRIC+ India in Health Sciences?",
        "expected": "3"
    },
    {
        "id": "Q8",
        "question": "What is the reporting period covered by the Nature Index profile?",
        "expected": "1 April 2024 – 31 March 2025"
    }
]

def main():
    engine = get_rag_engine()
    results = []

    print("======================================================================")
    print(" 🚀 RUNNING USER BENCHMARK QUESTIONS ON NIPGR_BRIC_Annual_Report_2025")
    print("======================================================================\n")

    for t in test_questions:
        qid = t["id"]
        q = t["question"]
        exp = t["expected"]

        print(f"\n--- [{qid}] {q} ---")
        res = engine.query_subgraph_graphrag(
            query=q,
            active_docs=["NIPGR_BRIC_Annual_Report_2025.pdf"],
            top_k=4,
            hops=2
        )
        ans = res.get("answer", "")
        cits = [c.get("chunk_id") for c in res.get("citations", [])]

        print(f"Answer:\n{ans}")
        print(f"Citations: {cits}")
        print(f"Expected: {exp}")

        results.append({
            "id": qid,
            "question": q,
            "answer": ans,
            "citations": cits,
            "expected": exp,
        })

    out_file = BACKEND_DIR / "data" / "processed" / "benchmark_test_results.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved test results to {out_file}")

if __name__ == "__main__":
    main()
