"""Status, result and escalation codes taken from SOP-CADC-ADM-003 v3.0 (sections 8, 12, 14, appendix A).

The SOP is the source for these names. When `interface/codes.json` arrives from the course kit,
check this file against it (see DEVLOG open items).
"""

LEAD_STATUSES = ("NEW", "ENGAGED", "CONVERTED")

ENROLMENT_STATUSES = (
    "DETAILS_PENDING",
    "INVOICED",
    "PARTIALLY_PAID",
    "ENROLLED",
    "CANCELLED",
    "APPLICATION_SUBMITTED",
)

PAYMENT_RESULTS = (
    "MATCHED",
    "PARTIAL",
    "OVERPAID",
    "WRONG_PAYEE",
    "NOT_COMPLETED",
    "DUPLICATE",
    "CLASS_MISMATCH",
    "SFC_AMOUNT_MISMATCH",
    "UNREADABLE",
)

# code -> (owner, automation_paused_for_learner)
ESCALATION_CODES = {
    "E1": ("Course Administration Executive", True),
    "E2": ("Accounts", True),
    "E3": ("Course Administration Executive", False),
    "E4": ("Course Administration Executive", True),
    "E5": ("Operations Manager", False),
    "E6": ("Admissions", False),
}

# Email subject prefixes (SOP sections 7.4, 8.4, 9.1, 10.3)
EMAIL_SUBJECT_PREFIXES = {
    "invoice": "Invoice",
    "receipt": "Receipt",
    "confirmation": "Enrolment Confirmed",
    "credit_note": "Credit Note",
    "weekly_report": "Weekly Report",
}
