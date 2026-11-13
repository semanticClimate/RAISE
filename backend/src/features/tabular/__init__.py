"""
RAISE Tabular Processing & Analytics Package
============================================
Provides deterministic table parsing, calculations, and mathematical verifications.
"""

from .polars_verifier import (
    PolarsTabularVerifier,
    TabularVerificationResult,
    get_tabular_verifier,
)

__all__ = [
    "PolarsTabularVerifier",
    "TabularVerificationResult",
    "get_tabular_verifier",
]
