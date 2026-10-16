# Turn Boundary Degradation: Forensic Analysis of Multi-Turn Seam Bugs & Signature Amnesia

**A deep-dive forensic study on the mechanical and semantic failure modes that emerge when multi-turn continuation harnesses (Anthropic / OpenAI) attempt large-scale codebase modernization.**

From the benchmark: [github.com/kelapure/longdecode-eval](https://github.com/kelapure/longdecode-eval)

---

## Executive Overview

In standard LLM benchmarking, models are evaluated on single prompts where all output fits within a single generation turn. In real-world enterprise modernization, generating production-grade services, DTOs, and comprehensive unit tests easily requires **50,000 to 100,000+ output tokens**.

Because providers enforce strict per-turn completion ceilings (8,192 to 64,000 tokens on Anthropic; 16,384 to 128,000 on OpenAI), developer tools rely on **multi-turn continuation harnesses**:
1. Detecting `finish_reason == "length"` or `"max_tokens"`.
2. Appending prior outputs back into prompt context.
3. Prompting the model to *"continue from the exact character where you stopped"*.

Our adversarial evaluation revealed that multi-turn continuations do not merely add latency and cost—**they introduce severe, clustered functional defects**. The failures in Anthropic's multi-turn runs clustered tightly into two distinct regimes: **Immediate Seam Bugs** and **Signature Amnesia across Boundary Horizons**.

---

## Failure Zone 1: Immediate "Seam Bugs" (±500 Characters from Cutoff)

When an LLM hits `stop=max_tokens`, the generation process is severed abruptly. The cutoff does not respect language grammar, indentation blocks, or file boundaries; it severs **mid-token, mid-string, or mid-tag**.

```text
Turn 1 Output Stream:
...
def RECONCILE_MODULE_BALANCES_04() -> Dict:
    with _lock:
        total_bal = sum(r.get("BAL      <── [CUTOFF AT TOKEN 8,192]
══════════════════════════════════════════ [SEAM BOUNDARY] ═════════
Turn 2 Injected Prompt: "Continue from the exact character where you stopped..."
Turn 2 Output Stream:
", 0.0) for r in _MOCK_DB_04.values())  <── [INDENTATION LOST / SYNTAX ERROR]
```

### Concrete Seam Bug Manifestations:

1. **The Tag-Splice Failure:**  
   Turn 1 cut off mid-XML tag: `<output_file path="massive_legacy_sample/module_0`.  
   Turn 2 resumed with: `7.py">\ndef INIT_MODULE_07():`.  
   Even with overlap deduplication, any slight jitter in character offsets corrupts the XML envelope, causing the file extractor to merge two independent modules into a single unparseable block.

2. **The Indentation Column Drop:**  
   When a turn ends inside a nested Python block (`with _lock:`, `for r in ...`), the model often resumes generating code at **column 0** instead of the required indentation level (column 8 or 12).  
   This immediately produces fatal `IndentationError: unexpected indent` or `SyntaxError: EOL while scanning string literal` exceptions, aborting Pytest during the collection phase before a single test can execute.

---

## Failure Zone 2: "Signature Amnesia" Across Boundary Horizons

The most insidious failure mode is **semantic signature drift**. In our 15-module legacy benchmark (Run 2), Anthropic fragmented across **8 sequential continuation turns**.

Because the legacy modules have circular and interdependent linkages (`module_07` calls `module_06`, `module_00` reconciles balances against `module_14`), modules generated in later turns must conform to data schemas established in early turns:

```text
Turn 1 & 2 (Tokens 0 - 16K)        Turn 4 & 5 (Tokens 24K - 40K)       Turn 7 & 8 (Tokens 48K - 59K)
┌───────────────────────────┐      ┌───────────────────────────┐       ┌───────────────────────────┐
│ Emits module_00 to 04     │      │ Emits module_05 to 09     │       │ Emits module_10 to 14     │
│ Implements:               │      │ Begins drifting on return │       │ Calls module_01 from T1:  │
│ def RECONCILE() -> dict   │      │ types and status codes    │       │ Asserts: rec.net_balance  │
│ Returns: {"BAL": 150.50}  │      │                           │       │ (AttributeError! It was a │
└───────────────────────────┘      └───────────────────────────┘       │  dict in Turn 1!)         │
                                                                       └───────────────────────────┘
                                   ◄─────────────────────────────────────────────┘
                                      Amnesia Gap: Schema declared 5 turns earlier
```

### The Mechanism of the 15 Failed Tests (96.8% Pass Rate in Run 2):

1. **What happened in Turn 1:**  
   In `module_01.py`, the model implemented `RECONCILE_MODULE_BALANCES_01()` returning a plain Python dictionary:  
   `{"NET_BALANCE": 150.50, "STATUS": "00"}`.
2. **What happened in Turn 7 (40,000 tokens later):**  
   When writing `test_module_12.py` (which exercises cross-module reconciliation against `module_01`), the model was operating on a prompt stuffed with 50,000 tokens of intermediate code. It suffered from schema amnesia.
3. **The Clustered Test Failures:**  
   The test generated in Turn 7 asserted:
   ```python
   res = module_01.RECONCILE_MODULE_BALANCES_01()
   assert res.net_balance == 150.50  # FAILED! AttributeError: 'dict' object has no attribute 'net_balance'
   ```
   **The 15 failed tests in Run 2 clustered 100% on cross-module assertions where the test was written in Turns 5–8 referencing modules declared in Turns 1–3.**

---

## Failure Zone 3: The 9-Turn File-Dropping Cliff (Run 3 Preliminary)

When scaling to 22 modules across 9 turns before strict anti-shortcut constraints were added:
* **Turns 1 to 5:** The model dutifully emitted pairs: `module_XX.py` followed by `test_module_XX.py`.
* **The Cliff at Turn 6:** After re-reading 400,000+ accumulated input tokens, the model lost tracking of the generation checklist. It stopped emitting test files entirely and only emitted source files.
* **Result:** **12 entire test files were dropped** (file completeness crashed to 73%), and Pytest aborted with `1 error during collection`.

---

## Architectural Comparison: Why Native 1M Long Decode is Immune

Gemini 4 Argon did not avoid these defects because of better Python heuristics—**it avoided them because of its physical execution architecture**:

| Architectural Dimension | Multi-Turn Continuation (Anthropic / OpenAI) | Native Long Decode (Gemini 4 Argon) |
| :--- | :--- | :--- |
| **Seam Boundaries** | 8 to 9 points of severed text and regex restitching | **Zero seam boundaries** (1 single continuous stream) |
| **Attention State** | Reset on every turn; relies on re-reading prior text from the prompt | Global attention memory stays continuously bound from Token 1 to Token 93,475 |
| **Cross-Module Linkage** | Suffers signature amnesia after 3–4 turns | Token 90,000 has direct, uncompressed attention access to the exact AST nodes created at Token 500 |
| **Prompt Re-Feeding Cost** | **Quadratic:** Prior turns re-fed on every continuation ($3.56 total) | **Linear:** Input context is read and billed exactly once ($1.31 total) |

---

## How to Audit This Independently

Every raw output stream containing these exact turn boundaries and error clusters is committed in [`new_run/`](./new_run/) and [`archive/`](./archive/).

You can verify these findings offline without API keys:

```bash
git clone https://github.com/kelapure/longdecode-eval.git
cd longdecode-eval
python3 -m venv .venv && source .venv/bin/activate
pip install pytest fastapi httpx

# Run the independent verification tool
python3 verify_artifacts.py --run-dir ./new_run
```
