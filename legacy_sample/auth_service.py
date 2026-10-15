"""
LEGACY AUTHENTICATION & ACCESS CONTROL SERVICE (PROCEDURAL STYLE)
Controls user authentication, legacy session tokens, and security entitlement matrices.
Interdependent with user_dao.py.
"""

import hashlib
import time
from typing import Dict, List, Optional
try:
    from legacy_sample import user_dao
except ImportError:
    import user_dao

_AUDIT_TRAIL_LOG: List[Dict] = []
_FAILED_ATTEMPTS: Dict[int, int] = {}
MAX_ALLOWED_FAILS = 3


def CALCULATE_SECURITY_HASH(raw_secret: str, salt_key: str = "LEGACY_SALT_KEY_99") -> str:
    """PROCEDURE: COMPUTE-HASH. Computes salted SHA-256 digest."""
    salted = f"{raw_secret}:{salt_key}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def AUDIT_SECURITY_EVENT(event_type: str, user_id: int, status_flg: str) -> Dict:
    """PROCEDURE: LOG-SECURITY-EVENT. Appends event to compliance audit store."""
    entry = {
        "TIMESTAMP": int(time.time()),
        "EVENT_TYPE": event_type[:16].upper(),
        "USER_ID": int(user_id),
        "STATUS_FLG": status_flg[:1].upper(),  # 'Y' = Success, 'N' = Failure
    }
    _AUDIT_TRAIL_LOG.append(entry)
    return entry


def AUTHENTICATE_CREDENTIALS(user_id: int, pin_attempt: str) -> Dict:
    """
    PROCEDURE: AUTHENTICATE-USER.
    Validates user credentials against stored VSAM master record.
    Enforces maximum failure threshold before triggering LOCK_USER_ACCOUNT.
    """
    user_rec = user_dao.READ_USER_RECORD(user_id)
    if user_rec.get("FILE_STATUS") != "00":
        AUDIT_SECURITY_EVENT("AUTH_ATTEMPT", user_id, "N")
        return {"AUTH_RESULT_FLG": "N", "ERR_CODE": "ERR_NOT_FOUND", "USER_ID": user_id}

    if user_rec.get("ACCT_STATUS") == "LK":
        AUDIT_SECURITY_EVENT("AUTH_ATTEMPT", user_id, "N")
        return {"AUTH_RESULT_FLG": "N", "ERR_CODE": "ERR_LOCKED", "USER_ID": user_id}

    if user_rec.get("ACCT_STATUS") != "AC":
        AUDIT_SECURITY_EVENT("AUTH_ATTEMPT", user_id, "N")
        return {"AUTH_RESULT_FLG": "N", "ERR_CODE": "ERR_INACTIVE", "USER_ID": user_id}

    hashed_attempt = CALCULATE_SECURITY_HASH(pin_attempt)
    stored_hash = user_rec.get("PIN_HASH", "").strip()

    if hashed_attempt == stored_hash or pin_attempt == stored_hash:
        _FAILED_ATTEMPTS[user_id] = 0
        AUDIT_SECURITY_EVENT("AUTH_ATTEMPT", user_id, "Y")
        return {
            "AUTH_RESULT_FLG": "Y",
            "ERR_CODE": "0000",
            "USER_ID": user_id,
            "ROLE_CD": user_rec.get("ROLE_CD", "").strip(),
            "SECURITY_LVL": user_rec.get("SECURITY_LVL", 1),
        }

    fails = _FAILED_ATTEMPTS.get(user_id, 0) + 1
    _FAILED_ATTEMPTS[user_id] = fails
    if fails >= MAX_ALLOWED_FAILS:
        user_dao.LOCK_USER_ACCOUNT(user_id, "MAX_FAILS")
        AUDIT_SECURITY_EVENT("ACCOUNT_LOCKOUT", user_id, "Y")

    AUDIT_SECURITY_EVENT("AUTH_ATTEMPT", user_id, "N")
    return {"AUTH_RESULT_FLG": "N", "ERR_CODE": "ERR_BAD_PIN", "USER_ID": user_id}


def VERIFY_SESSION_TOKEN(token_str: str, max_age_seconds: int = 3600) -> bool:
    """
    PROCEDURE: VERIFY-TOKEN.
    Validates legacy formatted session string:
    'USR-{USER_ID}-{ISSUE_TIMESTAMP}-{HASH_CHECKSUM}'
    """
    if not token_str or not token_str.startswith("USR-"):
        return False
    parts = token_str.split("-")
    if len(parts) != 4:
        return False

    try:
        user_id = int(parts[1])
        issued_at = int(parts[2])
    except ValueError:
        return False

    now = int(time.time())
    if now - issued_at > max_age_seconds:
        return False

    expected_sig = CALCULATE_SECURITY_HASH(f"{user_id}:{issued_at}")[:8]
    return parts[3] == expected_sig


def EVALUATE_ENTITLEMENT_RULE(user_id: int, resource_code: str) -> bool:
    """
    PROCEDURE: CHECK-ENTITLEMENT.
    Inspects user permissions against security authorization table.
    """
    user_rec = user_dao.READ_USER_RECORD(user_id)
    if user_rec.get("FILE_STATUS") != "00":
        return False

    if user_rec.get("ACCT_STATUS") != "AC":
        return False

    role = user_rec.get("ROLE_CD", "").strip().upper()
    sec_lvl = user_rec.get("SECURITY_LVL", 0)

    # Entitlement matrix
    if resource_code.upper() in ("BILLING_EXEC", "BATCH_POST"):
        return role in ("ADMIN", "SYSOP") and sec_lvl >= 5
    elif resource_code.upper() in ("USER_READ", "PROFILE_VIEW"):
        return True
    elif resource_code.upper() in ("USER_WRITE", "BALANCE_ADJ"):
        return role in ("ADMIN", "SYSOP")

    return False
