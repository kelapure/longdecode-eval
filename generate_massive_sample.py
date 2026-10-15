#!/usr/bin/env python3
"""
generate_massive_sample.py
Generates scalable, interdependent legacy procedural modules to stress-test
multi-turn 128K harnesses against native 1M Long Decode.
"""

import argparse
from pathlib import Path


def generate(file_count: int = 15, out_dir_path: str = "./massive_legacy_sample"):
    out_dir = Path(out_dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    template = '''"""
LEGACY DOMAIN MODULE {i:02d} (PROCEDURAL/MAINFRAME STYLE)
Interdependent with module_{prev:02d}.py and module_{next_mod:02d}.py
"""

from typing import Dict, List, Optional
try:
    from massive_legacy_sample import module_{prev:02d}
except ImportError:
    pass

_MOCK_DB_{i:02d}: Dict[int, Dict] = {{}}
_AUDIT_LOG_{i:02d}: List[Dict] = []


def INIT_MODULE_{i:02d}() -> bool:
    """PROCEDURE: INIT-STORAGE-{i:02d}."""
    global _MOCK_DB_{i:02d}
    _MOCK_DB_{i:02d} = {{
        1001: {{"ID": 1001, "CODE": "MOD_{i:02d}_A", "BAL": 150.50, "ACTIVE": True}},
        1002: {{"ID": 1002, "CODE": "MOD_{i:02d}_B", "BAL": 0.00, "ACTIVE": True}},
        1003: {{"ID": 1003, "CODE": "MOD_{i:02d}_C", "BAL": -45.20, "ACTIVE": False}},
    }}
    return True


def VALIDATE_RECORD_{i:02d}(rec: Dict) -> bool:
    """PROCEDURE: VALIDATE-PAYLOAD-{i:02d}."""
    if not rec or "ID" not in rec or "CODE" not in rec:
        return False
    return isinstance(rec.get("BAL"), (int, float)) and rec.get("ACTIVE") in (True, False)


def READ_RECORD_{i:02d}(rec_id: int) -> Dict:
    """PROCEDURE: READ-VSAM-KEY-{i:02d}."""
    if rec_id in _MOCK_DB_{i:02d}:
        rec = dict(_MOCK_DB_{i:02d}[rec_id])
        rec["FILE_STATUS"] = "00"
        return rec
    return {{"ID": rec_id, "FILE_STATUS": "23", "ERR_MSG": "KEY NOT FOUND"}}


def WRITE_RECORD_{i:02d}(rec: Dict) -> int:
    """PROCEDURE: WRITE-VSAM-RECORD-{i:02d}."""
    if not VALIDATE_RECORD_{i:02d}(rec):
        return 12
    rec_id = rec["ID"]
    _MOCK_DB_{i:02d}[rec_id] = dict(rec)
    return 0


def COMPUTE_FEE_SURCHARGE_{i:02d}(base_amt: float, factor: float = 1.05) -> float:
    """PROCEDURE: COMPUTE-SURCHARGE-{i:02d}."""
    if base_amt <= 0.0:
        return 0.0
    return round(float(base_amt) * factor + {i} * 0.10, 2)


def RECONCILE_MODULE_BALANCES_{i:02d}() -> Dict:
    """PROCEDURE: RECONCILE-BALANCES-{i:02d}."""
    total_bal = sum(r.get("BAL", 0.0) for r in _MOCK_DB_{i:02d}.values() if r.get("ACTIVE"))
    surcharge = COMPUTE_FEE_SURCHARGE_{i:02d}(total_bal)
    return {{
        "MODULE_ID": {i},
        "ACTIVE_COUNT": sum(1 for r in _MOCK_DB_{i:02d}.values() if r.get("ACTIVE")),
        "NET_BALANCE": round(total_bal, 2),
        "ADJUSTED_SURCHARGE": surcharge,
    }}


def AUDIT_SECURITY_LOG_{i:02d}(event_type: str, status_flg: str) -> Dict:
    """PROCEDURE: LOG-AUDIT-TRAIL-{i:02d}."""
    entry = {{
        "MODULE": {i},
        "EVENT": event_type[:16].upper(),
        "STATUS": status_flg[:1].upper(),
    }}
    _AUDIT_LOG_{i:02d}.append(entry)
    return entry


def PROCESS_BATCH_{i:02d}() -> int:
    """PROCEDURE: EXECUTE-BATCH-SWEEP-{i:02d}."""
    processed = 0
    recon = RECONCILE_MODULE_BALANCES_{i:02d}()
    for k, v in _MOCK_DB_{i:02d}.items():
        if v.get("ACTIVE"):
            v["BAL"] = round(v["BAL"] + 1.25, 2)
            processed += 1
            # {padding}
    AUDIT_SECURITY_LOG_{i:02d}("BATCH_SWEEP", "Y")
    return processed
'''

    for i in range(file_count):
        prev = i - 1 if i > 0 else file_count - 1
        next_mod = (i + 1) % file_count
        padding = "\n            # ".join([f"LEGACY_OPERATION_RULE_STEP_{j}" for j in range(120)])
        content = template.format(i=i, prev=prev, next_mod=next_mod, padding=padding)
        (out_dir / f"module_{i:02d}.py").write_text(content)

    print(f"[Done] Generated {file_count} legacy modules in: {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate scalable legacy module sets")
    parser.add_argument("--file-count", type=int, default=15, help="Number of files to generate")
    parser.add_argument("--out-dir", type=str, default="./massive_legacy_sample", help="Output directory")
    args = parser.parse_args()
    generate(args.file_count, args.out_dir)
