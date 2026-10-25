"""
Sub-suite conftest for Unit & Business Logic testing.
"""
import pytest

@pytest.fixture
def sample_financial_table_rows():
    headers = ["Financial Stream", "FY 2023-24 (Rs. Cr)", "FY 2024-25 (Rs. Cr)"]
    rows = [
        ["Sponsored Research Grants", "120.50", "154.20"],
        ["Tuition & Academic Fees", "85.00", "92.40"],
        ["Endowment Income", "42.10", "58.60"],
        ["Total Operational Revenue", "247.60", "305.20"],
    ]
    return headers, rows