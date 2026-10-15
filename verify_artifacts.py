#!/usr/bin/env python3
"""
verify_artifacts.py
===================
Offline verification script for the Long Decode Benchmark.

Allows any engineer from OpenAI, Anthropic, Google, or the open-source community
to independently reproduce the exact benchmark scorecard from the raw model outputs
saved on disk without needing API keys or making network calls.

Usage:
    python3 verify_artifacts.py [--run-dir ./new_run]
"""

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def audit_run(run_dir: Path):
    if not run_dir.exists():
        print(f"Error: Run directory '{run_dir}' does not exist.")
        sys.exit(1)

    models = [
        ("OpenAI GPT-6 Astra (128K Harness)", run_dir / "raw_output_128k_harness_openai_gpt-6_astra.txt"),
        ("Anthropic Claude Fable (64K Harness)", run_dir / "raw_output_128k_harness_anthropic_claude_fable.txt"),
        ("Gemini 4 Argon (1M Native Long Decode)", run_dir / "raw_output_native_1m_long_decode_gemini_4_argon.txt"),
    ]

    print("=" * 84)
    print("INDEPENDENT FORENSIC VERIFICATION: LONG DECODE BENCHMARK")
    print(f"Target Run Directory: {run_dir.resolve()}")
    print("=" * 84)

    file_tag_regex = re.compile(r'<output_file\s+path="([^"]+)">\s*(.*?)\s*</output_file>', re.DOTALL)
    lazy_regex = re.compile(
        r"(//|#|--|/\*)\s*(TODO|FIXME|omitted|rest of|remains unchanged|implement later|\.\.\.)",
        re.IGNORECASE,
    )

    for name, raw_path in models:
        if not raw_path.exists():
            print(f"\n[SKIP] Missing artifact for {name}: {raw_path}")
            continue

        raw = raw_path.read_text(encoding="utf-8")
        raw_chars = len(raw)

        extracted_files = {}
        for m in file_tag_regex.finditer(raw):
            fpath = m.group(1).strip()
            code = m.group(2).strip()
            # Strip XML CDATA if present
            if code.startswith("<![CDATA["):
                code = code[9:]
            if code.endswith("]]>"):
                code = code[:-3]
            extracted_files[fpath] = code.strip()

        py_files = {k: v for k, v in extracted_files.items() if k.endswith(".py")}
        lazy_count = len(lazy_regex.findall(raw))

        # AST Analysis
        ast_valid = 0
        ast_failed = 0
        total_functions = 0
        for fpath, code in py_files.items():
            try:
                tree = ast.parse(code, filename=fpath)
                ast_valid += 1
                funcs = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
                total_functions += funcs
            except SyntaxError:
                ast_failed += 1

        # Live Sandbox Pytest
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            for fpath, code in extracted_files.items():
                p = tmp_root / fpath
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(code, encoding="utf-8")
                (p.parent / "__init__.py").touch()

            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-o", "pythonpath=.", "-q"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=120,
                env={"PYTHONPATH": str(tmpdir)},
            )
            output = proc.stdout + proc.stderr
            passed_m = re.search(r"(\d+)\s+passed", output)
            failed_m = re.findall(r"(\d+)\s+(?:failed|error)", output)
            passed_count = int(passed_m.group(1)) if passed_m else 0
            failed_count = sum(int(x) for x in failed_m) if failed_m else 0
            pytest_summary = output.strip().splitlines()[-1] if output.strip() else "NO TESTS DETECTED"

        print(f"\nModel: {name}")
        print(f"  • Raw Output File:           {raw_path.name}")
        print(f"  • Total Code Characters:     {raw_chars:,} chars")
        print(f"  • Total Emitted Files:       {len(extracted_files)} files ({len(py_files)} Python source files)")
        print(f"  • Average Chars Per File:    {raw_chars // max(1, len(extracted_files)):,} chars/file")
        print(f"  • AST Valid Python Files:    {ast_valid}/{len(py_files)} ({ast_valid/max(1, len(py_files)):.1%})")
        print(f"  • AST Functions/Methods:     {total_functions} procedures declared")
        print(f"  • Lazy Placeholder Stubs:    {lazy_count} stubs")
        print(f"  • Pytest Exit Code:          {proc.returncode}")
        print(f"  • Pytest Execution Result:   {pytest_summary}")
        print(f"  • Verified Pytest Tally:     {passed_count} passed, {failed_count} failed")

    print("\n" + "=" * 84)
    print("Verification complete. Every figure independently derives from the raw emitted text.")
    print("=" * 84)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Long Decode Benchmark artifacts offline")
    parser.add_argument("--run-dir", type=str, default="./new_run", help="Path to run output directory")
    args = parser.parse_args()
    audit_run(Path(args.run_dir))
