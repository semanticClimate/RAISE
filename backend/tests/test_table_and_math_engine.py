import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.features.verification.table_engine import TableEngine
from src.features.verification.math_engine import DeterministicMathEngine

def test_table_and_math_advancements():
    print("=================================================================")
    print("[ADVANCED] TESTING CELL-COORDINATE BINDING & DETERMINISTIC MATH")
    print("=================================================================\n")

    # -------------------------------------------------------------------------
    # 1. TEST CELL-COORDINATE BINDING FOR FINANCIAL TABLES
    # -------------------------------------------------------------------------
    print("--- [1] Testing Cell-Coordinate Binding for Financial Statements ---")
    table_engine = TableEngine()
    
    # Financial Statement Sample (e.g. Balance Sheet / Statement of Financial Position)
    headers = ["Financial Stream", "FY 2023-24 (Rs. Cr)", "FY 2024-25 (Rs. Cr)"]
    rows = [
        ["Sponsored Research Grants", "120.50", "154.20"],
        ["Tuition & Academic Fees", "85.00", "92.40"],
        ["Endowment Income", "42.10", "58.60"],
        ["Total Operational Revenue", "247.60", "305.20"],
    ]

    record = table_engine.register_table(
        table_id="tbl_fin_stmt_01",
        document_id="Annual_Report_2024_25.pdf",
        university="Panjab University",
        title="Statement of Financial Revenues",
        page=48,
        headers=headers,
        rows=rows,
        currency="INR Crore"
    )

    coord_md = record.to_coordinate_bound_markdown()
    print("Generated Coordinate-Bound Markdown Table:")
    print(coord_md)

    # Verify Cell Lookup at [R1:C3] -> Sponsored Research FY 24-25
    cell = record.lookup_cell(row=1, col=3)
    print(f"\nLookup [R1:C3]: Header='{cell.header_col}', Row='{cell.header_row}', Value={cell.numeric_value} {cell.unit}")
    assert cell is not None
    assert cell.numeric_value == 154.20
    assert "[R1:C3]" in coord_md

    # -------------------------------------------------------------------------
    # 2. TEST DETERMINISTIC MATHEMATICAL PRE-COMPUTATION
    # -------------------------------------------------------------------------
    print("\n--- [2] Testing Deterministic Mathematical Pre-computation ---")
    
    # Query A: Growth Rate
    q_growth = "What was the growth rate of Sponsored Research Grants between FY 2023-24 and FY 2024-25?"
    intent_growth = DeterministicMathEngine.detect_math_intent(q_growth)
    res_growth = DeterministicMathEngine.compute("GROWTH_RATE", [120.50, 154.20])
    print(f"Query: '{q_growth}'")
    print(f"Detected Intent: {intent_growth}")
    print(f"Deterministic Calculation: {res_growth.formula_expression}")
    print(f"Verified Result: {res_growth.formatted_result}\n")
    assert intent_growth == "GROWTH_RATE"
    assert res_growth.calculated_value == 27.9668

    # Query B: Sum / Total
    q_sum = "What is the total combined revenue across all three streams in FY 2024-25?"
    intent_sum = DeterministicMathEngine.detect_math_intent(q_sum)
    res_sum = DeterministicMathEngine.compute("SUM", [154.20, 92.40, 58.60], units="Rs. Crore")
    print(f"Query: '{q_sum}'")
    print(f"Detected Intent: {intent_sum}")
    print(f"Deterministic Calculation: {res_sum.formula_expression}")
    print(f"Verified Result: {res_sum.formatted_result} {res_sum.units}\n")
    assert intent_sum == "SUM"
    assert res_sum.calculated_value == 305.20

    # Query C: Pre-computed Context Injection
    injected_context = DeterministicMathEngine.generate_precomputed_context(
        query=q_growth,
        extracted_numbers=[120.50, 154.20]
    )
    print("Injected Prompt Context for Qwen 2.5 7B:")
    print(injected_context)
    assert "DETERMINISTIC MATHEMATICAL PRE-COMPUTATION" in injected_context
    assert "+27.97%" in injected_context

    print("=" * 65)
    print("[ALL CELL-COORDINATE AND DETERMINISTIC MATH TESTS PASSED]")
    print("=========================================================")

if __name__ == "__main__":
    test_table_and_math_advancements()
