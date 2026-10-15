"""
LEGACY BATCH BILLING DISPATCH ENGINE (PROCEDURAL/BATCH STREAM)
Processes recurring monthly subscriber invoices, updates VSAM account balances,
and emits EBCDIC-compatible reconciliation audit summaries.
Interdependent with user_dao.py and auth_service.py.
"""

from typing import Dict, List, Optional
try:
    from legacy_sample import user_dao, auth_service
except ImportError:
    import user_dao, auth_service


def INITIALIZE_BILLING_CYCLE(cycle_month: int, cycle_year: int, operator_id: int) -> Dict:
    """
    PROCEDURE: INIT-BILLING-CYCLE.
    Verifies operator entitlement before creating batch run control block.
    """
    if not (1 <= cycle_month <= 12) or cycle_year < 1980:
        return {"STATUS": "FAILED", "ERR_MSG": "INVALID BILLING PERIOD"}

    has_perm = auth_service.EVALUATE_ENTITLEMENT_RULE(operator_id, "BILLING_EXEC")
    if not has_perm:
        auth_service.AUDIT_SECURITY_EVENT("UNAUTH_BATCH_ATTEMPT", operator_id, "N")
        return {"STATUS": "FAILED", "ERR_MSG": "SECURITY ENTITLEMENT REJECTED"}

    auth_service.AUDIT_SECURITY_EVENT("BATCH_INITIATED", operator_id, "Y")
    return {
        "STATUS": "INITIALIZED",
        "CYCLE_ID": f"CYC-{cycle_year:04d}{cycle_month:02d}",
        "CYCLE_MONTH": cycle_month,
        "CYCLE_YEAR": cycle_year,
        "OPERATOR_ID": operator_id,
    }


def COMPUTE_PRORATED_CHARGES(user_record: Dict, plan_rate: float, days_active: int) -> float:
    """
    PROCEDURE: COMPUTE-PRORATE.
    Implements 30-day fixed financial proration rule.
    """
    if days_active <= 0:
        return 0.00
    if days_active >= 30:
        return round(float(plan_rate), 2)

    daily_factor = round(float(plan_rate) / 30.0, 4)
    prorated = round(daily_factor * days_active, 2)
    return prorated


def PROCESS_MONTHLY_INVOICE_RECORD(
    user_id: int, cycle_control: Dict, base_rate: float = 49.99
) -> Dict:
    """
    PROCEDURE: PROCESS-INVOICE-RECORD.
    Loads subscriber from VSAM, calculates taxes, updates account balance,
    and returns processed invoice line item.
    """
    if cycle_control.get("STATUS") != "INITIALIZED":
        return {"INVOICE_STATUS": "ABORTED", "ERR_CD": "CYCLE_NOT_READY"}

    user_rec = user_dao.READ_USER_RECORD(user_id)
    if user_rec.get("FILE_STATUS") != "00":
        return {"INVOICE_STATUS": "ERROR", "ERR_CD": "USER_NOT_FOUND", "USER_ID": user_id}

    if user_rec.get("ACCT_STATUS") != "AC":
        return {"INVOICE_STATUS": "SKIPPED", "ERR_CD": "USER_NOT_ACTIVE", "USER_ID": user_id}

    tax_rate = 0.0825  # Standard municipal surcharge
    subtotal = COMPUTE_PRORATED_CHARGES(user_rec, base_rate, 30)
    tax_amt = round(subtotal * tax_rate, 2)
    total_due = round(subtotal + tax_amt, 2)

    current_bal = float(user_rec.get("ACCT_BAL_AMT", 0.0))
    new_bal = round(current_bal + total_due, 2)
    user_rec["ACCT_BAL_AMT"] = new_bal

    rc = user_dao.WRITE_USER_RECORD(user_rec)
    if rc != 0:
        return {"INVOICE_STATUS": "WRITE_FAILED", "ERR_CD": f"VSAM_RC_{rc}", "USER_ID": user_id}

    return {
        "INVOICE_STATUS": "POSTED",
        "INVOICE_ID": f"INV-{cycle_control.get('CYCLE_ID')}-{user_id}",
        "USER_ID": user_id,
        "SUBTOTAL": subtotal,
        "TAX_AMT": tax_amt,
        "TOTAL_DUE": total_due,
        "UPDATED_BAL": new_bal,
    }


def EXECUTE_BILLING_DISPATCH_BATCH(batch_limit: int = 50, operator_id: int = 10001) -> Dict:
    """
    PROCEDURE: EXECUTE-BATCH-RUN.
    Sweeps active subscribers, processes monthly invoices, and tabulates run totals.
    """
    cycle = INITIALIZE_BILLING_CYCLE(10, 2026, operator_id)
    if cycle.get("STATUS") != "INITIALIZED":
        return {"BATCH_RESULT": "ABORTED", "DETAILS": cycle}

    subscribers = user_dao.FETCH_ACTIVE_SUBSCRIBERS_CURSOR(batch_limit)
    invoices: List[Dict] = []
    total_billed = 0.0

    for sub in subscribers:
        uid = sub.get("USER_ID")
        inv = PROCESS_MONTHLY_INVOICE_RECORD(uid, cycle)
        invoices.append(inv)
        if inv.get("INVOICE_STATUS") == "POSTED":
            total_billed += inv.get("TOTAL_DUE", 0.0)

    summary = {
        "CYCLE_ID": cycle.get("CYCLE_ID"),
        "RECORDS_SCANNED": len(subscribers),
        "POSTED_COUNT": sum(1 for i in invoices if i.get("INVOICE_STATUS") == "POSTED"),
        "TOTAL_BILLED_AMT": round(total_billed, 2),
        "INVOICES": invoices,
    }
    return summary


def GENERATE_BILLING_AUDIT_TRAIL(batch_summary: Dict) -> str:
    """
    PROCEDURE: PRINT-RECON-REPORT.
    Formats 80-column legacy printer layout string for reconciliation archive.
    """
    lines = [
        "=" * 80,
        f"** SYSTEM RECONCILIATION AUDIT TRAIL : {batch_summary.get('CYCLE_ID', 'N/A')} **".center(80),
        "=" * 80,
        f"RECORDS SCANNED  : {batch_summary.get('RECORDS_SCANNED', 0):>10}",
        f"POSTED INVOICES   : {batch_summary.get('POSTED_COUNT', 0):>10}",
        f"TOTAL BILLED AMT  : ${batch_summary.get('TOTAL_BILLED_AMT', 0.0):>10.2f}",
        "-" * 80,
    ]
    for inv in batch_summary.get("INVOICES", []):
        uid = inv.get("USER_ID", 0)
        status = inv.get("INVOICE_STATUS", "")
        amt = inv.get("TOTAL_DUE", 0.0)
        lines.append(f"REC UID: {uid:<10} STATUS: {status:<15} BILLED: ${amt:>8.2f}")
    lines.append("=" * 80)
    return "\n".join(lines)
