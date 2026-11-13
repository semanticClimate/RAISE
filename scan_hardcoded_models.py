#!/usr/bin/env python3
"""
Standalone scanner to detect hardcoded LLM and Hugging Face model strings
across Python, JSON, YAML, and TOML files in the RAISE backend.
"""

import argparse
import ast
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Iterable, List, Set

# Directories to always skip
IGNORE_DIRS: Set[str] = {
    ".venv", "venv", "env", "__pycache__", ".git",
    "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "site-packages",
}

# Files allowed to hold model defaults when --strict is used
DEFAULT_ALLOWED_FILES: Set[str] = {"config.py", "settings.py", "scan_hardcoded_models.py"}

# 1. Regex for known LLM & Hugging Face model identifiers
MODEL_NAME_REGEX = re.compile(
    r"^(?:"
    # LLM families (with optional "models/" prefix for Gemini)
    r"(?:models/)?gemini-[\w.-]+|"
    r"gpt-(?:3\.5|4|4o|5)[\w.-]*|"
    r"o[134]-[\w.-]+|"
    r"claude-[\w.-]+|"
    r"llama-?[\d.]+[\w.-]*|"
    r"qwen[\d.]*-[\w.-]+|"
    r"deepseek-[\w.-]+|"
    r"mistral-[\w.-]+|"
    r"mixtral-[\w.-]+|"
    r"gemma-?[\d.]*[\w.-]*|"
    r"embeddinggemma[\w.-]*|"
    r"text-embedding-[\w.-]+|"
    # Common Hugging Face org/model patterns
    r"(?:BAAI|google|urchade|sentence-transformers|intfloat|nomic-ai|"
    r"jinaai|Qwen|meta-llama|mistralai|microsoft|HuggingFaceTB|"
    r"mixedbread-ai|Alibaba-NLP|Snowflake|allenai|facebook|openai)/[\w.-]+"
    r")$",
    re.IGNORECASE,
)

# Generic HF slug fallback: "org/model-name" (excludes file paths, URLs, MIME types)
HF_REPO_FALLBACK_REGEX = re.compile(
    r"^[A-Za-z0-9_.-]{2,35}/[A-Za-z0-9_.-]*(?:bge|gliner|gemma|embed|rerank|llama|qwen|bert|roberta|minilm|e5|gte|splade|colbert|v\d)[A-Za-z0-9_.-]*$",
    re.IGNORECASE,
)

# 2. Functions/Classes where the 1st positional string arg is a model ID
MODEL_LOADER_CALLS: Set[str] = {
    "from_pretrained",
    "SentenceTransformer",
    "CrossEncoder",
    "GLiNER",
    "GenerativeModel",
    "AutoModel",
    "AutoTokenizer",
    "AutoModelForSequenceClassification",
    "AutoModelForTokenClassification",
    "AutoModelForCausalLM",
    "HuggingFaceEmbeddings",
    "HuggingFaceBgeEmbeddings",
    "HuggingFaceCrossEncoder",
    "ChatGoogleGenerativeAI",
    "GoogleGenerativeAIEmbeddings",
    "ChatOpenAI",
    "OpenAIEmbeddings",
    "Ollama",
    "ChatOllama",
    "LLM",  # vLLM
}

# 3. Keyword argument names or default parameter names that expect a model string
MODEL_KEYWORD_NAMES: Set[str] = {
    "model",
    "model_name",
    "model_id",
    "model_name_or_path",
    "pretrained_model_name_or_path",
    "llm_model",
    "embedding_model",
    "reranker_model",
    "gliner_model",
    "ner_model",
}


@dataclass(frozen=True)
class Finding:
    file_path: pathlib.Path
    line_no: int
    col_no: int
    model_str: str
    reason: str
    source_line: str


def is_likely_model_string(val: str) -> bool:
    """Checks if a string matches known LLM or Hugging Face model naming patterns."""
    val = val.strip()
    if len(val) < 4 or len(val) > 120 or " " in val or "\n" in val:
        return False
    if val.startswith(("http://", "https://", "file://", "/", "./", "../", "application/", "text/")):
        return False
    return bool(MODEL_NAME_REGEX.match(val) or HF_REPO_FALLBACK_REGEX.match(val))


def get_call_name(func_node: ast.AST) -> str:
    """Extracts the function/method name from an ast.Call node."""
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        return func_node.attr
    return ""


class ModelASTScanner(ast.NodeVisitor):
    """Walks a Python AST to find hardcoded model strings while ignoring docstrings."""

    def __init__(self, file_path: pathlib.Path, source_lines: List[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.findings: List[Finding] = []
        self._docstring_nodes: Set[int] = set()

    def _record(self, node: ast.AST, value: str, reason: str) -> None:
        lineno = getattr(node, "lineno", 1)
        col = getattr(node, "col_offset", 0) + 1
        src = self.source_lines[lineno - 1].strip() if 0 < lineno <= len(self.source_lines) else ""
        self.findings.append(
            Finding(
                file_path=self.file_path,
                line_no=lineno,
                col_no=col,
                model_str=value,
                reason=reason,
                source_line=src,
            )
        )

    def _mark_docstring(self, node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            self._docstring_nodes.add(id(body[0].value))

    def visit_Module(self, node: ast.Module) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._mark_docstring(node)
        self._check_function_defaults(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._mark_docstring(node)
        self._check_function_defaults(node)
        self.generic_visit(node)

    def _check_function_defaults(self, node: ast.AST) -> None:
        args: ast.arguments = getattr(node, "args", None)
        if not args:
            return
        # Pair positional args with their trailing default values
        pos_args = args.posonlyargs + args.args
        defaults = args.defaults
        offset = len(pos_args) - len(defaults)
        for arg, default_node in zip(pos_args[offset:], defaults):
            if (
                arg.arg in MODEL_KEYWORD_NAMES
                and isinstance(default_node, ast.Constant)
                and isinstance(default_node.value, str)
                and default_node.value.strip()
            ):
                self._record(default_node, default_node.value, f"Default Arg ({arg.arg}=...)")

        # Check keyword-only args with defaults
        for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults):
            if (
                kw_arg.arg in MODEL_KEYWORD_NAMES
                and kw_default is not None
                and isinstance(kw_default, ast.Constant)
                and isinstance(kw_default.value, str)
                and kw_default.value.strip()
            ):
                self._record(kw_default, kw_default.value, f"Default Kwarg ({kw_arg.arg}=...)")

    def visit_Call(self, node: ast.Call) -> None:
        call_name = get_call_name(node.func)

        # 1. Check 1st positional arg on known model loaders
        if call_name in MODEL_LOADER_CALLS and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                self._record(first_arg, first_arg.value, f"Loader Call ({call_name})")

        # 2. Check os.getenv("...", "hardcoded-model") fallback defaults
        if call_name in {"getenv", "get"} and len(node.args) >= 2:
            second_arg = node.args[1]
            if (
                isinstance(second_arg, ast.Constant)
                and isinstance(second_arg.value, str)
                and is_likely_model_string(second_arg.value)
            ):
                self._record(second_arg, second_arg.value, f"Env Default ({call_name})")

        # 3. Check keyword arguments like model="...", model_name="..."
        for kw in node.keywords:
            if (
                kw.arg in MODEL_KEYWORD_NAMES
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
                and kw.value.value.strip()
            ):
                self._record(kw.value, kw.value.value, f"Keyword Arg ({kw.arg}=...)")

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self._docstring_nodes:
            return
        if isinstance(node.value, str) and is_likely_model_string(node.value):
            self._record(node, node.value, "Model String Pattern")


def scan_python_file(file_path: pathlib.Path) -> List[Finding]:
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError:
        return []

    lines = content.splitlines()
    scanner = ModelASTScanner(file_path, lines)
    scanner.visit(tree)

    # Deduplicate findings on the exact same line & string (prefer specific AST reason)
    deduped: dict[tuple[int, str], Finding] = {}
    for f in scanner.findings:
        key = (f.line_no, f.model_str)
        if key not in deduped or deduped[key].reason == "Model String Pattern":
            deduped[key] = f
    return sorted(deduped.values(), key=lambda x: x.line_no)


def scan_text_config_file(file_path: pathlib.Path) -> List[Finding]:
    """Scans YAML/JSON/TOML/ENV files for quoted or assigned model strings."""
    findings: List[Finding] = []
    quoted_str_re = re.compile(r'["\']([^"\'\r\n]{4,120})["\']')
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        for match in quoted_str_re.finditer(line):
            candidate = match.group(1)
            if is_likely_model_string(candidate):
                findings.append(
                    Finding(
                        file_path=file_path,
                        line_no=idx,
                        col_no=match.start(1) + 1,
                        model_str=candidate,
                        reason="Config/Script Literal",
                        source_line=stripped,
                    )
                )
    return findings


def iter_project_files(root: pathlib.Path, include_configs: bool) -> Iterable[pathlib.Path]:
    exts = {".py"}
    if include_configs:
        exts.update({".yaml", ".yml", ".json", ".toml"})

    for path in root.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in exts:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect hardcoded LLM and Hugging Face model strings across your codebase."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--include-configs",
        action="store_true",
        help="Also scan .yaml, .yml, .json, and .toml files",
    )
    parser.add_argument(
        "--ignore-allowed",
        action="store_true",
        help="Hide matches inside allowed config files (config.py, settings.py)",
    )
    args = parser.parse_args()

    root = pathlib.Path(args.path).resolve()
    if not root.exists():
        print(f"[ERROR] Path does not exist: {root}", file=sys.stderr)
        return 2

    all_findings: List[Finding] = []
    for file_path in sorted(iter_project_files(root, args.include_configs)):
        if args.ignore_allowed and file_path.name in DEFAULT_ALLOWED_FILES:
            continue
        if file_path.name == "scan_hardcoded_models.py":
            continue
        if file_path.suffix.lower() == ".py":
            all_findings.extend(scan_python_file(file_path))
        else:
            all_findings.extend(scan_text_config_file(file_path))

    if not all_findings:
        print(f"[OK] No hardcoded model strings detected under {root}")
        return 0

    print(f"\nFound {len(all_findings)} hardcoded model occurrence(s) under {root}:\n")
    print(f"{'LOCATION':<45} | {'DETECTED MODEL':<34} | {'REASON'}")
    print("-" * 110)

    violations_outside_config = 0
    for f in all_findings:
        rel_path = f.file_path.relative_to(root) if f.file_path.is_relative_to(root) else f.file_path
        is_allowed = f.file_path.name in DEFAULT_ALLOWED_FILES
        tag = " (allowed config)" if is_allowed else ""
        if not is_allowed:
            violations_outside_config += 1

        loc = f"{rel_path}:{f.line_no}:{f.col_no}"
        print(f"{loc:<45} | {f.model_str:<34} | {f.reason}{tag}")
        print(f"    -> {f.source_line}")

    print("-" * 110)
    print(
        f"Summary: {len(all_findings)} total match(es) | "
        f"{violations_outside_config} violation(s) outside {sorted(DEFAULT_ALLOWED_FILES - {'scan_hardcoded_models.py'})}"
    )

    return 1 if violations_outside_config > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
