# backend/tests/test_no_hardcoded_models.py
import pathlib
import re

FORBIDDEN_PATTERNS = re.compile(
    r'["\'](gemini-[\w.-]+|gpt-[\w.-]+|BAAI/[\w.-]+|google/embeddinggemma[\w.-]*|urchade/gliner[\w.-]*)["\']'
)
ALLOWED_FILES = {"config.py", "settings.py"}


def test_no_hardcoded_model_strings():
    src_root = pathlib.Path(__file__).resolve().parent.parent / "src"
    violations = []

    for py_file in src_root.rglob("*.py"):
        if py_file.name in ALLOWED_FILES:
            continue
        for line_no, line in enumerate(py_file.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip().startswith("#") and FORBIDDEN_PATTERNS.search(line):
                violations.append(f"{py_file.relative_to(src_root)}:{line_no} -> {line.strip()}")

    assert not violations, "Hardcoded model names found outside config.py:\n" + "\n".join(violations)
