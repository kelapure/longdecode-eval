#!/usr/bin/env python3
"""
eval_long_decode_v2.py
Adversarial-grade benchmark comparing:
  - Pipeline A: 128K Multi-Turn Steelman Harness (Overlap Dedup + Assistant Prefill + Cache Accounting)
  - Pipeline B: Native 1M Single-Pass Long Decode (background=True / 5K Server Checkpoints)

Includes:
  1. AST Function/Method Recall Counter
  2. Live Sandbox `pytest` Execution
  3. Seam-Bug Boundary Detector
  4. Executive Visual Chart Generator (HTML + Matplotlib PNG on a 0-100% "Higher is Better" scale)
"""

import argparse
import ast
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


def _auto_load_env():
    needed = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"]
    if any(k not in os.environ for k in needed):
        try:
            zsh_path = Path.home() / ".zshrc"
            if zsh_path.exists():
                proc = subprocess.run(
                    ["zsh", "-c", "source ~/.zshrc 2>/dev/null && env"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in proc.stdout.splitlines():
                    for k in needed:
                        if line.startswith(f"{k}=") and k not in os.environ:
                            os.environ[k] = line.split("=", 1)[1]
        except Exception:
            pass


_auto_load_env()

# =====================================================================
# 1. PROMPTS & STEELMAN CONTINUATION HELPERS
# =====================================================================

SYSTEM_PROMPT_TEMPLATE = """You are a Principal Enterprise Modernization Engine. You will be given a complete legacy module consisting of {file_count} interdependent source files wrapped in `<file path="...">` XML tags.

Your task is to migrate the entire module to {target_stack} along with a comprehensive unit test file for each migrated source file.

### STRICT OUTPUT RULES (CRITICAL FOR AUTOMATED PARSING):
1. **100% Completeness:** You must emit the complete, production-ready migrated code and unit tests for EVERY single input file.
2. **Zero Placeholders or Truncation:** You are strictly forbidden from using `// TODO`, `# TODO`, `FIXME`, `... rest of implementation`, or summarizing repeated methods. Every getter, setter, validation rule, SQL query, and error handler must be written out in full.
3. **Strict XML File Wrapping:** Wrap every generated file in `<output_file path="path/to/new_file.py">` and `</output_file>` tags. Do not use Markdown code fences inside or outside the XML tags.
4. **Cross-File Integrity:** Ensure all imports, shared DTOs, type definitions, and method signatures match across every file you generate.
5. **NO ABSTRACTION SHORTCUTS:** You must NOT create generic shared base classes (like a `core.py`) or thin proxy wrappers. Each module must independently implement its own logic in full.
6. **NO TEST INHERITANCE:** Each generated test file must contain independent, explicitly written test functions. Do not use test class inheritance or parameterized fixtures to generate tests dynamically."""


def build_anchored_continuation_prompt(existing_text: str) -> str:
    """Provides the last 3 lines as an exact anchor for OpenAI-style user-turn continuations."""
    last_lines = "\n".join(existing_text.splitlines()[-3:])
    return (
        "Continue generating from the exact character where you stopped. "
        "For context, here are the final 3 lines you emitted:\n"
        f"---\n{last_lines}\n---\n"
        "Do not repeat those lines or add conversational filler. Emit the very next character immediately."
    )


def stitch_with_overlap_dedup(existing_text: str, new_chunk: str, max_overlap: int = 400) -> str:
    """
    Steelman Stitching: If the 128K model repeats the tail of the previous turn when continuing,
    automatically detect and strip the duplicated overlap so trivial line repeats don't penalize Pipeline A.
    """
    if not existing_text or not new_chunk:
        return existing_text + new_chunk
    tail = existing_text[-max_overlap:]
    for i in range(len(tail), 8, -1):
        candidate = tail[-i:]
        if new_chunk.startswith(candidate):
            return existing_text + new_chunk[i:]
    return existing_text + new_chunk


# =====================================================================
# 2. TELEMETRY & SCORECARD DATA STRUCTURES
# =====================================================================

@dataclass
class PipelineTelemetry:
    pipeline_name: str
    raw_output: str = ""
    turns_taken: int = 0
    wall_time_sec: float = 0.0
    uncached_input_tokens: int = 0
    cached_input_tokens: int = 0
    billed_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    turn_boundary_char_offsets: List[int] = field(default_factory=list)


@dataclass
class Scorecard:
    pipeline_name: str
    expected_files: int
    emitted_files: int
    completeness_ratio: float
    expected_functions: int
    emitted_functions: int
    function_recall_ratio: float
    lazy_placeholder_count: int
    ast_valid_files: int
    ast_fail_files: int
    ast_pass_ratio: float
    seam_bugs_near_boundary: int
    unresolved_local_imports: int
    pytest_passed: int
    pytest_total: int
    pytest_pass_ratio: float
    turns_taken: int
    wall_time_sec: float
    uncached_input_tokens: int
    cached_input_tokens: int
    billed_output_tokens: int
    estimated_cost_usd: float
    raw_character_count: int
    avg_chars_per_file: int
    syntax_error_details: List[str] = field(default_factory=list)


# =====================================================================
# 3. INPUT PAYLOAD LOADER
# =====================================================================

def load_legacy_repo(directory_path: str) -> Tuple[str, int, int]:
    """
    Reads all source files in a directory, wraps them in <file> XML tags,
    and counts baseline functions/methods/procedures for Function Recall scoring.
    """
    repo_path = Path(directory_path)
    if not repo_path.exists():
        raise FileNotFoundError(f"Input directory '{directory_path}' does not exist.")

    valid_exts = {".py", ".java", ".cs", ".cob", ".php", ".js", ".ts", ".sql"}
    xml_blocks = []
    file_count = 0
    baseline_functions = 0

    func_regex = re.compile(
        r"\b(def\s+\w+|function\s+\w+|public\s+[\w<>[\]]+\s+\w+\s*\(|PROCEDURE\s+DIVISION)",
        re.IGNORECASE,
    )

    for root, _, files in os.walk(repo_path):
        for fname in sorted(files):
            fpath = Path(root) / fname
            if fpath.suffix.lower() in valid_exts:
                rel_path = fpath.relative_to(repo_path)
                content = fpath.read_text(encoding="utf-8", errors="replace")
                xml_blocks.append(f'<file path="{rel_path}">\n{content}\n</file>')
                file_count += 1
                baseline_functions += max(1, len(func_regex.findall(content)))

    return "\n\n".join(xml_blocks), file_count, baseline_functions


# =====================================================================
# 4. LIVE SDK ADAPTERS (Steelman 128K vs. Native 1M Long Decode)
# =====================================================================

async def call_128k_model_api(
    system_prompt: str,
    messages: list,
    max_tokens: int = 128000,
    provider: str = "openai",
    model_id: str = "gpt-6-astra",
) -> Tuple[str, str, int, int, int]:
    """
    Returns: (chunk_text, stop_reason, uncached_in_tokens, cached_in_tokens, out_tokens)
    """
    if provider == "openai":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(timeout=1800.0)
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        collected = []
        stop_reason = "stop"
        uncached_in, cached_in, out_tok = 0, 0, 0

        req_params = {
            "model": model_id,
            "messages": full_messages,
            "max_completion_tokens": min(max_tokens, 128000),  # Full 128K ceiling
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        char_count = 0
        last_log = time.time()
        stream = await client.chat.completions.create(**req_params)
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    collected.append(delta.content)
                    char_count += len(delta.content)
                    if time.time() - last_log > 15:
                        print(f"    [OpenAI Astra] ~{char_count // 4:,} tokens streamed...", flush=True)
                        last_log = time.time()
                if chunk.choices[0].finish_reason:
                    stop_reason = chunk.choices[0].finish_reason
            if getattr(chunk, "usage", None):
                total_in = chunk.usage.prompt_tokens or 0
                details = getattr(chunk.usage, "prompt_tokens_details", None)
                cached_in = getattr(details, "cached_tokens", 0) or 0
                uncached_in = max(0, total_in - cached_in)
                out_tok = chunk.usage.completion_tokens or 0

        return "".join(collected), stop_reason, uncached_in, cached_in, out_tok

    elif provider == "anthropic":
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(timeout=1800.0)
        collected = []
        target_model = "claude-sonnet-5-5" if model_id in ("gpt-6-astra", "claude-fable-5-1") else model_id

        char_count = 0
        last_log = time.time()
        system_block = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
        async with client.messages.stream(
            model=target_model,
            system=system_block,
            messages=messages,
            max_tokens=min(max_tokens, 64000),  # Full 64K Anthropic ceiling
        ) as stream:
            async for text in stream.text_stream:
                collected.append(text)
                char_count += len(text)
                if time.time() - last_log > 15:
                    print(f"    [Anthropic Fable] ~{char_count // 4:,} tokens streamed...", flush=True)
                    last_log = time.time()
            final_msg = await stream.get_final_message()

        stop_reason = final_msg.stop_reason or "end_turn"
        usage = final_msg.usage
        uncached_in = getattr(usage, "input_tokens", 0) or 0
        cached_in = getattr(usage, "cache_read_input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        return "".join(collected), stop_reason, uncached_in, cached_in, out_tok

    raise ValueError(f"Unsupported provider: {provider}")


async def call_1m_long_decode_api(
    system_prompt: str,
    user_payload: str,
    max_output_tokens: int = 800000,
    model_id: str = "gemini-4-argon",
) -> Tuple[str, int, int, int]:
    """
    Returns: (full_output_text, uncached_in_tokens, cached_in_tokens, out_tokens)
    """
    from google import genai
    from google.genai import types

    client = genai.Client(http_options=types.HttpOptions(timeout=3600 * 1000))
    cfg = types.GenerateContentConfig(
        system_instruction=system_prompt,
        max_output_tokens=max_output_tokens,
        temperature=0,
    )
    full_output = []
    uncached_in, cached_in, total_out = 0, 0, 0

    char_count = 0
    last_log = time.time()
    stream = await client.aio.models.generate_content_stream(
        model=model_id,
        contents=user_payload,
        config=cfg,
    )
    last_chunk = None
    async for chunk in stream:
        if chunk.text:
            full_output.append(chunk.text)
            char_count += len(chunk.text)
            if time.time() - last_log > 15:
                print(f"    [Gemini 4 Argon] ~{char_count // 4:,} tokens streamed...", flush=True)
                last_log = time.time()
        last_chunk = chunk

    if last_chunk and getattr(last_chunk, "usage_metadata", None):
        u = last_chunk.usage_metadata
        t_in = getattr(u, "prompt_token_count", 0) or 0
        c_in = getattr(u, "cached_content_token_count", 0) or 0
        uncached_in = max(0, t_in - c_in)
        cached_in = c_in
        total_out = (getattr(u, "candidates_token_count", 0) or 0) + (
            getattr(u, "thoughts_token_count", 0) or 0
        )

    return "".join(full_output), uncached_in, cached_in, total_out


# =====================================================================
# 5. PIPELINE ORCHESTRATORS (OpenAI vs. Anthropic vs. Gemini 1M)
# =====================================================================

async def run_pipeline_openai(
    system_prompt: str,
    user_payload: str,
    max_turns: int = 8,
    dry_run: bool = False,
    model_id: str = "gpt-6-astra",
) -> PipelineTelemetry:
    telemetry = PipelineTelemetry(pipeline_name="128K Harness (OpenAI GPT-6 Astra)")
    start_time = time.time()

    if dry_run:
        await asyncio.sleep(0.3)
        turn_1 = (
            '<output_file path="models/user.py">\n'
            'class User:\n'
            '    def __init__(self, uid: int, role: str = "member"):\n'
            '        self.uid = uid\n'
            '        self.role = role\n'
            '    def is_active(self) -> bool:\n'
            '        return self.uid > 0\n'
            '</output_file>\n'
            '<output_file path="services/auth.py">\n'
            'from models.user import User\n'
            'def authenticate(u: User) -> bool:\n'
            '    # TODO: migrate remaining legacy LDAP validation rules\n'
            '    return u.is_active() and ('
        )
        boundary_1 = len(turn_1)
        turn_2 = (
            'u.role in ("admin", "member"))\n'
            '</output_file>\n'
            '<output_file path="tests/test_user.py">\n'
            'from models.user import User\n'
            'def test_user_active():\n'
            '    assert User(1).is_active() is True\n'
            '</output_file>\n'
            '<output_file path="tests/test_auth.py">\n'
            'from models.user import User\n'
            'from services.auth import authenticate\n'
            'def test_auth_flow():\n'
            '    # Calling a method signature that drifted across turns (check_permissions was never emitted)\n'
            '    u = User(1)\n'
            '    assert authenticate(u) is True\n'
            '    assert u.check_permissions("read") is True\n'
            '</output_file>'
        )
        telemetry.raw_output = stitch_with_overlap_dedup(turn_1, turn_2)
        telemetry.turn_boundary_char_offsets.append(boundary_1)
        telemetry.turns_taken = 3
        telemetry.uncached_input_tokens = 250_000 + 45_000
        telemetry.cached_input_tokens = 580_000
        telemetry.billed_output_tokens = 310_000
        telemetry.estimated_cost_usd = (
            (telemetry.uncached_input_tokens / 1e6 * 2.50)
            + (telemetry.cached_input_tokens / 1e6 * 0.25)
            + (telemetry.billed_output_tokens / 1e6 * 50.00)
        )
        telemetry.wall_time_sec = time.time() - start_time
        return telemetry

    messages = [{"role": "user", "content": user_payload}]
    full_text = ""

    for turn in range(1, max_turns + 1):
        telemetry.turns_taken = turn
        print(f"  [OpenAI Astra] Launching Turn {turn}...", flush=True)
        chunk_text, stop_reason, uncached_in, cached_in, out_tok = await call_128k_model_api(
            system_prompt=system_prompt,
            messages=messages,
            provider="openai",
            model_id=model_id,
        )
        full_text = stitch_with_overlap_dedup(full_text, chunk_text)
        telemetry.uncached_input_tokens += uncached_in
        telemetry.cached_input_tokens += cached_in
        telemetry.billed_output_tokens += out_tok
        print(f"  [OpenAI Astra] Turn {turn} done (stop={stop_reason}, {out_tok:,} out tokens)", flush=True)

        if stop_reason in ("length", "max_tokens"):
            telemetry.turn_boundary_char_offsets.append(len(full_text))
            messages.append({"role": "assistant", "content": chunk_text})
            messages.append({"role": "user", "content": build_anchored_continuation_prompt(full_text)})
        else:
            break

    telemetry.raw_output = full_text
    telemetry.wall_time_sec = time.time() - start_time
    telemetry.estimated_cost_usd = (
        (telemetry.uncached_input_tokens / 1e6 * 2.50)
        + (telemetry.cached_input_tokens / 1e6 * 0.25)
        + (telemetry.billed_output_tokens / 1e6 * 50.00)
    )
    return telemetry


async def run_pipeline_anthropic(
    system_prompt: str,
    user_payload: str,
    max_turns: int = 8,
    dry_run: bool = False,
    model_id: str = "claude-sonnet-5-5",
) -> PipelineTelemetry:
    telemetry = PipelineTelemetry(pipeline_name="128K Harness (Anthropic Claude Fable)")
    start_time = time.time()

    if dry_run:
        await asyncio.sleep(0.3)
        turn_1 = (
            '<output_file path="models/user.py">\n'
            'class User:\n'
            '    def __init__(self, uid: int, role: str = "member"):\n'
            '        self.uid = uid\n'
            '        self.role = role\n'
            '    def is_active(self) -> bool:\n'
            '        return self.uid > 0\n'
            '    def check_permissions(self, perm: str) -> bool:\n'
            '        return self.is_active() and perm in ("read", "write")\n'
            '</output_file>\n'
            '<output_file path="services/auth.py">\n'
            'from models.user import User\n'
            'def authenticate(u: User) -> bool:\n'
            '    return u.is_active() and ('
        )
        b_1 = len(turn_1)
        turn_2 = (
            'u.role in ("admin", "member"))\n'
            'def verify_ldap_policy(u: User) -> bool:\n'
            '    return u.check_permissions("read")\n'
            '</output_file>\n'
            '<output_file path="tests/test_user.py">\n'
            'from models.user import User\n'
            'def test_user_active():\n'
            '    u = User(1)\n'
            '    assert u.is_active() is True\n'
            '</output_file>\n'
            '<output_file path="tests/test_auth.py">\n'
            'from models.user import User\n'
            'from services.auth import authenticate, verify_ldap_policy\n'
            'def test_auth_flow():\n'
            '    u = User(1)\n'
            '    assert authenticate(u) is True\n'
            '    assert verify_ldap_policy(u) is False  # Deliberate failure on cross-turn drift\n'
            '</output_file>'
        )
        telemetry.raw_output = stitch_with_overlap_dedup(turn_1, turn_2)
        telemetry.turn_boundary_char_offsets.append(b_1)
        telemetry.turns_taken = 2
        telemetry.uncached_input_tokens = 250_000 + 35_000
        telemetry.cached_input_tokens = 490_000
        telemetry.billed_output_tokens = 265_000
        telemetry.estimated_cost_usd = (
            (telemetry.uncached_input_tokens / 1e6 * 3.00)
            + (telemetry.cached_input_tokens / 1e6 * 0.30)
            + (telemetry.billed_output_tokens / 1e6 * 15.00)
        )
        telemetry.wall_time_sec = time.time() - start_time
        return telemetry

    messages = [{"role": "user", "content": user_payload}]
    full_text = ""

    for turn in range(1, max_turns + 1):
        telemetry.turns_taken = turn
        print(f"  [Anthropic Fable] Launching Turn {turn} (Assistant Prefill)...", flush=True)
        chunk_text, stop_reason, uncached_in, cached_in, out_tok = await call_128k_model_api(
            system_prompt=system_prompt,
            messages=messages,
            provider="anthropic",
            model_id=model_id,
        )
        full_text = stitch_with_overlap_dedup(full_text, chunk_text)
        telemetry.uncached_input_tokens += uncached_in
        telemetry.cached_input_tokens += cached_in
        telemetry.billed_output_tokens += out_tok
        print(f"  [Anthropic Fable] Turn {turn} done (stop={stop_reason}, {out_tok:,} out tokens)", flush=True)

        if stop_reason in ("length", "max_tokens"):
            telemetry.turn_boundary_char_offsets.append(len(full_text))
            # Model API mandates conversation ends with user message
            messages.append({"role": "assistant", "content": chunk_text})
            messages.append({"role": "user", "content": build_anchored_continuation_prompt(full_text)})
        else:
            break

    telemetry.raw_output = full_text
    telemetry.wall_time_sec = time.time() - start_time
    telemetry.estimated_cost_usd = (
        (telemetry.uncached_input_tokens / 1e6 * 3.00)
        + (telemetry.cached_input_tokens / 1e6 * 0.30)
        + (telemetry.billed_output_tokens / 1e6 * 15.00)
    )
    return telemetry


async def run_pipeline_gemini(
    system_prompt: str,
    user_payload: str,
    dry_run: bool = False,
    model_id: str = "gemini-4-argon",
) -> PipelineTelemetry:
    telemetry = PipelineTelemetry(pipeline_name="Native 1M Long Decode (Gemini 4 Argon)")
    start_time = time.time()

    if dry_run:
        await asyncio.sleep(0.3)
        telemetry.raw_output = (
            '<output_file path="models/user.py">\n'
            'class User:\n'
            '    def __init__(self, uid: int, role: str = "member"):\n'
            '        self.uid = uid\n'
            '        self.role = role\n'
            '    def is_active(self) -> bool:\n'
            '        return self.uid > 0\n'
            '    def check_permissions(self, perm: str) -> bool:\n'
            '        return self.is_active() and perm in ("read", "write")\n'
            '</output_file>\n'
            '<output_file path="services/auth.py">\n'
            'from models.user import User\n'
            'def authenticate(u: User) -> bool:\n'
            '    return u.is_active() and u.role in ("admin", "member")\n'
            'def verify_ldap_policy(u: User) -> bool:\n'
            '    return u.check_permissions("read")\n'
            '</output_file>\n'
            '<output_file path="tests/test_user.py">\n'
            'from models.user import User\n'
            'def test_user_active():\n'
            '    u = User(1)\n'
            '    assert u.is_active() is True\n'
            '    assert u.check_permissions("read") is True\n'
            '</output_file>\n'
            '<output_file path="tests/test_auth.py">\n'
            'from models.user import User\n'
            'from services.auth import authenticate, verify_ldap_policy\n'
            'def test_auth_flow():\n'
            '    u = User(1)\n'
            '    assert authenticate(u) is True\n'
            '    assert verify_ldap_policy(u) is True\n'
            '</output_file>'
        )
        telemetry.turns_taken = 1
        telemetry.uncached_input_tokens = 250_000
        telemetry.cached_input_tokens = 0
        telemetry.billed_output_tokens = 240_000
        telemetry.estimated_cost_usd = (
            (telemetry.uncached_input_tokens / 1e6 * 2.00)
            + (telemetry.cached_input_tokens / 1e6 * 0.10)
            + (telemetry.billed_output_tokens / 1e6 * 10.00)
        )
        telemetry.wall_time_sec = time.time() - start_time
        return telemetry

    print(f"  [Gemini 4 Argon] Launching single-pass 1M long decode streaming...", flush=True)
    raw_text, uncached_in, cached_in, out_tok = await call_1m_long_decode_api(
        system_prompt=system_prompt,
        user_payload=user_payload,
        model_id=model_id,
    )
    print(f"  [Gemini 4 Argon] Single-pass complete ({out_tok:,} out tokens)", flush=True)
    telemetry.raw_output = raw_text
    telemetry.turns_taken = 1
    telemetry.uncached_input_tokens = uncached_in
    telemetry.cached_input_tokens = cached_in
    telemetry.billed_output_tokens = out_tok
    telemetry.wall_time_sec = time.time() - start_time
    telemetry.estimated_cost_usd = (
        (uncached_in / 1e6 * 2.00) + (cached_in / 1e6 * 0.10) + (out_tok / 1e6 * 10.00)
    )
    return telemetry


# =====================================================================
# 6. ADVERSARIAL-GRADE SCORING ENGINE (AST + Pytest + Function Recall)
# =====================================================================

FILE_TAG_REGEX = re.compile(r'<output_file\s+path="([^"]+)">\s*(.*?)\s*</output_file>', re.DOTALL)
LAZY_PLACEHOLDER_REGEX = re.compile(
    r"(//|#|--|/\*)\s*(TODO|FIXME|omitted|rest of|remains unchanged|implement later|\.\.\.)",
    re.IGNORECASE,
)


def run_sandbox_pytest_and_symbol_count(
    extracted_files: Dict[str, Tuple[str, int, int]]
) -> Tuple[int, int, int]:
    """
    1. Counts total AST FunctionDef / AsyncFunctionDef nodes across all generated files.
    2. Writes all extracted <output_file> blocks to an isolated temp directory and runs pytest.
    """
    total_functions = 0
    for fpath, (code, _, _) in extracted_files.items():
        if fpath.endswith(".py"):
            try:
                tree = ast.parse(code)
                total_functions += sum(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    for node in ast.walk(tree)
                )
            except SyntaxError:
                pass

    if not extracted_files:
        return 0, 0, 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        for fpath, (code, _, _) in extracted_files.items():
            full_path = tmp_root / fpath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(code, encoding="utf-8")
            init_file = full_path.parent / "__init__.py"
            if not init_file.exists():
                init_file.write_text("", encoding="utf-8")

        try:
            sandbox_env = {**os.environ, "PYTHONPATH": str(tmpdir)}
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-o", "pythonpath=.", "--tb=short", "-q"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60,
                env=sandbox_env,
            )
            output = proc.stdout + proc.stderr
            passed = int(m.group(1)) if (m := re.search(r"(\d+)\s+passed", output)) else 0
            failed = sum(int(m) for m in re.findall(r"(\d+)\s+(?:failed|error)", output))
        except Exception:
            # Fallback if pytest isn't installed in current Python env: execute test functions directly
            passed, failed = 0, 0
            for fpath, (code, _, _) in extracted_files.items():
                if "test_" in fpath and fpath.endswith(".py"):
                    cmd = [
                        sys.executable,
                        "-c",
                        f"import sys; sys.path.insert(0, '{tmpdir}'); "
                        f"import {fpath[:-3].replace('/', '.') } as m; "
                        "[getattr(m, k)() for k in dir(m) if k.startswith('test_')]",
                    ]
                    res = subprocess.run(cmd, capture_output=True)
                    if res.returncode == 0:
                        passed += 1
                    else:
                        failed += 1

    return total_functions, passed, passed + failed


def evaluate_pipeline_output(
    telemetry: PipelineTelemetry,
    expected_output_file_count: int,
    expected_function_count: int,
) -> Scorecard:
    raw = telemetry.raw_output
    extracted_files: Dict[str, Tuple[str, int, int]] = {}

    for match in FILE_TAG_REGEX.finditer(raw):
        fpath = match.group(1).strip()
        code = match.group(2).strip()
        if code.startswith("<![CDATA["):
            code = code[9:]
        if code.endswith("]]>"):
            code = code[:-3]
        code = code.strip()
        extracted_files[fpath] = (code, *match.span(2))

    emitted_count = len(extracted_files)
    completeness = min(1.0, emitted_count / max(1, expected_output_file_count))
    lazy_count = len(LAZY_PLACEHOLDER_REGEX.findall(raw))

    ast_valid, ast_fail, seam_bugs = 0, 0, 0
    syntax_errors = []

    for fpath, (code, start_char, _) in extracted_files.items():
        if fpath.endswith(".py"):
            try:
                ast.parse(code, filename=fpath)
                ast_valid += 1
            except SyntaxError as err:
                ast_fail += 1
                err_line = err.lineno or 1
                lines = code.splitlines(keepends=True)
                err_offset = start_char + sum(len(l) for l in lines[: err_line - 1])
                near_seam = any(abs(err_offset - b) <= 500 for b in telemetry.turn_boundary_char_offsets)
                if near_seam:
                    seam_bugs += 1
                tag = "[SEAM BUG]" if near_seam else "[SYNTAX ERROR]"
                syntax_errors.append(f"{tag} {fpath}:{err_line} -> {err.msg}")

    ast_pass_ratio = ast_valid / max(1, emitted_count)

    known_modules = {f[:-3].replace("/", ".") for f in extracted_files if f.endswith(".py")}
    top_pkgs = {m.split(".")[0] for m in known_modules}
    unresolved_imports = 0
    for fpath, (code, _, _) in extracted_files.items():
        for imp in re.finditer(r"^\s*from\s+([a-zA-Z0-9_.]+)\s+import", code, re.MULTILINE):
            mod = imp.group(1)
            if mod.split(".")[0] in top_pkgs and mod not in known_modules:
                unresolved_imports += 1

    emitted_funcs, pytest_passed, pytest_total = run_sandbox_pytest_and_symbol_count(extracted_files)
    func_recall = min(1.0, emitted_funcs / max(1, expected_function_count))
    pytest_ratio = pytest_passed / max(1, pytest_total)

    raw_character_count = len(raw)
    avg_chars_per_file = raw_character_count // max(1, emitted_count)

    return Scorecard(
        pipeline_name=telemetry.pipeline_name,
        expected_files=expected_output_file_count,
        emitted_files=emitted_count,
        completeness_ratio=completeness,
        expected_functions=expected_function_count,
        emitted_functions=emitted_funcs,
        function_recall_ratio=func_recall,
        lazy_placeholder_count=lazy_count,
        ast_valid_files=ast_valid,
        ast_fail_files=ast_fail,
        ast_pass_ratio=ast_pass_ratio,
        seam_bugs_near_boundary=seam_bugs,
        unresolved_local_imports=unresolved_imports,
        pytest_passed=pytest_passed,
        pytest_total=pytest_total,
        pytest_pass_ratio=pytest_ratio,
        turns_taken=telemetry.turns_taken,
        wall_time_sec=telemetry.wall_time_sec,
        uncached_input_tokens=telemetry.uncached_input_tokens,
        cached_input_tokens=telemetry.cached_input_tokens,
        billed_output_tokens=telemetry.billed_output_tokens,
        estimated_cost_usd=telemetry.estimated_cost_usd,
        raw_character_count=raw_character_count,
        avg_chars_per_file=avg_chars_per_file,
        syntax_error_details=syntax_errors,
    )


# =====================================================================
# 7. ONE-CHART EXECUTIVE VISUAL GENERATOR (HTML + PNG FOR 3 MODELS)
# =====================================================================

def compute_normalized_executive_scores(scorecards: List[Scorecard]) -> Dict[str, List[float]]:
    """
    Normalizes all 4 core dimensions onto an intuitive 0% - 100% scale where HIGHER IS always BETTER.
    Works for any number of competitors (e.g. OpenAI, Anthropic, Gemini).
    """
    comp_scores = [round(((sc.completeness_ratio + sc.function_recall_ratio) / 2) * 100, 1) for sc in scorecards]
    stub_scores = [round(max(0.0, 100.0 - (sc.lazy_placeholder_count * 25.0)), 1) for sc in scorecards]
    test_scores = [round(sc.pytest_pass_ratio * 100, 1) for sc in scorecards]

    min_cost = min(sc.estimated_cost_usd for sc in scorecards)
    cost_scores = [round((min_cost / max(0.01, sc.estimated_cost_usd)) * 100, 1) for sc in scorecards]

    return {
        "Method & File Completeness": comp_scores,
        "Zero-Placeholder Integrity (No TODOs)": stub_scores,
        "Automated Unit Test Pass Rate (Pytest)": test_scores,
        "Cost Efficiency Index (per Migration)": cost_scores,
    }


def export_executive_visual(scorecards: List[Scorecard], out_prefix: str = "benchmark_executive_chart"):
    """
    Renders both:
      1. Clean, dark-mode 300-DPI PNG (`benchmark_executive_chart.png`) with all 3 models grouped
      2. Self-contained interactive Chart.js HTML (`benchmark_executive_chart.html`)
    """
    import matplotlib.pyplot as plt
    import numpy as np

    metrics = compute_normalized_executive_scores(scorecards)
    labels = list(metrics.keys())[::-1]  # Reverse so top metric is at top of horizontal chart
    n = len(scorecards)

    # Color palette: Vibrant Blue/Orange (OpenAI), Purple (Anthropic), Emerald Green (Gemini)
    colors = ["#f97316", "#a855f7", "#10b981"]

    y = np.arange(len(labels))
    total_group_height = 0.72
    bar_height = total_group_height / max(1, n)
    offsets = [(-total_group_height / 2 + (i + 0.5) * bar_height) for i in range(n)]

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=300)
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")

    for i, sc in enumerate(scorecards):
        scores = [metrics[k][i] for k in labels]
        color = colors[i % len(colors)]
        label_text = f"{sc.pipeline_name} ({sc.turns_taken}t, ${sc.estimated_cost_usd:.2f})"
        bars = ax.barh(
            y + offsets[i],
            scores,
            bar_height * 0.9,
            label=label_text,
            color=color,
            edgecolor="none",
        )
        ax.bar_label(bars, fmt="%.0f%%", padding=5, color=color, fontsize=9, fontweight="bold")

    ax.set_title(
        "Legacy Migration Benchmark: Multi-Turn 128K Harnesses vs. 1M Native Long Decode",
        color="#ffffff",
        fontsize=13.5,
        fontweight="bold",
        pad=22,
        loc="left",
    )
    plt.suptitle(
        "Normalized 0–100% Engineering Scorecard (Higher is Better Across All 4 Metrics)",
        color="#94a3b8",
        fontsize=10.5,
        x=0.125,
        y=0.92,
        ha="left",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, color="#f8fafc", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 114)
    ax.set_xlabel("Score (0% to 100% — Higher is Better →)", color="#cbd5e1", fontsize=10, labelpad=10)
    ax.tick_params(axis="x", colors="#cbd5e1")
    ax.grid(axis="x", color="#334155", linestyle="--", linewidth=0.7, alpha=0.7)
    ax.set_axisbelow(True)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#475569")

    leg = ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=min(3, n),
        frameon=False,
        fontsize=9.5,
    )
    for text in leg.get_texts():
        text.set_color("#f8fafc")

    png_path = f"{out_prefix}.png"
    plt.tight_layout()
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[Static Image Saved] High-DPI PNG chart written to: {png_path}")

    # Generate interactive Chart.js HTML
    chartjs_labels = list(metrics.keys())
    chart_datasets = []
    for i, sc in enumerate(scorecards):
        chart_datasets.append({
            "label": sc.pipeline_name,
            "data": [metrics[k][i] for k in chartjs_labels],
            "backgroundColor": colors[i % len(colors)],
            "borderRadius": 6,
        })

    footer_items = [
        f"<span><strong>{sc.pipeline_name}:</strong> {sc.turns_taken} turns | ${sc.estimated_cost_usd:.2f} total cost</span>"
        for sc in scorecards
    ]
    footer_html = "\n    ".join(footer_items)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>128K Harnesses vs. 1M Long Decode — Executive Benchmark</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; max-width: 1040px; margin: auto; }}
  .card {{ background: #1e293b; border-radius: 16px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
  h1 {{ font-size: 22px; margin: 0 0 8px 0; color: #ffffff; }}
  p.sub {{ font-size: 14px; color: #94a3b8; margin: 0 0 28px 0; }}
  .footer {{ display: flex; flex-direction: column; gap: 8px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #334155; font-size: 13px; color: #cbd5e1; }}
</style>
</head>
<body>
<div class="card">
  <h1>Why 128K Multi-Turn Harnesses Break on Legacy Modernization</h1>
  <p class="sub">Normalized 0–100% Engineering Scorecard (Higher is Better across all dimensions)</p>
  <canvas id="execChart" height="150"></canvas>
  <div class="footer">
    {footer_html}
  </div>
</div>
<script>
new Chart(document.getElementById('execChart'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(chartjs_labels)},
    datasets: {json.dumps(chart_datasets)}
  }},
  options: {{
    indexAxis: 'y',
    responsive: true,
    scales: {{
      x: {{ min: 0, max: 100, ticks: {{ color: '#cbd5e1', callback: v => v + '%' }}, grid: {{ color: '#334155' }} }},
      y: {{ ticks: {{ color: '#f8fafc', font: {{ size: 13, weight: 'bold' }} }}, grid: {{ display: false }} }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#f8fafc', font: {{ size: 13 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    html_path = f"{out_prefix}.html"
    Path(html_path).write_text(html_content, encoding="utf-8")
    print(f"[Visual Saved] Interactive executive chart written to: {html_path}")


def render_markdown_comparison(scorecards: List[Scorecard]) -> str:
    headers = ["Metric"] + [sc.pipeline_name for sc in scorecards]
    sep = [":---"] + [":---" for _ in scorecards]

    def make_row(label: str, values: List[str]) -> str:
        return f"| **{label}** | " + " | ".join(values) + " |"

    rows = [
        f"| " + " | ".join(headers) + " |",
        f"| " + " | ".join(sep) + " |",
        make_row("1. File Completeness", [f"{sc.emitted_files}/{sc.expected_files} ({sc.completeness_ratio:.0%})" for sc in scorecards]),
        make_row("2. AST Function/Method Recall", [f"**{sc.emitted_functions}/{sc.expected_functions} ({sc.function_recall_ratio:.0%})**" for sc in scorecards]),
        make_row("3. Lazy Placeholder Stubs (`TODO`/`FIXME`)", [f"**{sc.lazy_placeholder_count} stubs**" for sc in scorecards]),
        make_row("4. Sandbox `pytest` Pass Rate", [f"**{sc.pytest_passed}/{sc.pytest_total} ({sc.pytest_pass_ratio:.0%})**" for sc in scorecards]),
        make_row("5. Raw Code Volume (Characters)", [f"{sc.raw_character_count:,} chars (~{sc.avg_chars_per_file:,}/file)" for sc in scorecards]),
        make_row("6. Uncached / Cached Input Tokens", [f"{sc.uncached_input_tokens:,} / {sc.cached_input_tokens:,}" for sc in scorecards]),
        make_row("7. Billed Output + Thinking Tokens", [f"{sc.billed_output_tokens:,} ({sc.turns_taken}t)" for sc in scorecards]),
        make_row("8. Total Cost (With Cache Discounts)", [f"**${sc.estimated_cost_usd:.2f}**" for sc in scorecards]),
    ]

    return "\n## Adversarial-Grade Scorecard: Multi-Turn 128K vs. 1M Native Long Decode\n\n" + "\n".join(rows) + "\n"


async def main():
    parser = argparse.ArgumentParser(description="Adversarial v2 Benchmark: 128K Harness vs. 1M Long Decode")
    parser.add_argument("--input-dir", type=str, default="./legacy_sample")
    parser.add_argument("--target-lang", type=str, default="Python 3.12 (FastAPI + Pytest)")
    parser.add_argument("--provider", type=str, default="all", choices=["all", "openai", "anthropic"])
    parser.add_argument("--output-dir", type=str, default=".", help="Directory to save generated chart and scorecard assets")
    parser.add_argument("--output-prefix", type=str, default="benchmark_executive_chart", help="File prefix for visual assets")
    parser.add_argument("--max-turns", type=int, default=16, help="Maximum continuation turns for 128K multi-turn harnesses")
    parser.add_argument("--openai-model", type=str, default="gpt-6-astra", help="OpenAI model identifier")
    parser.add_argument("--anthropic-model", type=str, default="claude-sonnet-5-5", help="Anthropic model identifier")
    parser.add_argument("--gemini-model", type=str, default="gemini-4-argon", help="Google GenAI model identifier")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        user_payload = "<file path='user.cob'>...</file><file path='auth.cob'>...</file>"
        in_files, expected_funcs = 2, 6
    else:
        user_payload, in_files, expected_funcs = load_legacy_repo(args.input_dir)

    sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(file_count=in_files, target_stack=args.target_lang)

    print(f"[Benchmark Starting] Launching pipelines (provider={args.provider}, dry_run={args.dry_run})...")

    if args.provider == "openai":
        telemetries = await asyncio.gather(
            run_pipeline_openai(sys_prompt, user_payload, max_turns=args.max_turns, dry_run=args.dry_run, model_id=args.openai_model),
            run_pipeline_gemini(sys_prompt, user_payload, dry_run=args.dry_run, model_id=args.gemini_model),
        )
    elif args.provider == "anthropic":
        telemetries = await asyncio.gather(
            run_pipeline_anthropic(sys_prompt, user_payload, max_turns=args.max_turns, dry_run=args.dry_run, model_id=args.anthropic_model),
            run_pipeline_gemini(sys_prompt, user_payload, dry_run=args.dry_run, model_id=args.gemini_model),
        )
    else:
        # Run ALL THREE concurrently!
        print(f"[Concurrent Execution] Launching OpenAI ({args.openai_model}) + Anthropic ({args.anthropic_model}) + Gemini ({args.gemini_model}) in parallel...")
        telemetries = await asyncio.gather(
            run_pipeline_openai(sys_prompt, user_payload, max_turns=args.max_turns, dry_run=args.dry_run, model_id=args.openai_model),
            run_pipeline_anthropic(sys_prompt, user_payload, max_turns=args.max_turns, dry_run=args.dry_run, model_id=args.anthropic_model),
            run_pipeline_gemini(sys_prompt, user_payload, dry_run=args.dry_run, model_id=args.gemini_model),
        )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix_path = str(out_dir / args.output_prefix)

    # Preserve raw model outputs for auditing
    for t in telemetries:
        sanitized_name = t.pipeline_name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        raw_file = out_dir / f"raw_output_{sanitized_name}.txt"
        raw_file.write_text(t.raw_output, encoding="utf-8")
        print(f"[Raw Output Saved] {t.pipeline_name} -> {raw_file}")

    scorecards = [evaluate_pipeline_output(t, in_files * 2, expected_funcs) for t in telemetries]

    markdown_report = render_markdown_comparison(scorecards)
    print(markdown_report)

    report_file = out_dir / "benchmark_results.md"
    report_file.write_text(markdown_report, encoding="utf-8")
    print(f"[Report Saved] Scorecard written to: {report_file}")

    export_executive_visual(scorecards, out_prefix=out_prefix_path)


if __name__ == "__main__":
    asyncio.run(main())
