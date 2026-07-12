from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.make_sample_pdf import build_sample_annual_report


@pytest.fixture(scope="session")
def sample_pdf_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("fixtures") / "sample_annual_report.pdf"
    build_sample_annual_report(path)
    return path
