"""
LEGACY USER DATA ACCESS OBJECT (COBOL/PROCEDURAL STYLE)
DATA DIVISION: USER-RECORD-LAYOUT
01  USER-MASTER-RECORD.
    05  USER-ID            PIC 9(08).
    05  USER-NAME          PIC X(20).
    05  ACCT-STATUS        PIC X(02).   /* AC=ACTIVE, SU=SUSPENDED, LK=LOCKED, CL=CLOSED */
    05  ACCT-BAL-AMT       PIC S9(7)V99.
    05  ROLE-CD            PIC X(06).   /* MEMBER, ADMIN, SYSOP */
    05  PIN-HASH           PIC X(64).
    05  SECURITY-LVL       PIC 9(02).
"""

from typing import Dict, List, Optional

# Mock in-memory mainframe VSAM KSDS dataset table
_VSAM_USER_KSDS_TABLE: Dict[int, Dict] = {
    10001: {
        "USER_ID": 10001,
        "USER_NAME": "JOHN DOE            ",
        "ACCT_STATUS": "AC",
        "ACCT_BAL_AMT": 150.75,
        "ROLE_CD": "ADMIN ",
        "PIN_HASH": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "SECURITY_LVL": 9,
    },
    10002: {
        "USER_ID": 10002,
        "USER_NAME": "JANE SMITH          ",
        "ACCT_STATUS": "AC",
        "ACCT_BAL_AMT": 0.00,
        "ROLE_CD": "MEMBER",
        "PIN_HASH": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
        "SECURITY_LVL": 2,
    },
    10003: {
        "USER_ID": 10003,
        "USER_NAME": "BOB LOCKED          ",
        "ACCT_STATUS": "LK",
        "ACCT_BAL_AMT": -42.50,
        "ROLE_CD": "MEMBER",
        "PIN_HASH": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
        "SECURITY_LVL": 1,
    },
}

_VSAM_LOCKOUT_LOG: List[Dict] = []


def VALIDATE_USER_STATUS_CODE(status_cd: str) -> bool:
    """PROCEDURE: VALIDATE-STATUS-CODE. Validates 2-byte account status flag."""
    if not status_cd or len(status_cd.strip()) != 2:
        return False
    return status_cd.strip().upper() in ("AC", "SU", "LK", "CL")


def FORMAT_USER_FLAT_RECORD(
    user_id: int,
    name: str,
    status: str,
    bal: float,
    role: str,
    pin_hash: str,
    sec_lvl: int,
) -> Dict:
    """PROCEDURE: FORMAT-FLAT-RECORD. Enforces fixed PIC width field definitions."""
    return {
        "USER_ID": int(user_id),
        "USER_NAME": f"{name[:20]:<20}".upper(),
        "ACCT_STATUS": f"{status[:2]:<2}".upper(),
        "ACCT_BAL_AMT": round(float(bal), 2),
        "ROLE_CD": f"{role[:6]:<6}".upper(),
        "PIN_HASH": f"{pin_hash[:64]:<64}",
        "SECURITY_LVL": max(0, min(99, int(sec_lvl))),
    }


def READ_USER_RECORD(user_id: int) -> Dict:
    """
    PROCEDURE: READ-USER-RECORD.
    Emulates indexed VSAM read by primary key (USER_ID).
    Returns record dictionary with FILE_STATUS:
      '00' = SUCCESSFUL COMPLETION
      '23' = RECORD KEY NOT FOUND
    """
    if user_id in _VSAM_USER_KSDS_TABLE:
        rec = dict(_VSAM_USER_KSDS_TABLE[user_id])
        rec["FILE_STATUS"] = "00"
        return rec
    return {
        "USER_ID": user_id,
        "FILE_STATUS": "23",
        "ERR_MSG": "RECORD KEY NOT FOUND IN VSAM CLUSTER",
    }


def WRITE_USER_RECORD(user_record: Dict) -> int:
    """
    PROCEDURE: REWRITE-USER-RECORD.
    Updates existing record in VSAM cluster.
    Returns return code:
       0 = SUCCESS
      12 = VALIDATION ERROR (INVALID STATUS OR MISSING ID)
      23 = KEY NOT FOUND
    """
    uid = user_record.get("USER_ID")
    if not uid or uid not in _VSAM_USER_KSDS_TABLE:
        return 23

    st = user_record.get("ACCT_STATUS", "")
    if not VALIDATE_USER_STATUS_CODE(st):
        return 12

    formatted = FORMAT_USER_FLAT_RECORD(
        user_id=uid,
        name=user_record.get("USER_NAME", ""),
        status=st,
        bal=user_record.get("ACCT_BAL_AMT", 0.0),
        role=user_record.get("ROLE_CD", "MEMBER"),
        pin_hash=user_record.get("PIN_HASH", ""),
        sec_lvl=user_record.get("SECURITY_LVL", 1),
    )
    _VSAM_USER_KSDS_TABLE[uid] = formatted
    return 0


def LOCK_USER_ACCOUNT(user_id: int, reason_code: str) -> bool:
    """
    PROCEDURE: LOCK-USER-ACCOUNT.
    Transitions account to 'LK' status and appends entry to security audit trail.
    """
    rec = READ_USER_RECORD(user_id)
    if rec.get("FILE_STATUS") != "00":
        return False

    rec["ACCT_STATUS"] = "LK"
    rc = WRITE_USER_RECORD(rec)
    if rc == 0:
        _VSAM_LOCKOUT_LOG.append(
            {"USER_ID": user_id, "REASON_CD": reason_code[:10], "ACTION": "SUSPEND_CREDENTIALS"}
        )
        return True
    return False


def FETCH_ACTIVE_SUBSCRIBERS_CURSOR(batch_limit: int = 100) -> List[Dict]:
    """
    PROCEDURE: FETCH-ACTIVE-SUBSCRIBERS.
    Sequential cursor sweep across master cluster for status 'AC'.
    """
    active_rows: List[Dict] = []
    for uid in sorted(_VSAM_USER_KSDS_TABLE.keys()):
        rec = _VSAM_USER_KSDS_TABLE[uid]
        if rec.get("ACCT_STATUS") == "AC":
            active_rows.append(dict(rec))
            if len(active_rows) >= batch_limit:
                break
    return active_rows
