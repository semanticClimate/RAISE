"""
RAISE Comprehensive 3-Pass Certification Suite
==============================================
Executes 3 independent consecutive validation passes across all system layers:
  1. Unit & API Regression Suite (82 tests)
  2. Ragas Faithfulness, Relevance & Grounding Suite
  3. System Readiness & Rust Bridge FFI Suite (6 tests)
  4. Backend Contract & Payload Verification (6 tests)
  5. Sandbox Emulation Profiler (5 stages)
  6. Frontend TypeScript Compilation & Vite Build

Every pass must achieve a 100% pass rate to certify system integrity.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"


def run_step(step_name: str, cmd: list[str], cwd: Path) -> float:
    print(f"    -> Running {step_name}...")
    t0 = time.perf_counter()
    res = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    duration = time.perf_counter() - t0
    if res.returncode != 0:
        print(f"       [FAILED] {step_name} exited with code {res.returncode}")
        print("--- STDOUT ---")
        print(res.stdout[-1500:] if len(res.stdout) > 1500 else res.stdout)
        print("--- STDERR ---")
        print(res.stderr[-1500:] if len(res.stderr) > 1500 else res.stderr)
        raise RuntimeError(f"Step '{step_name}' failed with code {res.returncode}")
    print(f"       [PASSED] {step_name} completed in {duration:.2f}s")
    return duration


def execute_pass(pass_number: int) -> dict[str, float]:
    print("\n" + "=" * 80)
    print(f"STARTING CERTIFICATION PASS #{pass_number} / 3")
    print("=" * 80)
    pass_t0 = time.perf_counter()
    metrics: dict[str, float] = {}

    python_exe = sys.executable

    # 1. Unit Tests & API Routing
    cmd_unit = [
        python_exe,
        "-m",
        "pytest",
        "tests/unit",
        "tests/api/test_routes.py",
        "-q",
        "--tb=short",
    ]
    metrics["unit_and_api"] = run_step(
        "Unit & API Route Suite (82 tests)", cmd_unit, BACKEND_DIR
    )

    # 2. Ragas Evaluation
    cmd_ragas = [
        python_exe,
        "-m",
        "pytest",
        "tests/test_ragas_evaluation.py",
        "-q",
        "--tb=short",
    ]
    metrics["ragas"] = run_step(
        "Ragas Faithfulness & Quality Gate Suite", cmd_ragas, BACKEND_DIR
    )

    # 3. System Readiness & Rust Bridge
    cmd_readiness = [
        python_exe,
        "-m",
        "pytest",
        "evaluation/archive/legacy_evaluation_scripts/test_system_readiness_suite.py",
        "-q",
        "--tb=short",
    ]
    metrics["readiness"] = run_step(
        "System Readiness & FFI Bridge Suite", cmd_readiness, BACKEND_DIR
    )

    # 4. Backend Verification
    cmd_verify = [python_exe, "test_backend_verification.py"]
    metrics["verification"] = run_step(
        "Payload & Route Contract Verification", cmd_verify, BACKEND_DIR
    )

    # 5. Sandbox Emulation Profiler
    cmd_profiler = [python_exe, str(REPO_ROOT / "scripts" / "sandbox_emulation_profiler.py")]
    metrics["profiler"] = run_step(
        "Sandbox Emulation & Dependency Profiler", cmd_profiler, REPO_ROOT
    )

    # 6. Frontend Typecheck
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    metrics["frontend_typecheck"] = run_step(
        "Frontend TypeScript Typecheck", [npm_cmd, "run", "typecheck"], FRONTEND_DIR
    )

    # 7. Frontend Build
    metrics["frontend_build"] = run_step(
        "Frontend Vite Compilation & Bundle", [npm_cmd, "run", "build"], FRONTEND_DIR
    )

    total_pass_time = time.perf_counter() - pass_t0
    metrics["total_pass_duration"] = total_pass_time
    print(
        f"\n  [PASS #{pass_number} COMPLETED] All 7 tiers verified with 100% success in {total_pass_time:.2f}s"
    )
    return metrics


def main() -> None:
    print("=" * 80)
    print("RAISE TRIPLE CERTIFICATION RUNNER")
    print("Validating all system functions 3 consecutive times")
    print("=" * 80)

    overall_t0 = time.perf_counter()
    summary: dict[str, dict[str, float]] = {}

    for i in range(1, 4):
        summary[f"pass_{i}"] = execute_pass(i)
        time.sleep(1)

    overall_duration = time.perf_counter() - overall_t0

    print("\n" + "=" * 80)
    print("TRIPLE CERTIFICATION SUMMARY REPORT (3 / 3 PASSES SUCCESSFUL)")
    print("=" * 80)
    for p_name, p_data in summary.items():
        print(f"  {p_name.upper()}:")
        for k, v in p_data.items():
            print(f"    - {k}: {v:.2f}s")
    print("-" * 80)
    print(f"Total Certification Duration: {overall_duration:.2f}s")
    print("All functional tiers, Ragas metrics, and UI builds certified!")
    print("=" * 80)


if __name__ == "__main__":
    main()
