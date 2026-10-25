"""
Unit Tests for Polars Tabular Verifier & Deterministic Arithmetic Engine
========================================================================
Validates:
1. Markdown table parsing into strongly-typed DataFrames.
2. Numeric string cleaning (commas, parentheses negatives, currency signs).
3. Deterministic column aggregations (Sum, Mean, Min, Max).
4. Total / Sum row reconciliation against preceding line items.
5. Variance and percentage change computation.
6. Deterministic claim verification against tabular ground truth.
"""

import pytest
from src.features.tabular.polars_verifier import (
    PolarsTabularVerifier,
    get_tabular_verifier,
)


@pytest.mark.unit
def test_polars_verifier_singleton():
    """Verifies singleton accessor returns instance."""
    v1 = get_tabular_verifier()
    v2 = get_tabular_verifier()
    assert v1 is v2
    assert isinstance(v1, PolarsTabularVerifier)


@pytest.mark.unit
def test_clean_cell_numeric_formats():
    """Verifies numeric cleaning across accounting and currency formats."""
    v = PolarsTabularVerifier()
    assert v.clean_cell_numeric("1,234.56") == 1234.56
    assert v.clean_cell_numeric("₹ 50,000") == 50000.0
    assert v.clean_cell_numeric("Rs. 18.25") == 18.25
    assert v.clean_cell_numeric("(450.00)") == -450.00
    assert v.clean_cell_numeric("$ 1,000,000") == 1000000.0
    assert v.clean_cell_numeric("-") is None
    assert v.clean_cell_numeric("N/A") is None
    assert v.clean_cell_numeric("2022-23") is None
    assert v.clean_cell_numeric("2023-2024") is None


@pytest.mark.unit
def test_markdown_table_parsing_and_metrics():
    """Verifies parsing a Markdown financial schedule and computing deterministic column metrics."""
    v = PolarsTabularVerifier()
    markdown_table = (
        "| Department | Budget 2023 | Budget 2024 |\n"
        "| :--- | :--- | :--- |\n"
        "| Biotechnology | ₹ 100.00 | ₹ 125.00 |\n"
        "| Nanotechnology | ₹ 80.00 | ₹ 95.00 |\n"
        "| Bioinformatics | ₹ 60.00 | ₹ 70.00 |\n"
    )

    df = v.parse_markdown_table(markdown_table)
    assert df is not None
    assert df.height == 3

    metrics = v.compute_column_metrics(df)
    assert "budget_2023" in metrics
    assert "budget_2024" in metrics

    assert metrics["budget_2023"]["sum"] == 240.0
    assert metrics["budget_2024"]["sum"] == 290.0
    assert metrics["budget_2024"]["min"] == 70.0
    assert metrics["budget_2024"]["max"] == 125.0


@pytest.mark.unit
def test_verify_sum_row_reconciliation():
    """Verifies total row validation against line items."""
    v = PolarsTabularVerifier()
    markdown_table = (
        "| Item | Amount |\n"
        "| --- | --- |\n"
        "| Salaries | 50.0 |\n"
        "| Equipment | 30.0 |\n"
        "| Travel | 20.0 |\n"
        "| Total Expenditure | 100.0 |\n"
    )

    df = v.parse_markdown_table(markdown_table)
    assert df is not None

    is_valid, reported, calculated = v.verify_sum_row(
        df=df,
        numeric_col="amount",
        label_col="item",
    )

    assert is_valid is True
    assert reported == 100.0
    assert calculated == 100.0


@pytest.mark.unit
def test_calculate_variance():
    """Verifies exact variance and percentage change calculation."""
    v = PolarsTabularVerifier()
    var = v.calculate_variance(base_val=200.0, target_val=250.0)
    assert var["absolute_difference"] == 50.0
    assert var["percentage_change"] == 25.0


@pytest.mark.unit
def test_verify_numeric_claim():
    """Verifies checking claimed numerical values against tabular data."""
    v = PolarsTabularVerifier()
    markdown_table = (
        "| Category | Allocation |\n"
        "| --- | --- |\n"
        "| Grants | 120.50 |\n"
        "| Fellowships | 45.25 |\n"
    )
    df = v.parse_markdown_table(markdown_table)

    # Claim matches cell value
    ok, msg = v.verify_numeric_claim(claimed_value=120.50, df=df)
    assert ok is True
    assert "Exact match found" in msg

    # Claim matches column sum (120.50 + 45.25 = 165.75)
    ok_sum, msg_sum = v.verify_numeric_claim(claimed_value=165.75, df=df)
    assert ok_sum is True
    assert "Matches computed column sum" in msg_sum

    # Large financial figure relative tolerance check (0.5% tolerance)
    df_large = v.create_dataframe(["cost"], [[1500000.06]])
    assert df_large is not None
    ok_large, _ = v.verify_numeric_claim(claimed_value=1500000.0, df=df_large)
    assert ok_large is True

    # Ungrounded claim
    ok_false, _ = v.verify_numeric_claim(claimed_value=999.99, df=df)
    assert ok_false is False


@pytest.mark.unit
def test_verify_sum_row_with_footnote():
    """Verifies that Total row is correctly detected even when trailing footnote row exists."""
    v = PolarsTabularVerifier()
    table = (
        "| Department | Expenditure |\n"
        "| :--- | :--- |\n"
        "| Physics | 150.00 |\n"
        "| Chemistry | 250.00 |\n"
        "| Total | 400.00 |\n"
        "| * Audited by external auditors | |\n"
    )
    df = v.parse_markdown_table(table)
    assert df is not None
    is_valid, reported, calculated = v.verify_sum_row(df=df, numeric_col="expenditure")
    assert is_valid is True
    assert reported == 400.0
    assert calculated == 400.0
